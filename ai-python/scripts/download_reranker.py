from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from huggingface_hub import snapshot_download


def _is_ready(model_dir: Path) -> bool:
    if not model_dir.exists():
        return False
    if not (model_dir / "config.json").exists():
        return False
    has_weight = any(
        p.name.startswith("model")
        or p.name.endswith(".safetensors")
        or p.name.endswith(".bin")
        for p in model_dir.glob("*")
    )
    return has_weight


def _download_via_snapshot(local_dir: Path) -> Path:
    endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
    return Path(
        snapshot_download(
            repo_id="BAAI/bge-reranker-v2-m3",
            local_dir=str(local_dir),
            endpoint=endpoint,
        )
    )


def _safe_rmtree(path: Path, retries: int = 3, delay_seconds: float = 0.5) -> None:
    if not path.exists():
        return

    def _onerror(func, target, exc_info):  # type: ignore[no-untyped-def]
        try:
            os.chmod(target, 0o777)
            func(target)
        except Exception:
            pass

    last_err: Exception | None = None
    for _ in range(retries):
        try:
            shutil.rmtree(path, onerror=_onerror)
            if not path.exists():
                return
        except Exception as ex:
            last_err = ex
        time.sleep(delay_seconds)
    if path.exists():
        raise RuntimeError(f"failed to delete directory: {path}") from last_err


def _run_git(args: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(args, check=True, cwd=str(cwd) if cwd else None)


def _safe_replace_or_copy(src: Path, dst: Path, retries: int = 5, delay_seconds: float = 1.0) -> None:
    # Try fast atomic replace first.
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            if dst.exists():
                _safe_rmtree(dst)
            src.replace(dst)
            return
        except Exception as ex:
            last_err = ex
            time.sleep(delay_seconds)

    # Fallback path on Windows lock issues:
    # copy tree to destination, then clean src.
    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    _safe_rmtree(src)
    if not _is_ready(dst):
        raise RuntimeError(f"copied model directory but validation failed: {dst}") from last_err


def _download_via_git_lfs(local_dir: Path) -> None:
    repo_url = "https://hf-mirror.com/BAAI/bge-reranker-v2-m3"

    # Case 1: target is already a git repo -> directly pull + lfs pull.
    if (local_dir / ".git").exists():
        _run_git(["git", "-C", str(local_dir), "pull", "--ff-only"])
        _run_git(["git", "-C", str(local_dir), "lfs", "pull"])
        return

    # Case 2: target exists but is not a git repo -> clone to temp dir and replace.
    tmp_dir = local_dir.with_name(local_dir.name + ".tmp_download")
    if tmp_dir.exists():
        _safe_rmtree(tmp_dir)
    _run_git(["git", "clone", repo_url, str(tmp_dir)])
    _run_git(["git", "-C", str(tmp_dir), "lfs", "pull"])

    _safe_replace_or_copy(tmp_dir, local_dir)


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    local_dir = project_root / "models" / "bge-reranker-v2-m3"
    local_dir.parent.mkdir(parents=True, exist_ok=True)

    if _is_ready(local_dir):
        print(f"Model already ready: {local_dir}")
        return

    # clean incomplete directory before retry to avoid metadata/cache conflicts
    if local_dir.exists():
        _safe_rmtree(local_dir)

    try:
        path = _download_via_snapshot(local_dir)
        if _is_ready(local_dir):
            print(f"Download completed via snapshot: {path}")
            return
        raise RuntimeError("snapshot download completed but model files are incomplete")
    except Exception as ex:
        print(f"[WARN] snapshot_download failed: {ex}")
        print("[INFO] fallback to git-lfs clone from hf-mirror ...")

    _download_via_git_lfs(local_dir)
    if not _is_ready(local_dir):
        raise RuntimeError(f"git-lfs download finished but model seems incomplete: {local_dir}")
    print(f"Download completed via git-lfs: {local_dir}")


if __name__ == "__main__":
    main()
