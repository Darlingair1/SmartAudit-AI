from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AblationProfile:
    name: str
    env_patch: Mapping[str, str]
    description: str
    require_cross_encoder_success: bool = False


PROFILES: tuple[AblationProfile, ...] = (
    AblationProfile("lexical_only", {"RAG_MODE": "keyword", "LEGAL_BM25_ENABLED": "true", "RRF_ENABLED": "false", "RERANK_ENABLED": "false"}, "Production lexical retrieval, without RRF or reranking."),
    AblationProfile("vector_only", {"RAG_MODE": "vector", "LEGAL_BM25_ENABLED": "false", "RRF_ENABLED": "false", "RERANK_ENABLED": "false"}, "Production vector retrieval, without lexical retrieval, RRF, or reranking."),
    AblationProfile("hybrid_no_rrf", {"RAG_MODE": "hybrid", "LEGAL_BM25_ENABLED": "true", "RRF_ENABLED": "false", "RERANK_ENABLED": "false"}, "Production hybrid retrieval without RRF; ordering is BM25 candidates followed by vector candidates."),
    AblationProfile("hybrid_rrf", {"RAG_MODE": "hybrid", "LEGAL_BM25_ENABLED": "true", "RRF_ENABLED": "true", "RERANK_ENABLED": "false"}, "Production hybrid retrieval with RRF and without reranking."),
    AblationProfile("current_fallback", {"RAG_MODE": "hybrid", "LEGAL_BM25_ENABLED": "true", "RRF_ENABLED": "true", "RERANK_ENABLED": "true"}, "Current production profile; CrossEncoder fallback is accepted and counted."),
    AblationProfile("hybrid_crossencoder", {"RAG_MODE": "hybrid", "LEGAL_BM25_ENABLED": "true", "RRF_ENABLED": "true", "RERANK_ENABLED": "true"}, "Current production profile requiring CrossEncoder success for every executed case.", True),
)

DEFAULT_DATASET = Path("eval/datasets/rag_eval_dev_v1.jsonl")
DEFAULT_MANIFEST = Path("eval/manifests/rag_eval_dev_v1_documents.json")
DEFAULT_TOP_K = "1,3,5,10"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_command(python_executable: str, dataset: Path, manifest: Path, output: Path, top_k: str = DEFAULT_TOP_K) -> list[str]:
    return [python_executable, "-m", "eval.runners.run_retrieval_eval", "--dataset", str(dataset), "--manifest", str(manifest), "--profile", "current", "--top-k", top_k, "--output", str(output)]


def build_profile_environment(base: Mapping[str, str], profile: AblationProfile) -> dict[str, str]:
    environment = dict(base)
    environment.update(profile.env_patch)
    return environment


def _case_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    names = ("hit_at_1", "recall_at_1", "hit_at_3", "recall_at_3", "hit_at_5", "recall_at_5", "hit_at_10", "recall_at_10")
    return {"status": case.get("status"), "first_relevant_rank": case.get("first_relevant_rank"), "mrr": case.get("mrr"), **{name: case.get(name) for name in names}}


def paired_case_deltas(report: Mapping[str, Any], baseline: Mapping[str, Any]) -> list[dict[str, Any]]:
    baseline_cases = {case["case_id"]: case for case in baseline.get("cases", [])}
    metric_names = ("mrr", "hit_at_1", "recall_at_1", "hit_at_3", "recall_at_3", "hit_at_5", "recall_at_5", "hit_at_10", "recall_at_10")
    deltas: list[dict[str, Any]] = []
    for case in report.get("cases", []):
        baseline_case = baseline_cases.get(case["case_id"])
        if baseline_case is None:
            continue
        metric_deltas: dict[str, float | None] = {}
        for metric in metric_names:
            current_value, baseline_value = case.get(metric), baseline_case.get(metric)
            metric_deltas[metric] = round(float(current_value) - float(baseline_value), 6) if isinstance(current_value, (int, float)) and isinstance(baseline_value, (int, float)) else None
        current_rank, baseline_rank = case.get("first_relevant_rank"), baseline_case.get("first_relevant_rank")
        deltas.append({
            "case_id": case["case_id"],
            "document_id": case.get("document_id"),
            "current": _case_projection(case),
            "baseline": _case_projection(baseline_case),
            "delta": {"first_relevant_rank": current_rank - baseline_rank if isinstance(current_rank, int) and isinstance(baseline_rank, int) else None, **metric_deltas},
        })
    return deltas


def summarize_report(profile: AblationProfile, report_path: Path, report: Mapping[str, Any], command: Sequence[str]) -> dict[str, Any]:
    execution, coverage = report.get("execution", {}), report.get("coverage", {})
    executed = int(coverage.get("retrieval_executed_count") or 0)
    successes = int(execution.get("cross_encoder_success_count") or 0)
    timeout_fallbacks = int(execution.get("cross_encoder_timeout_fallback_count") or 0)
    other_fallbacks = int(execution.get("cross_encoder_other_fallback_count") or 0)
    fallback_counts: dict[str, int] = {}
    for case in report.get("cases", []):
        fallback = str(case.get("timing", {}).get("retrieval_fallback_path") or "unknown")
        fallback_counts[fallback] = fallback_counts.get(fallback, 0) + 1
    status, reason = "success", None
    if profile.name == "vector_only" and fallback_counts.get("keyword_regex", 0):
        status = "unavailable"
        reason = (
            "Production vector indexing was unavailable; cases used the "
            "keyword_regex fallback, so these are not vector-retrieval metrics."
        )
    if profile.require_cross_encoder_success and (successes != executed or timeout_fallbacks or other_fallbacks):
        status = "unavailable"
        reason = "CrossEncoder did not succeed for every executed case under the fixed production timeout. The report is retained as diagnostic evidence."
    return {
        "profile": profile.name,
        "description": profile.description,
        "env_patch": dict(profile.env_patch),
        "command": list(command),
        "status": status,
        "reason": reason,
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "coverage": coverage,
        "metrics": report.get("metrics", {}),
        "execution": execution,
        "retrieval_fallback_counts": fallback_counts,
        "metadata": report.get("metadata", {}),
        "case_deltas_vs_current_fallback": [],
    }


def apply_matrix_validity(results: list[dict[str, Any]]) -> None:
    by_name = {result["profile"]: result for result in results}
    vector = by_name.get("vector_only")
    if vector is None or vector.get("status") != "unavailable":
        return
    limitation = (
        "The vector-only control was unavailable, so vector and RRF contribution "
        "cannot be isolated in this run."
    )
    for name in ("hybrid_no_rrf", "hybrid_rrf"):
        result = by_name.get(name)
        if result is not None and result.get("status") == "success":
            result["status"] = "unavailable"
            result["reason"] = limitation
    for name in ("current_fallback", "hybrid_crossencoder"):
        result = by_name.get(name)
        if result is not None:
            result.setdefault("limitations", []).append(limitation)


def run_profile(*, profile: AblationProfile, python_executable: str, dataset: Path, manifest: Path, output: Path, top_k: str, cwd: Path, base_environment: Mapping[str, str]) -> dict[str, Any]:
    command = build_command(python_executable, dataset, manifest, output, top_k=top_k)
    completed = subprocess.run(command, cwd=cwd, env=build_profile_environment(base_environment, profile), capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not output.is_file():
        return {"profile": profile.name, "description": profile.description, "env_patch": dict(profile.env_patch), "command": command, "status": "failed", "reason": f"evaluation subprocess exited with code {completed.returncode}", "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:], "report_path": str(output), "case_deltas_vs_current_fallback": []}
    try:
        report = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"profile": profile.name, "description": profile.description, "env_patch": dict(profile.env_patch), "command": command, "status": "failed", "reason": f"invalid evaluation report: {error}", "report_path": str(output), "case_deltas_vs_current_fallback": []}
    return summarize_report(profile, output, report, command)


def _profile_map() -> dict[str, AblationProfile]:
    return {profile.name: profile for profile in PROFILES}


def _parse_profiles(value: str) -> list[AblationProfile]:
    names = [item.strip() for item in value.split(",") if item.strip()]
    available = _profile_map()
    unknown = [name for name in names if name not in available]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown profiles: {', '.join(unknown)}; available: {', '.join(available)}")
    if not names:
        raise argparse.ArgumentTypeError("at least one profile is required")
    return [available[name] for name in names]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run the fixed retrieval ablation matrix in isolated subprocesses")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--top-k", default=DEFAULT_TOP_K)
    parser.add_argument("--profiles", type=_parse_profiles, default=list(PROFILES), help="comma-separated profile names (default: full fixed matrix)")
    parser.add_argument("--reports-dir", type=Path, default=Path("eval/reports"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dataset = (root / args.dataset).resolve() if not args.dataset.is_absolute() else args.dataset
    manifest = (root / args.manifest).resolve() if not args.manifest.is_absolute() else args.manifest
    reports_dir = (root / args.reports_dir).resolve() if not args.reports_dir.is_absolute() else args.reports_dir
    if not dataset.is_file():
        parser.error(f"dataset not found: {dataset}")
    if not manifest.is_file():
        parser.error(f"manifest not found: {manifest}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = reports_dir / f"ablation_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    profile_results: list[dict[str, Any]] = []
    loaded_reports: dict[str, dict[str, Any]] = {}
    for profile in args.profiles:
        report_path = run_dir / f"{profile.name}.json"
        equivalent_source = next(
            (
                previous
                for previous in args.profiles
                if previous.name in loaded_reports
                and previous.env_patch == profile.env_patch
            ),
            None,
        )
        if equivalent_source is not None:
            source_result = next(
                item
                for item in profile_results
                if item["profile"] == equivalent_source.name
            )
            source_path = Path(source_result["report_path"])
            shutil.copyfile(source_path, report_path)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            command = build_command(
                sys.executable, dataset, manifest, report_path, top_k=args.top_k
            )
            result = summarize_report(profile, report_path, report, command)
            result["execution_reused_from"] = equivalent_source.name
        else:
            result = run_profile(profile=profile, python_executable=sys.executable, dataset=dataset, manifest=manifest, output=report_path, top_k=args.top_k, cwd=root, base_environment=os.environ)
        profile_results.append(result)
        if report_path.is_file():
            try:
                loaded_reports[profile.name] = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

    baseline = loaded_reports.get("current_fallback")
    if baseline is not None:
        for result in profile_results:
            report = loaded_reports.get(result["profile"])
            if report is not None:
                result["case_deltas_vs_current_fallback"] = paired_case_deltas(report, baseline)

    apply_matrix_validity(profile_results)

    summary = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "dataset": str(dataset),
            "dataset_sha256": sha256_file(dataset),
            "manifest": str(manifest),
            "manifest_sha256": sha256_file(manifest),
            "top_k": args.top_k,
            "baseline_profile": "current_fallback",
            "runner_profile": "current",
            "production_code_modified": False,
        },
        "matrix": profile_results,
    }
    summary_path = args.output or run_dir / "summary.json"
    if not summary_path.is_absolute():
        summary_path = (root / summary_path).resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(summary_path))


if __name__ == "__main__":
    main()
