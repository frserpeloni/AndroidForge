"""Validação HTTP de credenciais individuais de dispositivos SERMAX.

Este módulo não altera o middleware nem publica rotas. A integração com a API
deve chamar authenticate_device_headers somente para requisições remotas,
depois de validar Host, HTTPS e Origin.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3

try:
    from .lan_security import authenticate
except ImportError:  # execução direta pelo diretório backend
    from lan_security import authenticate


class DeviceAuthenticationError(ValueError):
    """Credencial de dispositivo ausente ou inválida."""


def authenticate_device_headers(
    device_id: str | None,
    authorization: str | None,
    *,
    db_path: Path | str,
) -> str:
    """Valida X-Sermax-Device + Authorization: Bearer sem expor segredos.

    A credencial nunca é retornada, registrada ou incluída em mensagens de erro.
    """
    if not isinstance(device_id, str) or not device_id.strip() or len(device_id) > 128:
        raise DeviceAuthenticationError("Dispositivo não autenticado.")

    if not isinstance(authorization, str) or len(authorization) > 520:
        raise DeviceAuthenticationError("Dispositivo não autenticado.")

    scheme, separator, credential = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not credential
        or credential.strip() != credential
        or any(char.isspace() for char in credential)
        or len(credential) > 512
    ):
        raise DeviceAuthenticationError("Dispositivo não autenticado.")

    try:
        valid = authenticate(device_id.strip(), credential, db_path=db_path)
    except (ValueError, OSError, sqlite3.Error):
        valid = False

    if not valid:
        raise DeviceAuthenticationError("Dispositivo não autenticado.")

    return device_id.strip()
