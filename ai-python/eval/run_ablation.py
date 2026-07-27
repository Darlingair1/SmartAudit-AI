from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

PROFILES = {
    "old_pipeline": {
        "RAG_V3_ENABLED": "false",
    },
    "v3_without_rerank": {
        "RAG_V3_ENABLED": "true",
        "RERANK_ENABLED": "false",
        "LLM_JUDGE_ENABLED": "true",
        "JUDGE_MODE": "observe",
    },
    "v3_without_judge": {
        "RAG_V3_ENABLED": "true",
        "RERANK_ENABLED": "true",
        "LLM_JUDGE_ENABLED": "false",
    },
    "v3_full_observe": {
        "RAG_V3_ENABLED": "true",
        "RERANK_ENABLED": "true",
        "LLM_JUDGE_ENABLED": "true",
        "JUDGE_MODE": "observe",
    },
}


def main() -> None:
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    out_dir = Path(__file__).resolve().parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"generated_at": now, "profiles": []}

    for name, env_patch in PROFILES.items():
        env = os.environ.copy()
        env.update(env_patch)
        # Placeholder runner: user can replace with their benchmark script.
        result = {
            "profile": name,
            "env_patch": env_patch,
            "status": "prepared",
            "note": "Integrate with your benchmark runner (e.g. _tmp_mode_once.py / API smoke).",
        }
        report["profiles"].append(result)

    (out_dir / f"ablation_{now}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

