"""Write-once blind evaluation for the frozen External Holdout V1.

This evaluator is intentionally separate from the development evaluators. It
freezes its input contract before invoking any Judge and refuses to overwrite
any first-run artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from eval.documents.external_holdout.validate_external_holdout_v1 import validate
from services.evidence_judge import judge_evidence_support
from services.evidence_judge_v1 import judge_claim_evidence_v1
from services.evidence_judge_v2 import judge_claim_evidence_v2
from services.evidence_judge_v2_1 import judge_claim_evidence_v2_1
from services.v3_types import RetrievalCandidate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GIT_ROOT = PROJECT_ROOT.parent
EXPECTED_DATASET_SHA256 = "d0f98891bd7e0471516afe11f99a4bae5d51026c9a1d140eee22c3e9b7ca89d3"
EXPECTED_V2_1_SHA256 = "403a6e3318e9c48196162090070f91bbea091e5c34fdfbbeae0e57738c22fbb7"
LABELS = ("SUPPORTED", "PARTIAL", "UNSUPPORTED")
DECISION_LABELS = {"YES": "SUPPORTED", "UNCERTAIN": "PARTIAL", "NO": "UNSUPPORTED"}
FIRST_RUN_FILES = {
    "v0": "v0_external_blind_first_run.json",
    "v1": "v1_external_blind_first_run.json",
    "v2": "v2_external_blind_first_run.json",
    "v2_1": "v2_1_external_blind_first_run.json",
}
EVALUATOR_CONFIG = {
    "schema_version": "external_holdout_blind_evaluator_v1",
    "claim_field": "claim.riskDesc",
    "risk_type_field": "claim.riskType",
    "evidence_order": "ascending frozen candidate rank",
    "evidence_top_n": 8,
    "v0_evidence_contract": "ordered RetrievalCandidate list",
    "v1_v2_evidence_contract": "same ordered texts joined with LF",
    "label_mapping": DECISION_LABELS,
    "human_review_definition": "predicted PARTIAL",
    "automation_definition": "predicted SUPPORTED or UNSUPPORTED",
    "selective_accuracy_definition": "accuracy among non-PARTIAL predictions",
    "risk_type_minimum_n": 3,
    "confidence_interval": {"method": "Wilson score", "confidence": 0.95, "z": 1.959963984540054},
    "latency_scope": "Judge function invocation only; input preparation excluded",
    "external_model_api": False,
    "development_acceptance": {
        "v2_1_overall": "FAIL",
        "failed_gate": "semantically_related_but_insufficient accuracy = 0.666667 < 0.75",
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def divide(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def wilson_interval(numerator: int, denominator: int, z: float = 1.959963984540054) -> dict[str, Any]:
    if denominator == 0:
        return {"method": "wilson_95", "numerator": numerator, "denominator": denominator, "low": None, "high": None}
    p = numerator / denominator
    z2 = z * z
    center = (p + z2 / (2 * denominator)) / (1 + z2 / denominator)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * denominator)) / denominator) / (1 + z2 / denominator)
    return {
        "method": "wilson_95",
        "numerator": numerator,
        "denominator": denominator,
        "low": round(max(0.0, center - margin), 6),
        "high": round(min(1.0, center + margin), 6),
    }


def metric_bundle(predictions: list[dict[str, Any]], present_labels_only: bool = False) -> dict[str, Any]:
    matrix = {gold: {pred: 0 for pred in LABELS} for gold in LABELS}
    for row in predictions:
        matrix[row["gold_label"]][row["predicted_label"]] += 1
    per_class: dict[str, Any] = {}
    f1_values: list[float] = []
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[gold][label] for gold in LABELS if gold != label)
        fn = sum(matrix[label][pred] for pred in LABELS if pred != label)
        support = sum(matrix[label].values())
        precision_denominator = tp + fp
        precision = divide(tp, precision_denominator)
        recall = divide(tp, support)
        f1 = divide(2 * tp, 2 * tp + fp + fn)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "precision_count": {"numerator": tp, "denominator": precision_denominator},
            "recall_count": {"numerator": tp, "denominator": support},
            "precision_wilson_95": wilson_interval(tp, precision_denominator),
            "recall_wilson_95": wilson_interval(tp, support),
        }
        if not present_labels_only or support:
            f1_values.append(f1)
    count = len(predictions)
    correct = sum(row["gold_label"] == row["predicted_label"] for row in predictions)
    unsafe_denominator = sum(row["gold_label"] in {"PARTIAL", "UNSUPPORTED"} for row in predictions)
    unsafe = sum(row["gold_label"] in {"PARTIAL", "UNSUPPORTED"} and row["predicted_label"] == "SUPPORTED" for row in predictions)
    supported_denominator = sum(row["gold_label"] == "SUPPORTED" for row in predictions)
    false_rejection = sum(row["gold_label"] == "SUPPORTED" and row["predicted_label"] != "SUPPORTED" for row in predictions)
    hard_false_rejection = sum(row["gold_label"] == "SUPPORTED" and row["predicted_label"] == "UNSUPPORTED" for row in predictions)
    review = sum(row["predicted_label"] == "PARTIAL" for row in predictions)
    automated = count - review
    selective_correct = sum(row["predicted_label"] != "PARTIAL" and row["gold_label"] == row["predicted_label"] for row in predictions)
    return {
        "case_count": count,
        "accuracy": divide(correct, count),
        "accuracy_count": {"numerator": correct, "denominator": count},
        "macro_f1": round(sum(f1_values) / len(f1_values), 6) if f1_values else 0.0,
        "macro_f1_scope": "labels present in this slice" if present_labels_only else "all three labels",
        "per_class": per_class,
        "supported_precision": per_class["SUPPORTED"]["precision"],
        "supported_recall": per_class["SUPPORTED"]["recall"],
        "partial_f1": per_class["PARTIAL"]["f1"],
        "unsupported_recall": per_class["UNSUPPORTED"]["recall"],
        "unsafe_acceptance_rate": divide(unsafe, unsafe_denominator),
        "unsafe_acceptance_count": {"numerator": unsafe, "denominator": unsafe_denominator},
        "unsafe_acceptance_wilson_95": wilson_interval(unsafe, unsafe_denominator),
        "supported_false_rejection_rate": divide(false_rejection, supported_denominator),
        "supported_false_rejection_count": {"numerator": false_rejection, "denominator": supported_denominator},
        "hard_false_rejection_rate": divide(hard_false_rejection, supported_denominator),
        "hard_false_rejection_count": {"numerator": hard_false_rejection, "denominator": supported_denominator},
        "human_review_rate": divide(review, count),
        "human_review_count": {"numerator": review, "denominator": count},
        "human_review_wilson_95": wilson_interval(review, count),
        "automation_coverage": divide(automated, count),
        "automation_coverage_count": {"numerator": automated, "denominator": count},
        "automation_coverage_wilson_95": wilson_interval(automated, count),
        "selective_accuracy": divide(selective_correct, automated),
        "selective_accuracy_count": {"numerator": selective_correct, "denominator": automated},
        "confusion_matrix": matrix,
    }


def latency_bundle(values: list[float], error_count: int = 0) -> dict[str, Any]:
    ordered = sorted(values)
    if not ordered:
        distribution = {"mean": None, "p50": None, "p95": None, "max": None}
    else:
        p95_index = min(len(ordered) - 1, max(0, math.ceil(0.95 * len(ordered)) - 1))
        distribution = {
            "mean": round(statistics.mean(ordered), 6),
            "p50": round(statistics.median(ordered), 6),
            "p95": round(ordered[p95_index], 6),
            "max": round(max(ordered), 6),
        }
    return {
        "invocation_count": len(values) + error_count,
        "successful_invocation_count": len(values),
        "latency_ms": distribution,
        "timeout_count": 0,
        "error_count": error_count,
        "fallback_count": 0,
        "external_model_api_invocation_count": 0,
        "estimated_external_model_cost": 0.0,
    }


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-c", f"safe.directory={GIT_ROOT.as_posix()}", *args], cwd=GIT_ROOT, text=True, stderr=subprocess.STDOUT).strip()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _claim_text(row: dict[str, Any]) -> str:
    value = str(row.get("claim", {}).get("riskDesc") or "").strip()
    if not value:
        raise ValueError(f"{row.get('case_id')}: claim.riskDesc is empty")
    return value


def _risk_type(row: dict[str, Any]) -> str:
    return str(row.get("claim", {}).get("riskType") or "UNKNOWN").strip() or "UNKNOWN"


def _scoped_evidence(row: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = sorted(row.get("evidence_candidates") or [], key=lambda item: (int(item.get("rank") or 10**9), str(item.get("candidate_id") or "")))
    scoped = candidates[: int(EVALUATOR_CONFIG["evidence_top_n"])]
    if not scoped:
        raise ValueError(f"{row.get('case_id')}: no evidence candidates")
    return scoped


def _retrieval_candidate(item: dict[str, Any]) -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id=str(item["candidate_id"]), parent_id=str(item.get("parent_id") or ""), child_id=str(item.get("child_id") or ""),
        page_no=int(item.get("page_no") or 1), clause_id=str(item.get("clause_id") or ""), clause_title=str(item.get("clause_title") or ""),
        snippet=str(item.get("text") or ""), bm25_rank=item.get("bm25_rank"), vector_rank=item.get("vector_rank"),
        rrf_score=float(item.get("rrf_score") or 0.0), query_source=str(item.get("query_source") or ""),
        matched_terms=list(item.get("matched_terms") or []), metadata=dict(item.get("metadata") or {}), page_start=item.get("page_start"),
        page_end=item.get("page_end"), page_nos=list(item.get("page_nos") or []),
    )


def _common_prediction(row: dict[str, Any], scoped: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_id": row["case_id"], "document_id": row["document_id"], "document_filename": row["document_filename"],
        "risk_type": _risk_type(row), "gold_label": row["gold_label"], "claim_text": _claim_text(row),
        "used_evidence_ids": [item["candidate_id"] for item in scoped], "used_evidence_ranks": [item["rank"] for item in scoped],
        "evidence_count": len(scoped), "reviewer_notes": row.get("reviewer_notes"),
    }


def run_judge(judge: str, row: dict[str, Any]) -> tuple[dict[str, Any], float]:
    scoped = _scoped_evidence(row)
    claim = _claim_text(row)
    risk_type = _risk_type(row)
    evidence_ids = [str(item["candidate_id"]) for item in scoped]
    evidence_text = "\n".join(str(item.get("text") or "") for item in scoped)
    started = time.perf_counter()
    if judge == "v0":
        result = judge_evidence_support(query=claim, risk_type=risk_type, candidates=[_retrieval_candidate(item) for item in scoped], settings=SimpleNamespace(judge_top_n=8))
        normalized = {
            "predicted_label": DECISION_LABELS[result.decision], "raw_decision": result.decision, "reason_code": result.reason_code,
            "reason": result.reason, "confidence": result.confidence, "requires_human_review_raw": result.requires_human_review,
            "supporting_evidence_ids": result.supporting_evidence_ids, "feature_result": None,
        }
    elif judge == "v1":
        result = judge_claim_evidence_v1(claim, evidence_text)
        normalized = {
            "predicted_label": result["predicted_label"], "raw_decision": result["decision"], "reason_code": result["reason_code"],
            "confidence": result.get("lexical_score"), "requires_human_review_raw": result["requires_human_review"], "feature_result": result,
        }
    elif judge == "v2":
        result = judge_claim_evidence_v2(claim, evidence_text, evidence_ids)
        normalized = {
            "predicted_label": result["predicted_label"], "raw_decision": result["decision"], "reason_code": result["reason_code"],
            "confidence": result.get("confidence"), "requires_human_review_raw": result["requires_human_review"], "feature_result": result,
        }
    elif judge == "v2_1":
        result = judge_claim_evidence_v2_1(claim, evidence_text, evidence_ids)
        normalized = {
            "predicted_label": result["predicted_label"], "raw_decision": result["decision"], "reason_code": result["reason_code"],
            "confidence": result.get("confidence"), "requires_human_review_raw": result["requires_human_review"], "feature_result": result,
        }
    else:
        raise ValueError(f"unknown Judge: {judge}")
    elapsed = (time.perf_counter() - started) * 1000
    return {**_common_prediction(row, scoped), **normalized, "latency_ms": round(elapsed, 6)}, elapsed


def transition_analysis(left: list[dict[str, Any]], right: list[dict[str, Any]], pair: str) -> dict[str, Any]:
    right_by_id = {row["case_id"]: row for row in right}
    categories: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for old in left:
        new = right_by_id[old["case_id"]]
        gold, before, after = old["gold_label"], old["predicted_label"], new["predicted_label"]
        names: list[str] = []
        if pair == "v1_to_v2_1":
            if before != gold and after == gold: names.append("v1_wrong_to_v2_1_correct")
            if before == gold and after != gold: names.append("v1_correct_to_v2_1_wrong")
            if gold == "SUPPORTED" and before != "SUPPORTED" and after == "SUPPORTED": names.append("v1_false_rejection_to_v2_1_correct")
            if gold in {"PARTIAL", "UNSUPPORTED"} and before != "SUPPORTED" and after == "SUPPORTED": names.append("v1_safe_to_v2_1_unsafe")
        else:
            if gold in {"PARTIAL", "UNSUPPORTED"} and before == "SUPPORTED" and after == gold: names.append("v2_unsafe_to_v2_1_correct")
            if gold in {"PARTIAL", "UNSUPPORTED"} and before == "SUPPORTED" and after == "PARTIAL": names.append("v2_unsafe_to_v2_1_partial_hitl")
            if gold == "SUPPORTED" and before == "SUPPORTED" and after != "SUPPORTED": names.append("v2_correct_supported_to_v2_1_false_rejection")
            if gold == "PARTIAL" and before == "PARTIAL" and after != "PARTIAL": names.append("v2_correct_partial_to_v2_1_regression")
            if before != gold and after == gold: names.append("v2_wrong_to_v2_1_correct")
            if before == gold and after != gold: names.append("v2_correct_to_v2_1_wrong")
        detail = {
            "case_id": old["case_id"], "document_id": old["document_id"], "risk_type": old["risk_type"], "gold": gold,
            "before_prediction": before, "after_prediction": after, "before_reason_code": old.get("reason_code"),
            "after_reason_code": new.get("reason_code"), "after_feature_result": new.get("feature_result"),
            "used_evidence_ids": new.get("used_evidence_ids", []),
        }
        for name in names:
            categories[name].append(detail)
    return {"pair": pair, "counts": {name: len(items) for name, items in sorted(categories.items())}, "cases": dict(sorted(categories.items()))}


def classify_failure(row: dict[str, Any]) -> dict[str, Any]:
    claim = row.get("claim_text", "")
    notes = str(row.get("reviewer_notes") or "")
    reason = str(row.get("reason_code") or "")
    text = f"{claim} {notes} {reason}".lower()
    if row["gold_label"] in {"PARTIAL", "UNSUPPORTED"}:
        source = "retrieval_evidence_failure"
        evidence_state = "retrieved evidence adjudicated insufficient or conflicting"
    else:
        source = "judge_failure"
        evidence_state = "retrieved evidence adjudicated sufficient"
    if any(token in text for token in ("冲突", "矛盾", "conflict")):
        category = "conflicting_evidence"
    elif any(token in text for token in ("多段", "多条", "multiple", "multi", "分别")):
        category = "multi_evidence_failure"
    elif any(token in text for token in ("主体", "指代", "甲方", "乙方", "采购人", "供应商", "coreference")) and "entity" in reason.lower():
        category = "implicit_entity_coreference"
    elif any(token in text for token in ("例外", "除非", "但", "条件", "范围", "限定", "exception", "qualifier")):
        category = "qualifier_exception_scope"
    elif any(token in text for token in ("金额", "比例", "日期", "期限", "工作日", "%", "numeric", "temporal")):
        category = "numeric_temporal_failure"
    elif any(token in text for token in ("推断", "风险", "可能", "导致", "inference")):
        category = "implicit_risk_inference"
    elif row["gold_label"] == "PARTIAL":
        category = "partial_support_boundary"
    elif row["gold_label"] == "UNSUPPORTED":
        category = "semantically_related_but_insufficient"
    elif row.get("evidence_count", 0) > 1:
        category = "semantic_paraphrase_failure"
    else:
        category = "other"
    return {
        "case_id": row["case_id"], "document_id": row["document_id"], "risk_type": row["risk_type"],
        "gold_label": row["gold_label"], "predicted_label": row["predicted_label"], "reason_code": reason,
        "failure_category": category, "primary_source": source, "evidence_state": evidence_state,
        "judge_prediction_incorrect": True, "used_evidence_ids": row.get("used_evidence_ids", []),
    }


def _write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_text_exclusive(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def _result_artifact(judge: str, predictions: list[dict[str, Any]], latencies: list[float], errors: list[dict[str, Any]], provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "external_holdout_blind_first_run_v1", "immutable_first_run": True, "judge": judge,
        "provenance": provenance, "metrics": metric_bundle(predictions), "latency": latency_bundle(latencies, len(errors)),
        "errors": errors, "predictions": predictions,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Evidence Judge External Holdout V1 Blind Evaluation", "",
        "Status: `EXTERNAL_BLIND_EVALUATION_COMPLETE`", "",
        f"Dataset SHA256: `{report['provenance']['dataset_sha256']}`", "",
        "The External result is descriptive. Evidence Judge v2.1 development acceptance remains **FAIL** because `semantically_related_but_insufficient accuracy = 0.666667 < 0.75`.", "",
        "| Judge | Accuracy | Macro-F1 | SUP Precision | SUP Recall | PARTIAL F1 | UNSUP Recall | Unsafe acceptance | Human review | Selective accuracy |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for judge in ("v0", "v1", "v2", "v2_1"):
        m = report["metrics"][judge]
        lines.append(f"| {judge} | {m['accuracy']:.6f} | {m['macro_f1']:.6f} | {m['supported_precision']:.6f} | {m['supported_recall']:.6f} | {m['partial_f1']:.6f} | {m['unsupported_recall']:.6f} | {m['unsafe_acceptance_rate']:.6f} ({m['unsafe_acceptance_count']['numerator']}/{m['unsafe_acceptance_count']['denominator']}) | {m['human_review_rate']:.6f} | {m['selective_accuracy']:.6f} |")
    lines.extend(["", "All four Judges are deterministic and model-free. External model/API invocations and estimated external model cost are zero.", "", "No new acceptance gate was applied and no Judge, threshold, dataset, Gold label, retrieval result, or candidate ranking was modified.", ""])
    return "\n".join(lines)


def run(dataset_dir: Path, sample_dir: Path, output_dir: Path) -> dict[str, Any]:
    dataset_path = dataset_dir / "external_holdout_v1.jsonl"
    freeze_manifest_path = dataset_dir / "freeze_manifest.json"
    validator = validate(dataset_dir, sample_dir)
    if validator["status"] != "PASS" or validator["dataset_sha256"] != EXPECTED_DATASET_SHA256:
        raise RuntimeError(f"BLOCKED_EXTERNAL_HOLDOUT_INTEGRITY_FAILURE: {validator}")
    if output_dir.exists():
        existing = [path.name for path in output_dir.iterdir()]
        raise FileExistsError(f"blind output directory already exists; refusing overwrite: {existing}")

    implementation_paths = {
        "v0": PROJECT_ROOT / "services/evidence_judge.py", "v1": PROJECT_ROOT / "services/evidence_judge_v1.py",
        "v2": PROJECT_ROOT / "services/evidence_judge_v2.py", "v2_1": PROJECT_ROOT / "services/evidence_judge_v2_1.py",
        "evaluator": Path(__file__).resolve(),
    }
    implementation_hashes = {name: sha256_file(path) for name, path in implementation_paths.items()}
    if implementation_hashes["v2_1"] != EXPECTED_V2_1_SHA256:
        raise RuntimeError("v2.1 implementation hash differs from preregistered value")
    rows = _load_rows(dataset_path)
    if len(rows) != 120:
        raise RuntimeError("BLOCKED_EXTERNAL_HOLDOUT_INTEGRITY_FAILURE: expected 120 rows")
    git_head = _git("rev-parse", "HEAD")
    try:
        working_tree = _git("status", "--short").splitlines()
    except subprocess.CalledProcessError as exc:
        working_tree = [f"status unavailable: {exc.output}"]
    config_fingerprint = canonical_hash(EVALUATOR_CONFIG)
    provenance = {
        "dataset_sha256": validator["dataset_sha256"], "freeze_manifest_sha256": sha256_file(freeze_manifest_path),
        "git_head": git_head, "working_tree_status": working_tree, "implementation_sha256": implementation_hashes,
        "evaluator_config": EVALUATOR_CONFIG, "evaluator_config_fingerprint": config_fingerprint,
        "python_version": sys.version, "platform": platform.platform(), "source_pipeline_run_id": rows[0].get("pipeline_run_id"),
    }
    freeze_state = {
        "schema_version": "external_holdout_blind_freeze_state_v1", "status": "PREFLIGHT_PASSED_BEFORE_INFERENCE",
        "validator": validator, "provenance": provenance, "first_run_files": FIRST_RUN_FILES,
        "preexisting_first_run_files": [], "judge_invocation_count_before_evaluation": 0,
        "development_acceptance_preserved": EVALUATOR_CONFIG["development_acceptance"],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json_exclusive(output_dir / "freeze_state.json", freeze_state)

    artifacts: dict[str, dict[str, Any]] = {}
    for judge in ("v0", "v1", "v2", "v2_1"):
        predictions: list[dict[str, Any]] = []
        latencies: list[float] = []
        errors: list[dict[str, Any]] = []
        for row in rows:
            try:
                prediction, elapsed = run_judge(judge, row)
                predictions.append(prediction)
                latencies.append(elapsed)
            except Exception as exc:
                errors.append({"case_id": row.get("case_id"), "error_type": type(exc).__name__, "error": str(exc)})
        artifacts[judge] = _result_artifact(judge, predictions, latencies, errors, provenance)

    # Predictions are complete in memory before any first-run result is exposed.
    for judge, filename in FIRST_RUN_FILES.items():
        _write_json_exclusive(output_dir / filename, artifacts[judge])

    metrics = {judge: artifact["metrics"] for judge, artifact in artifacts.items()}
    comparison = {
        "schema_version": "external_holdout_blind_comparison_v1", "provenance": provenance, "metrics": metrics,
        "development_acceptance": EVALUATOR_CONFIG["development_acceptance"],
        "external_interpretation": "descriptive blind evaluation; no post-hoc acceptance gate",
    }
    _write_json_exclusive(output_dir / "comparison.json", comparison)
    _write_text_exclusive(output_dir / "comparison.md", _markdown(comparison))
    _write_json_exclusive(output_dir / "confusion_matrices.json", {judge: metrics[judge]["confusion_matrix"] for judge in metrics})

    per_document: dict[str, Any] = {}
    for judge, artifact in artifacts.items():
        grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in artifact["predictions"]:
            grouped[row["document_filename"]].append(row)
        per_document[judge] = {
            name: {"label_distribution": dict(Counter(row["gold_label"] for row in group)), "metrics": metric_bundle(group, present_labels_only=True)}
            for name, group in sorted(grouped.items())
        }
    _write_json_exclusive(output_dir / "per_document_metrics.json", per_document)

    per_risk: dict[str, Any] = {"minimum_n": EVALUATOR_CONFIG["risk_type_minimum_n"], "excluded_small_categories_are_not_interpreted": True, "judges": {}}
    for judge, artifact in artifacts.items():
        grouped = defaultdict(list)
        for row in artifact["predictions"]:
            grouped[row["risk_type"]].append(row)
        per_risk["judges"][judge] = {
            name: {"label_distribution": dict(Counter(row["gold_label"] for row in group)), "metrics": metric_bundle(group, present_labels_only=True)}
            for name, group in sorted(grouped.items()) if len(group) >= EVALUATOR_CONFIG["risk_type_minimum_n"]
        }
    _write_json_exclusive(output_dir / "per_risk_type_metrics.json", per_risk)

    transitions = {
        "v1_to_v2_1": transition_analysis(artifacts["v1"]["predictions"], artifacts["v2_1"]["predictions"], "v1_to_v2_1"),
        "v2_to_v2_1": transition_analysis(artifacts["v2"]["predictions"], artifacts["v2_1"]["predictions"], "v2_to_v2_1"),
    }
    _write_json_exclusive(output_dir / "transitions.json", transitions)
    v2_1_errors = [classify_failure(row) for row in artifacts["v2_1"]["predictions"] if row["gold_label"] != row["predicted_label"]]
    failure_analysis = {
        "judge": "v2_1", "error_count": len(v2_1_errors),
        "taxonomy_counts": dict(Counter(row["failure_category"] for row in v2_1_errors)),
        "source_counts": dict(Counter(row["primary_source"] for row in v2_1_errors)), "errors": v2_1_errors,
    }
    _write_json_exclusive(output_dir / "failure_analysis.json", failure_analysis)
    _write_json_exclusive(output_dir / "latency.json", {judge: artifact["latency"] for judge, artifact in artifacts.items()})

    result_hashes = {filename: sha256_file(output_dir / filename) for filename in FIRST_RUN_FILES.values()}
    _write_json_exclusive(output_dir / "result_hashes.json", {"sha256": result_hashes, "hash_method": "SHA256 of exact first-run artifact bytes"})
    summary = {**comparison, "first_run_result_sha256": result_hashes, "transitions": {name: value["counts"] for name, value in transitions.items()}, "v2_1_failure_analysis": {key: value for key, value in failure_analysis.items() if key != "errors"}}
    _write_json_exclusive(output_dir / "summary.json", summary)
    _write_text_exclusive(output_dir / "summary.md", _markdown(summary))
    return {"status": "EXTERNAL_BLIND_EVALUATION_COMPLETE", "dataset_sha256": validator["dataset_sha256"], "result_hashes": result_hashes, "metrics": metrics}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--sample-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.dataset_dir, args.sample_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
