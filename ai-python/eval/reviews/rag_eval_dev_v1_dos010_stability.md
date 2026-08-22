# rag_eval_dev_v1 DOS_010 Stability Review

## Outcome

The 39-case state is frozen as a **diagnostic development baseline candidate**.
It is reproducible on the current machine and its fallback ranking is stable,
but it is not a formal regression or CI gate.

## Current Balance

| Dimension | Counts |
|---|---|
| Reviewed / draft | 39 / 1 |
| Documents | 6 total; 3 public PDFs; 3 synthetic documents |
| Source type | public: 21; synthetic: 18 |
| Difficulty | easy: 3; medium: 15; hard: 19; unspecified smoke: 2 |
| Gold count | 1: 13; 2: 14; 3: 9; 4: 1; 6: 2 |

Case types are multi-label:

| Case type | Count |
|---|---:|
| multiple_evidence | 24 |
| hard_negative | 17 |
| single_evidence | 9 |
| long_distance | 9 |
| numeric_confusion | 7 |
| conditional_clause | 6 |
| similar_clause | 5 |
| party_confusion | 5 |
| negation | 4 |

The corpus is large enough for a development baseline. More PDFs are not a
prerequisite for this candidate freeze.

## CrossEncoder Diagnostic

- Runtime: PyTorch 2.10.0 CPU-only
- CUDA available: no
- Production timeout: 3.000 seconds
- Batch size: 8
- Maximum sequence length: 512
- Model load, measured separately: 2.934 seconds
- Direct inference for 10 query/candidate pairs: 6.070 seconds
- Full evaluation: 0 success / 39 timeout fallback / 0 other fallback

The model is present and loads successfully. Direct CPU inference exceeds the
unchanged timeout. The production reranker submits work to a single-worker
executor; a timed-out future is not cancelled, so subsequent calls can time out
while earlier inference continues or while waiting in the queue. This is an
environment/runtime finding only. No timeout, model, executor, or retrieval code
was changed.

## Fixed-Case Repeatability

Cases q004, q005, and q008 were rerun with the same current profile. For every
case:

- top-10 candidate IDs and order were identical;
- scores were exactly identical;
- maximum absolute score delta was 0.0;
- original and repeat runs both used `timeout_fallback`;
- retrieval coverage was 100% with no retrieval error.

This verifies repeatability of the current fallback ranking. It does not prove
repeatability of successful CrossEncoder ranking.

## Error Review

| Case | Recall@5 | Initial category | Finding |
|---|---:|---|---|
| q001 | 0.166667 | `GOLD_LABEL_ERROR` plus `TRUE_RETRIEVAL_MISS` | Page 3 contains a valid alternative date/extension statement not represented by the current all-required Gold schema; page 18 notice evidence was also missed. |
| q002 | 0.500000 | `TRUE_RETRIEVAL_MISS` | Value evidence retrieved; no-minimum-spend child missed. |
| q003 | 0.000000 | `TRUE_RETRIEVAL_MISS` | Invoice-frequency evidence absent from top 10. |
| q007 | 0.500000 | `TRUE_RETRIEVAL_MISS` | Data-destruction evidence retrieved; notice-calculation evidence missed. |
| q008 | 0.666667 | `TRUE_RETRIEVAL_MISS` at K=5 | Unlimited-indemnity evidence appears at rank 7; Recall@10 is 1.0. |

No algorithm or Gold was changed in response to these results.

## Remaining Gates

1. q001 equivalent-evidence adjudication is resolved through the approved
   Option A split into q001 and q009.
2. CrossEncoder integration execution is now verified by a successful
   current-profile smoke run with the unchanged timeout.
3. A formal all-case reranked baseline would still require a runtime capable of
   completing the normal 10-candidate batches within the production timeout, or
   a separately approved baseline policy for mixed reranker/fallback results.

## Subsequent Annotation Decision

After this 39-case snapshot was frozen, q001 adjudication Option A was approved.
The current dataset splits the former q001 into an Order Form case (q001) and an
extension-procedure case (q009), producing 40 reviewed cases. The frozen lock
and its report remain immutable historical artifacts and therefore still record
the pre-split q001 result. The q001 annotation-semantics blocker is resolved for
the current dataset; successful CrossEncoder execution remains outstanding.

The post-adjudication full run executed all 40 reviewed cases successfully at
100% coverage. q001 reached Recall@5=1.0. The new q009 reached Recall@5=0.666667
and Recall@10=1.0. The run still used CrossEncoder timeout fallback for all 40
cases, so `formal_regression_baseline_ready` remains false. The current snapshot
is frozen separately in
`rag_eval_dev_v1_dos010_option_a_candidate_lock.json`.

## CrossEncoder Integration Smoke

The existing reviewed `dev_smoke_payment_001` case was run through the real
current production retrieval and reranker path. No retrieval mock was used.

- Environment: `OMP_NUM_THREADS=8`, `MKL_NUM_THREADS=8`
- Production timeout: unchanged at 3000 ms
- Candidate count: 2
- CrossEncoder success / timeout fallback / other fallback: 1 / 0 / 0
- Reranker status: `success`
- Coverage: 100%
- Hit@1 / Recall@1 / MRR: 1.0 / 1.0 / 1.0

This closes the Phase 1.5 CrossEncoder integration gate. It does not change the
meaning of the frozen 40-case report, where all cases used timeout fallback.

## Verification

- Benchmark validator: PASS (`6` documents, `41` total cases, `40` reviewed,
  `1` draft).
- Candidate lock dataset, manifest, requirements, full-report, and repeat-report
  SHA256 checks: PASS.
- Baseline lock targeted test: `1 passed`.
- Full Python suite: `67 passed`.
- Coverage: `42.35%`, above the configured `25%` gate.
