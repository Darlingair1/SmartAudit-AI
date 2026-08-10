from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


DocumentSourceType = Literal["public", "synthetic", "anonymized"]


class ManifestDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_id: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    source_type: DocumentSourceType
    sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: str
    documents: list[ManifestDocument]


class ManifestValidationError(ValueError):
    pass


def load_document_manifest(path: str | Path) -> DocumentManifest:
    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Document manifest not found: {manifest_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ManifestValidationError(
            f"Invalid document manifest JSON in {manifest_path}: {error.msg}"
        ) from error
    try:
        manifest = DocumentManifest.model_validate(raw)
    except ValidationError as error:
        raise ManifestValidationError(
            f"Invalid document manifest {manifest_path}: {error}"
        ) from error
    seen: set[str] = set()
    for document in manifest.documents:
        if document.document_id in seen:
            raise ManifestValidationError(
                f"Duplicate document_id in {manifest_path}: {document.document_id}"
            )
        seen.add(document.document_id)
    return manifest


def resolve_manifest_document(manifest_path: Path, document: ManifestDocument) -> Path:
    path = Path(document.path).expanduser()
    if not path.is_absolute():
        path = manifest_path.resolve().parent / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_document_map(
    manifest_path: str | Path,
) -> dict[str, tuple[ManifestDocument, Path]]:
    path = Path(manifest_path).expanduser().resolve()
    manifest = load_document_manifest(path)
    return {
        document.document_id: (document, resolve_manifest_document(path, document))
        for document in manifest.documents
    }
