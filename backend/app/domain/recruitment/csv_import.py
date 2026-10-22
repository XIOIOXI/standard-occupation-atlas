"""CSV schema validation, mapping, normalisation, preview, and snapshot creation.

No function in this module calls an LLM or performs skill inference.
"""

from __future__ import annotations

import csv
import codecs
import hashlib
import re
import zipfile
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

from .models import (
    DatasetSnapshot,
    FieldIssue,
    PreviewResult,
    RecruitmentRecord,
    ValidationReport,
    stable_record_id,
)

SCHEMA_VERSION = "2026-recruitment-csv-v1"
MAX_PREVIEW_ROWS = 50

# Internal field -> accepted Chinese CSV headers. Keep aliases explicit and versioned.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "updated_at": ("更新时间",),
    "company_name": ("公司",),
    "company_type": ("企业类型",),
    "recruitment_session": ("招聘届次",),
    "recruitment_batch": ("批次（暑期实习）", "招聘批次", "批次"),
    "industry_category": ("行业类别",),
    "location": ("工作地点",),
    "job_title": ("招聘岗位",),
    "deadline_raw": ("截止时间",),
    "recruitment_url": ("简历投递链接", "招聘链接"),
    "announcement_url": ("公告链接",),
    "education_requirement": ("学历要求",),
    "major_requirement": ("专业要求",),
}

REQUIRED_FIELDS = frozenset(
    {
        "updated_at",
        "company_name",
        "company_type",
        "recruitment_session",
        "recruitment_batch",
        "industry_category",
        "location",
        "job_title",
        "deadline_raw",
        "recruitment_url",
        "announcement_url",
        "education_requirement",
        "major_requirement",
    }
)

_EMPTY_MARKERS = frozenset({"", "-", "--", "/", "n/a", "na", "null", "none", "无", "暂无"})
_OPEN_DEADLINES = frozenset({"尽快投递", "长期有效", "招满即止", "待定"})


def _read_encoding(path: Path) -> str:
    """Detect supported source encodings without consuming parsed records."""

    sample = path.read_bytes()[:4096]
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            # `final=False` accepts a multi-byte character split at the sample boundary.
            codecs.getincrementaldecoder(encoding)(errors="strict").decode(sample, final=False)
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV encoding must be UTF-8, UTF-8 with BOM, or GB18030")


def _source_format(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".csv"}:
        return "csv"
    if suffix in {".xlsx"}:
        return "xlsx"
    raise ValueError("Source file must be a CSV or XLSX file")


def _xlsx_column_index(reference: str) -> int:
    """Return the zero-based spreadsheet column for an A1 cell reference."""

    letters = "".join(character for character in reference if character.isalpha()).upper()
    result = 0
    for letter in letters:
        result = result * 26 + ord(letter) - ord("A") + 1
    return result - 1


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return ["".join(node.itertext()) for node in root.findall("x:si", namespace)]


def _xlsx_rows(path: Path) -> Iterator[list[str]]:
    """Read the first XLSX worksheet without adding an Excel dependency.

    Values are yielded as display strings, then flow through the exact same
    header mapping and row normalisation as CSV input.  Formula cells retain
    their cached value; files without a cached formula result are represented
    as an empty value rather than calculating formulas during import.
    """

    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        sheet_paths = sorted(
            name for name in archive.namelist()
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
        )
        if not sheet_paths:
            raise ValueError("XLSX file has no worksheet")
        root = ElementTree.fromstring(archive.read(sheet_paths[0]))
        for row in root.findall(".//x:sheetData/x:row", namespace):
            values: dict[int, str] = {}
            for cell in row.findall("x:c", namespace):
                reference = cell.get("r", "A1")
                column = _xlsx_column_index(reference)
                cell_type = cell.get("t")
                if cell_type == "inlineStr":
                    value = "".join(cell.itertext())
                else:
                    value_node = cell.find("x:v", namespace)
                    raw_value = value_node.text if value_node is not None else ""
                    if cell_type == "s" and raw_value:
                        value = shared_strings[int(raw_value)]
                    elif cell_type == "b":
                        value = "TRUE" if raw_value == "1" else "FALSE"
                    else:
                        value = raw_value or ""
                values[column] = value
            if values:
                yield [values.get(index, "") for index in range(max(values) + 1)]


def _read_headers(path: Path) -> tuple[list[str], str | None]:
    source_format = _source_format(path)
    if source_format == "xlsx":
        return next(_xlsx_rows(path), []), None
    encoding = _read_encoding(path)
    with path.open("r", encoding=encoding, newline="") as stream:
        return next(csv.reader(stream), []), encoding


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()
    return None if cleaned.casefold() in _EMPTY_MARKERS else cleaned


def _normalise_text(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    normalised = cleaned.replace("（", "(").replace("）", ")").replace("，", ",")
    normalised = re.sub(r"\s*,\s*", ", ", normalised)
    # Casefolding preserves Chinese text while canonicalising English role names.
    return normalised.casefold()


def _parse_date(value: str | None) -> date | None:
    cleaned = _clean(value)
    if not cleaned or cleaned in _OPEN_DEADLINES:
        return None
    candidates = ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m", "%Y-%m")
    for pattern in candidates:
        try:
            parsed = __import__("datetime").datetime.strptime(cleaned, pattern)
            return parsed.date()
        except ValueError:
            continue
    # XLSX stores calendar values as serial day counts.  The lightweight XLSX
    # reader deliberately preserves cell values as text, so accept the normal
    # Excel range here rather than losing the source update date in calendars.
    if re.fullmatch(r"\d{4,5}(?:\.0+)?", cleaned):
        serial = float(cleaned)
        if 1 <= serial <= 100_000:
            return date(1899, 12, 30) + timedelta(days=serial)
    return None


def _url_or_issue(value: str | None, field: str, issues: list[FieldIssue]) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        issues.append(FieldIssue(field=field, code="missing_optional", message="URL is unavailable."))
        return None
    if not re.match(r"^https?://", cleaned, flags=re.IGNORECASE):
        issues.append(FieldIssue(field=field, code="invalid_url", message="URL must start with http:// or https://."))
        return None
    return cleaned


def build_field_mapping(headers: list[str]) -> tuple[dict[str, str], list[str]]:
    """Return internal-field -> source-header mapping and unmapped source headers."""

    normalised_headers = {_clean(header): header for header in headers if _clean(header)}
    mapping: dict[str, str] = {}
    for internal_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalised_headers:
                mapping[internal_name] = normalised_headers[alias]
                break
    used_headers = set(mapping.values())
    return mapping, [header for header in headers if header not in used_headers]


def validate_csv_schema(path: str | Path) -> ValidationReport:
    """Validate only the header and field mapping; this does not parse all rows."""

    source = Path(path)
    headers, _ = _read_headers(source)
    headers = [_clean(header) or "" for header in headers]
    mapping, unknown_headers = build_field_mapping(headers)
    missing = sorted(REQUIRED_FIELDS - set(mapping))
    return ValidationReport(
        valid=not missing,
        headers=headers,
        field_mapping=mapping,
        missing_required_fields=missing,
        unknown_headers=unknown_headers,
    )


def _mapped_payload(raw_row: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    return {internal: raw_row.get(header, "") for internal, header in mapping.items()}


def normalise_row(
    raw_row: dict[str, str], *, row_number: int, mapping: dict[str, str]
) -> RecruitmentRecord:
    """Normalise a single raw row while retaining it and surfacing validation issues."""

    payload = _mapped_payload(raw_row, mapping)
    issues: list[FieldIssue] = []
    # A parsable row remains retained by default. Company + job title are the only
    # minimum conditions for record-level market analysis; all other quality gaps
    # remain inspectable as field issues.
    core_fields = {"company_name", "job_title"}
    for field in REQUIRED_FIELDS - {"deadline_raw", "recruitment_url", "announcement_url"}:
        if not _clean(payload.get(field)):
            issues.append(
                FieldIssue(
                    field=field,
                    code="missing_core" if field in core_fields else "missing_optional",
                    message="Core value is missing." if field in core_fields else "Optional analysis context is unavailable.",
                    severity="error" if field in core_fields else "warning",
                )
            )

    updated_at = _parse_date(payload.get("updated_at"))
    if payload.get("updated_at") and not updated_at:
        issues.append(FieldIssue(field="updated_at", code="invalid_date", message="Expected YYYY/MM/DD or equivalent."))
    deadline_raw = _clean(payload.get("deadline_raw"))
    deadline = _parse_date(deadline_raw)
    if deadline_raw and deadline_raw not in _OPEN_DEADLINES and not deadline:
        issues.append(FieldIssue(field="deadline_raw", code="unparsed_deadline", message="Deadline was retained but could not be parsed as a date."))

    recruitment_url = _url_or_issue(payload.get("recruitment_url"), "recruitment_url", issues)
    announcement_url = _url_or_issue(payload.get("announcement_url"), "announcement_url", issues)

    stable_payload = {
        "company_name": _clean(payload.get("company_name")) or "",
        "job_title": _clean(payload.get("job_title")) or "",
        "recruitment_session": _clean(payload.get("recruitment_session")) or "",
        "recruitment_batch": _clean(payload.get("recruitment_batch")) or "",
        "location": _clean(payload.get("location")) or "",
        "recruitment_url": recruitment_url or "",
        "announcement_url": announcement_url or "",
    }

    has_core_identity = all(_clean(payload.get(field)) for field in core_fields)
    has_industry_context = bool(_clean(payload.get("industry_category")))
    eligibility_reasons: list[str] = []
    if not has_core_identity:
        eligibility_reasons.append("Missing company_name or job_title; excluded from market and industry analysis.")
    elif not has_industry_context:
        eligibility_reasons.append("Missing industry_category; retained for market analysis but excluded from industry-segment analysis.")

    return RecruitmentRecord(
        record_id=stable_record_id(stable_payload),
        row_number=row_number,
        updated_at=updated_at,
        company_name=_clean(payload.get("company_name")),
        company_type=_clean(payload.get("company_type")),
        recruitment_session=_clean(payload.get("recruitment_session")),
        recruitment_batch=_clean(payload.get("recruitment_batch")),
        industry_category=_clean(payload.get("industry_category")),
        location=_clean(payload.get("location")),
        job_title=_clean(payload.get("job_title")),
        normalized_job_title=_normalise_text(payload.get("job_title")),
        deadline=deadline,
        deadline_raw=deadline_raw,
        education_requirement=_clean(payload.get("education_requirement")),
        major_requirement=_clean(payload.get("major_requirement")),
        normalized_major_requirement=_normalise_text(payload.get("major_requirement")),
        recruitment_url=recruitment_url,
        announcement_url=announcement_url,
        record_status="valid" if has_core_identity else "invalid",
        eligible_for_market_analysis=has_core_identity,
        eligible_for_industry_analysis=has_core_identity and has_industry_context,
        eligibility_reasons=eligibility_reasons,
        validation_issues=issues,
        raw_payload={key: value or "" for key, value in raw_row.items()},
    )


def _iter_rows(path: Path, encoding: str | None) -> Iterator[tuple[int, dict[str, str]]]:
    if _source_format(path) == "xlsx":
        iterator = _xlsx_rows(path)
        headers = next(iterator, [])
        for row_number, values in enumerate(iterator, start=2):
            yield row_number, {
                header: values[index] if index < len(values) else ""
                for index, header in enumerate(headers)
            }
        return
    if encoding is None:
        raise ValueError("CSV source encoding is required")
    with path.open("r", encoding=encoding, newline="") as stream:
        reader = csv.DictReader(stream)
        for row_number, row in enumerate(reader, start=2):
            yield row_number, {key: value or "" for key, value in row.items()}


def preview_csv(path: str | Path, *, limit: int = 20) -> PreviewResult:
    """Read only a bounded number of rows for an import confirmation screen."""

    if not 1 <= limit <= MAX_PREVIEW_ROWS:
        raise ValueError(f"Preview limit must be between 1 and {MAX_PREVIEW_ROWS}.")
    source = Path(path)
    schema = validate_csv_schema(source)
    _, encoding = _read_headers(source)
    records: list[RecruitmentRecord] = []
    if schema.valid:
        for row_number, raw_row in _iter_rows(source, encoding):
            records.append(normalise_row(raw_row, row_number=row_number, mapping=schema.field_mapping))
            if len(records) >= limit:
                break
    schema.row_issues = {
        record.row_number: record.validation_issues
        for record in records
        if record.validation_issues
    }
    return PreviewResult(
        source_file_name=source.name,
        encoding=encoding or "xlsx",
        requested_rows=limit,
        returned_rows=len(records),
        schema_report=schema,
        records=records,
    )


def create_snapshot(path: str | Path, *, source_name: str = "2026 recruitment dataset") -> DatasetSnapshot:
    """Create a complete in-memory snapshot when a later import action explicitly permits it."""

    source = Path(path)
    schema = validate_csv_schema(source)
    if not schema.valid:
        raise ValueError(f"Cannot snapshot CSV with missing fields: {schema.missing_required_fields}")
    _, encoding = _read_headers(source)
    records = [
        normalise_row(raw_row, row_number=row_number, mapping=schema.field_mapping)
        for row_number, raw_row in _iter_rows(source, encoding)
    ]
    # Preserve all source rows but identify repeated stable identities deterministically.
    seen_record_ids: set[str] = set()
    deduplicated_records: list[RecruitmentRecord] = []
    for record in records:
        if record.record_status == "valid" and record.record_id in seen_record_ids:
            deduplicated_records.append(record.model_copy(update={"record_status": "duplicate"}))
        else:
            deduplicated_records.append(record)
            if record.record_status == "valid":
                seen_record_ids.add(record.record_id)
    records = deduplicated_records
    valid_records = [record for record in records if record.record_status == "valid"]
    invalid_count = sum(record.record_status == "invalid" for record in records)
    duplicate_count = sum(record.record_status == "duplicate" for record in records)
    update_dates = [record.updated_at for record in valid_records if record.updated_at]
    return DatasetSnapshot(
        source_name=source_name,
        source_format=_source_format(source),
        source_file_name=source.name,
        source_checksum=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_updated_at=max(update_dates) if update_dates else None,
        schema_version=SCHEMA_VERSION,
        record_count=len(records),
        valid_record_count=len(valid_records),
        invalid_record_count=invalid_count,
        validation_summary={
            "valid": len(valid_records),
            "invalid": invalid_count,
            "duplicate": duplicate_count,
            "total": len(records),
        },
        records=records,
    )
