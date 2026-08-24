# Evidence Judge v2.1 Safety Hardening

Acceptance criteria SHA256: `779611d9ef7ecadf965ff543272f1eb4e9d40dad5812c36f95d45061548b9b53`
Dataset SHA256: `8b171081aa27a07e7e4d9d0b4ccc8de75e28926aa582822a04985182b7831d8e`
Implementation SHA256: `403a6e3318e9c48196162090070f91bbea091e5c34fdfbbeae0e57738c22fbb7`

| Metric | v0 | v1 | v2 | v2.1 |
|---|---:|---:|---:|---:|
| accuracy | 0.420561 | 0.383178 | 0.411215 | 0.588785 |
| macro_f1 | 0.339287 | 0.270165 | 0.365646 | 0.586788 |
| supported_precision | 0.857143 | 0.800000 | 0.636364 | 0.941176 |
| supported_recall | 0.150000 | 0.100000 | 0.525000 | 0.400000 |
| partial_f1 | 0.153846 | 0.042553 | 0.428572 | 0.481013 |
| unsupported_recall | 0.875000 | 0.900000 | 0.050000 | 0.700000 |
| unsafe_acceptance_rate | 0.014925 | 0.014925 | 0.179104 | 0.014925 |
| supported_false_rejection_rate | 0.850000 | 0.900000 | 0.475000 | 0.600000 |
| hard_false_rejection_rate | 0.450000 | 0.525000 | 0.000000 | 0.075000 |
| human_review_rate | 0.233645 | 0.186916 | 0.663551 | 0.485981 |
| automation_coverage | 0.766355 | 0.813084 | 0.336449 | 0.514019 |
| selective_accuracy | 0.500000 | 0.459770 | 0.638889 | 0.800000 |

## Acceptance

```json
{
  "unsafe_acceptance_gate": true,
  "conflicting_evidence_gate": true,
  "insufficient_evidence_gate": false,
  "unsupported_recall_gate": true,
  "supported_recall_preservation_gate": true,
  "partial_f1_preservation_gate": true,
  "multi_evidence_preservation_gate": true,
  "macro_f1_gate": true,
  "overall_pass": false
}
```

## Failure Types

| Type | Count | v0 | v1 | v2 | v2.1 |
|---|---:|---:|---:|---:|---:|
| chinese_numeral_or_amount | 7 | 0.285714 | 0.285714 | 0.714286 | 0.571429 |
| complex_negation_exception | 6 | 0.166667 | 0.000000 | 0.500000 | 0.166667 |
| conflicting_evidence | 16 | 0.875000 | 0.875000 | 0.000000 | 0.750000 |
| cross_sentence_qualifier | 7 | 0.142857 | 0.000000 | 0.571429 | 0.571429 |
| implicit_entity_coreference | 7 | 0.142857 | 0.142857 | 0.571429 | 0.571429 |
| implicit_risk_inference | 6 | 0.000000 | 0.000000 | 0.500000 | 0.333333 |
| multi_evidence_support | 27 | 0.148148 | 0.037037 | 0.777778 | 0.703704 |
| paraphrase_synonym | 7 | 0.142857 | 0.142857 | 0.285714 | 0.142857 |
| semantically_related_but_insufficient | 24 | 0.875000 | 0.916667 | 0.083333 | 0.666667 |

## Final Answers

A. Acceptance gates passed: False.
B. SUPPORTED Recall change: -0.125000; PARTIAL F1 change: +0.052441.
C. Freeze and proceed to External Holdout recommendation: NO.

No second tuning, Judge v3, External Holdout, README claim, or resume update was performed.
