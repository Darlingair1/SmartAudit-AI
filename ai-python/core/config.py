import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def _to_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _first_non_empty(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip() != "":
            return value.strip()
    return default


def _split_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _llm_base_url() -> str:
    """Select the endpoint matching the configured provider."""
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider in {"openai-compatible", "openai", "azure-openai"}:
        return _first_non_empty(
            "OPENAI_BASE_URL",
            "DEEPSEEK_BASE_URL",
            default="https://api.deepseek.com",
        )
    return _first_non_empty(
        "DEEPSEEK_BASE_URL",
        "OPENAI_BASE_URL",
        default="https://api.deepseek.com",
    )


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "SmartAudit-AI Python Service")
    app_env: str = os.getenv("APP_ENV", "dev")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()

    default_model: str = _first_non_empty("LLM_MODEL", "DEEPSEEK_MODEL", default="deepseek-v4-flash")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
    llm_max_retries: int = min(5, max(0, int(os.getenv("LLM_MAX_RETRIES", "2"))))
    max_contract_chars: int = int(os.getenv("MAX_CONTRACT_CHARS", "40000"))
    map_chunk_pages: int = int(os.getenv("MAP_CHUNK_PAGES", "10"))
    map_chunk_overlap_pages: int = int(os.getenv("MAP_CHUNK_OVERLAP_PAGES", "1"))
    map_max_concurrency: int = int(os.getenv("MAP_MAX_CONCURRENCY", "4"))
    review_context_chars: int = int(os.getenv("REVIEW_CONTEXT_CHARS", "50000"))
    fallback_review_context_chars: int = int(os.getenv("FALLBACK_REVIEW_CONTEXT_CHARS", "6000"))
    fallback_workflow_single_pass: bool = _to_bool(os.getenv("FALLBACK_WORKFLOW_SINGLE_PASS"), default=True)
    rag_top_k_per_query: int = int(os.getenv("RAG_TOP_K_PER_QUERY", "2"))
    rag_max_chars: int = int(os.getenv("RAG_MAX_CHARS", "12000"))
    rag_mode: str = os.getenv("RAG_MODE", "hybrid").strip().lower()
    agent2_mode: str = os.getenv("AGENT2_MODE", "workflow").strip().lower()
    react_max_steps: int = int(os.getenv("REACT_MAX_STEPS", "8"))
    react_max_tool_calls: int = int(os.getenv("REACT_MAX_TOOL_CALLS", "12"))
    react_tool_timeout_ms: int = int(os.getenv("REACT_TOOL_TIMEOUT_MS", "2000"))
    react_retry_strict_once: bool = _to_bool(os.getenv("REACT_RETRY_STRICT_ONCE"), default=True)
    react_strict_max_steps: int = int(os.getenv("REACT_STRICT_MAX_STEPS", "6"))
    react_strict_max_tool_calls: int = int(os.getenv("REACT_STRICT_MAX_TOOL_CALLS", "8"))
    react_require_evidence_before_final: bool = _to_bool(
        os.getenv("REACT_REQUIRE_EVIDENCE_BEFORE_FINAL"),
        default=True,
    )
    react_min_evidence_tool_calls: int = int(os.getenv("REACT_MIN_EVIDENCE_TOOL_CALLS", "1"))
    react_drop_unmatched_excerpt: bool = _to_bool(os.getenv("REACT_DROP_UNMATCHED_EXCERPT"), default=True)
    react_autofill_legal_basis: bool = _to_bool(os.getenv("REACT_AUTOFILL_LEGAL_BASIS"), default=True)
    react_trace_enabled: bool = _to_bool(os.getenv("REACT_TRACE_ENABLED"), default=True)
    react_trace_include_detail: bool = _to_bool(os.getenv("REACT_TRACE_INCLUDE_DETAIL"), default=False)
    react_trace_dir: str = os.getenv(
        "REACT_TRACE_DIR",
        str((BASE_DIR.parent / "logs" / "react-traces").resolve()),
    )
    react_use_native_tool_calling: bool = _to_bool(os.getenv("REACT_USE_NATIVE_TOOL_CALLING"), default=True)
    react_final_allow_tools: bool = _to_bool(os.getenv("REACT_FINAL_ALLOW_TOOLS"), default=False)
    react_finalize_on_budget_exhaust: bool = _to_bool(os.getenv("REACT_FINALIZE_ON_BUDGET_EXHAUST"), default=True)
    react_obs_max_chars: int = int(os.getenv("REACT_OBS_MAX_CHARS", "1200"))
    react_obs_topk_cap: int = int(os.getenv("REACT_OBS_TOPK_CAP", "2"))
    embedding_model_path: str = os.getenv(
        "EMBEDDING_MODEL_PATH",
        str((BASE_DIR.parent / "models" / "bge-m3").resolve()),
    )
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    embedding_normalize: bool = _to_bool(os.getenv("EMBEDDING_NORMALIZE"), default=True)
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
    vector_chunk_size: int = int(os.getenv("VECTOR_CHUNK_SIZE", "900"))
    vector_chunk_overlap: int = int(os.getenv("VECTOR_CHUNK_OVERLAP", "120"))
    vector_top_k: int = int(os.getenv("VECTOR_TOP_K", "3"))
    vector_max_chars: int = int(os.getenv("VECTOR_MAX_CHARS", "10000"))
    chroma_persist_dir: str = os.getenv(
        "CHROMA_PERSIST_DIR",
        str((BASE_DIR.parent / "storage" / "chroma").resolve()),
    )
    chroma_collection_prefix: str = os.getenv("CHROMA_COLLECTION_PREFIX", "smartaudit-task")
    vector_reindex_each_run: bool = _to_bool(os.getenv("VECTOR_REINDEX_EACH_RUN"), default=True)

    openai_api_key: str = _first_non_empty(
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        default="",
    )
    openai_base_url: str = _llm_base_url()

    callback_timeout_seconds: int = int(os.getenv("CALLBACK_TIMEOUT_SECONDS", "15"))
    callback_retry_times: int = min(5, max(1, int(os.getenv("CALLBACK_RETRY_TIMES", "3"))))
    callback_retry_interval_seconds: float = float(os.getenv("CALLBACK_RETRY_INTERVAL_SECONDS", "2"))
    callback_verify_ssl: bool = _to_bool(os.getenv("CALLBACK_VERIFY_SSL"), default=True)
    callback_signature_enabled: bool = _to_bool(os.getenv("CALLBACK_SIGNATURE_ENABLED"), default=True)
    callback_signature_secret: str = _first_non_empty(
        "CALLBACK_SIGNATURE_SECRET",
        "SMARTAUDIT_CALLBACK_SIGNATURE_SECRET",
        default="",
    )
    internal_api_token: str = os.getenv("INTERNAL_API_TOKEN", "").strip()

    # -----------------------
    # V3 feature flags
    # -----------------------
    rag_v3_enabled: bool = _to_bool(os.getenv("RAG_V3_ENABLED"), default=True)
    parent_child_enabled: bool = _to_bool(os.getenv("PARENT_CHILD_ENABLED"), default=True)
    legal_bm25_enabled: bool = _to_bool(os.getenv("LEGAL_BM25_ENABLED"), default=True)
    risk_query_builder_enabled: bool = _to_bool(os.getenv("RISK_QUERY_BUILDER_ENABLED"), default=True)
    rrf_enabled: bool = _to_bool(os.getenv("RRF_ENABLED"), default=True)
    rerank_enabled: bool = _to_bool(os.getenv("RERANK_ENABLED"), default=True)
    llm_judge_enabled: bool = _to_bool(os.getenv("LLM_JUDGE_ENABLED"), default=True)
    final_check_enabled: bool = _to_bool(os.getenv("FINAL_CHECK_ENABLED"), default=True)
    rag_eval_enabled: bool = _to_bool(os.getenv("RAG_EVAL_ENABLED"), default=False)

    # -----------------------
    # V3 tenant isolation
    # -----------------------
    strict_tenant_isolation: bool = _to_bool(os.getenv("STRICT_TENANT_ISOLATION"), default=False)
    tenant_filter_required: bool = _to_bool(os.getenv("TENANT_FILTER_REQUIRED"), default=True)
    default_tenant_id: str = os.getenv("DEFAULT_TENANT_ID", "default").strip()
    default_org_id: str = os.getenv("DEFAULT_ORG_ID", "default-org").strip()
    default_user_id: str = os.getenv("DEFAULT_USER_ID", "system").strip()
    default_permission_scope: str = os.getenv("DEFAULT_PERMISSION_SCOPE", "audit:read").strip()

    # -----------------------
    # V3 budget controller
    # -----------------------
    max_expanded_queries_per_risk: int = int(os.getenv("MAX_EXPANDED_QUERIES_PER_RISK", "6"))
    max_risk_candidates_before_rrf: int = int(os.getenv("MAX_RISK_CANDIDATES_BEFORE_RRF", "120"))
    max_rrf_candidates_per_risk: int = int(os.getenv("MAX_RRF_CANDIDATES_PER_RISK", "40"))
    max_rerank_candidates_per_risk: int = int(os.getenv("MAX_RERANK_CANDIDATES_PER_RISK", "10"))
    max_judge_evidence_per_risk: int = int(os.getenv("MAX_JUDGE_EVIDENCE_PER_RISK", "8"))
    max_parent_context_tokens: int = int(os.getenv("MAX_PARENT_CONTEXT_TOKENS", "1200"))
    max_total_context_tokens_per_risk: int = int(os.getenv("MAX_TOTAL_CONTEXT_TOKENS_PER_RISK", "2200"))

    # -----------------------
    # V3 parser/chunking
    # -----------------------
    parser_version: str = os.getenv("PARSER_VERSION", "parser_v3").strip()
    chunk_version: str = os.getenv("CHUNK_VERSION", "pc_v1").strip()
    source_type_default: str = os.getenv("SOURCE_TYPE_DEFAULT", "BODY").strip()
    parent_chunk_min_tokens: int = int(os.getenv("PARENT_CHUNK_MIN_TOKENS", "500"))
    parent_chunk_max_tokens: int = int(os.getenv("PARENT_CHUNK_MAX_TOKENS", "1200"))
    child_chunk_size_tokens: int = int(os.getenv("CHILD_CHUNK_SIZE_TOKENS", "250"))
    child_chunk_overlap_tokens: int = int(os.getenv("CHILD_CHUNK_OVERLAP_TOKENS", "60"))

    # -----------------------
    # V3 retrieval and RRF
    # -----------------------
    bm25_top_k: int = int(os.getenv("BM25_TOP_K", "30"))
    vector_top_k_v3: int = int(os.getenv("VECTOR_TOP_K_V3", os.getenv("VECTOR_TOP_K", "30")))
    rrf_top_k: int = int(os.getenv("RRF_TOP_K", "40"))
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    risk_query_template_version: str = os.getenv("RISK_QUERY_TEMPLATE_VERSION", "v1").strip()
    rrf_config_version: str = os.getenv("RRF_CONFIG_VERSION", "rrf_v1").strip()
    bm25_index_version: str = os.getenv("BM25_INDEX_VERSION", "bm25_v1").strip()
    vector_index_version: str = os.getenv("VECTOR_INDEX_VERSION", "vector_v1").strip()

    # -----------------------
    # V3 rerank
    # -----------------------
    rerank_model_path: str = os.getenv("RERANK_MODEL_PATH", "BAAI/bge-reranker-v2-m3").strip()
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N", "10"))
    rerank_batch_size: int = int(os.getenv("RERANK_BATCH_SIZE", "8"))
    rerank_max_length: int = int(os.getenv("RERANK_MAX_LENGTH", "512"))
    rerank_timeout_ms: int = int(os.getenv("RERANK_TIMEOUT_MS", "3000"))
    rerank_strict: bool = _to_bool(os.getenv("RERANK_STRICT"), default=False)
    rerank_model_version: str = os.getenv("RERANK_MODEL_VERSION", "bge-reranker-v2-m3").strip()

    # -----------------------
    # V3 judge/final-check
    # -----------------------
    judge_mode: str = os.getenv("JUDGE_MODE", "observe").strip().lower()
    judge_reject_policy: str = os.getenv("JUDGE_REJECT_POLICY", "soft").strip().lower()
    judge_top_n: int = int(os.getenv("JUDGE_TOP_N", "8"))
    judge_min_confidence: float = float(os.getenv("JUDGE_MIN_CONFIDENCE", "0.75"))
    judge_timeout_ms: int = int(os.getenv("JUDGE_TIMEOUT_MS", "8000"))
    judge_prompt_version: str = os.getenv("JUDGE_PROMPT_VERSION", "v3_judge").strip()
    final_check_timeout_ms: int = int(os.getenv("FINAL_CHECK_TIMEOUT_MS", "5000"))
    final_check_prompt_version: str = os.getenv("FINAL_CHECK_PROMPT_VERSION", "v3_final_check").strip()
    judge_schema_version: str = os.getenv("JUDGE_SCHEMA_VERSION", "v1").strip()
    final_check_policy_version: str = os.getenv("FINAL_CHECK_POLICY_VERSION", "v1").strip()

    # -----------------------
    # V3 trace compliance
    # -----------------------
    debug_trace_enabled: bool = _to_bool(os.getenv("DEBUG_TRACE_ENABLED"), default=False)
    trace_store_full_text: bool = _to_bool(os.getenv("TRACE_STORE_FULL_TEXT"), default=False)
    trace_retention_days: int = int(os.getenv("TRACE_RETENTION_DAYS", "7"))
    pii_masking_enabled: bool = _to_bool(os.getenv("PII_MASKING_ENABLED"), default=True)
    trace_encryption_enabled: bool = _to_bool(os.getenv("TRACE_ENCRYPTION_ENABLED"), default=True)
    trace_secret: str = _first_non_empty("TRACE_SECRET", default="")
    rag_metrics_log_enabled: bool = _to_bool(os.getenv("RAG_METRICS_LOG_ENABLED"), default=True)
    rag_cache_ttl_seconds: int = int(os.getenv("RAG_CACHE_TTL_SECONDS", "3600"))
    judge_cache_ttl_seconds: int = int(os.getenv("JUDGE_CACHE_TTL_SECONDS", "86400"))

    # -----------------------
    # V3 eval/ablation
    # -----------------------
    eval_dataset_path: str = os.getenv("EVAL_DATASET_PATH", str((BASE_DIR / "eval" / "rag_eval_set.jsonl").resolve()))
    eval_output_dir: str = os.getenv("EVAL_OUTPUT_DIR", str((BASE_DIR / "eval" / "reports").resolve()))
    eval_baseline_profile: str = os.getenv("EVAL_BASELINE_PROFILE", "old_pipeline").strip()
    eval_ablation_profiles: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv(
                "EVAL_ABLATION_PROFILES",
                "old_pipeline,v3_without_rerank,v3_without_judge,v3_full_observe",
            )
        )
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
