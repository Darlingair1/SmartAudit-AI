# Public test data

The repository does not add new real contract PDF fixtures. Contributors must provide their own synthetic documents when demonstrating PDF preview and audit workflows.

Three historical public-contract PDFs remain in earlier Git history but are removed from the current tree because no explicit redistribution permission was identified. Their provenance, SHA256, and benchmark metadata remain in `ai-python/eval/manifests/rag_eval_dev_v1_documents.json`; no history rewrite is performed. New External Holdout PDFs remain local-only and must not be added to Git, Git LFS, or a GitHub Release without explicit copyright, privacy, and redistribution approval.

- Locally supplied fixtures must be fictional and must not contain real personal, customer, or confidential information.
- Runtime uploads under `storage/` and `backend-java/storage/` are private local data and must never be committed.
- `ai-python/test.pdf` is not part of the public fixture set and is excluded from the repository until its origin and redistribution rights are verified.
- Locally supplied fixtures are not covered by this repository's Apache-2.0 license unless their owner explicitly grants compatible redistribution rights.
- Before each release, maintainers must confirm that no local PDF fixture has entered the Git or release file lists.
- A clean clone does not contain the historical PDFs. Retrieval benchmark reproduction requires the maintainer to supply the matching files locally and verify them against the manifest SHA256 values.

For new real External Holdout documents, the public repository may contain only data-minimized provenance: title, publisher, stable official landing page when available, source domain, document identifiers, file SHA256, normalized-text SHA256, page count, qualification status, and aggregate benchmark metadata. Capability-style query parameters, PDF bytes, extracted contract text, candidate text, claims, and reviewer notes remain local-only.

Any locally supplied fixture is for software testing only. It is not a real agreement, legal template, or legal advice.
