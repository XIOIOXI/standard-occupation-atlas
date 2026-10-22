# Job Market Intelligence Product Data Layer

Deterministic, read-only product artifacts derived from frozen selective-1000 market data. No upstream analysis is rerun.

- Occupations: 520 (84 mapped, 436 unmapped)
- Comparison-eligible occupations: 74
- Skills: 2396
- Graph nodes / edges: 2927 / 7443
- PMI edges: 128; Louvain communities: 11

## Semantics

PMI edges are global market co-occurrence relationships, not prerequisites or learning order. Louvain labels are UI fallback labels only. Occupation/context edges are deterministic derivations from completed inference groups.

## Product Manager hero demo

OCC0289 is available with 13 contexts and 34 skills; its detail, graph subset, context comparison and evidence references are in `product_manager_demo.json`.

## Limitations

- Selective-1000 is not complete 15,622-group inference coverage.
- Unmapped records remain candidate labels and must not be presented as canonical occupations.
- No unsupported prerequisite/causal edges are generated.
