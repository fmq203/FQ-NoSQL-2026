from pydantic import BaseModel, field_validator
from typing import Optional


class BaseValidator(BaseModel):
    """Modelo base con validadores comunes."""
    
    class Config:
        validate_assignment = True
        str_strip_whitespace = True


def validate_email(email: str) -> str:
    """Validador personalizado para email."""
    if not email or "@" not in email:
        raise ValueError("Email inválido")
    return email.lower()


def validate_string_not_empty(value: str, field_name: str, min_len: int = 1, max_len: int = 200) -> str:
    """Validar string no vacío con límites."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} no puede estar vacío")
    if len(value.strip()) < min_len or len(value.strip()) > max_len:
        raise ValueError(f"{field_name} debe tener entre {min_len} y {max_len} caracteres")
    return value.strip()


def validate_uuid(value: str) -> str:
    """Validar formato UUID."""
    import re
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    if not uuid_pattern.match(value):
        raise ValueError("Formato UUID inválido")
    return value