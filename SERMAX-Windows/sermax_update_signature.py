"""Backend Ed25519 fail-closed para autenticação de manifestos SERMAX.

As chaves públicas são fornecidas pelo código de inicialização confiável.
Nunca carregar chaves públicas de dentro do manifesto nem aceitar chave privada
neste módulo. A allowlist de produção permanece vazia até aprovação formal.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_KEY_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_PUBLIC_KEY_BYTES = 32
_SIGNATURE_BYTES = 64


def build_ed25519_verifier(
    trusted_public_keys: Mapping[str, bytes],
):
    """Retorna callback compatível com validate_signed_manifest.

    trusted_public_keys deve ser uma allowlist controlada pelo aplicativo,
    indexada por key_id e contendo chaves públicas Ed25519 raw de 32 bytes.
    IDs desconhecidos, chaves malformadas e assinaturas inválidas retornam
    False. Nenhuma chave é obtida do manifesto.
    """
    if not isinstance(trusted_public_keys, Mapping):
        raise TypeError("A allowlist de chaves públicas deve ser um mapping.")

    public_keys: dict[str, Ed25519PublicKey] = {}
    for key_id, raw_key in trusted_public_keys.items():
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise ValueError("key_id inválido na allowlist confiável.")
        if not isinstance(raw_key, bytes) or len(raw_key) != _PUBLIC_KEY_BYTES:
            raise ValueError(f"Chave pública Ed25519 inválida para {key_id}.")
        public_keys[key_id] = Ed25519PublicKey.from_public_bytes(raw_key)

    def verify_signature(key_id: str, payload: bytes, signature: bytes) -> bool:
        if not isinstance(key_id, str) or not isinstance(payload, bytes):
            return False
        if not isinstance(signature, bytes) or len(signature) != _SIGNATURE_BYTES:
            return False
        public_key = public_keys.get(key_id)
        if public_key is None:
            return False
        try:
            public_key.verify(signature, payload)
        except (InvalidSignature, ValueError):
            return False
        return True

    return verify_signature
