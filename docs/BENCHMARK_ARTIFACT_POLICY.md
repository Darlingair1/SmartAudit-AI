# Benchmark Artifact Publication Policy

This policy separates reproducible public metadata from contract content and machine-local experiment state. It applies to retrieval, Evidence Judge, and External Holdout artifacts.

## PUBLIC

The following may enter Git after the publication scan passes:

- evaluator, validator, runner, and diagnostic source code;
- schemas and tests;
- aggregate Markdown summaries and aggregate machine-readable metrics;
- confusion matrices and latency statistics;
- hashes, provenance metadata, freeze manifests, and sampling manifests;
- public projections containing no contract text, claims, reviewer notes, capability URLs, credentials, or local paths;
- reproducibility metadata using repository-relative paths.

Public projections must identify their source artifact by SHA256 and declare a projection version. A projection does not replace or mutate its source artifact.

## LOCAL_ONLY

The following must not enter Git by default:

- real contract PDFs and OCR derivatives;
- raw pipeline capture and annotation review packages;
- complete evidence or candidate text;
- claims, Gold rows, adjudicator/reviewer notes, and full frozen JSONL datasets containing contract text;
- full candidate snapshots and case-level replay/ranking dumps;
- full first-run prediction artifacts and case-level transitions;
- duplicate experiment outputs, local model paths, machine paths, and capability-style source URLs.

Local-only artifacts retain their original hashes. Do not sanitize them in place when doing so would invalidate frozen provenance.

## OPTIONAL_RELEASE

Large datasets, snapshots, raw predictions, or source documents may be published only as a separate artifact after an explicit copyright, privacy, redistribution, and sensitive-content review. Approval must identify the exact hashes and distribution channel. Optional artifacts are never uploaded automatically and are not implicitly licensed under the repository license.

## External Holdout

External Holdout public metadata is data-minimized. It may include title, publisher, stable official landing page, source domain, document identifier, original SHA256, normalized-text SHA256, page count, sampling metadata, label distribution, aggregate metrics, immutable result hashes, and freeze status. It must not include PDF bytes, extracted text, claims, evidence, reviewer notes, or access tokens/query parameters.

The six External Holdout source PDFs collected in August 2026 are local-only. Three older PDFs remain in earlier Git history, but are removed from the current tree because explicit redistribution permission was not identified. Their hashes and provenance metadata remain public; publication hardening does not rewrite history.

## Release Gate

Before staging benchmark changes:

1. Generate the publication manifest and sensitive scan.
2. Require zero critical secrets, local-path leaks, and capability URLs in `PUBLIC_COMMIT` files.
3. Verify frozen dataset, Judge implementation, baseline, and first-run hashes.
4. Use explicit path-based `git add` commands. Never use `git add .` for benchmark publication.
5. Keep source artifacts and public projections in separate commit groups.
