from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Protocol, Sequence

from eval.dataset_loader import EvaluationCase, load_dataset, select_evaluation_cases
from eval.benchmark_manifest import manifest_document_map
from eval.matching.evidence_matcher import match_evidence
from eval.metrics.retrieval_metrics import (
    DEFAULT_TOP_KS,
    aggregate_retrieval_metrics,
    calculate_case_metrics,
    calculate_evaluation_coverage,
)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    parent_id: str | None
    page: int | None
    score: float
    text: str


class Retriever(Protocol):
    def __call__(
        self, case: EvaluationCase, document_path: Path, limit: int
    ) -> Sequence[RetrievedChunk]: ...


DocumentResolver = Callable[[EvaluationCase], Path | None]


def build_document_resolver(
    dataset_path: Path,
    documents_dir: Path | None = None,
    manifest_path: Path | None = None,
) -> DocumentResolver:
    dataset_dir = dataset_path.resolve().parent
    root = documents_dir.resolve() if documents_dir else None
    manifest_documents = manifest_document_map(manifest_path) if manifest_path else {}

    def resolve(case: EvaluationCase) -> Path | None:
        configured = case.metadata.document_path
        if configured:
            candidate = Path(configured).expanduser()
            if not candidate.is_absolute():
                candidate = dataset_dir / candidate
            if candidate.is_file():
                return candidate.resolve()
        if root:
            direct = root / case.document_id
            candidates = [direct] if direct.suffix else [
                root / f"{case.document_id}{suffix}"
                for suffix in (".pdf", ".txt", ".md")
            ]
            for candidate in candidates:
                if candidate.is_file():
                    return candidate.resolve()
        manifest_document = manifest_documents.get(case.document_id)
        if manifest_document and manifest_document[1].is_file():
            return manifest_document[1]
        return None

    return resolve


class CurrentPipelineRetriever:
    """Thin adapter over production V3 chunking, retrieval, and reranking.

    Production imports are intentionally lazy so dataset/matcher/runner tests do
    not initialize embedding or cross-encoder dependencies.
    """

    def __init__(self) -> None:
        from core.config import get_settings

        settings = get_settings()
        self.embedding_model = settings.embedding_model_path
        self.reranker_model = settings.rerank_model_version

    def __call__(
        self, case: EvaluationCase, document_path: Path, limit: int
    ) -> Sequence[RetrievedChunk]:
        from core.config import get_settings
        from services.audit_agent import _load_pdf_pages
        from services.parser_quality_gate import analyze_parser_quality
        from services.reranker import rerank_candidates
        from services.retrieval_hybrid import (
            _index_vector_children,
            build_parent_child_chunks,
            retrieve_hybrid_for_risk,
        )
        from services.risk_query_builder import build_risk_queries
        from services.v3_types import SecurityContext

        settings = get_settings()
        self.embedding_model = settings.embedding_model_path
        self.reranker_model = settings.rerank_model_version
        suffix = document_path.suffix.lower()
        if suffix == ".pdf":
            page_texts = _load_pdf_pages(str(document_path))
        elif suffix in {".txt", ".md"}:
            text = document_path.read_text(encoding="utf-8")
            page_texts = text.split("\f")
        else:
            raise ValueError(f"unsupported document type: {suffix or '<none>'}")
        if not page_texts:
            raise ValueError("document contains no extractable pages")

        eval_id = hashlib.sha256(case.case_id.encode("utf-8")).hexdigest()[:16]
        security_context = SecurityContext(
            tenant_id="offline-eval",
            org_id="offline-eval",
            user_id="offline-eval",
            permission_scope="evaluation:read",
            task_id=f"eval-{eval_id}",
            document_id=case.document_id,
            contract_id=case.document_id,
        )
        parents, children = build_parent_child_chunks(
            page_texts,
            security_context,
            settings,
            analyze_parser_quality(page_texts),
        )
        vector_store = None
        if settings.rag_mode in {"vector", "hybrid"}:
            try:
                vector_store = _index_vector_children(children, security_context, settings)
            except Exception:
                # This mirrors the production V3 fallback to lexical retrieval.
                vector_store = None
        retrieval = retrieve_hybrid_for_risk(
            sec=security_context,
            settings=settings,
            parent_chunks=parents,
            child_chunks=children,
            expanded_queries=build_risk_queries(
                {
                    "riskType": case.risk_type or "",
                    "riskDesc": case.query,
                    "clauseTitle": case.query,
                }
            )["expanded_queries"],
            risk_type=case.risk_type or "",
            vector_store=vector_store,
        )
        reranked, _ = rerank_candidates(
            query=case.query,
            candidates=list(retrieval.candidates),
            settings=settings,
        )
        return [
            RetrievedChunk(
                chunk_id=candidate.child_id or candidate.candidate_id,
                parent_id=candidate.parent_id or None,
                page=candidate.page_no,
                score=float(
                    candidate.metadata.get("rerank_score", candidate.rrf_score)
                ),
                text=candidate.snippet,
            )
            for candidate in reranked[:limit]
        ]


def _empty_case_result(
    case: EvaluationCase, top_ks: Sequence[int], status: str, error: str | None = None
) -> dict[str, Any]:
    metrics = calculate_case_metrics([], len(case.expected_evidence), top_ks)
    return {
        "case_id": case.case_id,
        "document_id": case.document_id,
        "query": case.query,
        "status": status,
        "error_review_category": case.metadata.error_review_category,
        "retrieval_executed": status == "retrieval_error",
        "retrieval_successful": False,
        **metrics,
        "latency_ms": None,
        "matched_evidence": [],
        "top_results": [],
        "error": error,
    }


def evaluate_case(
    case: EvaluationCase,
    retriever: Retriever,
    document_resolver: DocumentResolver,
    top_ks: Sequence[int] = DEFAULT_TOP_KS,
    min_text_coverage: float = 0.7,
    require_page_match: bool = True,
) -> dict[str, Any]:
    document_path = document_resolver(case)
    if document_path is None:
        return _empty_case_result(case, top_ks, "document_not_found")

    started = perf_counter()
    try:
        chunks = list(retriever(case, document_path, max(top_ks)))
    except Exception as error:
        result = _empty_case_result(case, top_ks, "retrieval_error", str(error))
        result["latency_ms"] = round((perf_counter() - started) * 1000, 3)
        return result
    latency_ms = round((perf_counter() - started) * 1000, 3)

    relevance: list[list[bool]] = []
    top_results: list[dict[str, Any]] = []
    best_gold_matches: dict[int, dict[str, Any]] = {}
    for rank, chunk in enumerate(chunks, start=1):
        row: list[bool] = []
        matched_gold: list[int] = []
        for gold_index, gold in enumerate(case.expected_evidence):
            match = match_evidence(
                chunk,
                gold,
                min_text_coverage=min_text_coverage,
                require_page_match=require_page_match,
            )
            row.append(match.matched)
            if match.matched:
                matched_gold.append(gold_index)
                current = best_gold_matches.get(gold_index)
                if current is None or match.text_coverage > current["text_coverage"]:
                    best_gold_matches[gold_index] = {
                        "gold_index": gold_index,
                        "rank": rank,
                        "page": gold.page,
                        "text": gold.text,
                        "text_coverage": round(match.text_coverage, 6),
                    }
        relevance.append(row)
        top_results.append(
            {
                "rank": rank,
                "chunk_id": chunk.chunk_id,
                "parent_id": chunk.parent_id,
                "page": chunk.page,
                "score": chunk.score,
                "text_preview": chunk.text[:500],
                "matched_gold": matched_gold,
            }
        )

    metrics = calculate_case_metrics(relevance, len(case.expected_evidence), top_ks)
    matched_count = len(best_gold_matches)
    if not case.expected_evidence:
        status = "no_expected_evidence"
    elif matched_count == 0:
        status = "no_relevant_evidence_retrieved"
    elif matched_count < len(case.expected_evidence):
        status = "partial_evidence_retrieved"
    else:
        status = "success"
    return {
        "case_id": case.case_id,
        "document_id": case.document_id,
        "query": case.query,
        "status": status,
        "error_review_category": case.metadata.error_review_category,
        "retrieval_executed": True,
        "retrieval_successful": True,
        **metrics,
        "latency_ms": latency_ms,
        "matched_evidence": [best_gold_matches[i] for i in sorted(best_gold_matches)],
        "top_results": top_results,
        "error": None,
    }


def _git_commit(repo_dir: Path) -> str:
    try:
        return subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={repo_dir.as_posix()}",
                "rev-parse",
                "HEAD",
            ],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def run_evaluation(
    *,
    dataset_path: Path,
    retriever: Retriever,
    document_resolver: DocumentResolver,
    top_ks: Sequence[int] = DEFAULT_TOP_KS,
    profile: str = "current",
    min_text_coverage: float = 0.7,
    require_page_match: bool = True,
    embedding_model: str = "",
    reranker_model: str = "",
    include_draft: bool = False,
) -> dict[str, Any]:
    if profile != "current":
        raise ValueError("only the 'current' retrieval profile is supported")
    dataset_cases = load_dataset(dataset_path)
    cases = select_evaluation_cases(dataset_cases, include_draft=include_draft)
    case_results = [
        evaluate_case(
            case,
            retriever,
            document_resolver,
            top_ks,
            min_text_coverage,
            require_page_match,
        )
        for case in cases
    ]
    now = datetime.now(timezone.utc)
    return {
        "metadata": {
            "dataset": str(dataset_path.resolve()),
            "dataset_version": "v1",
            "profile": profile,
            "case_count": len(cases),
            "dataset_case_count": len(dataset_cases),
            "excluded_draft_count": len(dataset_cases) - len(cases),
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "git_commit": _git_commit(Path(__file__).resolve().parents[3]),
            "embedding_model": embedding_model,
            "reranker_model": reranker_model,
            "min_text_coverage": min_text_coverage,
            "require_page_match": require_page_match,
        },
        "coverage": calculate_evaluation_coverage(case_results),
        "metrics": aggregate_retrieval_metrics(case_results, top_ks),
        "cases": case_results,
    }


def _parse_top_ks(value: str) -> tuple[int, ...]:
    try:
        values = tuple(sorted(set(int(item.strip()) for item in value.split(","))))
    except ValueError as error:
        raise argparse.ArgumentTypeError("top-k must be comma-separated integers") from error
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("top-k values must be positive")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate current retrieval pipeline")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--profile", default="current", choices=("current",))
    parser.add_argument("--top-k", type=_parse_top_ks, default=DEFAULT_TOP_KS)
    parser.add_argument("--documents-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-text-coverage", type=float, default=0.7)
    parser.add_argument("--no-page-match", action="store_true")
    parser.add_argument("--include-draft", action="store_true")
    args = parser.parse_args()

    retriever = CurrentPipelineRetriever()
    report = run_evaluation(
        dataset_path=args.dataset,
        retriever=retriever,
        document_resolver=build_document_resolver(
            args.dataset, args.documents_dir, args.manifest
        ),
        top_ks=args.top_k,
        profile=args.profile,
        min_text_coverage=args.min_text_coverage,
        require_page_match=not args.no_page_match,
        include_draft=args.include_draft,
    )
    report["metadata"]["embedding_model"] = retriever.embedding_model
    report["metadata"]["reranker_model"] = retriever.reranker_model

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or Path(__file__).resolve().parents[1] / "reports" / f"retrieval_eval_{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(output.resolve()))


if __name__ == "__main__":
    main()
