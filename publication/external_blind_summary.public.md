# External Blind Evaluation: Public Summary

Dataset SHA256: `d0f98891bd7e0471516afe11f99a4bae5d51026c9a1d140eee22c3e9b7ca89d3`

The result is descriptive. Evidence Judge v2.1 development acceptance remains **FAIL** because `semantically_related_but_insufficient accuracy = 0.666667 < 0.75`.

| Judge | Accuracy | Macro-F1 | SUP Precision | SUP Recall | PARTIAL F1 | UNSUP Recall | Unsafe acceptance | Human review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v0 | 0.133333 | 0.113193 | 0.000000 | 0.000000 | 0.142857 | 0.857143 | 0.000000 (0/58) | 0.100000 |
| v1 | 0.150000 | 0.142907 | 0.000000 | 0.000000 | 0.277778 | 0.571429 | 0.000000 (0/58) | 0.233333 |
| v2 | 0.416667 | 0.289574 | 0.500000 | 0.241935 | 0.542636 | 0.000000 | 0.258621 (15/58) | 0.708333 |
| v2_1 | 0.366667 | 0.238954 | 0.400000 | 0.129032 | 0.521739 | 0.000000 | 0.206897 (12/58) | 0.783333 |

Production recommendation: **HITL-first**. v2.1 is not an autonomous default gate.

Full first-run predictions, claims, evidence, reviewer notes, and case-level transitions are local-only. Their immutable SHA256 values remain in the machine-readable public summary.
