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
        self.assertEqual(backend.max_tokens, 2048)

    def test_caps_configured_token_budget(self):
        backend = self.make_backend(max_tokens=9000)
        self.assertEqual(backend.max_tokens, 4096)

    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_sends_completion_budget_and_returns_content(self, mocked_open):
        mocked_open.return_value = FakeResponse({
            "choices": [{"message": {"content": "resposta"}}]
        })
        backend = self.make_backend(max_tokens=2048)
        self.assertEqual(backend("Analista", "Analise esta tarefa"), "resposta")
        request = mocked_open.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["max_completion_tokens"], 2048)
        self.assertEqual(payload["model"], "openai/gpt-oss-20b")
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertNotIn("test-key", request.data.decode("utf-8"))
        self.assertNotIn("response_format", payload)

    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_programmer_uses_strict_proposal_schema(self, mocked_open):
        mocked_open.return_value = FakeResponse({
            "choices": [{"message": {"content": '{"summary":"ok","files":[],"tests":[]}'}}]
        })
        backend = self.make_backend()
        backend("programador", "Retorne a proposta")
        payload = json.loads(mocked_open.call_args.args[0].data.decode("utf-8"))
        response_format = payload["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(
            schema["required"], ["summary", "files", "tests"]
        )
        self.assertFalse(schema["additionalProperties"])
        file_schema = schema["properties"]["files"]["items"]
        self.assertEqual(
            file_schema["required"],
            ["path", "content", "edits"],
        )
        self.assertEqual(
            file_schema["properties"]["edits"]["type"],
            ["array", "null"],
        )
        self.assertEqual(
            file_schema["properties"]["edits"]["items"]["required"],
            ["old", "new"],
        )

    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_tester_uses_strict_verdict_schema(self, mocked_open):
        mocked_open.return_value = FakeResponse({
            "choices": [{"message": {"content": '{"verdict":"PASS","evidence":"ok"}'}}]
        })
        backend = self.make_backend()
        backend("testador", "Avalie os testes")
        payload = json.loads(mocked_open.call_args.args[0].data.decode("utf-8"))
        response_format = payload["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(
            schema["properties"]["verdict"]["enum"], ["PASS", "FAIL"]
        )
        self.assertEqual(schema["required"], ["verdict", "evidence"])

    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_unsupported_model_falls_back_to_json_object_mode(self, mocked_open):
        mocked_open.return_value = FakeResponse({
            "choices": [{"message": {"content": '{"summary":"ok"}'}}]
        })
        backend = self.make_backend(model="modelo/sem-json-schema")
        backend("programador", "Retorne JSON")
        payload = json.loads(mocked_open.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertNotIn("reasoning_effort", payload)

    @patch("sermax_groq_backend.urllib.request.urlopen")
    def test_empty_content_reports_finish_reason_and_usage(self, mocked_open):
        mocked_open.return_value = FakeResponse({
            "choices": [{
                "message": {"content": ""},
                "finish_reason": "length",
            }],
            "usage": {
                "completion_tokens": 2048,
                "completion_tokens_details": {"reasoning_tokens": 1900},
            },
        })
        backend = self.make_backend()
        with self.assertRaisesRegex(
            GroqAPIError,
            "finish_reason=length.*completion_tokens=2048.*reasoning_tokens=1900",
        ):
            backend("programador", "Retorne JSON")

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
        def rate_limit_error():
            return urllib.error.HTTPError(
                "https://api.groq.com/openai/v1/chat/completions",
                429,
                "Too Many Requests",
                Message(),
                io.BytesIO(b'{"error":"try again in 2s"}'),
            )

        mocked_open.side_effect = [rate_limit_error(), rate_limit_error()]
        backend = self.make_backend(max_retries=1)
        with self.assertRaisesRegex(GroqAPIError, "Groq HTTP 429"):
            backend("Programador", "Implemente")
        self.assertEqual(mocked_open.call_count, 2)
        self.assertEqual(mocked_sleep.call_count, 1)
        mocked_sleep.assert_called_once_with(3.0)

    def test_rejects_empty_prompt(self):
        backend = self.make_backend()
        with self.assertRaises(ValueError):
            backend("Analista", " ")


if __name__ == "__main__":
    unittest.main()
