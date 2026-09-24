import pytest
from src.utils.validation import (
    validate_precio_precision,
    validate_positive_int,
    validate_non_empty_string,
    validate_unique_items,
    validate_sum_disponibles,
    BaseModelWithConfig,
)
from decimal import Decimal
from pydantic import ValidationError


class TestValidationUtils:
    def test_validate_precio_precision_valid(self):
        assert validate_precio_precision(Decimal("100.00")) == Decimal("100.00")
        assert validate_precio_precision(Decimal("100.12")) == Decimal("100.12")
    
    def test_validate_precio_precision_invalid(self):
        with pytest.raises(ValueError, match="precio must have at most 2 decimal places"):
            validate_precio_precision(Decimal("100.123"))
    
    def test_validate_positive_int_valid(self):
        assert validate_positive_int(0) == 0
        assert validate_positive_int(10) == 10
    
    def test_validate_positive_int_invalid(self):
        with pytest.raises(ValueError, match="value must be >= 0"):
            validate_positive_int(-1)
    
    def test_validate_non_empty_string_valid(self):
        assert validate_non_empty_string("hello", 10) == "hello"
        assert validate_non_empty_string("  hello  ", 10) == "hello"
    
    def test_validate_non_empty_string_empty(self):
        with pytest.raises(ValueError, match="value cannot be empty"):
            validate_non_empty_string("", 10)
        with pytest.raises(ValueError, match="value cannot be empty"):
            validate_non_empty_string("   ", 10)
    
    def test_validate_non_empty_string_too_long(self):
        with pytest.raises(ValueError, match="value must be at most 5 characters"):
            validate_non_empty_string("hello world", 5)
    
    def test_validate_unique_items_valid(self):
        class Item:
            def __init__(self, categoria):
                self.categoria = categoria
        
        items = [Item("A"), Item("B"), Item("C")]
        result = validate_unique_items(items, "categoria")
        assert result == items
    
    def test_validate_unique_items_invalid(self):
        class Item:
            def __init__(self, categoria):
                self.categoria = categoria
        
        items = [Item("A"), Item("B"), Item("A")]
        with pytest.raises(ValueError, match="categoria must be unique"):
            validate_unique_items(items, "categoria")
    
    def test_validate_unique_items_dict_valid(self):
        items = [{"categoria": "A"}, {"categoria": "B"}]
        result = validate_unique_items(items, "categoria")
        assert result == items
    
    def test_validate_sum_disponibles_valid(self):
        class Precio:
            def __init__(self, disponibles):
                self.disponibles = disponibles
        
        precios = [Precio(10), Precio(20), Precio(30)]
        result = validate_sum_disponibles(precios, 100)
        assert result == precios
    
    def test_validate_sum_disponibles_invalid(self):
        class Precio:
            def __init__(self, disponibles):
                self.disponibles = disponibles
        
        precios = [Precio(40), Precio(40), Precio(40)]
        with pytest.raises(ValueError, match="sum of precios.disponibles cannot exceed entradas_disponibles"):
            validate_sum_disponibles(precios, 100)


class TestBaseModelWithConfig:
    def test_base_model_with_config(self):
        class TestModel(BaseModelWithConfig):
            name: str
            value: int
        
        model = TestModel(name="test", value=123)
        assert model.name == "test"
        assert model.value == 123