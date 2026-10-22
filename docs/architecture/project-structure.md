# Recommended Project Structure

```text
ai-curriculum-intelligence-agent/
├─ AGENTS.md
├─ data/
│  ├─ raw/                         # Source XLSX backup and runtime CSV; never mutate
│  ├─ vocabularies/                 # Versioned skills, aliases, and classifications
│  └─ fixtures/                     # Small synthetic/test fixtures only
├─ docs/
│  └─ architecture/
│     ├─ data-model.md
│     ├─ data-flow.md
│     ├─ development-constraints.md
│     └─ project-structure.md
├─ backend/
│  ├─ app/
│  │  ├─ api/                       # Import, programme, analysis, and report endpoints
│  │  ├─ domain/
│  │  │  ├─ recruitment/            # Snapshots, records, normalisation, future Job Groups
│  │  │  ├─ taxonomy/                # Canonical occupations, domain links, mapping contracts
│  │  │  ├─ skills/                 # Observed/Inferred skill contracts and vocabulary
│  │  │  ├─ curriculum/             # Program, Curriculum, Course, Outcome models
│  │  │  └─ analysis/               # Demand profiles, mappings, structural gaps
│  │  ├─ repositories/              # Persistence boundaries and cache lookups
│  │  ├─ services/                  # Explicit business workflows
│  │  ├─ tools/                     # Deterministic Python statistics/graph analysis only
│  │  ├─ inference/                 # Offline context builder, version gate, persistence contract
│  │  ├─ agent/                     # Single-agent orchestration and evidence-constrained prompts
│  │  ├─ reporting/                 # Provenance-preserving report schemas/rendering
│  │  └─ migrations/                # Database schema and unique constraints
│  └─ tests/
│     ├─ unit/
│     ├─ integration/
│     └─ fixtures/
├─ frontend/
│  └─ src/
│     ├─ features/recruitment/
│     ├─ features/programme/
│     ├─ features/analysis/
│     └─ features/reports/
└─ scripts/
   └─ offline/                      # Explicitly invoked maintenance/import jobs only
```

## Boundary rules

- `inference/` is not called by interactive API reads or front-end page loads. It owns only explicit offline enrichment jobs and their cache/version gate.
- `tools/` contains deterministic Python calculations, including frequency, coverage, PMI, network metrics, Louvain clustering, and structural-gap calculations. It never calls an LLM.
- `agent/` may read evidence-pack results and call the recommendation model, but cannot execute hidden inference or fabricate measures.
- `repositories/` expose `ObservedSkill` and `InferredSkill` separately, including their source/evidence/version fields.
- `scripts/offline/` must require an explicit command and target scope; it is the only future home for batch inference orchestration.
- `data/raw/` is an immutable source area. The runtime uses CSV; XLSX remains a backup. Small test inputs belong in `data/fixtures/`, not alongside source data.
