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

## v2.1 Quality And Safety

- SUPPORTED precision: 8/20 = 0.400000, Wilson 95% CI [0.218807, 0.613418].
- SUPPORTED recall: 8/62 = 0.129032, Wilson 95% CI [0.066859, 0.234493].
- UNSUPPORTED recall: 0/14 = 0.000000, Wilson 95% CI [0.000000, 0.215311].
- Unsafe acceptance: 12/58 = 0.206897, Wilson 95% CI [0.122515, 0.327692].
- Human review: 94/120 = 0.783333, Wilson 95% CI [0.701456, 0.847633]. Automation coverage is 26/120 = 0.216667, Wilson 95% CI [0.152367, 0.298544].
- Supported false rejection is 54/62 = 0.870968; hard false rejection is 6/62 = 0.096774.

Compared with v2, v2.1 reduced unsafe acceptance from 15/58 to 12/58 and moved three unsafe v2 cases to PARTIAL/HITL and one to the correct label. This safety effect only partially reproduced: one other transition offset part of the improvement, UNSUPPORTED recall remained 0/14, SUPPORTED recall fell from 15/62 to 8/62, and accuracy fell from 50/120 to 44/120. PARTIAL recall improved slightly from 35/44 to 36/44, but the high PARTIAL prediction rate means this is not broad three-class generalization.

## Per Document

| Document | Cases | v2.1 Accuracy | Macro-F1 | SUP Recall | PARTIAL F1 | UNSUP Recall | Unsafe |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1746527472741_5024.pdf | 40 | 0.500000 | 0.337165 | 0.227273 | 0.666667 | 0.000000 | 2/18 |
| 8a69c65e95a7fec40195faa1360d1770.pdf | 25 | 0.400000 | 0.235215 | 0.071429 | 0.580645 | 0.000000 | 1/11 |
| 8a69c8e290831b250190964f57453e46.pdf | 55 | 0.254545 | 0.165068 | 0.076923 | 0.387097 | 0.000000 | 9/29 |

Only `约定不明` met the preregistered risk-type reporting threshold (`n >= 3`; n=7). v2.1 accuracy was 0.428571 for that slice. All other risk types were too sparse for interpretation.

## Failure Analysis

v2.1 made 76 errors. The read-only taxonomy counts are: `qualifier_exception_scope=26`, `implicit_risk_inference=20`, `conflicting_evidence=10`, `numeric_temporal_failure=9`, `semantic_paraphrase_failure=6`, `multi_evidence_failure=4`, and `partial_support_boundary=1`.

For 54 errors, Gold says the retrieved evidence was sufficient, so the failure is directly attributable to Judge rejection. The other 22 errors occur where human adjudication says the captured evidence is partial, insufficient, or conflicting; those rows retain an upstream evidence-failure flag while also recording that the Judge prediction did not match the evidence-sufficiency label.

## Latency And Cost

| Judge | Mean ms | p50 ms | p95 ms | Max ms | Errors / timeouts / fallback |
|---|---:|---:|---:|---:|---:|
| v0 | 8.383751 | 8.352950 | 11.750100 | 13.203900 | 0 / 0 / 0 |
| v1 | 12.434243 | 12.012400 | 18.581600 | 21.911200 | 0 / 0 / 0 |
| v2 | 19.256252 | 19.539900 | 24.960100 | 35.443400 | 0 / 0 / 0 |
| v2.1 | 26.154084 | 26.899050 | 33.810700 | 55.662200 | 0 / 0 / 0 |

Each Judge completed 120 invocations. External API/model invocation count and external model cost were zero.

## First-Run Integrity

- v0: `0edd9d5ec982a7eaa38d8bd1ef5b0eb1668c898aa01c3e7105ec07c8eae851d7`
- v1: `ca9efe86d94225cd1c0cb8bdf26814e08f567ca1670ac0cf9a0248f960387ef5`
- v2: `1386eb7947277ed544ca71c6c2912fb3aa1cdaf6695aa5b3ba2ec5f4d522130a`
- v2.1: `be626a2643c5c91df4da15100cc86efe1354b43c803ec453853a7f15ef3793a2`

## Recommendation

Do not make v2.1 an autonomous default gate. The External Holdout reproduces only a modest unsafe-acceptance reduction and exposes severe false rejection, zero UNSUPPORTED recall, and weak selective accuracy. Keep the pipeline HITL-first. If v2.1 is retained operationally, use it only as a secondary review signal whose PARTIAL/UNSUPPORTED outputs cannot automatically reject findings.
