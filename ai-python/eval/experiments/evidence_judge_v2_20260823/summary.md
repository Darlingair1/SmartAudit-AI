# Evidence Judge v0/v1/v2 Development Comparison

Dataset SHA256: `8b171081aa27a07e7e4d9d0b4ccc8de75e28926aa582822a04985182b7831d8e`

| Metric | v0 | v1 | v2 |
|---|---:|---:|---:|
| accuracy | 0.420561 | 0.383178 | 0.411215 |
| macro_f1 | 0.339287 | 0.270165 | 0.365646 |
| supported_precision | 0.857143 | 0.800000 | 0.636364 |
| supported_recall | 0.150000 | 0.100000 | 0.525000 |
| partial_f1 | 0.153846 | 0.042553 | 0.428572 |
| unsupported_recall | 0.875000 | 0.900000 | 0.050000 |
| unsafe_acceptance_rate | 0.014925 | 0.014925 | 0.179104 |
| supported_false_rejection_rate | 0.850000 | 0.900000 | 0.475000 |
| hard_false_rejection_rate | 0.450000 | 0.525000 | 0.000000 |
| human_review_rate | 0.233645 | 0.186916 | 0.663551 |
| automation_coverage | 0.766355 | 0.813084 | 0.336449 |
| selective_accuracy | 0.500000 | 0.459770 | 0.638889 |

## Transition Summary

{
  "v1_wrong_v2_correct": 38,
  "v1_correct_v2_wrong": 35,
  "supported_false_rejection_repaired": 17,
  "partial_correctly_recovered": 21,
  "new_unsafe_acceptance": 11,
  "unsupported_upgraded_to_supported": 7
}

## Failure Types

| Type | Count | v0 Acc | v1 Acc | v2 Acc |
|---|---:|---:|---:|---:|
| chinese_numeral_or_amount | 7 | 0.285714 | 0.285714 | 0.714286 |
| complex_negation_exception | 6 | 0.166667 | 0.000000 | 0.500000 |
| conflicting_evidence | 16 | 0.875000 | 0.875000 | 0.000000 |
| cross_sentence_qualifier | 7 | 0.142857 | 0.000000 | 0.571429 |
| implicit_entity_coreference | 7 | 0.142857 | 0.142857 | 0.571429 |
| implicit_risk_inference | 6 | 0.000000 | 0.000000 | 0.500000 |
| multi_evidence_support | 27 | 0.148148 | 0.037037 | 0.777778 |
| paraphrase_synonym | 7 | 0.142857 | 0.142857 | 0.285714 |
| semantically_related_but_insufficient | 24 | 0.875000 | 0.916667 | 0.083333 |

Semantic implementation: model-free normalization, alias/concept coverage, multi-evidence concatenation, and deterministic conflict guards. No LLM/service invocation; latency/cost are local deterministic inference with zero timeout/error/fallback.

No Judge v3 or external holdout was created.
