from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

GiskardScanMode = Literal["off", "full"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — Groq
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_max_tokens: int = Field(default=4096, alias="GROQ_MAX_TOKENS")

    # Vector store
    chromadb_persist_dir: str = Field(default="./data/chromadb", alias="CHROMADB_PERSIST_DIR")
    chromadb_collection_name: str = Field(default="ori_incidents", alias="CHROMADB_COLLECTION_NAME")

    # Embeddings
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    embedding_cache_dir: str = Field(default="./data/embedding_cache", alias="EMBEDDING_CACHE_DIR")

    # Data paths
    raw_data_dir: str = Field(default="./data/raw", alias="RAW_DATA_DIR")
    processed_data_dir: str = Field(default="./data/processed", alias="PROCESSED_DATA_DIR")
    synthetic_data_path: str = Field(
        default="./data/synthetic/synthetic_incidents.json", alias="SYNTHETIC_DATA_PATH"
    )

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_reload: bool = Field(default=True, alias="API_RELOAD")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8501", alias="CORS_ORIGINS"
    )

    # Giskard / governance eval (offline; caps LLM via sampling + cache)
    giskard_scan_enabled: bool = Field(default=True, alias="GISKARD_SCAN_ENABLED")
    giskard_hf_token: str = Field(default="", alias="GISKARD_HF_TOKEN")
    giskard_eval_sample_size: int = Field(default=5, alias="GISKARD_EVAL_SAMPLE_SIZE")
    giskard_eval_pool_size: int = Field(default=50, alias="GISKARD_EVAL_POOL_SIZE")
    giskard_eval_seed: int = Field(default=42, alias="GISKARD_EVAL_SEED")
    # Live UI: one-row giskard.scan after Groq (no extra Groq in predict). Batch: giskard-scan mode.
    giskard_scan_mode: str = Field(default="off", alias="GISKARD_SCAN_MODE")
    giskard_live_scan: bool = Field(default=True, alias="GISKARD_LIVE_SCAN")
    giskard_use_full_scan: bool = Field(default=True, alias="GISKARD_USE_FULL_SCAN")
    input_validation_cases_path: str = Field(
        default="./testcases/input_validation.json",
        validation_alias=AliasChoices(
            "INPUT_VALIDATION_CASES_PATH",
            "INGESTION_TESTCASES_PATH",
        ),
    )
    giskard_reuse_cache: bool = Field(default=True, alias="GISKARD_REUSE_CACHE")
    governance_cache_path: str = Field(
        default="./data/governance/rca_predictions.json",
        validation_alias=AliasChoices(
            "GOVERNANCE_CACHE_PATH",
            "GISKARD_EVAL_CACHE_PATH",
        ),
    )
    giskard_eval_report_dir: str = Field(default="./reports", alias="GISKARD_EVAL_REPORT_DIR")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="pretty", alias="LOG_FORMAT")
    log_file: str = Field(default="./logs/ori.log", alias="LOG_FILE")

    @property
    def effective_giskard_mode(self) -> GiskardScanMode:
        if not self.giskard_scan_enabled:
            return "off"
        mode = (self.giskard_scan_mode or "off").strip().lower()
        if mode in ("off", "full"):
            return mode  # type: ignore[return-value]
        return "off"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
