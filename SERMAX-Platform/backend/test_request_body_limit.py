"""Testes do limite global de corpo HTTP da Plataforma."""
import asyncio
import unittest

from request_body_limit import RequestBodyLimitMiddleware


class RequestBodyLimitTests(unittest.TestCase):
    def _run(self, messages, headers=(), limit=5):
        received_messages = list(messages)
        sent = []
        downstream_called = []

        async def receive():
            if received_messages:
                return received_messages.pop(0)
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        async def downstream(scope, inner_receive, inner_send):
            downstream_called.append(True)
            while True:
                message = await inner_receive()
                if message["type"] == "http.disconnect":
                    break
                if message["type"] == "http.request" and not message.get("more_body", False):
                    break
            await inner_send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await inner_send({"type": "http.response.body", "body": b"ok"})

        middleware = RequestBodyLimitMiddleware(downstream, max_body_bytes=limit)
        scope = {"type": "http", "headers": list(headers)}
        asyncio.run(middleware(scope, receive, send))
        status = next(
            message["status"]
            for message in sent
            if message["type"] == "http.response.start"
        )
        return status, downstream_called

    def test_rejects_content_length_over_limit_before_route(self):
        status, called = self._run(
            [{"type": "http.request", "body": b"", "more_body": False}],
            headers=[(b"content-length", b"6")],
        )
        self.assertEqual(status, 413)
        self.assertFalse(called)

    def test_rejects_chunked_body_when_total_exceeds_limit(self):
        status, called = self._run([
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"456", "more_body": False},
        ])
        self.assertEqual(status, 413)
        self.assertTrue(called)

    def test_accepts_body_exactly_at_limit(self):
        status, called = self._run([
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ])
        self.assertEqual(status, 200)
        self.assertTrue(called)

    def test_rejects_invalid_or_duplicate_content_length(self):
        invalid, _ = self._run(
            [{"type": "http.request", "body": b"", "more_body": False}],
            headers=[(b"content-length", b"five")],
        )
        duplicate, _ = self._run(
            [{"type": "http.request", "body": b"", "more_body": False}],
            headers=[(b"content-length", b"1"), (b"content-length", b"1")],
        )
        self.assertEqual(invalid, 400)
        self.assertEqual(duplicate, 400)


if __name__ == "__main__":
    unittest.main()
