from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SourceType = Literal["synthetic", "public", "manually_annotated", "anonymized"]
AnnotationStatus = Literal["draft", "reviewed"]
ErrorReviewCategory = Literal[
    "TRUE_RETRIEVAL_MISS",
    "GOLD_LABEL_ERROR",
    "MATCHER_FALSE_NEGATIVE",
    "DOCUMENT_PARSE_ERROR",
    "PAGE_MAPPING_ERROR",
    "AMBIGUOUS_QUERY",
]


class ExpectedEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int = Field(..., ge=1, strict=True)
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class EvaluationMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_type: SourceType
    contract_type: str | None = None
    difficulty: str | None = None
    document_path: str | None = None
    purpose: str | None = None
    annotation_status: AnnotationStatus | None = None
    error_review_category: ErrorReviewCategory | None = None


class EvaluationCase(BaseModel):
    """Version 1 retrieval evaluation case.

    Extra fields are retained so later evaluation phases can add annotations
    without making this reader incompatible with older v1 tooling.
    """

    model_config = ConfigDict(extra="allow")

    case_id: str
    document_id: str
    query: str
    risk_type: str | None = None
    expected_answer: str | None = None
    expected_evidence: list[ExpectedEvidence]
    expected_reason_codes: list[str] = Field(default_factory=list)
    metadata: EvaluationMetadata

    @field_validator("case_id", "document_id", "query")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class DatasetValidationError(ValueError):
    def __init__(
        self,
        path: Path,
        line_number: int,
        message: str,
        case_id: str | None = None,
    ) -> None:
        self.path = path
        self.line_number = line_number
        self.case_id = case_id
        self.detail = message
        case_part = f", case_id={case_id!r}" if case_id else ""
        super().__init__(
            f"Invalid evaluation case in {path} at line {line_number}{case_part}: {message}"
        )


def _validation_message(error: ValidationError) -> str:
    first = error.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = str(first.get("msg", "validation failed"))
    if first.get("type") == "missing":
        return f'missing required field "{location}"'
    return f"{location}: {message}" if location else message


def load_dataset(path: str | Path) -> list[EvaluationCase]:
    """Load and strictly validate a UTF-8 JSONL evaluation dataset."""

    dataset_path = Path(path).expanduser().resolve()
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Evaluation dataset not found: {dataset_path}")

    cases: list[EvaluationCase] = []
    seen_case_ids: dict[str, int] = {}
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                value: Any = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise DatasetValidationError(
                    dataset_path,
                    line_number,
                    f"invalid JSON: {error.msg} (column {error.colno})",
                ) from error

            case_id = value.get("case_id") if isinstance(value, dict) else None
            if not isinstance(value, dict):
                raise DatasetValidationError(
                    dataset_path, line_number, "case must be a JSON object"
                )
            try:
                case = EvaluationCase.model_validate(value)
            except ValidationError as error:
                raise DatasetValidationError(
                    dataset_path,
                    line_number,
                    _validation_message(error),
                    str(case_id) if case_id is not None else None,
                ) from error

            if case.case_id in seen_case_ids:
                raise DatasetValidationError(
                    dataset_path,
                    line_number,
                    f"duplicate case_id; first declared at line {seen_case_ids[case.case_id]}",
                    case.case_id,
                )
            seen_case_ids[case.case_id] = line_number
            cases.append(case)

    return cases


def select_evaluation_cases(
    cases: Sequence[EvaluationCase], *, include_draft: bool = False
) -> list[EvaluationCase]:
    """Exclude explicitly draft annotations unless a caller opts in."""

    if include_draft:
        return list(cases)
    return [case for case in cases if case.metadata.annotation_status != "draft"]
