from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "eventflow"
    mongodb_collection: str = "usuarios"
    redis_url: str = "redis://localhost:6379"
    postgresql_uri: str = "postgresql://eventflow_user:eventflow_password@localhost:5432/eventflow"
    service_port: int = 8001
    log_level: str = "INFO"
    health_check_timeout_ms: int = 2000
    health_check_degraded_threshold_ms: int = 50
    health_check_unhealthy_threshold_ms: int = 500
    # Clave HMAC de los pseudonimos del export. Vacia = se genera una al azar
    # al arrancar el servicio (anonimizacion; los pseudonimos no se pueden
    # relacionar entre reinicios). Con valor = pseudonimizacion estable.
    export_pseudonym_key: str = ""

    # Cache de lecturas (GET) en Redis, DB 1 (reservas usa la 0). Ver services/lectura_cache.py
    cache_enabled: bool = True
    cache_redis_url: str = "redis://localhost:6379/1"
    cache_fresh_seconds: int = 30
    cache_stale_seconds: int = 600

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()