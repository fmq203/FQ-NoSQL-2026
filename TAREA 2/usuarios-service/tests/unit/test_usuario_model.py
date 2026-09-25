import pytest
from src.models.usuario import UsuarioCreate, TipoDocumento
from pydantic import ValidationError
from uuid import uuid4


class TestUsuarioModel:
    """Unit tests para validación de modelos."""

    def test_usuario_create_valido(self):
        """UsuarioCreate con datos válidos."""
        usuario = UsuarioCreate(
            tipo_documento=TipoDocumento.DNI,
            nro_documento="12345678",
            nombre="Juan",
            apellido="Pérez",
            email="juan@example.com"
        )
        assert usuario.tipo_documento == TipoDocumento.DNI
        assert usuario.email == "juan@example.com"

    def test_email_normalizado_minusculas(self):
        """Email debe normalizarse a minúsculas."""
        usuario = UsuarioCreate(
            tipo_documento=TipoDocumento.DNI,
            nro_documento="12345678",
            nombre="Juan",
            apellido="Pérez",
            email="JUAN@EXAMPLE.COM"
        )
        assert usuario.email == "juan@example.com"

    def test_email_invalido(self):
        """Email inválido debe fallar."""
        with pytest.raises(ValidationError):
            UsuarioCreate(
                tipo_documento=TipoDocumento.DNI,
                nro_documento="12345678",
                nombre="Juan",
                apellido="Pérez",
                email="email-invalido"
            )

    def test_tipo_documento_invalido(self):
        """Tipo documento inválido debe fallar."""
        with pytest.raises(ValidationError):
            UsuarioCreate(
                tipo_documento="CEDULA",
                nro_documento="12345678",
                nombre="Juan",
                apellido="Pérez",
                email="juan@example.com"
            )

    def test_campos_obligatorios(self):
        """Todos los campos son obligatorios."""
        with pytest.raises(ValidationError):
            UsuarioCreate(
                tipo_documento=TipoDocumento.DNI,
                nro_documento="12345678",
                nombre="Juan",
                # falta apellido y email
            )

    def test_longitud_nombre_apellido(self):
        """Nombre y apellido deben tener longitud válida."""
        with pytest.raises(ValidationError):
            UsuarioCreate(
                tipo_documento=TipoDocumento.DNI,
                nro_documento="12345678",
                nombre="",  # vacío
                apellido="Pérez",
                email="juan@example.com"
            )

        with pytest.raises(ValidationError):
            UsuarioCreate(
                tipo_documento=TipoDocumento.DNI,
                nro_documento="12345678",
                nombre="J" * 101,  # > 100 chars
                apellido="Pérez",
                email="juan@example.com"
            )

    def test_tipos_documento_validos(self):
        """DNI y Pasaporte son válidos."""
        for tipo in [TipoDocumento.DNI, TipoDocumento.PASAPORTE]:
            usuario = UsuarioCreate(
                tipo_documento=tipo,
                nro_documento="12345678",
                nombre="Juan",
                apellido="Pérez",
                email="juan@example.com"
            )
            assert usuario.tipo_documento == tipo