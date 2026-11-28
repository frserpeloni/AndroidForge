"""Limite global do corpo HTTP antes do parsing das rotas."""
from __future__ import annotations

import json
from typing import Any


class RequestBodyLimitMiddleware:
    """Rejeita corpos HTTP acima do limite, inclusive transferências em partes."""

    def __init__(self, app: Any, max_body_bytes: int = 12 * 1024 * 1024) -> None:
        if isinstance(max_body_bytes, bool) or not isinstance(max_body_bytes, int) or max_body_bytes < 1:
            raise ValueError("max_body_bytes deve ser inteiro positivo")
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def _reject(self, send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        content_lengths = [
            value.strip()
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if len(content_lengths) > 1:
            await self._reject(send, 400, "Cabeçalho Content-Length inválido.")
            return
        if content_lengths:
            raw_length = content_lengths[0]
            if not raw_length or not raw_length.isdigit():
                await self._reject(send, 400, "Cabeçalho Content-Length inválido.")
                return
            if int(raw_length) > self.max_body_bytes:
                await self._reject(send, 413, "Corpo da requisição excede o limite permitido.")
                return

        received = 0

        class BodyTooLarge(Exception):
            pass

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise BodyTooLarge
            return message

        response_started = False

        async def tracked_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except BodyTooLarge:
            if not response_started:
                await self._reject(send, 413, "Corpo da requisição excede o limite permitido.")
