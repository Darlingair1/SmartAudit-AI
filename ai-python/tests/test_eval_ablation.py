import json
from pathlib import Path

from eval.run_ablation import (
    PROFILES,
    AblationProfile,
    apply_matrix_validity,
    build_command,
    build_profile_environment,
    paired_case_deltas,
    run_profile,
    normalize_paths,
    render_baseline_markdown,
    repo_relative_path,
    sha256_file,
    summarize_report,
)


def _profile(name: str) -> AblationProfile:
    return next(profile for profile in PROFILES if profile.name == name)


def _report(case_id: str = "case-1", mrr: float = 1.0) -> dict:
    return {
        "metadata": {"case_count": 1},
        "coverage": {"total_case_count": 1, "retrieval_executed_count": 1, "retrieval_success_count": 1, "evaluation_coverage": 1.0},
        "metrics": {"mrr": mrr, "hit_at_1": mrr == 1.0},
        "execution": {"cross_encoder_success_count": 0, "cross_encoder_timeout_fallback_count": 0, "cross_encoder_other_fallback_count": 0},
        "cases": [{"case_id": case_id, "document_id": "doc-1", "status": "success", "first_relevant_rank": 1 if mrr == 1.0 else 2, "mrr": mrr, "hit_at_1": mrr == 1.0, "recall_at_1": 1.0 if mrr == 1.0 else 0.0}],
    }


def test_fixed_profile_matrix_has_expected_switches() -> None:
    assert [profile.name for profile in PROFILES] == ["lexical_only", "vector_only", "hybrid_no_rrf", "hybrid_rrf", "current_fallback", "hybrid_crossencoder", "hybrid_rrf_crossencoder_strict"]
    assert _profile("lexical_only").env_patch["RAG_MODE"] == "keyword"
    assert _profile("vector_only").env_patch["LEGAL_BM25_ENABLED"] == "false"
    assert _profile("hybrid_no_rrf").env_patch["RRF_ENABLED"] == "false"
    assert _profile("hybrid_rrf").env_patch["RERANK_ENABLED"] == "false"
    assert _profile("hybrid_crossencoder").require_cross_encoder_success is True
    assert _profile("hybrid_rrf_crossencoder_strict").env_patch["RERANK_STRICT"] == "true"


def test_build_command_uses_current_runner_and_fixed_inputs(tmp_path: Path) -> None:
    command = build_command("python", tmp_path / "data.jsonl", tmp_path / "manifest.json", tmp_path / "out.json")
    assert command[:3] == ["python", "-m", "eval.runners.run_retrieval_eval"]
    assert command[command.index("--profile") + 1] == "current"
    assert command[command.index("--top-k") + 1] == "1,3,5,10"


def test_profile_environment_is_isolated_from_base() -> None:
    base = {"RAG_MODE": "old", "UNCHANGED": "yes"}
    environment = build_profile_environment(base, _profile("vector_only"))
    assert base == {"RAG_MODE": "old", "UNCHANGED": "yes"}
    assert environment["RAG_MODE"] == "vector"
    assert environment["UNCHANGED"] == "yes"


def test_sha256_file_is_content_hash(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"same")
    second.write_bytes(b"same")
    assert sha256_file(first) == sha256_file(second)


def test_repo_relative_paths_never_emit_local_absolute_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    inside = repo_root / "ai-python" / "eval" / "report.json"
    assert repo_relative_path(str(inside), repo_root) == "ai-python/eval/report.json"
    assert repo_relative_path(str(tmp_path / "outside"), repo_root) == "<external-path>"
    normalized = normalize_paths(
        {
            "report_path": str(inside),
            "command": ["python", "--output", str(inside)],
            "text_preview": "G://contract text that is not a local path",
        },
        repo_root,
    )
    assert normalized == {
        "report_path": "ai-python/eval/report.json",
        "command": ["python", "--output", "ai-python/eval/report.json"],
        "text_preview": "G://contract text that is not a local path",
    }


def test_baseline_markdown_contains_provenance_and_fallback_warning() -> None:
    summary = {
        "metadata": {
            "git_commit": "abc123",
            "dataset": "ai-python/eval/datasets/data.jsonl",
            "dataset_sha256": "dataset-hash",
            "manifest": "ai-python/eval/manifests/manifest.json",
            "manifest_sha256": "manifest-hash",
            "environment": {"python_version": "3.11.5", "pypdf_version": "6.14.2"},
            "reviewed_case_count": 40,
        },
        "matrix": [{
            "profile": "current_fallback",
            "status": "success",
            "metrics": {"hit_at_1": 1.0, "recall_at_5": 1.0, "recall_at_10": 1.0, "mrr": 1.0, "latency": {"mean_ms": 1}},
            "execution": {"cross_encoder_success_count": 0, "cross_encoder_timeout_fallback_count": 1, "cross_encoder_other_fallback_count": 0},
        }],
    }
    markdown = render_baseline_markdown(summary)
    assert "abc123" in markdown
    assert "timeout fallback 1" in markdown
    assert "must not be attributed" in markdown


def test_paired_case_deltas_are_calculated_by_case_id() -> None:
    delta = paired_case_deltas(_report(mrr=1.0), _report(mrr=0.5))[0]
    assert delta["case_id"] == "case-1"
    assert delta["delta"]["mrr"] == 0.5
    assert delta["delta"]["first_relevant_rank"] == -1
    assert delta["delta"]["hit_at_1"] == 1.0


def test_paired_case_deltas_skip_cases_missing_from_baseline() -> None:
    assert paired_case_deltas(_report("new"), _report("old")) == []


def test_crossencoder_profile_preserves_fallback_as_unavailable(tmp_path: Path) -> None:
    report = _report()
    report["execution"]["cross_encoder_timeout_fallback_count"] = 1
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    summary = summarize_report(_profile("hybrid_crossencoder"), path, report, ["python", "runner"])
    assert summary["status"] == "unavailable"
    assert summary["execution"]["cross_encoder_timeout_fallback_count"] == 1


def test_vector_keyword_fallback_is_not_reported_as_vector_success(tmp_path: Path) -> None:
    report = _report()
    report["cases"][0]["timing"] = {"retrieval_fallback_path": "keyword_regex"}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    summary = summarize_report(_profile("vector_only"), path, report, [])
    assert summary["status"] == "unavailable"
    assert summary["retrieval_fallback_counts"] == {"keyword_regex": 1}


def test_unavailable_vector_invalidates_hybrid_comparisons() -> None:
    results = [
        {"profile": "vector_only", "status": "unavailable"},
        {"profile": "hybrid_no_rrf", "status": "success"},
        {"profile": "hybrid_rrf", "status": "success"},
        {"profile": "current_fallback", "status": "success"},
    ]
    apply_matrix_validity(results)
    assert results[1]["status"] == "unavailable"
    assert results[2]["status"] == "unavailable"
    assert results[3]["status"] == "success"
    assert results[3]["limitations"]


def test_crossencoder_profile_requires_success_for_every_executed_case(tmp_path: Path) -> None:
    report = _report()
    report["execution"]["cross_encoder_success_count"] = 1
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert summarize_report(_profile("hybrid_crossencoder"), path, report, [])["status"] == "success"


def test_current_and_crossencoder_profiles_have_same_execution_environment() -> None:
    assert _profile("current_fallback").env_patch == _profile(
        "hybrid_crossencoder"
    ).env_patch
    assert _profile("current_fallback").require_cross_encoder_success is False
    assert _profile("hybrid_crossencoder").require_cross_encoder_success is True


def test_run_profile_records_subprocess_failure(monkeypatch, tmp_path: Path) -> None:
    class Completed:
        returncode, stdout, stderr = 7, "output", "failure"

    monkeypatch.setattr("eval.run_ablation.subprocess.run", lambda *args, **kwargs: Completed())
    result = run_profile(profile=_profile("lexical_only"), python_executable="python", dataset=tmp_path / "data", manifest=tmp_path / "manifest", output=tmp_path / "missing.json", top_k="1,3,5,10", cwd=tmp_path, base_environment={})
    assert result["status"] == "failed"
    assert result["reason"].endswith("code 7")


def test_run_profile_loads_and_hashes_valid_report(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    class Completed:
        returncode, stdout, stderr = 0, "", ""

    def fake_run(*args, **kwargs):
        output.write_text(json.dumps(_report()), encoding="utf-8")
        return Completed()

    monkeypatch.setattr("eval.run_ablation.subprocess.run", fake_run)
    result = run_profile(profile=_profile("lexical_only"), python_executable="python", dataset=tmp_path / "data", manifest=tmp_path / "manifest", output=output, top_k="1,3,5,10", cwd=tmp_path, base_environment={})
    assert result["status"] == "success"
    assert result["report_sha256"] == sha256_file(output)
