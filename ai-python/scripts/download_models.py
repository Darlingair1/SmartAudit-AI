from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import snapshot_download


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCK_FILE = PROJECT_ROOT / "ai-python" / "models.lock.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_models() -> dict[str, dict[str, str]]:
    return json.loads(LOCK_FILE.read_text(encoding="utf-8"))["models"]


def verify_model(name: str, metadata: dict[str, str], destination: Path) -> None:
    weight = destination / metadata["weight_file"]
    if not weight.is_file():
        raise RuntimeError(f"missing model weight: {weight}")
    actual = sha256_file(weight)
    if actual != metadata["sha256"]:
        raise RuntimeError(f"SHA256 mismatch for {name}: expected {metadata['sha256']}, got {actual}")


def download_model(name: str, metadata: dict[str, str], models_dir: Path, verify_only: bool) -> None:
    destination = models_dir / name
    if not verify_only:
        snapshot_download(
            repo_id=metadata["repo_id"],
            revision=metadata["revision"],
            local_dir=str(destination),
            endpoint=os.getenv("HF_ENDPOINT", "https://huggingface.co"),
        )
    verify_model(name, metadata, destination)
    print(f"Verified {name} at revision {metadata['revision']}")


def main() -> None:
    models = load_models()
    parser = argparse.ArgumentParser(description="Download and verify optional SmartAudit BGE models")
    parser.add_argument("model", choices=["all", *models.keys()], nargs="?", default="all")
    parser.add_argument("--models-dir", type=Path, default=PROJECT_ROOT / "models")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    selected = models.items() if args.model == "all" else [(args.model, models[args.model])]
    for name, metadata in selected:
        download_model(name, metadata, args.models_dir.resolve(), args.verify_only)


if __name__ == "__main__":
    main()
