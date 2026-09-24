import pytest
from uuid import UUID
from decimal import Decimal
from src.models.evento import (
    EstadoEvento,
    PrecioCategoria,
    Ubicacion,
    EventoCreate,
    EventoResponse,
)


class TestEventoModel:
    def test_precio_categoria_valid(self):
        precio = PrecioCategoria(categoria="VIP", precio=Decimal("15000.00"), disponibles=100)
        assert precio.categoria == "VIP"
        assert precio.precio == Decimal("15000.00")
        assert precio.disponibles == 100
    
    def test_precio_categoria_precision(self):
        precio = PrecioCategoria(categoria="VIP", precio=Decimal("15000.12"), disponibles=100)
        assert precio.precio == Decimal("15000.12")
    
    def test_precio_categoria_invalid_precision(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Decimal input should have no more than 2 decimal places"):
            PrecioCategoria(categoria="VIP", precio=Decimal("15000.123"), disponibles=100)
    
    def test_precio_categoria_negative_price(self):
        with pytest.raises(ValueError, match="Input should be greater than or equal to 0"):
            PrecioCategoria(categoria="VIP", precio=Decimal("-100.00"), disponibles=100)
    
    def test_precio_categoria_negative_disponibles(self):
        with pytest.raises(ValueError, match="Input should be greater than or equal to 0"):
            PrecioCategoria(categoria="VIP", precio=Decimal("100.00"), disponibles=-1)
    
    def test_ubicacion_valid(self):
        ubicacion = Ubicacion(ciudad="Buenos Aires", pais="Argentina", direccion="Estadio Luna Park")
        assert ubicacion.ciudad == "Buenos Aires"
        assert ubicacion.pais == "Argentina"
        assert ubicacion.direccion == "Estadio Luna Park"
    
    def test_ubicacion_without_direccion(self):
        ubicacion = Ubicacion(ciudad="Montevideo", pais="Uruguay")
        assert ubicacion.ciudad == "Montevideo"
        assert ubicacion.pais == "Uruguay"
        assert ubicacion.direccion is None
    
    def test_ubicacion_empty_ciudad(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            Ubicacion(ciudad="", pais="Argentina")
    
    def test_evento_create_valid(self):
        evento = EventoCreate(
            nombre="Concierto Rock 2026",
            estado=EstadoEvento.PUBLICADO,
            aforo_total=5000,
            entradas_disponibles=5000,
            precios=[
                PrecioCategoria(categoria="VIP", precio=Decimal("15000.00"), disponibles=100),
                PrecioCategoria(categoria="General", precio=Decimal("5000.00"), disponibles=4900)
            ],
            ubicacion=Ubicacion(ciudad="Buenos Aires", pais="Argentina", direccion="Estadio Luna Park")
        )
        assert evento.nombre == "Concierto Rock 2026"
        assert evento.estado == EstadoEvento.PUBLICADO
        assert evento.aforo_total == 5000
        assert evento.entradas_disponibles == 5000
        assert len(evento.precios) == 2
    
    def test_evento_create_aforo_exceeded(self):
        with pytest.raises(ValueError, match="entradas_disponibles cannot exceed aforo_total"):
            EventoCreate(
                nombre="Test",
                estado=EstadoEvento.PUBLICADO,
                aforo_total=100,
                entradas_disponibles=200,
                precios=[PrecioCategoria(categoria="VIP", precio=Decimal("100.00"), disponibles=200)],
                ubicacion=Ubicacion(ciudad="Buenos Aires", pais="Argentina")
            )
    
    def test_evento_create_duplicate_categoria(self):
        with pytest.raises(ValueError, match="categoria must be unique within precios"):
            EventoCreate(
                nombre="Test",
                estado=EstadoEvento.PUBLICADO,
                aforo_total=100,
                entradas_disponibles=100,
                precios=[
                    PrecioCategoria(categoria="VIP", precio=Decimal("100.00"), disponibles=50),
                    PrecioCategoria(categoria="VIP", precio=Decimal("200.00"), disponibles=50)
                ],
                ubicacion=Ubicacion(ciudad="Buenos Aires", pais="Argentina")
            )
    
    def test_evento_create_precios_disponibles_exceeds_entradas(self):
        with pytest.raises(ValueError, match="sum of precios.disponibles cannot exceed entradas_disponibles"):
            EventoCreate(
                nombre="Test",
                estado=EstadoEvento.PUBLICADO,
                aforo_total=100,
                entradas_disponibles=100,
                precios=[
                    PrecioCategoria(categoria="VIP", precio=Decimal("100.00"), disponibles=60),
                    PrecioCategoria(categoria="General", precio=Decimal("50.00"), disponibles=60)
                ],
                ubicacion=Ubicacion(ciudad="Buenos Aires", pais="Argentina")
            )
    
    def test_evento_create_zero_aforo_valid(self):
        evento = EventoCreate(
            nombre="Evento Borrador",
            estado=EstadoEvento.BORRADOR,
            aforo_total=0,
            entradas_disponibles=0,
            precios=[PrecioCategoria(categoria="Gratis", precio=Decimal("0.00"), disponibles=0)],
            ubicacion=Ubicacion(ciudad="Montevideo", pais="Uruguay")
        )
        assert evento.aforo_total == 0
        assert evento.entradas_disponibles == 0
    
    def test_evento_create_free_event_valid(self):
        evento = EventoCreate(
            nombre="Evento Gratis",
            estado=EstadoEvento.PUBLICADO,
            aforo_total=100,
            entradas_disponibles=100,
            precios=[PrecioCategoria(categoria="General", precio=Decimal("0.00"), disponibles=100)],
            ubicacion=Ubicacion(ciudad="Buenos Aires", pais="Argentina")
        )
        assert evento.precios[0].precio == Decimal("0.00")
    
    def test_evento_create_invalid_estado(self):
        with pytest.raises(ValueError):
            EventoCreate(
                nombre="Test",
                estado="invalido",
                aforo_total=100,
                entradas_disponibles=100,
                precios=[PrecioCategoria(categoria="VIP", precio=Decimal("100.00"), disponibles=100)],
                ubicacion=Ubicacion(ciudad="Buenos Aires", pais="Argentina")
            )