"""Cross-industry taxonomy contracts.

These contracts deliberately sit beside the legacy workbook reader.  They do
not change how the current Reference Taxonomy is loaded or mapped; they provide
the target canonical-occupation model for versioned semantic review and a
future, explicitly approved migration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain.taxonomy.coverage import TaxonomyEntry


DomainRelationshipType = Literal["canonical", "applicable"]
IdentityDecision = Literal[
    "alias_of_existing",
    "proposed_new_occupation",
    "merge_with_candidate",
    "too_generic",
    "company_specific_or_program",
    "pending_identity_review",
]
PlacementStatus = Literal[
    "single_domain",
    "cross_industry",
    "context_dependent",
    "placement_review_required",
]
CareerOrProgramModifier = Literal["management_trainee"]


@dataclass(frozen=True)
class OccupationDomainLink:
    """A governed domain in which a canonical occupation is applicable."""

    occupation_id: str
    level_1: str
    level_2: str
    relationship_type: DomainRelationshipType

    def __post_init__(self) -> None:
        if not self.occupation_id or not self.level_1 or not self.level_2:
            raise ValueError("OccupationDomainLink requires occupation_id, level_1, and level_2.")
        if self.relationship_type not in {"canonical", "applicable"}:
            raise ValueError("relationship_type must be canonical or applicable.")


@dataclass(frozen=True)
class CanonicalOccupation:
    """Occupation identity, independent of how many domains can use it."""

    canonical_occupation_id: str
    standard_title: str
    definition: str | None
    aliases: tuple[str, ...]
    status: str
    taxonomy_version: str | None
    domain_links: tuple[OccupationDomainLink, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.canonical_occupation_id or not self.standard_title:
            raise ValueError("CanonicalOccupation requires an ID and standard title.")
        canonical_links = [link for link in self.domain_links if link.relationship_type == "canonical"]
        if len(canonical_links) != 1:
            raise ValueError("CanonicalOccupation requires exactly one canonical domain link.")
        if any(link.occupation_id != self.canonical_occupation_id for link in self.domain_links):
            raise ValueError("All domain links must belong to the canonical occupation.")

    @property
    def canonical_domain(self) -> OccupationDomainLink:
        return next(link for link in self.domain_links if link.relationship_type == "canonical")


@dataclass(frozen=True)
class SemanticCandidateReviewV2:
    """Version-2 semantic-review result contract.

    Identity and placement are intentionally independent.  A stable occupation
    can therefore retain ``placement_review_required`` without being forced to
    ``pending_identity_review``.
    """

    family_id: str
    representative_title: str
    identity_decision: IdentityDecision
    placement_status: PlacementStatus
    matched_existing_canonical_occupation_id: str | None
    matched_existing_canonical_occupation_title: str | None
    recommended_standard_title: str | None
    canonical_level_1: str | None
    canonical_level_2: str | None
    applicable_domains: tuple[OccupationDomainLink, ...]
    career_or_program_modifiers: tuple[CareerOrProgramModifier, ...]
    semantic_review_version: str = "semantic-review-v2"
    prompt_version: str = "semantic-candidate-review-prompt-v2"

    def __post_init__(self) -> None:
        if not self.family_id or not self.representative_title:
            raise ValueError("SemanticCandidateReviewV2 requires a family and title.")
        if self.identity_decision not in {
            "alias_of_existing", "proposed_new_occupation", "merge_with_candidate",
            "too_generic", "company_specific_or_program", "pending_identity_review",
        }:
            raise ValueError("Unsupported identity_decision.")
        if self.placement_status not in {
            "single_domain", "cross_industry", "context_dependent", "placement_review_required",
        }:
            raise ValueError("Unsupported placement_status.")
        if self.placement_status == "single_domain" and not (
            self.canonical_level_1 and self.canonical_level_2
        ):
            raise ValueError("single_domain requires canonical_level_1 and canonical_level_2.")
        if self.placement_status == "cross_industry" and not self.applicable_domains:
            raise ValueError("cross_industry requires at least one applicable domain.")
        if any(
            modifier != "management_trainee" for modifier in self.career_or_program_modifiers
        ):
            raise ValueError("Unsupported career_or_program_modifier.")


def canonical_occupation_from_legacy_entry(
    entry: TaxonomyEntry, *, taxonomy_version: str | None = None
) -> CanonicalOccupation:
    """Adapt one legacy workbook row without changing the workbook or reader.

    Every current Level-3 row becomes a canonical occupation with its existing
    Level-1/Level-2 placement as its sole canonical domain.  Later applicable
    domain links are additive and require taxonomy governance.
    """

    domain = OccupationDomainLink(
        occupation_id=entry.occupation_id,
        level_1=entry.level_1,
        level_2=entry.level_2,
        relationship_type="canonical",
    )
    return CanonicalOccupation(
        canonical_occupation_id=entry.occupation_id,
        standard_title=entry.level_3,
        definition=None,
        aliases=entry.aliases,
        status="active",
        taxonomy_version=taxonomy_version,
        domain_links=(domain,),
    )


def canonical_occupations_from_legacy_entries(
    entries: list[TaxonomyEntry], *, taxonomy_version: str | None = None
) -> list[CanonicalOccupation]:
    """Compatibility adapter for the unchanged 452-row Reference Taxonomy."""

    return [
        canonical_occupation_from_legacy_entry(entry, taxonomy_version=taxonomy_version)
        for entry in entries
    ]
