import csv
import hmac
import io
import logging
import secrets
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from src.services.mongodb import get_collection, get_database
from src.config import get_settings
from src.models.usuario import (
    UsuarioCreate,
    UsuarioResponse,
    UsuarioAnonimizado,
    CompraAnonimizada,
    HistorialCompra,
    TipoDocumento,
)
from src.utils.errors import EventFlowHTTPException

logger = logging.getLogger(__name__)

# Clave por proceso para los pseudonimos cuando no se configura EXPORT_PSEUDONYM_KEY
_clave_efimera: Optional[bytes] = None

CSV_COLUMNAS = [
    "pseudonimo", "tipo_documento", "mes_alta",
    "evento_id", "evento_nombre", "fecha_compra", "entradas", "total_pagado", "estado",
]


def _celda_segura(valor) -> str:
    """Evita CSV/formula injection: Excel ejecuta celdas que empiezan con = + - @."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def usuarios_anonimizados_a_csv(usuarios: List[UsuarioAnonimizado]) -> str:
    """Una fila por compra; los usuarios sin compras salen en una fila con las
    columnas de compra vacias (para no perderlos del analisis)."""
    salida = io.StringIO()
    writer = csv.writer(salida)
    writer.writerow(CSV_COLUMNAS)
    for u in usuarios:
        base = [u.pseudonimo, u.tipo_documento.value, u.mes_alta]
        if not u.historial_compras:
            writer.writerow([_celda_segura(c) for c in base + [""] * 6])
        for c in u.historial_compras:
            writer.writerow([_celda_segura(x) for x in base + [
                c.evento_id, c.evento_nombre, c.fecha_compra.isoformat(),
                c.entradas, c.total_pagado, c.estado,
            ]])
    return salida.getvalue()


class UsuarioService:
    def __init__(self):
        self.settings = get_settings()
        self._collection_name = self.settings.mongodb_collection

    @property
    def collection(self):
        return get_collection(self._collection_name)

    def _clave_pseudonimos(self) -> bytes:
        global _clave_efimera
        if self.settings.export_pseudonym_key:
            return self.settings.export_pseudonym_key.encode()
        if _clave_efimera is None:
            _clave_efimera = secrets.token_bytes(32)
        return _clave_efimera

    def _pseudonimo(self, usuario_id: UUID) -> str:
        """HMAC-SHA256 del usuario_id (un UUID v4 aleatorio: no se puede
        enumerar ni adivinar), truncado a 128 bits."""
        return hmac.new(self._clave_pseudonimos(), str(usuario_id).encode(), "sha256").hexdigest()[:32]

    def _to_response(self, doc: dict) -> UsuarioResponse:
        """Convertir documento MongoDB a response model."""
        return UsuarioResponse(
            usuario_id=doc["_id"],
            tipo_documento=doc["tipo_documento"],
            nro_documento=doc["nro_documento"],
            nombre=doc["nombre"],
            apellido=doc["apellido"],
            email=doc["email"],
            creado_en=doc["creado_en"],
            actualizado_en=doc["actualizado_en"],
            historial_compras=[
                HistorialCompra(**h) for h in doc.get("historial_compras", [])
            ],
        )

    def _to_anonimizado(self, doc: dict) -> UsuarioAnonimizado:
        """Convertir documento a version anonimizada (sin datos personales)."""
        return UsuarioAnonimizado(
            pseudonimo=self._pseudonimo(doc["_id"]),
            tipo_documento=doc["tipo_documento"],
            mes_alta=doc["creado_en"].strftime("%Y-%m"),
            historial_compras=[
                CompraAnonimizada(
                    evento_id=h["evento_id"],
                    evento_nombre=h["evento_nombre"],
                    fecha_compra=h["fecha_compra"].date(),
                    entradas=h["entradas"],
                    total_pagado=h["total_pagado"],
                    estado=h["estado"],
                )
                for h in doc.get("historial_compras", [])
            ],
        )

    async def crear_usuario(self, usuario: UsuarioCreate) -> UsuarioResponse:
        """Crear nuevo usuario con validaciones."""
        # Verificar email único
        existing = await self.collection.find_one({"email": usuario.email})
        if existing:
            raise EventFlowHTTPException(
                error_code="duplicate-resource",
                title="Conflict",
                status_code=409,
                detail=f"Email {usuario.email} ya registrado",
                instance="/api/usuarios"
            )

        # Verificar nro_documento único
        existing = await self.collection.find_one({"nro_documento": usuario.nro_documento})
        if existing:
            raise EventFlowHTTPException(
                error_code="duplicate-resource",
                title="Conflict",
                status_code=409,
                detail=f"Documento {usuario.nro_documento} ya registrado",
                instance="/api/usuarios"
            )

        now = datetime.now(timezone.utc)
        usuario_id = uuid4()

        doc = {
            "_id": usuario_id,
            "tipo_documento": usuario.tipo_documento.value,
            "nro_documento": usuario.nro_documento,
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "creado_en": now,
            "actualizado_en": now,
            "historial_compras": [],
        }

        await self.collection.insert_one(doc)
        logger.info(f"✅ Usuario creado: {usuario_id}")

        return UsuarioResponse(
            usuario_id=usuario_id,
            tipo_documento=usuario.tipo_documento,
            nro_documento=usuario.nro_documento,
            nombre=usuario.nombre,
            apellido=usuario.apellido,
            email=usuario.email,
            creado_en=now,
            actualizado_en=now,
            historial_compras=[],
        )

    async def listar_usuarios(self, skip: int = 0, limit: int = 10) -> List[UsuarioResponse]:
        """Listar usuarios con paginación."""
        cursor = self.collection.find().skip(skip).limit(limit).sort("creado_en", -1)
        docs = await cursor.to_list(length=limit)
        return [self._to_response(doc) for doc in docs]

    async def obtener_usuario(self, usuario_id: UUID) -> Optional[UsuarioResponse]:
        """Obtener usuario por ID."""
        doc = await self.collection.find_one({"_id": usuario_id})
        if not doc:
            return None
        return self._to_response(doc)

    async def exportar_usuarios_anonimizados(self) -> List[UsuarioAnonimizado]:
        """Exportar todos los usuarios con datos anonimizados (GDPR)."""
        cursor = self.collection.find({})
        docs = await cursor.to_list(length=None)
        return [self._to_anonimizado(doc) for doc in docs]

    async def agregar_compra_historial(
        self,
        usuario_id: UUID,
        evento_id: UUID,
        evento_nombre: str,
        entradas: int,
        total_pagado: float,
        estado: str,
        reserva_id: Optional[UUID] = None,
    ) -> Optional[bool]:
        """Agregar compra al historial del usuario (idempotente por reserva_id).

        Returns:
            True si se agrego, False si esa reserva_id ya estaba en el
            historial (reintento), None si el usuario no existe.
        """
        compra = HistorialCompra(
            evento_id=evento_id,
            evento_nombre=evento_nombre,
            fecha_compra=datetime.now(timezone.utc),
            entradas=entradas,
            total_pagado=total_pagado,
            estado=estado,
            reserva_id=reserva_id,
        )

        filtro: dict = {"_id": usuario_id}
        if reserva_id is not None:
            # Solo matchea si NINGUNA compra del historial tiene esa reserva_id
            filtro["historial_compras.reserva_id"] = {"$ne": reserva_id}

        result = await self.collection.update_one(
            filtro,
            {
                "$push": {"historial_compras": compra.model_dump()},
                "$set": {"actualizado_en": datetime.now(timezone.utc)},
            },
        )
        if result.modified_count > 0:
            return True
        existe = await self.collection.count_documents({"_id": usuario_id}, limit=1)
        return False if existe else None
