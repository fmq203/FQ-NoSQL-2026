from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "eventflow"
    mongodb_collection_reservas: str = "reservas"
    redis_url: str = "redis://localhost:6379"
    postgresql_uri: str = "postgresql://eventflow_user:eventflow_password@localhost:5432/eventflow"
    usuarios_service_url: str = "http://localhost:8001"
    eventos_service_url: str = "http://localhost:8002"
    service_port: int = 8003
    log_level: str = "INFO"
    health_check_timeout_ms: int = 2000
    health_check_degraded_threshold_ms: int = 50
    health_check_unhealthy_threshold_ms: int = 500

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()