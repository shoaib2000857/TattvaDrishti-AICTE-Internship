from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "LLM MalignOps Shield"
    environment: str = Field("dev", validation_alias="APP_ENV")
    secret_key: str = Field("super-secret-key", validation_alias="APP_SECRET")
    database_url: str = Field("sqlite:///./data/app.db", env="DATABASE_URL")
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    sharing_allowed_regions: List[str] = Field(
        default_factory=lambda: ["USA", "EU", "IN", "AUS"]
    )
    watermark_secret: str = Field(
        "default-watermark-seed",
        validation_alias="WATERMARK_SEED",
    )
    # Hugging Face AI Detection
    hf_model_name: str = Field("disabled", env="HF_MODEL_NAME")
    hf_tokenizer_name: str = Field("disabled", env="HF_TOKENIZER_NAME")
    hf_device: int = Field(-1, env="HF_DEVICE")  # -1 CPU, >=0 GPU id
    hf_score_threshold: float = Field(0.6, env="HF_SCORE_THRESHOLD")
    disable_ai_models: bool = Field(False, env="DISABLE_AI_MODELS")
    
    # Ollama Configuration (for semantic risk analysis)
    ollama_model: str = Field("qwen2.5:7b", env="OLLAMA_MODEL")
    ollama_enabled: bool = Field(True, env="OLLAMA_ENABLED")  # Enable by default
    ollama_host: str = Field("http://localhost:11434", env="OLLAMA_HOST")
    ollama_timeout: int = Field(30, env="OLLAMA_TIMEOUT")
    ollama_prompt_chars: int = Field(2000, env="OLLAMA_PROMPT_CHARS")
    ollama_timeout_ceiling: int = Field(90, env="OLLAMA_TIMEOUT_CEILING")
    ollama_keep_alive: str = Field("10m", env="OLLAMA_KEEP_ALIVE")
    ollama_num_ctx: int = Field(4096, env="OLLAMA_NUM_CTX")
    ollama_num_predict: int = Field(280, env="OLLAMA_NUM_PREDICT")
    ollama_temperature: float = Field(0.1, env="OLLAMA_TEMPERATURE")
    ollama_micro_batch_size: int = Field(4, env="OLLAMA_MICRO_BATCH_SIZE")
    ollama_micro_batch_chars: int = Field(8000, env="OLLAMA_MICRO_BATCH_CHARS")

    # Batch ingestion. Limits are deliberately bounded so one upload cannot
    # monopolise a worker or exhaust model memory.
    batch_max_records: int = Field(5000, env="BATCH_MAX_RECORDS")
    batch_max_file_bytes: int = Field(25 * 1024 * 1024, env="BATCH_MAX_FILE_BYTES")
    batch_parallelism: int = Field(4, env="BATCH_PARALLELISM")
    batch_ai_model_size: int = Field(16, env="BATCH_AI_MODEL_SIZE")
    batch_ollama_parallelism: int = Field(1, env="BATCH_OLLAMA_PARALLELISM")

    # Narrative graph matching. The engine combines concept-normalised token,
    # character, entity, and tag signals to identify paraphrased campaigns.
    narrative_similarity_threshold: float = Field(0.36, env="NARRATIVE_SIMILARITY_THRESHOLD")
    narrative_candidate_limit: int = Field(5000, env="NARRATIVE_CANDIDATE_LIMIT")
    narrative_candidates_per_item: int = Field(250, env="NARRATIVE_CANDIDATES_PER_ITEM")
    narrative_major_cluster_size: int = Field(3, env="NARRATIVE_MAJOR_CLUSTER_SIZE")
    narrative_neighbors_per_item: int = Field(20, env="NARRATIVE_NEIGHBORS_PER_ITEM")

    # Investigator-requested similarity uses the stored narrative feature index.
    # It is intentionally on-demand and does not affect ingestion or scoring.
    similar_message_threshold: float = Field(0.36, env="SIMILAR_MESSAGE_THRESHOLD")
    similar_message_limit: int = Field(20, env="SIMILAR_MESSAGE_LIMIT")

    # Routine inter-node sharing. Payloads are protected with AES-256-GCM even
    # when a development node is temporarily unavailable. Production nodes
    # should expose HTTPS endpoints and set SECURE_TRANSFER_REQUIRE_TLS=true.
    secure_transfer_key: str = Field(
        "LULSnIHlBjTSfWDfqVl0kTV9qXUFN0EpGbynAB_34TM=",
        env="SECURE_TRANSFER_KEY",
    )
    secure_transfer_key_id: str = Field("tattvadrishti-demo-key-v1", env="SECURE_TRANSFER_KEY_ID")
    secure_transfer_node_id: str = Field("analyst-node", env="SECURE_TRANSFER_NODE_ID")
    secure_transfer_nodes: str = Field(
        "USA=http://localhost:8001,EU=http://localhost:8002,"
        "IN=http://localhost:8003,AUS=http://localhost:8004",
        env="SECURE_TRANSFER_NODES",
    )
    secure_transfer_require_tls: bool = Field(False, env="SECURE_TRANSFER_REQUIRE_TLS")
    secure_transfer_verify_tls: bool = Field(True, env="SECURE_TRANSFER_VERIFY_TLS")
    secure_transfer_timeout: int = Field(8, env="SECURE_TRANSFER_TIMEOUT")
    secure_transfer_ttl_seconds: int = Field(300, env="SECURE_TRANSFER_TTL_SECONDS")
    
    # Federated Blockchain Configuration
    federated_encryption_key: str = Field(
        "LULSnIHlBjTSfWDfqVl0kTV9qXUFN0EpGbynAB_34TM=",
        validation_alias="BLOCK_ENCRYPTION_KEY",
    )
    federated_nodes: str = Field("http://localhost:8000,http://localhost:8001,http://localhost:8002,http://localhost:8003,http://localhost:8004", env="FEDERATED_NODES")
    
    # Sightengine Image Detection API
    sightengine_api_user: str = Field("", env="SIGHTENGINE_API_USER")
    sightengine_api_secret: str = Field("", env="SIGHTENGINE_API_SECRET")
    node_url: str = Field("http://localhost:8000", env="NODE_URL")
    main_api_url: str = Field("http://localhost:8000", env="MAIN_API_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(Settings.Config.env_file)
    if config_path.exists():
        return Settings(_env_file=config_path)
    return Settings()
