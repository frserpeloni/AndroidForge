import io
import json
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from sermax_groq_backend import GroqAPIError, GroqChatBackend


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit=-1):
        return json.dumps(self.payload).encode("utf-8")


class GroqBackendTests(unittest.TestCase):
    def make_backend(self, **kwargs):
        return GroqChatBackend(api_key="test-key", **kwargs)

    def test_uses_conservative_default_token_budget(self):
        backend = self.make_backend()
        self.assertEqual(backend.max_tokens, 1024)

    def test_caps_configured_token_budget(self):
        backend = self.make_backend(max_tokens=9000)
        self.assertEqual(backend.max_tokens, 4096)

    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_sends_configured_token_budget_and_returns_content(self, mocked_open):
        mocked_open.return_value = FakeResponse({
            "choices": [{"message": {"content": "resposta"}}]
        })
        backend = self.make_backend(max_tokens=2048)
        self.assertEqual(backend("Analista", "Analise esta tarefa"), "resposta")
        request = mocked_open.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["max_tokens"], 2048)
        self.assertEqual(payload["model"], "openai/gpt-oss-20b")
        self.assertNotIn("test-key", request.data.decode("utf-8"))

    @patch("sermax_groq_backend.time.sleep")
    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_retries_rate_limit_using_retry_after_header(self, mocked_open, mocked_sleep):
        headers = Message()
        headers["Retry-After"] = "3"
        rate_limit = urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            429,
            "Too Many Requests",
            headers,
            io.BytesIO(b'{"error":"rate limit"}'),
        )
        mocked_open.side_effect = [
            rate_limit,
            FakeResponse({"choices": [{"message": {"content": "recuperado"}}]}),
        ]
        backend = self.make_backend(max_retries=1)
        self.assertEqual(backend("Testador", "Teste"), "recuperado")
        mocked_sleep.assert_called_once_with(4.0)
        self.assertEqual(mocked_open.call_count, 2)

    @patch("sermax_groq_backend.time.sleep")
    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_stops_after_retry_limit(self, mocked_open, mocked_sleep):
        error = urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            429,
            "Too Many Requests",
            Message(),
            io.BytesIO(b'{"error":"try again in 2s"}'),
        )
        mocked_open.side_effect = error
        backend = self.make_backend(max_retries=1)
        with self.assertRaisesRegex(GroqAPIError, "Groq HTTP 429"):
            backend("Programador", "Implemente")
        self.assertEqual(mocked_open.call_count, 2)
        self.assertEqual(mocked_sleep.call_count, 1)

    def test_rejects_empty_prompt(self):
        backend = self.make_backend()
        with self.assertRaises(ValueError):
            backend("Analista", " ")


if __name__ == "__main__":
    unittest.main()
