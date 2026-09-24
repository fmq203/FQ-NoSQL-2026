from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal


class BaseModelWithConfig(BaseModel):
    class Config:
        from_attributes = True
        populate_by_name = True
        use_enum_values = True
        json_schema_extra = {}


def validate_precio_precision(v: Decimal) -> Decimal:
    if v.as_tuple().exponent < -2:
        raise ValueError("precio must have at most 2 decimal places")
    return v


def validate_positive_int(v: int) -> int:
    if v < 0:
        raise ValueError("value must be >= 0")
    return v


def validate_non_empty_string(v: str, max_length: int) -> str:
    if not v or not v.strip():
        raise ValueError("value cannot be empty")
    if len(v) > max_length:
        raise ValueError(f"value must be at most {max_length} characters")
    return v.strip()


def validate_unique_items(items: list, key_attr: str = "categoria") -> list:
    seen = set()
    for item in items:
        key = getattr(item, key_attr) if hasattr(item, key_attr) else item.get(key_attr)
        if key in seen:
            raise ValueError(f"{key_attr} must be unique")
        seen.add(key)
    return items


def validate_sum_disponibles(precios: list, entradas_disponibles: int) -> list:
    total = sum(
        getattr(p, "disponibles") if hasattr(p, "disponibles") else p.get("disponibles", 0)
        for p in precios
    )
    if total > entradas_disponibles:
        raise ValueError("sum of precios.disponibles cannot exceed entradas_disponibles")
    return precios