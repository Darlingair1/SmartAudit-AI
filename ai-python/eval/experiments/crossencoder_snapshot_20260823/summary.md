# Frozen Candidate Snapshot

The 40 reviewed-case `hybrid_rrf` candidates were exported from the diagnostic report without rerunning retrieval. Snapshot hash: `2b627d8d5a89e75e5bd1e0d83c37e981bcf78afb5454095c866f94b8275f61a1`.

The snapshot records query, document, ordered candidates, rank, text preview, page metadata, lexical/vector/RRF diagnostics, and matched gold indexes. Its provenance records source commit, dataset hash, settings fingerprint, profile, and schema version.

Three no-op snapshot replays produced the same 40/40 candidate order and fingerprint `37dc3b56bd6244482c807aa90334a59d0e15cf77925ee70083f0dbcae8b2cf84`.

Strict reranker replay did not execute retrieval. With the local model available, two small cases succeeded; the next CrossEncoder request timed out at 3 seconds and the circuit returned `circuit_open_after_timeout` for the remaining 37 cases. Heuristic fallbacks were zero. The replay fingerprint stayed equal to the snapshot because the two successful calls did not change candidate order. Failed/circuit-open rankings are not CrossEncoder quality metrics.

After the first CrossEncoder timeout, the process circuit opens with reason `circuit_open_after_timeout`; later calls return the original RRF candidate order immediately. The in-flight Python worker is not force-killed and may continue, which is the deliberate limitation of this simple fail-fast design.
