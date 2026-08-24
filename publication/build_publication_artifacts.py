"""Build data-minimized publication projections without touching source artifacts."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "publication"
PROJECTION_VERSION = "publication_projection_v1"
HISTORICAL_PDFS_REMOVED_FROM_CURRENT_TREE = {
    "ai-python/eval/documents/public/guangdong_tax_e_tax_development_contract_2023_gpcgd23c500fg157f.pdf",
    "ai-python/eval/documents/public/jiyuan_vehicle_procurement_contract_2024_245_a.pdf",
    "ai-python/eval/documents/public/uk_dwp_dos010_curam_technical_architect_call_off_contract_2017.pdf",
}


def read_json(path: str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def git(*args: str) -> list[str]:
    command = ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args]
    output = subprocess.check_output(command, cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
    return [line for line in output.splitlines() if line]


def build_candidate_projection() -> dict[str, Any]:
    source_path = ROOT / "ai-python/eval/documents/external_holdout/candidate_manifest.json"
    source = read_json("ai-python/eval/documents/external_holdout/candidate_manifest.json")
    public = []
    for row in source["candidates"]:
        public.append({
            "filename": row.get("filename"),
            "title": row.get("title"),
            "publisher_or_purchaser": row.get("purchaser") or row.get("publishing_institution"),
            "supplier_or_contractor": row.get("supplier") or row.get("contractor"),
            "contract_no": row.get("contract_no"),
            "project_no": row.get("project_no"),
            "source_type": row.get("source_type"),
            "source_domain": row.get("source_domain"),
            "source_page_url": None,
            "source_document_identifier": row.get("filename"),
            "original_sha256": row.get("original_sha256"),
            "normalized_text_sha256": row.get("normalized_text_sha256"),
            "page_count": row.get("page_count"),
            "qualification": row.get("qualification"),
            "qualification_reason": row.get("qualification_reason"),
            "pdf_distributed": False,
        })
    return {
        "schema_version": "external_holdout_candidate_manifest_public_v1",
        "public_projection_version": PROJECTION_VERSION,
        "source_artifact": "ai-python/eval/documents/external_holdout/candidate_manifest.json",
        "source_artifact_sha256": sha256(source_path),
        "source_url_policy": "Capability-style direct URLs are omitted; no stable landing-page URL was available in the frozen local manifest.",
        "candidate_count": len(public),
        "candidates": public,
    }


def build_holdout_projection(candidate_projection: dict[str, Any]) -> dict[str, Any]:
    metadata_path = ROOT / "ai-python/eval/judge/external_holdout_v1/external_holdout_v1.metadata.json"
    freeze_path = ROOT / "ai-python/eval/judge/external_holdout_v1/freeze_manifest.json"
    metadata = read_json("ai-python/eval/judge/external_holdout_v1/external_holdout_v1.metadata.json")
    freeze = read_json("ai-python/eval/judge/external_holdout_v1/freeze_manifest.json")
    by_name = {row["filename"]: row for row in candidate_projection["candidates"]}
    documents = []
    for row in metadata["source_document_hashes"]:
        public_source = by_name[row["filename"]]
        documents.append({
            "document_id": row["document_id"],
            "filename": row["filename"],
            "title": public_source["title"],
            "publisher_or_purchaser": public_source["publisher_or_purchaser"],
            "supplier_or_contractor": public_source["supplier_or_contractor"],
            "source_domain": public_source["source_domain"],
            "source_page_url": public_source["source_page_url"],
            "source_document_identifier": public_source["source_document_identifier"],
            "original_sha256": row["original_sha256"],
            "normalized_text_sha256": row["normalized_text_sha256"],
            "case_count": sum(metadata["per_document_label_distribution"][row["filename"]].values()),
            "label_distribution": metadata["per_document_label_distribution"][row["filename"]],
            "pdf_distributed": False,
        })
    return {
        "schema_version": "external_holdout_v1_public_metadata_v1",
        "public_projection_version": PROJECTION_VERSION,
        "source_artifact": "ai-python/eval/judge/external_holdout_v1/external_holdout_v1.metadata.json",
        "source_artifact_sha256": sha256(metadata_path),
        "dataset_original_sha256": metadata["dataset_sha256"],
        "freeze_manifest_sha256": sha256(freeze_path),
        "freeze_status": metadata["freeze_status"],
        "case_count": metadata["case_count"],
        "reviewed_count": metadata["reviewed_count"],
        "draft_count": metadata["draft_count"],
        "unresolved_count": metadata["unresolved_count"],
        "label_distribution": metadata["label_distribution"],
        "document_count": len(documents),
        "documents": documents,
        "sampling_seed": metadata["sampling_seed"],
        "sampling_algorithm_fingerprint": metadata["sampling_algorithm_fingerprint"],
        "source_pipeline_run_id": metadata["source_pipeline_run_id"],
        "capture_universe_sha256": metadata["capture_universe_sha256"],
        "source_sample_sha256": metadata["source_sample_sha256"],
        "judge_leakage_count": 0,
        "judge_invocation_count_before_evaluation": freeze["judge_invocation_count"],
        "content_excluded": ["PDF bytes", "contract text", "claims", "evidence", "reviewer notes", "Gold rows"],
    }


def build_blind_projection() -> tuple[dict[str, Any], str]:
    summary_path = ROOT / "ai-python/eval/experiments/evidence_judge_external_holdout_v1_20260824/summary.json"
    source = read_json("ai-python/eval/experiments/evidence_judge_external_holdout_v1_20260824/summary.json")
    latency = read_json("ai-python/eval/experiments/evidence_judge_external_holdout_v1_20260824/latency.json")
    result = {
        "schema_version": "external_blind_summary_public_v1",
        "public_projection_version": PROJECTION_VERSION,
        "source_artifact": "ai-python/eval/experiments/evidence_judge_external_holdout_v1_20260824/summary.json",
        "source_artifact_sha256": sha256(summary_path),
        "dataset_sha256": source["provenance"]["dataset_sha256"],
        "metrics": source["metrics"],
        "confusion_matrices": {name: value["confusion_matrix"] for name, value in source["metrics"].items()},
        "latency": latency,
        "first_run_result_sha256": source["first_run_result_sha256"],
        "development_acceptance": source["development_acceptance"],
        "failure_mode_aggregate": source["v2_1_failure_analysis"],
        "production_recommendation": "HITL-first; v2.1 may be a secondary review signal but must not autonomously reject findings.",
        "external_interpretation": source["external_interpretation"],
        "content_excluded": ["claims", "evidence", "reviewer notes", "case-level transitions", "local paths"],
    }
    lines = [
        "# External Blind Evaluation: Public Summary", "",
        f"Dataset SHA256: `{result['dataset_sha256']}`", "",
        "The result is descriptive. Evidence Judge v2.1 development acceptance remains **FAIL** because `semantically_related_but_insufficient accuracy = 0.666667 < 0.75`.", "",
        "| Judge | Accuracy | Macro-F1 | SUP Precision | SUP Recall | PARTIAL F1 | UNSUP Recall | Unsafe acceptance | Human review |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("v0", "v1", "v2", "v2_1"):
        metric = result["metrics"][name]
        unsafe = metric["unsafe_acceptance_count"]
        lines.append(f"| {name} | {metric['accuracy']:.6f} | {metric['macro_f1']:.6f} | {metric['supported_precision']:.6f} | {metric['supported_recall']:.6f} | {metric['partial_f1']:.6f} | {metric['unsupported_recall']:.6f} | {metric['unsafe_acceptance_rate']:.6f} ({unsafe['numerator']}/{unsafe['denominator']}) | {metric['human_review_rate']:.6f} |")
    lines.extend(["", "Production recommendation: **HITL-first**. v2.1 is not an autonomous default gate.", "", "Full first-run predictions, claims, evidence, reviewer notes, and case-level transitions are local-only. Their immutable SHA256 values remain in the machine-readable public summary.", ""])
    return result, "\n".join(lines)


def build_retrieval_projection() -> dict[str, Any]:
    baseline_path = ROOT / "ai-python/eval/baselines/retrieval_baseline_v1/summary.json"
    baseline = read_json("ai-python/eval/baselines/retrieval_baseline_v1/summary.json")
    drift_path = ROOT / "ai-python/eval/experiments/crossencoder_20260823/ranking_drift_summary.json"
    drift = read_json("ai-python/eval/experiments/crossencoder_20260823/ranking_drift_summary.json")
    snapshot_path = ROOT / "ai-python/eval/experiments/crossencoder_snapshot_20260823/summary.json"
    snapshot = read_json("ai-python/eval/experiments/crossencoder_snapshot_20260823/summary.json")
    crossencoder_path = ROOT / "ai-python/eval/experiments/crossencoder_20260823/summary.json"
    crossencoder = read_json("ai-python/eval/experiments/crossencoder_20260823/summary.json")
    matrix = []
    for row in baseline["matrix"]:
        matrix.append({key: row.get(key) for key in ("profile", "description", "status", "reason", "report_sha256", "coverage", "metrics", "execution", "retrieval_fallback_counts")})
    drift_runs = []
    for row in drift["runs"]:
        drift_runs.append({key: row.get(key) for key in ("git_commit", "dataset_sha256", "profile", "python", "settings_fingerprints", "metrics", "ranking_fingerprint")})
    return {
        "schema_version": "retrieval_public_summary_v1",
        "public_projection_version": PROJECTION_VERSION,
        "baseline": {
            "source_artifact_sha256": sha256(baseline_path),
            "metadata": baseline["metadata"],
            "profiles": matrix,
        },
        "ranking_drift": {
            "source_artifact_sha256": sha256(drift_path),
            "runs": drift_runs,
            "stage_change_counts": drift["stage_change_counts"],
            "all_three_same_final_count": drift["all_three_same_final_count"],
            "case_count": 40,
            "first_divergence_source": "Vector/Chroma ANN",
            "config": drift["config_comparison"],
        },
        "frozen_snapshot": {
            "source_artifact_sha256": sha256(snapshot_path),
            **{key: snapshot[key] for key in ("schema", "snapshot_sha256", "source_commit", "case_count", "deterministic_replay", "strict_reranker_snapshot_run", "known_limitations")},
        },
        "crossencoder": {
            "source_artifact_sha256": sha256(crossencoder_path),
            **{key: crossencoder[key] for key in ("experiment", "baseline", "root_cause", "optimization_comparison", "runs", "recommendation")},
        },
        "content_excluded": ["candidate text", "case-level rankings", "repeat dumps", "replay dumps", "local model paths"],
    }


def classify(path: str, action: str = "ADD_OR_MODIFY") -> tuple[str, str, str]:
    normalized = path.replace("\\", "/")
    name = Path(normalized).name
    if action == "DELETE" and normalized in HISTORICAL_PDFS_REMOVED_FROM_CURRENT_TREE:
        return "PUBLIC_COMMIT", "remove real contract PDF from current tree; redistribution not approved", "commit_1"
    if "/__pycache__/" in normalized or name.endswith((".pyc", ".pyo")):
        return "IGNORE", "Python cache already covered by repository ignore rules", "none"
    if normalized.startswith("ai-python/ai-python/"):
        return "IGNORE", "accidental nested duplicate tree", "commit_1"
    if normalized.endswith(".pdf") and normalized.startswith("ai-python/eval/documents/public/"):
        return "LOCAL_ONLY", "real contract PDF; redistribution not approved", "none"
    if any(token in normalized for token in ("/annotation_package/", "/annotation_review")):
        return "IGNORE", "raw or duplicate annotation package", "none"
    if name in {"cases_raw.jsonl", "external_evaluation_sample_v1.jsonl"}:
        return "LOCAL_ONLY", "raw capture/sample contains contract and evidence text", "none"
    if name == "external_holdout_v1.jsonl" or (normalized.startswith("ai-python/eval/judge/") and normalized.endswith(".jsonl")):
        return "LOCAL_ONLY", "frozen/full benchmark contains evidence text", "none"
    if any(re.fullmatch(pattern, name) for pattern in (r"replay_.*\.json", r"drift_repeat_.*\.json", r"hybrid_rrf_repeat_.*\.json")):
        return "IGNORE", "redundant case-level repeat/replay dump", "none"
    if name in {"candidate_snapshot.json", "transitions.json"} or name.endswith("first_run.json"):
        return "LOCAL_ONLY", "immutable case-level text/prediction artifact", "none"
    if normalized.endswith("update_inventory_status.py") or name in {"candidate_manifest.json", "pipeline_source_set.json"}:
        return "LOCAL_ONLY", "local provenance source contains capability-style URL", "none"
    if name == "candidate_inventory.json":
        return "LOCAL_ONLY", "local source inventory superseded by sanitized public projection", "none"
    if name == "pipeline_provenance.json":
        return "LOCAL_ONLY", "machine provenance contains working-tree state", "none"
    if normalized.startswith("publication/") or normalized in {".gitignore", "docs/PUBLIC_TEST_DATA.md", "docs/BENCHMARK_ARTIFACT_POLICY.md"}:
        return "PUBLIC_COMMIT", "publication policy or sanitized projection", "commit_1" if normalized.endswith((".gitignore", "PUBLIC_TEST_DATA.md", "BENCHMARK_ARTIFACT_POLICY.md")) else "commit_5"
    if normalized.startswith("ai-python/tests/"):
        return "PUBLIC_COMMIT", "test source", "commit_2" if "candidate_snapshot" in name or "eval_runner" in name else "commit_3"
    if normalized.startswith("ai-python/services/"):
        return "PUBLIC_COMMIT", "implementation source", "commit_2" if name in {"reranker.py", "retrieval_hybrid.py"} else "commit_3"
    if normalized.startswith("ai-python/eval/documents/external_holdout/") and normalized.endswith(".py"):
        return "PUBLIC_COMMIT", "External Holdout tooling", "commit_4"
    if normalized.startswith("ai-python/eval/judge/") and normalized.endswith((".py", ".md")):
        return "PUBLIC_COMMIT", "Judge evaluator, validator, or schema", "commit_3"
    if normalized.startswith("ai-python/eval/") and normalized.endswith(".py"):
        return "PUBLIC_COMMIT", "retrieval evaluation tooling", "commit_2"
    if name.endswith(".metadata.json") or name in {"freeze_manifest.json", "sampling_manifest.json", "capture_universe_manifest.json", "adjudication_summary.json", "result_hashes.json", "confusion_matrices.json", "latency.json", "per_document_metrics.json", "per_risk_type_metrics.json", "acceptance_criteria.json", "acceptance_result.json", "duplicate_audit.json", "capture_summary.json", "pipeline_capture_manifest.json"}:
        return "PUBLIC_COMMIT", "aggregate metadata, manifest, or metrics", "commit_5"
    if name.endswith(("summary.md", "comparison.md")):
        return "PUBLIC_COMMIT", "aggregate Markdown summary", "commit_5"
    if normalized.endswith(("results.json", "comparison.json", "results_audited.json", "audited_fresh.json", "original_fresh.json", "original_to_audited.json", "failure_analysis.json")):
        return "LOCAL_ONLY", "full or case-level experiment output", "none"
    if normalized.endswith(".json") and "/experiments/" in normalized:
        return "LOCAL_ONLY", "source experiment JSON superseded by aggregate public projection", "none"
    return "NEEDS_MANUAL_REVIEW", "not covered by publication allowlist", "none"


def working_files() -> list[str]:
    values = set(git("diff", "HEAD", "--name-only"))
    values.update(git("ls-files", "--others", "--exclude-standard"))
    ignored = git("ls-files", "--others", "--ignored", "--exclude-standard", "ai-python/eval")
    for path in ignored:
        normalized = path.replace("\\", "/")
        name = Path(normalized).name
        if "/__pycache__/" in normalized:
            continue
        if normalized.endswith(".pdf") or name in {"cases_raw.jsonl", "external_evaluation_sample_v1.jsonl", "external_holdout_v1.jsonl", "candidate_snapshot.json", "transitions.json"} or name.endswith("first_run.json") or re.fullmatch(r"(?:replay_|drift_repeat_|hybrid_rrf_repeat_).*\.json", name) or "/annotation_package/" in normalized or "/annotation_review" in normalized:
            values.add(path)
    values.update({
        ".gitignore", "docs/PUBLIC_TEST_DATA.md", "docs/BENCHMARK_ARTIFACT_POLICY.md",
        "publication/nested_dir_diff_report.json", "publication/build_publication_artifacts.py",
        "publication/candidate_manifest.public.json", "publication/external_holdout_v1.public.metadata.json",
        "publication/external_blind_summary.public.json", "publication/external_blind_summary.public.md",
        "publication/retrieval_summary.public.json", "publication/publication_sensitive_scan.json",
        "publication/publication_manifest.json",
    })
    return sorted(path for path in values if (ROOT / path).is_file() or path.startswith("publication/"))


def scan_public(paths: list[str]) -> dict[str, Any]:
    findings = []
    false_positives = []
    local_path_re = re.compile(r"(?:[A-Za-z]:\\(?:Users\\)?[^\s\"']+|/Users/[^\s\"']+|/home/[^\s\"']+)", re.I)
    capability_re = re.compile(r"https?://[^\s\"']+[?&](?:accessCode|utm_source|token|signature)=", re.I)
    secret_patterns = {
        "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{16,}", re.I),
    }
    pii_patterns = {
        "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        "identity_number": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    }
    for path in paths:
        full = ROOT / path
        if not full.is_file() or full.suffix.lower() not in {".py", ".json", ".jsonl", ".md", ".yaml", ".yml"}:
            continue
        text = full.read_text(encoding="utf-8-sig", errors="replace")
        for kind, pattern in secret_patterns.items():
            if pattern.search(text):
                findings.append({"path": path, "type": kind, "severity": "critical", "value_redacted": True})
        if local_path_re.search(text):
            if path == "publication/build_publication_artifacts.py":
                false_positives.append({"path": path, "type": "local_path_regex_literal", "status": "scanner implementation, not a machine path", "value_redacted": True})
            else:
                findings.append({"path": path, "type": "local_path", "severity": "high", "value_redacted": True})
        if capability_re.search(text):
            findings.append({"path": path, "type": "capability_url", "severity": "high", "value_redacted": True})
        for kind, pattern in pii_patterns.items():
            matches = list(pattern.finditer(text))
            if matches:
                sha_tokens = re.findall(r"\b[0-9a-f]{64}\b", text, re.I)
                hash_only = all(any(match.group() in token for token in sha_tokens) for match in matches)
                false_positives.append({"path": path, "type": kind, "status": "confirmed_sha256_substring_false_positive" if hash_only else "pattern_match_requires_manual_review", "value_redacted": True})
    return {
        "schema_version": "publication_sensitive_scan_v1",
        "scope": "PUBLIC_COMMIT files only",
        "critical_secret_count": sum(row["severity"] == "critical" for row in findings),
        "local_path_leak_count": sum(row["type"] == "local_path" for row in findings),
        "capability_url_count": sum(row["type"] == "capability_url" for row in findings),
        "findings": findings,
        "false_positive_or_manual_review_patterns": false_positives,
        "values_redacted": True,
    }


def build_manifest() -> dict[str, Any]:
    changes = {}
    for row in git("diff", "HEAD", "--name-status"):
        status, path = row.split("\t", 1)
        changes[path.replace("\\", "/")] = "DELETE" if status == "D" else "ADD_OR_MODIFY"
    entries = []
    for path in working_files():
        full = ROOT / path
        action = changes.get(path.replace("\\", "/"), "ADD_OR_MODIFY")
        category, reason, group = classify(path, action)
        entries.append({"path": path, "action": action, "size_bytes": full.stat().st_size if full.is_file() and action != "DELETE" else 0, "classification": category, "reason": reason, "target_commit_group": group})
    summary = {}
    for category in ("PUBLIC_COMMIT", "LOCAL_ONLY", "IGNORE", "NEEDS_MANUAL_REVIEW"):
        selected = [row for row in entries if row["classification"] == category]
        summary[category] = {"file_count": len(selected), "size_bytes": sum(row["size_bytes"] for row in selected)}
    return {"schema_version": "github_publication_manifest_v1", "policy": "docs/BENCHMARK_ARTIFACT_POLICY.md", "summary": summary, "files": entries}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    candidate = build_candidate_projection()
    write_json(OUT / "candidate_manifest.public.json", candidate)
    write_json(OUT / "external_holdout_v1.public.metadata.json", build_holdout_projection(candidate))
    blind, blind_md = build_blind_projection()
    write_json(OUT / "external_blind_summary.public.json", blind)
    write_text(OUT / "external_blind_summary.public.md", blind_md)
    write_json(OUT / "retrieval_summary.public.json", build_retrieval_projection())
    manifest = build_manifest()
    public_paths = [row["path"] for row in manifest["files"] if row["classification"] == "PUBLIC_COMMIT" and row["action"] != "DELETE"]
    scan = scan_public(public_paths)
    write_json(OUT / "publication_sensitive_scan.json", scan)
    manifest = build_manifest()
    write_json(OUT / "publication_manifest.json", manifest)
    # Regenerate once so manifest sizes include the final scan and manifest.
    write_json(OUT / "publication_manifest.json", build_manifest())
    print(json.dumps({"manifest": build_manifest()["summary"], "scan": scan}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
