# Retrieval Baseline V1

Frozen evaluation snapshot for the 40 reviewed `rag_eval_dev_v1` cases.
This is a retrieval diagnostic baseline, not a CI quality gate.

## Reproduction

```powershell
cd ai-python
python -m eval.run_ablation --baseline-dir eval/baselines/retrieval_baseline_v1
```

## Provenance

- Git commit: `5825dfbe18f2de720f8103149bd9a6ce11ef09d8`
- Dataset: `ai-python/eval/datasets/rag_eval_dev_v1.jsonl`
- Dataset SHA256: `b00e0a9b9a83c8e838edca6f48c5cebe7878f75d50d38550307b0c00e62737be`
- Manifest: `ai-python/eval/manifests/rag_eval_dev_v1_documents.json`
- Manifest SHA256: `c484e5ec45fcc8e2be770097eaa4d53229da10c5f052295daeb9168a773e8bff`
- Python: `3.11.5`
- pypdf: `6.14.2`
- Dataset cases: `40 reviewed`

## Profiles

| Profile | Status | Hit@1 | Recall@5 | Recall@10 | MRR | Mean latency ms |
|---|---|---:|---:|---:|---:|---:|
| lexical_only | success | 0.65 | 0.841667 | 0.95 | 0.774196 | 1431.74 |
| vector_only | success | 0.65 | 0.85 | 0.916667 | 0.768571 | 5915.93 |
| hybrid_no_rrf | success | 0.65 | 0.841667 | 0.95 | 0.774196 | 8122.701 |
| hybrid_rrf | success | 0.725 | 0.891667 | 0.922917 | 0.81 | 8777.833 |
| current_fallback | success | 0.875 | 0.91875 | 0.935417 | 0.908333 | 16993.626 |
| hybrid_crossencoder | unavailable | 0.875 | 0.91875 | 0.935417 | 0.908333 | 16993.626 |

## Reranker Status

- `lexical_only`: CrossEncoder success 0, timeout fallback 0, other fallback 0.
- `vector_only`: CrossEncoder success 0, timeout fallback 0, other fallback 0.
- `hybrid_no_rrf`: CrossEncoder success 0, timeout fallback 0, other fallback 0.
- `hybrid_rrf`: CrossEncoder success 0, timeout fallback 0, other fallback 0.
- `current_fallback`: CrossEncoder success 0, timeout fallback 40, other fallback 0.
- `hybrid_crossencoder`: CrossEncoder success 0, timeout fallback 40, other fallback 0.

CrossEncoder timeout fallback metrics must not be attributed to a successful CrossEncoder.
The current CPU environment retains the production 3000 ms timeout; the full reranked arm is unavailable when all cases time out.

## Limitations

- This baseline freezes current behavior and is not a regression gate.
- Any change to retrieval, chunking, embeddings, RRF, reranking, dependencies, dataset, or manifest requires a new baseline.
- Latency is environment-dependent and is diagnostic only.
