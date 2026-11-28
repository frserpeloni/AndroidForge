"""Rotas de pareamento de dispositivos SERMAX.

As rotas administrativas dependem do middleware local da API. As rotas de
reserva e finalização são preparadas para o futuro cliente remoto, mas continuam
inacessíveis externamente enquanto o middleware da Plataforma estiver em modo
loopback-only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from . import lan_security
except ImportError:
    import lan_security


class DeviceInput(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)


class PairingReserveInput(DeviceInput):
    code: str = Field(min_length=1, max_length=256)


class PairingFinalizeInput(DeviceInput):
    reservation_id: str = Field(min_length=1, max_length=128)


def create_pairing_router(db_path_provider: Callable[[], Path]) -> APIRouter:
    router = APIRouter()

    @router.post("/api/local/pairings", status_code=201)
    def create_local_pairing(payload: DeviceInput):
        try:
            code = lan_security.generate_pairing_code(
                payload.device_id.strip(), db_path=db_path_provider()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Identificador de dispositivo inválido.") from exc
        return {"device_id": payload.device_id.strip(), "code": code, "expires_in": 300}

    @router.get("/api/local/pairings/pending")
    def pending_local_pairings():
        try:
            return {"items": lan_security.list_pending_pairings(db_path_provider())}
        except (OSError, RuntimeError):
            raise HTTPException(status_code=503, detail="Não foi possível consultar os pedidos de pareamento.")

    @router.post("/api/local/pairings/{reservation_id}/approve")
    def approve_local_pairing(reservation_id: str, payload: DeviceInput):
        try:
            approved = lan_security.approve_pairing_locally(
                reservation_id, payload.device_id.strip(), db_path=db_path_provider()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Dados de aprovação inválidos.") from exc
        if not approved:
            raise HTTPException(status_code=404, detail="Pedido expirado ou não encontrado.")
        return {"approved": True, "device_id": payload.device_id.strip()}

    @router.post("/api/device/pairing/reserve", status_code=202)
    def reserve_device_pairing(payload: PairingReserveInput):
        try:
            reservation_id = lan_security.reserve_pairing(
                payload.device_id.strip(), payload.code, db_path=db_path_provider()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Dados de pareamento inválidos.") from exc
        if reservation_id is None:
            raise HTTPException(status_code=400, detail="Código inválido, expirado ou já utilizado.")
        return {"reservation_id": reservation_id, "status": "awaiting_local_approval"}

    @router.post("/api/device/pairing/finalize")
    def finalize_device_pairing(payload: PairingFinalizeInput):
        try:
            credential = lan_security.finalize_pairing(
                payload.reservation_id, payload.device_id.strip(), db_path=db_path_provider()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Dados de pareamento inválidos.") from exc
        if credential is None:
            raise HTTPException(status_code=403, detail="Pareamento ainda não aprovado ou expirado.")
        return {"device_id": payload.device_id.strip(), "credential": credential}

    @router.post("/api/local/devices/{device_id}/revoke")
    def revoke_local_device(device_id: str):
        try:
            revoked = lan_security.revoke(device_id, db_path=db_path_provider())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Identificador de dispositivo inválido.") from exc
        if not revoked:
            raise HTTPException(status_code=404, detail="Dispositivo ativo não encontrado.")
        return {"revoked": True, "device_id": device_id}

    return router
