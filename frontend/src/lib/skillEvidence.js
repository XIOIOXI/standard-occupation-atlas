export function recruitmentRecordIds(value) {
  const values = Array.isArray(value) ? value : typeof value === 'string' ? value.split(/[\s,]+/) : [];
  return [...new Set(values.map(id => String(id).trim()).filter(Boolean))];
}

export function matchingSkillEvidence(records, references) {
  const ids = new Set(recruitmentRecordIds(references?.source_recruitment_record_ids));
  return records.filter(record => ids.has(record.source_record_id));
}
