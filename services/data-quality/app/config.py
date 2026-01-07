from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuration for Data Quality Service."""

    # Service Settings
    service_name: str = "data-quality"
    
    # LLM Provider Settings
    LLM_PROVIDER: str 
    OPENAI_API_KEY: str 
    OPENAI_API_URL: str
    GEMINI_API_KEY: str
    OPENAI_MODEL: str 
    GEMINI_MODEL: str
    INPUT_DEFAULT_MAX_CHARACTERS: int = 1024


    # Quality Thresholds
    MIN_QUALITY_SCORE: float = 50.0  # 0-100 scale
    BLOCK_LOW_QUALITY: bool = False  # If True, don't publish low-quality docs
    
    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_CONSUMER_GROUP: str
    CDC_DOCUMENTS_TOPIC: str 
    QUALITY_CHECKS_TOPIC: str

    # MinIO Settings (for fetching document content)
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False
    MINIO_BUCKET_DOCUMENTS: str 


    class Config:
        env_file=".env"

@lru_cache
def get_settings():
    return Settings()