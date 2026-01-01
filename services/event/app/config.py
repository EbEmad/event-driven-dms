from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_bootstrap_servers: str
    kafka_consumer_group: str 
    elasticsearch_url: str
    elasticsearch_index_documents: str
    cdc_documents_topic: str 
    service_name: str 

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()