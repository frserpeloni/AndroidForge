"""Rotas de pareamento de dispositivos SERMAX.

As rotas administrativas dependem do middleware local da API. As rotas de
reserva e finalização aceitam o primeiro vínculo remoto somente quando a política
de proxy confiável estiver habilitada. Essa política permanece desligada por padrão.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

try:
    from . import lan_security
except ImportError:
    import lan_security

try:
    from .pairing_rate_limit import SlidingWindowRateLimiter
except ImportError:
    from pairing_rate_limit import SlidingWindowRateLimiter


PAIRING_RATE_LIMITER = SlidingWindowRateLimiter(limit=8, window_seconds=60)


def _enforce_pairing_rate_limit(request: Request, operation: str) -> None:
    client = request.client
    peer = client.host if client is not None else "unknown"
    if not PAIRING_RATE_LIMITER.allow(operation + ":" + peer):
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de pareamento. Aguarde antes de tentar novamente.",
            headers={"Retry-After": "60"},
        )


class DeviceInput(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)


class PairingReserveInput(DeviceInput):
    code: str = Field(min_length=1, max_length=256)


class PairingFinalizeInput(DeviceInput):
    reservation_id: str = Field(min_length=1, max_length=128)


def create_pairing_router(db_path_provider: Callable[[], Path]) -> APIRouter:
    router = APIRouter()

    @router.post("/api/local/pairings", status_code=201)
    def create_local_pairing(payload: DeviceInput, request: Request):
        _enforce_pairing_rate_limit(request, "create")
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
    def reserve_device_pairing(payload: PairingReserveInput, request: Request):
        _enforce_pairing_rate_limit(request, "reserve")
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
    def finalize_device_pairing(
        payload: PairingFinalizeInput, request: Request, response: Response
    ):
        _enforce_pairing_rate_limit(request, "finalize")
        try:
            credential = lan_security.finalize_pairing(
                payload.reservation_id, payload.device_id.strip(), db_path=db_path_provider()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Dados de pareamento inválidos.") from exc
        if credential is None:
            raise HTTPException(status_code=403, detail="Pareamento ainda não aprovado ou expirado.")

        # A credencial sai somente em cookie protegido. O JavaScript nunca recebe o segredo.
        response.set_cookie(
            "sermax_device_id",
            payload.device_id.strip(),
            max_age=lan_security.DEFAULT_CREDENTIAL_TTL_SECONDS,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        response.set_cookie(
            "sermax_device_credential",
            credential,
            max_age=lan_security.DEFAULT_CREDENTIAL_TTL_SECONDS,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        return {"device_id": payload.device_id.strip(), "authenticated": True}

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
