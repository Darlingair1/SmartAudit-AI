# Evidence Judge v0/v1 Generalization Comparison

Dataset SHA256: `8b171081aa27a07e7e4d9d0b4ccc8de75e28926aa582822a04985182b7831d8e`
Dataset source commit: `cf29aae27f51d02ff194d42d156315ebd038be25`
Judge implementation commit SHA: `cf29aae27f51d02ff194d42d156315ebd038be25`
Evaluator config fingerprint: `72970afe28e0daaa9a587fe12422028d20a8f8a411417b4b248a706bdb255daf`

## Generalization Dataset

| Metric | v0 | v1 |
|---|---:|---:|
| accuracy | 0.420561 | 0.383178 |
| macro_f1 | 0.339287 | 0.270165 |
| supported_precision | 0.857143 | 0.800000 |
| supported_recall | 0.150000 | 0.100000 |
| unsupported_recall | 0.875000 | 0.900000 |
| partial_f1 | 0.153846 | 0.042553 |
| supported_false_rejection_rate | 0.850000 | 0.900000 |
| hard_false_rejection_rate | 0.450000 | 0.525000 |
| selective_accuracy | 0.500000 | 0.459770 |
| unsafe_acceptance_rate | 0.014925 | 0.014925 |
| human_review_rate | 0.233645 | 0.186916 |
| automation_coverage | 0.766355 | 0.813084 |

## Generalization Confusion Matrices

v0:
```json
{"SUPPORTED": {"SUPPORTED": 6, "PARTIAL": 16, "UNSUPPORTED": 18}, "PARTIAL": {"SUPPORTED": 1, "PARTIAL": 4, "UNSUPPORTED": 22}, "UNSUPPORTED": {"SUPPORTED": 0, "PARTIAL": 5, "UNSUPPORTED": 35}}
```
v1:
```json
{"SUPPORTED": {"SUPPORTED": 4, "PARTIAL": 15, "UNSUPPORTED": 21}, "PARTIAL": {"SUPPORTED": 1, "PARTIAL": 1, "UNSUPPORTED": 25}, "UNSUPPORTED": {"SUPPORTED": 0, "PARTIAL": 4, "UNSUPPORTED": 36}}
```

## Controlled Benchmark V1 (separate)

Controlled V1 metrics and matrix are copied from the frozen report and are not pooled with generalization metrics.

## Provenance

- v0 implementation file SHA256: `557befaba4ca5b044f4b01262eabc66f5e1f03cd77caa77c95a0eeddbb9ee2d3`
- v1 implementation file SHA256: `041633435db6feb2da1814a1638c0308c0b3e484d27fea93b11994ccccb21bc5`
- immutable blind v1 result SHA256: `9b71be7b643975636ee76d0266b6631cdb5266a3f1f4cddcf458281ec39d72d3`
