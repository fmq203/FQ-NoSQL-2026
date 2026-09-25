import logging
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from hashlib import sha256
from src.services.mongodb import get_collection, get_database
from src.config import get_settings
from src.models.usuario import (
    UsuarioCreate,
    UsuarioResponse,
    UsuarioAnonimizado,
    HistorialCompra,
    TipoDocumento,
)
from src.utils.errors import EventFlowHTTPException

logger = logging.getLogger(__name__)


class UsuarioService:
    def __init__(self):
        self.settings = get_settings()
        self._collection_name = self.settings.mongodb_collection

    @property
    def collection(self):
        return get_collection(self._collection_name)

    def _hash_pii(self, value: str) -> str:
        """Hash irreversible para anonimización GDPR."""
        return sha256(value.encode()).hexdigest()[:16]

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
        """Convertir documento a versión anonimizada."""
        return UsuarioAnonimizado(
            usuario_id_hash=self._hash_pii(str(doc["_id"])),
            tipo_documento=doc["tipo_documento"],
            nro_documento_hash=self._hash_pii(doc["nro_documento"]),
            nombre_hash=self._hash_pii(doc["nombre"]),
            apellido_hash=self._hash_pii(doc["apellido"]),
            email_hash=self._hash_pii(doc["email"]),
            creado_en=doc["creado_en"],
            historial_compras=[
                HistorialCompra(**h) for h in doc.get("historial_compras", [])
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
        logger.info(f"✅ Usuario creado: {usuario_id} - {usuario.email}")

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
        estado: str
    ) -> bool:
        """Agregar compra al historial del usuario."""
        compra = HistorialCompra(
            evento_id=evento_id,
            evento_nombre=evento_nombre,
            fecha_compra=datetime.now(timezone.utc),
            entradas=entradas,
            total_pagado=total_pagado,
            estado=estado,
        )

        result = await self.collection.update_one(
            {"_id": usuario_id},
            {
                "$push": {"historial_compras": compra.model_dump()},
                "$set": {"actualizado_en": datetime.now(timezone.utc)}
            }
        )
        return result.modified_count > 0