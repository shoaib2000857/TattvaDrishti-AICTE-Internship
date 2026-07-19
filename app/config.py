from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "LLM MalignOps Shield"
    environment: str = Field("dev", env="APP_ENV")
    secret_key: str = Field("super-secret-key", env="APP_SECRET")
    database_url: str = Field("sqlite:///./data/app.db", env="DATABASE_URL")
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    sharing_allowed_regions: List[str] = Field(
        default_factory=lambda: ["USA", "EU", "IN", "AUS"]
    )
    watermark_secret: str = Field("default-watermark-seed", env="WATERMARK_SEED")
    # Hugging Face AI Detection
    hf_model_name: str = Field("disabled", env="HF_MODEL_NAME")
    hf_tokenizer_name: str = Field("disabled", env="HF_TOKENIZER_NAME")
    hf_device: int = Field(-1, env="HF_DEVICE")  # -1 CPU, >=0 GPU id
    hf_score_threshold: float = Field(0.6, env="HF_SCORE_THRESHOLD")
    
    # Ollama Configuration (for semantic risk analysis)
    ollama_model: str = Field("llama3.2:3b", env="OLLAMA_MODEL")  # Lightweight and efficient
    ollama_enabled: bool = Field(True, env="OLLAMA_ENABLED")  # Enable by default
    ollama_host: str = Field("http://localhost:11434", env="OLLAMA_HOST")
    ollama_timeout: int = Field(30, env="OLLAMA_TIMEOUT")
    ollama_prompt_chars: int = Field(2000, env="OLLAMA_PROMPT_CHARS")
    ollama_timeout_ceiling: int = Field(90, env="OLLAMA_TIMEOUT_CEILING")

    # Batch ingestion. Limits are deliberately bounded so one upload cannot
    # monopolise a worker or exhaust model memory.
    batch_max_records: int = Field(5000, env="BATCH_MAX_RECORDS")
    batch_max_file_bytes: int = Field(25 * 1024 * 1024, env="BATCH_MAX_FILE_BYTES")
    batch_parallelism: int = Field(4, env="BATCH_PARALLELISM")
    batch_ai_model_size: int = Field(16, env="BATCH_AI_MODEL_SIZE")
    batch_ollama_parallelism: int = Field(2, env="BATCH_OLLAMA_PARALLELISM")
    
    # Federated Blockchain Configuration
    federated_encryption_key: str = Field("LULSnIHlBjTSfWDfqVl0kTV9qXUFN0EpGbynAB_34TM=", env="BLOCK_ENCRYPTION_KEY")
    federated_nodes: str = Field("http://localhost:8000,http://localhost:8001,http://localhost:8002,http://localhost:8003,http://localhost:8004", env="FEDERATED_NODES")
    
    # Sightengine Image Detection API
    sightengine_api_user: str = Field("907314243", env="SIGHTENGINE_API_USER")
    sightengine_api_secret: str = Field("B6S8o9JwQg9B3pv5ppo8BgLNA2gyweh3", env="SIGHTENGINE_API_SECRET")
    node_url: str = Field("http://localhost:8000", env="NODE_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(Settings.Config.env_file)
    if config_path.exists():
        return Settings(_env_file=config_path)
    return Settings()
