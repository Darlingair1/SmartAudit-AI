# DOS_010 Reviewed Cases - Retrieval Evaluation Result

## Run Identity

- Dataset: `eval/datasets/rag_eval_dev_v1.jsonl`
- Manifest: `eval/manifests/rag_eval_dev_v1_documents.json`
- Report: `eval/reports/retrieval_eval_dev_v1_uk_dwp_dos010.json`
- Profile: `current`
- Top K: `1,3,5,10`
- Page matching: enabled
- Text coverage threshold: 0.7
- Git commit recorded by runner: `2e557d4d1f3e81cac54304905fcd2a88185bf184`
- Evaluation timestamp: `2026-08-22T06:58:21.666779Z`

## Validation

- Status: PASS
- Manifest documents: 6
- Dataset cases: 40
- Reviewed cases: 39
- Excluded draft cases: 1
- DOS_010 reviewed cases added: 8

## Whole rag_eval_dev_v1

- Evaluation coverage: 100% (39/39)
- Retrieval success: 39/39
- Document not found: 0
- Retrieval error: 0
- Hit@1/3/5/10: 0.871795 / 0.974359 / 0.974359 / 0.974359
- Recall@1/3/5/10: 0.679487 / 0.861111 / 0.918803 / 0.927350
- MRR: 0.914530
- Latency mean/median/P95: 20903.100 / 3372.786 / 134942.610 ms
- Total runtime: 818180.453 ms
- CrossEncoder success / timeout fallback / other fallback: 0 / 39 / 0

## New DOS_010 Batch

- Evaluation coverage: 100% (8/8)
- Retrieval success: 8/8
- Hit@1/3/5/10: 0.750000 / 0.875000 / 0.875000 / 0.875000
- Recall@1/3/5/10: 0.395833 / 0.562500 / 0.604167 / 0.645833
- MRR: 0.812500
- Latency mean/median/P95: 50415.872 / 4123.157 / 372933.625 ms
- CrossEncoder success / timeout fallback / other fallback: 0 / 8 / 0

The q001 latency includes the first preparation of this 41-page document:
369100.110 ms document preparation plus retrieval and timeout fallback. It is
retained in the reported latency and was not removed as an outlier.

## Case Results

### q001

- Status: `partial_evidence_retrieved`
- Hit@1/3/5/10: 0 / 1 / 1 / 1
- Recall@1/3/5/10: 0 / 0.166667 / 0.166667 / 0.166667
- First relevant rank: 2
- MRR: 0.5
- Latency: 372933.625 ms
- Matched Gold indexes: `[5]`
- Reranker: `timeout_fallback`

Top 5:

| Rank | Candidate | Parent | page_no / page_nos | Score | Matched Gold |
|---:|---|---|---|---:|---|
| 1 | `c-0003-0013` | `p-0003` | 3 / `[3]` | 0.338373 | `[]` |
| 2 | `c-0013-0083` | `p-0013` | 13 / `[13]` | 0.335597 | `[5]` |
| 3 | `c-0013-0082` | `p-0013` | 13 / `[13]` | 0.327818 | `[]` |
| 4 | `c-0020-0122` | `p-0020` | 20 / `[20]` | 0.304711 | `[]` |
| 5 | `c-0033-0262` | `p-0033` | 33 / `[33]` | 0.274296 | `[]` |

Error analysis: primary `GOLD_LABEL_ERROR`, with a secondary
`TRUE_RETRIEVAL_MISS`. Rank 1 on physical page 3 contains an alternative,
contract-valid statement of commencement date and maximum extension, but the
reviewed Gold labels those facts only on physical page 2. The extension notice
evidence on page 18 was not retrieved in the top 10, which is a true miss. No
Gold or algorithm was changed after observing this result.

### q002

- Status: `partial_evidence_retrieved`
- Hit@1/3/5/10: 1 / 1 / 1 / 1
- Recall@1/3/5/10: 0.5 / 0.5 / 0.5 / 0.5
- First relevant rank: 1
- MRR: 1.0
- Latency: 3915.258 ms
- Matched Gold indexes: `[0]`
- Reranker: `timeout_fallback`

Top 5: `c-0004-0024` page `[4]` score 0.441212 Gold `[0]`;
`c-0029-0223` page `[29]` 0.245415; `c-0034-0274` page `[34]` 0.245086;
`c-0018-0108` page `[18]` 0.242545; `c-0008-0054` page `[8]` 0.228687.

Error analysis: `TRUE_RETRIEVAL_MISS`. The cumulative value was retrieved at
rank 1, but the adjacent no-minimum-spend evidence in another child was absent
from the top 10. Page mapping and matcher behavior were correct.

### q003

- Status: `no_relevant_evidence_retrieved`
- Hit@1/3/5/10: 0 / 0 / 0 / 0
- Recall@1/3/5/10: 0 / 0 / 0 / 0
- First relevant rank: null
- MRR: 0
- Latency: 3953.501 ms
- Matched Gold indexes: `[]`
- Reranker: `timeout_fallback`

Top 5: `c-0008-0052` page `[8]` score 0.289738;
`c-0025-0173` page `[25]` 0.274457; `c-0029-0223` page `[29]` 0.263534;
`c-0018-0108` page `[18]` 0.244361; `c-0034-0274` page `[34]` 0.240347.

Error analysis: `TRUE_RETRIEVAL_MISS`. None of the top 10 candidates contains
the invoice-frequency Gold on physical page 4. There is no page or parser
evidence of a matcher false negative.

### q004

- Status: `success`
- Hit@1/3/5/10: 1 / 1 / 1 / 1
- Recall@1/3/5/10: 1 / 1 / 1 / 1
- First relevant rank: 1
- MRR: 1.0
- Latency: 4201.410 ms
- Matched Gold indexes: `[0]`
- Reranker: `timeout_fallback`

Top 5: `c-0012-0078` page `[12]` score 0.370993 Gold `[0]`;
`c-0012-0077` page `[12]` 0.345788; `c-0028-0210` page `[28]` 0.245128;
`c-0028-0211` page `[28]` 0.230566; `c-0014-0087` page `[14]` 0.216272.

### q005

- Status: `success`
- Hit@1/3/5/10: 1 / 1 / 1 / 1
- Recall@1/3/5/10: 0.333333 / 0.666667 / 1 / 1
- First relevant rank: 1
- MRR: 1.0
- Latency: 6146.542 ms
- Matched Gold indexes: `[0,1,2]`
- Reranker: `timeout_fallback`

Top 5: `c-0021-0133` page `[21]` score 0.336051 Gold `[1]`;
`c-0022-0137` page `[22]` 0.335900 Gold `[2]`; `c-0022-0138` page `[22]`
0.302161; `c-0021-0131` page `[21]` 0.287267 Gold `[0]`;
`c-0021-0132` page `[21]` 0.283248 Gold `[0,1]`.

### q006

- Status: `success`
- Hit@1/3/5/10: 1 / 1 / 1 / 1
- Recall@1/3/5/10: 0.5 / 1 / 1 / 1
- First relevant rank: 1
- MRR: 1.0
- Latency: 3930.323 ms
- Matched Gold indexes: `[0,1]`
- Reranker: `timeout_fallback`

Top 5: `c-0026-0190` page `[26]` score 0.423317 Gold `[0]`;
`c-0026-0186` page `[26]` 0.372299; `c-0026-0191` page `[26]` 0.352382
Gold `[1]`; `c-0003-0017` page `[3]` 0.333996; `c-0008-0052` page `[8]`
0.309035.

### q007

- Status: `partial_evidence_retrieved`
- Hit@1/3/5/10: 1 / 1 / 1 / 1
- Recall@1/3/5/10: 0.5 / 0.5 / 0.5 / 0.5
- First relevant rank: 1
- MRR: 1.0
- Latency: 4124.237 ms
- Matched Gold indexes: `[3,4,5]`
- Reranker: `timeout_fallback`

Top 5: `c-0030-0227` page `[30]` score 0.372065 Gold `[3,4,5]`;
`c-0029-0222` page `[29]` 0.333580; `c-0030-0226` page `[30]` 0.303174
Gold `[3]`; `c-0030-0230` page `[30]` 0.284815; `c-0030-0233` page `[30]`
0.240371.

Error analysis: `TRUE_RETRIEVAL_MISS`. The complete data-destruction evidence
on page 30 was retrieved at rank 1, but none of the three notice-calculation
Gold items on page 29 matched in the top 10. The page-29 rank-2 candidate is
clause 24 rather than clauses 23.2-23.3, so this is not a matcher false negative.

### q008

- Status: `success` at K=10; partial at K=5
- Hit@1/3/5/10: 1 / 1 / 1 / 1
- Recall@1/3/5/10: 0.333333 / 0.666667 / 0.666667 / 1
- First relevant rank: 1
- MRR: 1.0
- Latency: 4122.077 ms
- Matched Gold indexes: `[0,1,2]`
- Reranker: `timeout_fallback`

Top 5: `c-0033-0259` page `[33]` score 0.379479 Gold `[1]`;
`c-0033-0260` page `[33]` 0.354839 Gold `[2]`; `c-0033-0263` page `[33]`
0.321729; `c-0034-0269` page `[34]` 0.305423; `c-0025-0172` page `[25]`
0.276570.

Error analysis: `TRUE_RETRIEVAL_MISS` at K=5. The unlimited-indemnity Gold on
page 32 appears at rank 7 (`c-0032-0253`, page_nos `[32]`), so Recall@10 reaches
1.0. This is a ranking-depth miss, not a page-mapping or matcher problem.

## Page Metadata Verification

All candidates that matched Gold used singleton `page_nos` equal to the Gold's
physical page: 4, 12, 13, 21, 22, 26, 30, 32, or 33 as applicable. This PDF
produces one Parent per physical page and no cross-page Child chunks. The
multiple-evidence cases are covered through separate candidates on separate
physical pages; no candidate falsely claimed a continuous page range.

## Constraints Preserved

No production retrieval implementation, Parent/Child setting, embedding,
lexical/vector/RRF behavior, reranker timeout, matcher, or reviewed Gold was
changed after the run. The frozen baseline was not updated.
