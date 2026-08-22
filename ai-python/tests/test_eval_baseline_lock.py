import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_dev_baseline_candidate_lock_matches_snapshot() -> None:
    root = Path(__file__).resolve().parents[1]
    lock_path = (
        root
        / "eval"
        / "baselines"
        / "rag_eval_dev_v1_dos010_option_a_candidate_lock.json"
    )
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    assert lock["status"] == "diagnostic_baseline_candidate"
    assert lock["frozen"] is True
    assert lock["ci_regression_gate"] is False
    assert lock["dataset_sha256"] == _sha256(
        root / "eval" / "datasets" / "rag_eval_dev_v1.jsonl"
    )
    assert lock["manifest_sha256"] == _sha256(
        root / "eval" / "manifests" / "rag_eval_dev_v1_documents.json"
    )
    assert lock["requirements_lock_sha256"] == _sha256(root / "requirements.lock.txt")
    report_path = (lock_path.parent / lock["report"]["path"]).resolve()
    assert lock["report"]["sha256"] == _sha256(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ranking_projection = [
        {
            "case_id": case["case_id"],
            "first_relevant_rank": case["first_relevant_rank"],
            "top_results": [
                {
                    "rank": result["rank"],
                    "chunk_id": result["chunk_id"],
                    "parent_id": result["parent_id"],
                    "page": result["page"],
                    "page_nos": result["page_nos"],
                    "score": result["score"],
                }
                for result in case["top_results"]
            ],
        }
        for case in report["cases"]
    ]
    ranking_bytes = json.dumps(
        ranking_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert lock["report"]["case_result_count"] == len(report["cases"])
    assert lock["report"]["ranking_projection"]["sha256"] == hashlib.sha256(
        ranking_bytes
    ).hexdigest()
    repeatability = lock["repeatability_check"]
    repeat_report_path = (lock_path.parent / repeatability["report_path"]).resolve()
    assert repeatability["report_sha256"] == _sha256(repeat_report_path)
    assert repeatability["top_10_candidate_ids_equal"] is True
    assert repeatability["top_10_scores_exact"] is True
    assert repeatability["maximum_absolute_score_delta"] == 0.0
    cross_encoder_smoke = lock["cross_encoder_integration_smoke"]
    cross_encoder_report_path = (
        lock_path.parent / cross_encoder_smoke["report_path"]
    ).resolve()
    assert cross_encoder_smoke["report_sha256"] == _sha256(
        cross_encoder_report_path
    )
    cross_encoder_report = json.loads(
        cross_encoder_report_path.read_text(encoding="utf-8")
    )
    assert cross_encoder_report["execution"]["cross_encoder_success_count"] == 1
    assert cross_encoder_report["execution"][
        "cross_encoder_timeout_fallback_count"
    ] == 0
    assert cross_encoder_report["cases"][0]["reranker_status"] == "success"
    assert lock["entry_gate"]["full_evaluation_reproducible"] is True
    assert lock["entry_gate"]["reviewed_cases_satisfied"] is True
    assert lock["entry_gate"]["public_pdf_documents_satisfied"] is True
    assert lock["entry_gate"]["ranking_repeatability_passed"] is True
    assert lock["entry_gate"]["cross_encoder_execution_succeeded"] is True
    assert lock["entry_gate"]["phase_1_5_entry_gate_satisfied"] is True
    assert lock["entry_gate"]["formal_regression_baseline_ready"] is False
