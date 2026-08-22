# SmartAudit Retrieval Evaluation

This package runs deterministic offline retrieval evaluation without invoking an
LLM. It reuses the current V3 parent-child chunking, lexical/vector retrieval,
RRF, and reranker. Evidence Judge and the audit agents are outside this phase.

Part 1.5 adds a synthetic integration smoke corpus and a small development
benchmark. The smoke corpus is a wiring check, not a production baseline.

## Dataset

The versioned JSONL schema is documented in `datasets/schema.md`. Add one JSON
object per line, use a unique `case_id`, and point `metadata.document_path` to
the source PDF/text file. Alternatively place files named after `document_id`
under the directory passed with `--documents-dir`. Validation is strict and
reports the file, line, available case ID, and concrete error. Invalid rows are
never skipped.

`rag_eval_v1.jsonl` remains the legacy one-row dataset. The Part 1.5 datasets
are `datasets/rag_eval_smoke.jsonl` and `datasets/rag_eval_dev_v1.jsonl`.
Document IDs are mapped by `manifests/rag_eval_dev_v1_documents.json`, which
stores a relative path, source type, and SHA256.

PDF evidence is localized against the same canonical page texts used by
production retrieval (`services.document_parser.load_pdf_pages`). The loader
preserves physical page slots and strips only leading/trailing page whitespace.

## Evidence Matching

Both texts are normalized with Unicode NFKC, common Unicode punctuation is
canonicalized, and whitespace/newlines are removed. Coverage is the longest
contiguous common substring divided by normalized gold text length. A match
requires coverage at or above `--min-text-coverage` (default `0.7`) and, by
default, an exact page match. `--no-page-match` disables the page constraint.
The matcher uses no embedding model or LLM.

## Metrics

- Hit@K: whether at least one gold evidence is matched by the top K results.
- Recall@K: distinct gold evidence items matched by top K divided by the number of gold items.
- MRR: reciprocal rank of the first result that matches any gold evidence.
- Latency: mean, median, and nearest-rank P95 of end-to-end retrieval calls.

Dataset-level retrieval metrics are macro averages over completed retrieval
cases only. `document_not_found` is not a retrieval miss and is excluded from
Hit/Recall/MRR. `retrieval_error` is reported separately and is also excluded
from quality metrics. Latency aggregates only cases where retrieval was
actually attempted; an unattempted case has `latency_ms: null`.

Every report has a `coverage` object with total, executed, successful,
not-found, error counts, and `evaluation_coverage`. When no completed
retrieval exists, quality and latency values are `null`, not zero. Cases may
carry future manual review categories such as `TRUE_RETRIEVAL_MISS`,
`GOLD_LABEL_ERROR`, `MATCHER_FALSE_NEGATIVE`, `DOCUMENT_PARSE_ERROR`,
`PAGE_MAPPING_ERROR`, or `AMBIGUOUS_QUERY`.

## Run

From `ai-python`:

```text
python -m eval.runners.run_retrieval_eval \
  --dataset eval/datasets/rag_eval_smoke.jsonl \
  --documents-dir eval/fixtures \
  --manifest eval/manifests/rag_eval_dev_v1_documents.json \
  --profile current \
  --top-k 1,3,5,10
```

Only profile `current` exists. It uses production defaults and performs no LLM
call. If a vector model/index is unavailable, the current production behavior
falls back to lexical retrieval. Draft cases are excluded by default; pass
`--include-draft` to inspect them explicitly. The report is written to
`eval/reports/retrieval_eval_<UTC timestamp>.json`, or to `--output` when set.

Each case includes its status, Hit/Recall values, MRR, first relevant rank,
latency, matched gold evidence, and ranked result previews. Status values
include `success`, `partial_evidence_retrieved`,
`no_relevant_evidence_retrieved`, `document_not_found`, and `retrieval_error`.
Invalid dataset cases fail loading with `DatasetValidationError`, rather than
appearing in a partial report as `invalid_eval_case`.

Within one evaluation process, immutable document preparation is cached by
document ID, document SHA256, and a chunk/vector settings fingerprint. Page
loading, parent/child construction, and vector indexing run once per document;
query expansion, retrieval, RRF, reranking, matching, and metrics still run for
every case. The report's `execution` object records cache hits/misses, total
runtime, and cross-encoder success or fallback counts. Case-level `timing`
separates runtime initialization, document preparation, retrieval, reranking,
and matching. These diagnostics are not retrieval quality metrics.

## Retrieval Ablation

Run the fixed Phase 2 matrix from `ai-python`:

```text
python -m eval.run_ablation
```

The command executes each distinct production configuration in an isolated
subprocess and retains one raw report per profile plus `summary.json`. The
matrix covers lexical only, vector only, hybrid without RRF, hybrid with RRF,
the current fallback-capable profile, and the current profile under the stricter
requirement that CrossEncoder succeed for every executed case. The last two
profiles share one execution because their environment switches are identical;
only their acceptance rules differ.

`hybrid_no_rrf` reflects the existing production behavior: BM25 candidates are
followed by vector candidates. It is not a learned or score-normalized fusion.
If the vector-only control falls back to `keyword_regex`, its metrics and the
dependent hybrid/RRF comparisons are marked `unavailable`, rather than being
presented as vector-quality measurements. `current_fallback` remains a valid
record of the production fallback path, with the limitation recorded.

## Benchmark Validation

Validate document paths, hashes, page bounds, duplicate queries/evidence, and
gold-text location before running retrieval:

```text
python -m eval.validate_benchmark \
  --dataset eval/datasets/rag_eval_dev_v1.jsonl \
  --manifest eval/manifests/rag_eval_dev_v1_documents.json
```

The command fails with all discovered validation errors. It never silently
accepts a gold excerpt that cannot be located in its source document.

## Annotation Workflow

1. Add a source document under `eval/documents/public`, `eval/documents/synthetic`, or an approved external corpus path.
2. Add its `document_id`, relative path, source type, and SHA256 to a manifest.
3. Create a candidate JSONL case and manually check its query and evidence.
4. Set `metadata.annotation_status` to `reviewed` only after review; leave drafts as `draft`.
5. Run `validate_benchmark`, then retrieval evaluation, then inspect failed cases.

The recommended development path is 30-50 reviewed cases. The current dev
benchmark contains 40 reviewed cases across six documents and one draft case.
`baselines/rag_eval_dev_v1_candidate_lock.json` preserves the earlier 31-case
snapshot. `baselines/rag_eval_dev_v1_dos010_candidate_lock.json` freezes the
historical 39-case pre-adjudication snapshot. The current 40-case Option A
snapshot is frozen in
`baselines/rag_eval_dev_v1_dos010_option_a_candidate_lock.json`, including
hashed full and repeatability ranking projections. All remain baseline
candidates only and are not formal regression or CI gates.

On the current CPU-only Windows environment, a real CrossEncoder integration
smoke succeeds with the unchanged 3000 ms production timeout when the process
is started with `OMP_NUM_THREADS=8` and `MKL_NUM_THREADS=8`. This has been
verified for the two-candidate reviewed smoke case. Normal 10-candidate batches
remain slower than the timeout on this machine, so the full benchmark report is
still explicitly a timeout-fallback snapshot rather than an all-case reranked
baseline.

## Dependency Reproduction

From `ai-python`, use the same source as CI and release:

```text
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt -r requirements-dev.txt
```

The lock file is the runtime source of truth and pins `langchain-chroma==0.2.3`,
`chromadb==0.6.3`, `langchain-huggingface==1.2.2`,
`sentence-transformers==5.2.3`, and `transformers==5.5.0`. Docker installs the
same lock contents; `requirements.txt` is an unpinned convenience input only.

## Known Limitations

- Public documents require explicit provenance and manual visual/extraction review.
- The checked-in synthetic fixture is not a quality benchmark or legal corpus.
- PDF quality depends on the existing production parser; OCR is not added here.
- Text coverage is deterministic and interpretable but does not detect semantic paraphrases.
- The current vector pipeline may write an isolated `offline-eval` Chroma collection.
- Ablation results are development diagnostics, not a formal baseline or CI gate.
- Evidence Judge evaluation is not included.
