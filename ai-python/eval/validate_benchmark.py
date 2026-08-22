from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from eval.benchmark_manifest import manifest_document_map, sha256_file
from eval.dataset_loader import EvaluationCase, load_dataset
from eval.matching.evidence_matcher import normalize_text


class BenchmarkValidationError(ValueError):
    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__(
            "Benchmark validation failed:\n- " + "\n- ".join(self.errors)
        )


def _load_document_pages(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from services.document_parser import load_pdf_pages

        return load_pdf_pages(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8").split("\f")
    raise ValueError(f"unsupported document type: {suffix or '<none>'}")


def _validate_case(
    case: EvaluationCase,
    document_pages: list[str] | None,
) -> list[str]:
    errors: list[str] = []
    prefix = f"case_id={case.case_id}"
    if not case.expected_evidence:
        errors.append(f"{prefix}: expected_evidence is empty")
        return errors

    evidence_keys: set[tuple[int, str]] = set()
    normalized_pages = [normalize_text(page) for page in document_pages or []]
    for index, evidence in enumerate(case.expected_evidence):
        key = (evidence.page, normalize_text(evidence.text))
        if key in evidence_keys:
            errors.append(f"{prefix}: duplicate evidence at index {index}")
        evidence_keys.add(key)
        if document_pages is None:
            continue
        if evidence.page > len(document_pages):
            errors.append(
                f"{prefix}: evidence index {index} page {evidence.page} exceeds "
                f"document page count {len(document_pages)}"
            )
            continue
        if key[1] not in normalized_pages[evidence.page - 1]:
            errors.append(
                f"{prefix}: evidence index {index} cannot be located on page "
                f"{evidence.page}"
            )
    return errors


def validate_benchmark(
    dataset_path: str | Path,
    manifest_path: str | Path,
) -> dict[str, Any]:
    dataset = Path(dataset_path).expanduser().resolve()
    manifest = Path(manifest_path).expanduser().resolve()
    cases = load_dataset(dataset)
    documents = manifest_document_map(manifest)
    errors: list[str] = []
    pages_by_document: dict[str, list[str] | None] = {}

    for document_id, (entry, path) in documents.items():
        if not path.is_file():
            errors.append(f"document_id={document_id}: document not found: {path}")
            pages_by_document[document_id] = None
            continue
        actual_hash = sha256_file(path)
        if actual_hash.lower() != entry.sha256.lower():
            errors.append(
                f"document_id={document_id}: SHA256 mismatch; "
                f"expected {entry.sha256.lower()}, got {actual_hash}"
            )
        try:
            pages_by_document[document_id] = _load_document_pages(path)
        except (OSError, ValueError) as error:
            errors.append(f"document_id={document_id}: cannot parse document: {error}")
            pages_by_document[document_id] = None

    seen_queries: dict[tuple[str, str], str] = {}
    for case in cases:
        document = documents.get(case.document_id)
        if document is None:
            errors.append(
                f"case_id={case.case_id}: document_id not present in manifest: "
                f"{case.document_id}"
            )
            document_pages = None
        else:
            entry, _ = document
            if (
                case.metadata.source_type != "manually_annotated"
                and case.metadata.source_type != entry.source_type
            ):
                errors.append(
                    f"case_id={case.case_id}: source_type {case.metadata.source_type!r} "
                    f"does not match manifest source_type {entry.source_type!r}"
                )
            document_pages = pages_by_document.get(case.document_id)

        query_key = (case.document_id, normalize_text(case.query))
        duplicate_of = seen_queries.get(query_key)
        if duplicate_of:
            errors.append(
                f"case_id={case.case_id}: duplicate query of case_id={duplicate_of}"
            )
        else:
            seen_queries[query_key] = case.case_id
        errors.extend(_validate_case(case, document_pages))

    if errors:
        raise BenchmarkValidationError(errors)
    reviewed = sum(case.metadata.annotation_status == "reviewed" for case in cases)
    draft = sum(case.metadata.annotation_status == "draft" for case in cases)
    return {
        "dataset": str(dataset),
        "manifest": str(manifest),
        "document_count": len(documents),
        "case_count": len(cases),
        "reviewed_case_count": reviewed,
        "draft_case_count": draft,
        "status": "valid",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a retrieval benchmark")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_benchmark(args.dataset, args.manifest)
    except BenchmarkValidationError as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
