from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_CONSUMER_GROUP: str 
    ELASTICSEARCH_URL: str
    ELASTICSEARCH_INDEX_DOCUMENTS: str
    CDC_DOCUMENTS_TOPIC: str 
    SERVICE_NAME: str 

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()