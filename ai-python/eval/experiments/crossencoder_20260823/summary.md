# CrossEncoder Optimization Experiment

This experiment is additive and does not modify `eval/baselines/retrieval_baseline_v1`.

## Scope and root cause

The frozen reference is commit `5825dfbe18f2de720f8103149bd9a6ce11ef09d8`, 40 reviewed cases. The existing reranker already caches one model per `(model, device, max_length)`, runs in the same evaluation process, and calls `CrossEncoder.predict` with batching. Profiling shows tokenization is ~5 ms while CPU model forward averages 8,669 ms for about 9.25 candidates (about 282 tokens each); 38/40 direct samples exceed the fixed 3,000 ms timeout. The bottleneck is CPU forward plus queued timeout work, not repeated initialization or tokenization.

## Optimization measurements

| Variant | Mean rerank (ms) | Finding |
|---|---:|---|
| Warmup, 512/8 | 8,257 | small improvement |
| Batch 1, 512 | 8,769 | no improvement |
| 4 CPU threads | 11,746 | worse |
| 16 CPU threads | 8,781 | no improvement |
| Max length 256, batch 10 | 6,267 | best, still above timeout |
| Max length 384, batch 10 | 8,753 | no improvement |
| Microbatch 4 | 8,724 | no improvement |

## 40-case runs

The non-reranking controls were also rerun in `ablation_summary.json`: lexical-only Hit@1/Recall@5/MRR = 0.650/0.840/0.770 (mean 608 ms), vector-only = 0.650/0.850/0.770 (mean 6,085 ms), hybrid without RRF = 0.650/0.840/0.770 (mean 6,633 ms), and hybrid RRF = 0.750/0.890/0.830 (mean 5,944 ms).

`hybrid_rrf_crossencoder_max256_fallback` retained the existing fallback contract: 2 CrossEncoder successes, 38 timeout fallbacks. Metrics were Hit@1 0.875, Recall@1/3/5/10 0.670833/0.858333/0.918750/0.935417, MRR 0.908333; end-to-end latency mean/p50/p95 13,491/5,355/41,173 ms.

`hybrid_rrf_crossencoder_strict_max256` disables heuristic fallback. It recorded 2 successes and 38 explicit CrossEncoder errors, so it is **unavailable** as a CrossEncoder quality profile. Its ranking is the underlying RRF order for failed cases; do not attribute those metrics to successful CrossEncoder inference. Metrics: Hit@1 0.750, Recall@1/3/5/10 0.560417/0.808333/0.891667/0.935417, MRR 0.830000; latency mean/p50/p95 80,202/4,632/53,143 ms.

## Engineering decision

CrossEncoder is not recommended for the default production pipeline on this CPU environment. The only material tuning, truncation to 256 tokens, remains slower than the timeout and does not provide 40-case success. No timeout increase was used to mask the issue. Use the unchanged RRF/fallback baseline; reconsider with GPU or a dedicated inference service.

Machine-readable details and report paths are in `summary.json` and the sibling run files.

## Ranking drift diagnostic

Three identical `hybrid_rrf` runs were executed with BM25/RRF enabled, reranking disabled, CPU embedding, `OMP_NUM_THREADS=8`, and `MKL_NUM_THREADS=8`. Dataset hash and settings fingerprint were identical across runs; all document and extraction hashes matched. Metrics were not stable: Hit@1 was `0.750, 0.750, 0.725`; Recall@5 was `0.891667, 0.879167, 0.891667`; MRR was `0.830000, 0.833333, 0.818333`. Only 24/40 cases had identical final rankings across all three runs.

The first divergence was vector retrieval for all 8 Guangdong-tax cases and all 8 software-service cases in the pairwise comparisons. Lexical candidate lists were stable across repeats; vector candidate IDs/distances changed, then propagated through RRF input, RRF scores, and final ranking. This identifies the vector/Chroma ANN stage as the first observed divergence, rather than RRF arithmetic. The frozen baseline comparison also contains four DWP cases whose first difference is lexical candidates, but that comparison used a different commit (`5825dfb` vs the diagnostic commit), so it is not a clean repeatability test.

Per-case changed IDs, stage comparisons, configuration, hashes, and ranking fingerprints are in `ranking_drift_summary.json`. The runner now records a SHA-256 ranking fingerprint over `case_id + ordered candidate_ids`; future reranker experiments should consume a frozen candidate snapshot when ranking reproducibility is required. No deterministic behavior was fabricated and no retrieval algorithm was changed.
