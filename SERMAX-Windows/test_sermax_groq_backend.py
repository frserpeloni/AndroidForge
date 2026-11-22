"""Testes sem rede para o contrato de requisição do backend Groq."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from sermax_groq_backend import GroqChatBackend


class FakeResponse:
    def __init__(self, payload: dict):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit: int):
        return self.raw[:limit]


class GroqChatBackendRequestTests(unittest.TestCase):
    def test_gpt_oss_sends_final_answer_parameters(self):
        response = FakeResponse({
            "choices": [{
                "message": {"content": "proposta final"},
                "finish_reason": "stop",
            }]
        })
        with patch("sermax_groq_backend.urllib.request.urlopen", return_value=response) as send:
            backend = GroqChatBackend(
                api_key="test-key",
                model="openai/gpt-oss-20b",
                max_tokens=1024,
                max_retries=0,
            )
            answer = backend("analista", "Analise este trecho.")

        self.assertEqual(answer, "proposta final")
        request = send.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIs(payload["include_reasoning"], False)
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertEqual(payload["max_completion_tokens"], 1024)
        self.assertNotIn("max_tokens", payload)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    def test_other_models_keep_legacy_token_parameter(self):
        response = FakeResponse({
            "choices": [{
                "message": {"content": "resposta"},
                "finish_reason": "stop",
            }]
        })
        with patch("sermax_groq_backend.urllib.request.urlopen", return_value=response) as send:
            backend = GroqChatBackend(
                api_key="test-key",
                model="llama-3.3-70b-versatile",
                max_tokens=768,
                max_retries=0,
            )
            answer = backend("analista", "Analise.")

        self.assertEqual(answer, "resposta")
        payload = json.loads(send.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["max_tokens"], 768)
        self.assertNotIn("include_reasoning", payload)
        self.assertNotIn("max_completion_tokens", payload)


if __name__ == "__main__":
    unittest.main()
