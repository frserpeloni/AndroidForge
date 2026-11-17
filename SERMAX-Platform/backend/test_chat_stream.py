import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import server


class StreamingCore:
    sessao = []

    @classmethod
    def perguntar(cls, message, receber_parte=None):
        answer = "Resposta incremental completa."
        cls.sessao.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ])
        if receber_parte:
            receber_parte("Resposta ")
            receber_parte(answer)
        return answer


class FailingStreamingCore:
    sessao = []

    @classmethod
    def perguntar(cls, message, receber_parte=None):
        if receber_parte:
            receber_parte("Trecho parcial")
        raise RuntimeError("falha simulada no streaming")


class ChatStreamApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "stream.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        self.client = TestClient(server.app, client=("127.0.0.1", 50120))
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def events(self, body):
        parsed = []
        for frame in body.split("\n\n"):
            if not frame.strip():
                continue
            event_name = "message"
            data_lines = []
            for line in frame.splitlines():
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
            if data_lines:
                parsed.append((event_name, json.loads("\n".join(data_lines))))
        return parsed

    def test_stream_sends_snapshots_and_persists_final_answer(self):
        server.CORE_MODULE = StreamingCore
        original_session = [{"role": "assistant", "content": "sessão original"}]
        StreamingCore.sessao = original_session.copy()

        response = self.client.post(
            "/api/chat/stream",
            json={"message": "Teste de streaming"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        events = self.events(response.text)
        self.assertIn("snapshot", [name for name, _ in events])
        complete = [data for name, data in events if name == "complete"]
        self.assertEqual(len(complete), 1)
        self.assertEqual(complete[0]["answer"], "Resposta incremental completa.")
        self.assertEqual(StreamingCore.sessao, original_session)

        conversation_id = complete[0]["conversation_id"]
        history = self.client.get(
            f"/api/conversations/{conversation_id}", headers=self.headers
        ).json()
        self.assertEqual(
            [item["content"] for item in history["messages"]],
            ["Teste de streaming", "Resposta incremental completa."],
        )
        self.assertTrue(all(item["status"] == "complete" for item in history["messages"]))

    def test_stream_reports_failure_and_marks_user_message_as_error(self):
        server.CORE_MODULE = FailingStreamingCore
        response = self.client.post(
            "/api/chat/stream",
            json={"message": "Teste de falha"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        events = self.events(response.text)
        errors = [data for name, data in events if name == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("falha simulada", errors[0]["detail"])
        conversations = self.client.get("/api/conversations", headers=self.headers).json()
        history = self.client.get(
            f"/api/conversations/{conversations[0]['id']}", headers=self.headers
        ).json()
        self.assertEqual(history["messages"][0]["status"], "error")

    def test_empty_stream_message_is_rejected(self):
        response = self.client.post(
            "/api/chat/stream", json={"message": " "}, headers=self.headers
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
