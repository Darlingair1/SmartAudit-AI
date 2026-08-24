import json
from pathlib import Path
from types import SimpleNamespace

from eval.dataset_loader import load_dataset
from eval.runners.run_retrieval_eval import (
    CurrentPipelineRetriever,
    EvaluationDocumentContext,
    RetrievedChunk,
    build_document_resolver,
    evaluate_case,
    run_evaluation,
)
from eval.runners.run_retrieval_eval import _ranking_fingerprint


def test_ranking_fingerprint_uses_case_and_ordered_ids() -> None:
    cases = [{"case_id": "b", "top_results": [{"chunk_id": "2"}, {"chunk_id": "1"}]}, {"case_id": "a", "top_results": [{"chunk_id": "3"}]}]
    first = _ranking_fingerprint(cases)
    second = _ranking_fingerprint(list(reversed(cases)))
    assert first == second
    assert first["case_count"] == 2
    cases[0]["top_results"].reverse()
    assert _ranking_fingerprint(cases)["sha256"] != first["sha256"]


def _write_dataset(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "document_id": "doc-1",
                "query": "payment",
                "expected_evidence": [{"page": 2, "text": "pay on time"}],
                "metadata": {"source_type": "synthetic", "document_path": "doc.txt"},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_runner_case_result_with_mock_retrieval(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    _write_dataset(dataset)
    document = tmp_path / "doc.txt"
    document.write_text("page one\fpay on time", encoding="utf-8")
    case = load_dataset(dataset)[0]

    def retrieve(case, path, limit):
        assert path == document
        return [
            RetrievedChunk("c1", "p1", 1, 0.9, "unrelated"),
            RetrievedChunk("c2", "p2", 2, 0.8, "pay on time"),
        ]

    result = evaluate_case(case, retrieve, build_document_resolver(dataset), (1, 3))
    assert result["status"] == "success"
    assert result["hit_at_1"] is False
    assert result["hit_at_3"] is True
    assert result["first_relevant_rank"] == 2
    assert result["top_results"][1]["matched_gold"] == [0]


def test_runner_reports_retrieval_error_and_document_not_found(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    _write_dataset(dataset)
    case = load_dataset(dataset)[0]
    missing = evaluate_case(case, lambda *_: [], build_document_resolver(dataset), (1,))
    assert missing["status"] == "document_not_found"
    assert missing["retrieval_executed"] is False
    assert missing["latency_ms"] is None

    document = tmp_path / "doc.txt"
    document.write_text("content", encoding="utf-8")
    broken = evaluate_case(
        case,
        lambda *_: (_ for _ in ()).throw(RuntimeError("boom")),
        build_document_resolver(dataset),
        (1,),
    )
    assert broken["status"] == "retrieval_error"
    assert broken["retrieval_executed"] is True
    assert broken["retrieval_successful"] is False
    assert "boom" in broken["error"]


def test_document_not_found_is_excluded_from_report_aggregates(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    _write_dataset(dataset)
    report = run_evaluation(
        dataset_path=dataset,
        retriever=lambda *_: [],
        document_resolver=build_document_resolver(dataset),
        top_ks=(1,),
    )
    assert report["coverage"]["evaluation_coverage"] == 0.0
    assert report["coverage"]["document_not_found_count"] == 1
    assert report["metrics"]["hit_at_1"] is None
    assert report["metrics"]["recall_at_1"] is None
    assert report["metrics"]["mrr"] is None
    assert report["metrics"]["latency"]["mean_ms"] is None


def test_run_evaluation_report_shape(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    _write_dataset(dataset)
    (tmp_path / "doc.txt").write_text("content", encoding="utf-8")
    report = run_evaluation(
        dataset_path=dataset,
        retriever=lambda *_: [],
        document_resolver=build_document_resolver(dataset),
        top_ks=(1, 3),
    )
    assert report["metadata"]["case_count"] == 1
    assert report["coverage"]["evaluation_coverage"] == 1.0
    assert set(report["metrics"]) == {"hit_at_1", "hit_at_3", "recall_at_1", "recall_at_3", "mrr", "latency"}
    assert report["cases"][0]["status"] == "no_relevant_evidence_retrieved"


def test_draft_cases_are_excluded_by_default(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    base = {
        "document_id": "doc-1",
        "query": "payment",
        "expected_evidence": [{"page": 1, "text": "payment"}],
        "metadata": {
            "source_type": "synthetic",
            "document_path": "doc.txt",
            "annotation_status": "reviewed",
        },
    }
    reviewed = {**base, "case_id": "reviewed"}
    draft = json.loads(json.dumps(base))
    draft["case_id"] = "draft"
    draft["query"] = "delivery"
    draft["metadata"]["annotation_status"] = "draft"
    dataset.write_text(
        json.dumps(reviewed) + "\n" + json.dumps(draft) + "\n", encoding="utf-8"
    )
    (tmp_path / "doc.txt").write_text("payment", encoding="utf-8")
    report = run_evaluation(
        dataset_path=dataset,
        retriever=lambda *_: [],
        document_resolver=build_document_resolver(dataset),
        top_ks=(1,),
    )
    assert report["metadata"]["dataset_case_count"] == 2
    assert report["metadata"]["case_count"] == 1
    assert report["metadata"]["excluded_draft_count"] == 1


def test_checked_in_smoke_document_resolves():
    root = Path(__file__).resolve().parents[1]
    dataset = root / "eval" / "datasets" / "rag_eval_smoke.jsonl"
    case = load_dataset(dataset)[0]
    resolved = build_document_resolver(dataset)(case)
    assert resolved == root / "eval" / "fixtures" / "synthetic_contract_smoke.md"


def test_evaluation_document_context_cache_reuses_same_document(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    _write_dataset(dataset)
    document = tmp_path / "doc.txt"
    document.write_text("content", encoding="utf-8")
    case = load_dataset(dataset)[0]
    settings = SimpleNamespace(child_chunk_size_tokens=250)
    retriever = CurrentPipelineRetriever.__new__(CurrentPipelineRetriever)
    retriever._document_cache = {}
    retriever.cache_hits = 0
    retriever.cache_misses = 0
    built = []

    def build(case, path, settings, document_hash, settings_fingerprint):
        built.append((case.document_id, document_hash, settings_fingerprint))
        return EvaluationDocumentContext(
            security_context=object(),
            parents=[],
            children=[],
            vector_store=None,
            prepare_ms=12.0,
            document_sha256=document_hash,
            settings_fingerprint=settings_fingerprint,
        )

    monkeypatch.setattr(retriever, "_build_document_context", build)
    first, first_hit = retriever._get_document_context(case, document, settings)
    second, second_hit = retriever._get_document_context(case, document, settings)
    assert first is second
    assert (first_hit, second_hit) == (False, True)
    assert len(built) == 1
    assert (retriever.cache_hits, retriever.cache_misses) == (1, 1)


def test_settings_fingerprint_changes_with_chunk_configuration():
    first = SimpleNamespace(child_chunk_size_tokens=250)
    second = SimpleNamespace(child_chunk_size_tokens=251)
    assert CurrentPipelineRetriever._settings_fingerprint(first) != CurrentPipelineRetriever._settings_fingerprint(second)


def test_execution_metadata_aggregates_cache_and_reranker_status(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    _write_dataset(dataset)
    (tmp_path / "doc.txt").write_text("pay on time", encoding="utf-8")

    class DiagnosticRetriever:
        last_diagnostics = {}

        def __call__(self, case, path, limit):
            self.last_diagnostics = {
                "document_cache_hit": False,
                "document_prepare_ms": 4.0,
                "retrieval_ms": 2.0,
                "reranker_ms": 3.0,
                "reranker_status": "timeout_fallback",
            }
            return [RetrievedChunk("c1", "p1", 2, 0.9, "pay on time")]

    report = run_evaluation(
        dataset_path=dataset,
        retriever=DiagnosticRetriever(),
        document_resolver=build_document_resolver(dataset),
        top_ks=(1,),
    )
    assert report["execution"]["document_cache_misses"] == 1
    assert report["execution"]["document_cache_hits"] == 0
    assert report["execution"]["cross_encoder_timeout_fallback_count"] == 1
    assert report["cases"][0]["timing"]["matcher_ms"] >= 0
    assert report["cases"][0]["reranker_status"] == "timeout_fallback"
