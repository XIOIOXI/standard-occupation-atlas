# ADR: SNO v3 directory reset

## Decision

The product adopts `sno-v3-directory-design` as the replacement directory design for SNO display and future role classification. Its official source is the user-supplied `SNO职业目录一二三级_v3.md`, snapshotted in `data/taxonomy/sno_v3/` with a SHA-256 checksum.

This is a directory reset, not a bulk migration. All historical OCC/SNO display placements are deprecated for display and can only be retained as review context.

## Why

The prior structure allowed category choices to depend too heavily on industry, technology, title fragments, and display holding groups. That created overlapping bubbles and ambiguous placement. V3 instead has one primary level-2 position per atomic role, derives level 1 from it, makes level 3 optional, and stores industry, technology, object/scenario, and role-stage attributes as tags.

## Consequences

- A role can appear in one primary bubble only. Parent totals are roll-ups, never duplicated role mappings.
- A known level 2 with insufficient level-3 evidence is valid and remains at level 2.
- Information-insufficient, multi-role-to-split, non-role text, primary-responsibility-uncertain, and real-directory-gap are explicit review states. They are not a catch-all occupation category.
- Historical mappings must be re-evaluated at atomic-role / original-record evidence level. No category-wide copy-forward is valid.
- No recruitment data is reclassified by this change alone. A subsequent, separately approved reclassification run must preserve the original records and mapping evidence.
