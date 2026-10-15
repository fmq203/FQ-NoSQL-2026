import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status, Query
from src.models.usuario import (
    CompraRegistrada,
    CompraRegistrar,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioAnonimizado,
    TipoDocumento,
)
from src.services.usuario_service import UsuarioService
from src.utils.errors import EventFlowHTTPException
from uuid import UUID
from typing import List, Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["usuarios"])


def get_usuario_service() -> UsuarioService:
    return UsuarioService()


@router.post("/usuarios", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    usuario: UsuarioCreate,
    service: UsuarioService = Depends(get_usuario_service),
):
    """
    Crear un nuevo usuario.

    Validaciones:
    - Email debe ser único (409 si existe)
    - Nombre y email obligatorios
    - Tipo documento: DNI o Pasaporte

    Retorna usuario creado con ID único y timestamps.
    """
    try:
        return await service.crear_usuario(usuario)
    except EventFlowHTTPException:
        raise
    except Exception:
        logger.exception("Error inesperado creando usuario")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al crear usuario"
        )


@router.get("/usuarios", response_model=List[UsuarioResponse])
async def listar_usuarios(
    skip: int = Query(0, ge=0, description="Saltar N registros"),
    limit: int = Query(10, ge=1, le=100, description="Máximo de registros a retornar"),
    service: UsuarioService = Depends(get_usuario_service),
):
    """
    Listar usuarios con paginación.

    Query Parameters:
    - skip: saltar N registros (default: 0)
    - limit: máximo de registros a retornar (default: 10, max: 100)
    """
    return await service.listar_usuarios(skip=skip, limit=limit)


@router.get("/usuarios/exportar", response_model=List[UsuarioAnonimizado])
async def exportar_usuarios(
    format: str = Query("json", description="Formato de exportación: json o csv"),
    service: UsuarioService = Depends(get_usuario_service),
):
    """
    Exportar usuarios anonimizados (GDPR).

    - Nombres/emails: anonimizados irreversiblemente (hash)
    - Historial de compras: preservado para análisis
    - Formatos soportados: json, csv

    NOTA: esta ruta debe declararse antes de /usuarios/{usuario_id} -
    FastAPI/Starlette resuelve las rutas en orden de registro, y un
    registro inverso hace que "exportar" se intente parsear como UUID
    y devuelva 422 en vez de ejecutar la exportación.
    """
    if format.lower() not in ["json", "csv"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Use 'json' o 'csv'"
        )
    return await service.exportar_usuarios_anonimizados()


@router.get("/usuarios/{usuario_id}", response_model=UsuarioResponse)
async def obtener_usuario(
    usuario_id: UUID,
    service: UsuarioService = Depends(get_usuario_service),
):
    """
    Obtener usuario por ID.

    Incluye historial de compras.
    Retorna 404 si no existe.
    """
    usuario = await service.obtener_usuario(usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return usuario


@router.post(
    "/usuarios/{usuario_id}/historial",
    response_model=CompraRegistrada,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "La compra ya estaba registrada (reintento idempotente)"}},
)
async def registrar_compra(
    usuario_id: UUID,
    compra: CompraRegistrar,
    response: Response,
    service: UsuarioService = Depends(get_usuario_service),
):
    """
    Registrar una compra confirmada en el historial del usuario.

    Uso interno: lo llama reservas-service despues de confirmar una reserva.
    Idempotente por `reserva_id`: reintentar la misma compra devuelve 200
    sin duplicarla en el historial. 404 si el usuario no existe.
    """
    agregada = await service.agregar_compra_historial(
        usuario_id=usuario_id,
        evento_id=compra.evento_id,
        evento_nombre=compra.evento_nombre,
        entradas=compra.entradas,
        total_pagado=compra.total_pagado,
        estado=compra.estado,
        reserva_id=compra.reserva_id,
    )
    if agregada is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    if not agregada:
        response.status_code = status.HTTP_200_OK
    return CompraRegistrada(usuario_id=usuario_id, reserva_id=compra.reserva_id, registrada=agregada)
