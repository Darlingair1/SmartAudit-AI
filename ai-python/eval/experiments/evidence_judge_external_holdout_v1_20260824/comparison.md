# Evidence Judge External Holdout V1 Blind Evaluation

Status: `EXTERNAL_BLIND_EVALUATION_COMPLETE`

Dataset SHA256: `d0f98891bd7e0471516afe11f99a4bae5d51026c9a1d140eee22c3e9b7ca89d3`

The External result is descriptive. Evidence Judge v2.1 development acceptance remains **FAIL** because `semantically_related_but_insufficient accuracy = 0.666667 < 0.75`.

| Judge | Accuracy | Macro-F1 | SUP Precision | SUP Recall | PARTIAL F1 | UNSUP Recall | Unsafe acceptance | Human review | Selective accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v0 | 0.133333 | 0.113193 | 0.000000 | 0.000000 | 0.142857 | 0.857143 | 0.000000 (0/58) | 0.100000 | 0.111111 |
| v1 | 0.150000 | 0.142907 | 0.000000 | 0.000000 | 0.277778 | 0.571429 | 0.000000 (0/58) | 0.233333 | 0.086957 |
| v2 | 0.416667 | 0.289574 | 0.500000 | 0.241935 | 0.542636 | 0.000000 | 0.258621 (15/58) | 0.708333 | 0.428571 |
| v2_1 | 0.366667 | 0.238954 | 0.400000 | 0.129032 | 0.521739 | 0.000000 | 0.206897 (12/58) | 0.783333 | 0.307692 |

All four Judges are deterministic and model-free. External model/API invocations and estimated external model cost are zero.

No new acceptance gate was applied and no Judge, threshold, dataset, Gold label, retrieval result, or candidate ranking was modified.
