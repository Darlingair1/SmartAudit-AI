# Evidence Judge v1 Deterministic Baseline

`evidence_judge_v1` adds structured deterministic checks without changing v0, retrieval, reranking, or the frozen benchmark. It uses no model dependency.

## Metrics on frozen benchmark

| Metric | v0 | v1 | Delta |
|---|---:|---:|---:|
| Accuracy | 0.425000 | 1.000000 | +0.575000 |
| Macro-F1 | 0.336594 | 1.000000 | +0.663406 |
| SUPPORTED Precision | 0.366972 | 1.000000 | +0.633028 |
| SUPPORTED Recall | 1.000000 | 1.000000 | 0 |
| PARTIAL Precision / Recall / F1 | 1.000000 / 0.075000 / 0.139535 | 1 / 1 / 1 | improved |
| UNSUPPORTED Recall | 0.200000 | 1.000000 | +0.800000 |
| Abstention Precision / Recall | 1.000000 / 0.075000 | 1 / 1 | improved |
| Human review rate | 0.091667 | 0.666667 | +0.575000 |
| Unsafe acceptance rate | 0.862500 | 0.000000 | -0.862500 |

v1 confusion matrix is diagonal: 40/40 for each class. There were 69 prediction transitions, all v0-wrong/v1-correct. v0-correct/v1-wrong = 0; supported false rejection = 0.

## Feature contribution

- Qualifier completeness: corrected 37 missing-qualifier unsafe acceptances; all 40 qualifier cases now abstain as PARTIAL.
- Entity consistency: corrected all 23 wrong-entity cases with `ENTITY_MISMATCH`.
- Numeric consistency: corrected four numeric mismatch cases, including clause/table index counts.
- Temporal consistency: the check is emitted for every prediction, but the benchmark's single temporal-mismatch sample was corrected by the overlapping numeric check and is attributed to `NUMERIC_MISMATCH`. This run therefore does not demonstrate an independently attributable temporal-check correction.
- Semantic scope: corrected four lexical-overlap-but-insufficient negation cases. Eight unsupported-risk-inference controls were already correct in v0 and remain correct with an explicit reason.
- Lexical support: preserves all 40 direct SUPPORTED cases and provides the base support signal after structured conflicts are checked.

Each prediction in `results.json` records PASS/FAIL/UNKNOWN, reason code, matched/missing/conflicting items for every check. Every transition with feature details is in `comparison.json`.

## Regressions and limitations

Measured regressions on this benchmark: zero. This does not establish general natural-language entailment quality. The benchmark is a controlled, template-derived dataset designed around entity, number, time, qualifier, negation, and unsupported-inference perturbations, so v1's perfect score reflects alignment with those known constructions. Entity vocabulary is intentionally small; Chinese-number words, implicit entities, paraphrased conditions, multi-evidence reasoning, and complex negation remain UNKNOWN or uncovered. The human-review rate rises to 66.7% because PARTIAL and UNSUPPORTED decisions require review.

No LLM/NLI/CrossEncoder Judge was implemented.
