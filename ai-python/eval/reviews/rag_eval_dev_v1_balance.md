# rag_eval_dev_v1 Balance Audit

Snapshot: 31 reviewed cases across 5 documents.

## Distribution

| Dimension | Counts |
|---|---|
| Source type | synthetic: 18; public: 13 |
| Difficulty | easy: 2; medium: 12; hard: 15; unspecified: 2 |
| Gold count | 1: 11; 2: 12; 3: 7; 4: 1 |
| Document | smoke: 2; purchase synthetic: 8; software synthetic: 8; public vehicle procurement: 5; public software development: 8 |

Case types are multi-label:

| Case type | Count |
|---|---:|
| multiple_evidence | 18 |
| hard_negative | 13 |
| single_evidence | 7 |
| long_distance | 6 |
| conditional_clause | 6 |
| similar_clause | 5 |
| party_confusion | 5 |
| numeric_confusion | 4 |
| negation | 3 |

## Remaining Gaps

- Easy coverage remains low; future documents should include clean easy and medium cases.
- Public evidence is now 13/31 cases across two PDFs, but the public corpus is still procurement-contract heavy.
- Long-distance labels require a chunk-dispersion audit because multiple facts do not necessarily imply multi-parent retrieval.
- The two smoke cases have no difficulty annotation and should remain wiring checks rather than benchmark design targets.
- The frozen current-profile run used cross-encoder timeout fallback for all 31 cases, so it is not evidence of successful reranker execution.

## Gate Status

- Full current-profile evaluation reproducible: PASS
- Validator: PASS
- Ranking equivalence: PASS
- Reviewed cases >= 30: PASS (31)
- Public PDFs >= 2: PASS (2)
- Development baseline candidate freeze: FROZEN
- Formal regression or CI gate: NOT ENABLED
