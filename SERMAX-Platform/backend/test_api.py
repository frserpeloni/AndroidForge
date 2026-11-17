import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import server


class FakeCore:
    sessao = []

    @classmethod
    def perguntar(cls, message):
        cls.sessao.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": "Resposta de teste: " + message},
        ])
        return "Resposta de teste: " + message


class PlatformApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "test.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        self.client = TestClient(server.app, client=("127.0.0.1", 50000))
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_health_reports_service(self):
        response = self.client.get("/api/health", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "online")

    def test_empty_message_is_rejected(self):
        response = self.client.post(
            "/api/chat", json={"message": " "}, headers=self.headers
        )
        self.assertEqual(response.status_code, 422)

    def test_untrusted_origin_is_rejected(self):
        response = self.client.get(
            "/api/health",
            headers={**self.headers, "origin": "https://example.invalid"},
        )
        self.assertEqual(response.status_code, 403)

    def test_external_ip_is_rejected(self):
        # Cliente com IP externo (não loopback)
        external_client = TestClient(server.app, client=("192.0.2.10", 50002))
        try:
            response = external_client.get(
                "/api/health",
                headers={**self.headers, "host": "127.0.0.1:8765"}
            )
            self.assertEqual(response.status_code, 403)
        finally:
            external_client.close()

    def test_chat_is_saved_and_can_be_reopened(self):
        server.CORE_MODULE = FakeCore
        response = self.client.post(
            "/api/chat", json={"message": "Olá MAX"}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]
        history = self.client.get(
            f"/api/conversations/{conversation_id}", headers=self.headers
        )
        self.assertEqual(history.status_code, 200)
        messages = history.json()["messages"]
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertTrue(all(item["status"] == "complete" for item in messages))

    def test_failed_core_marks_user_message_as_error(self):
        with patch.object(server, "load_core", side_effect=RuntimeError("núcleo offline")):
            response = self.client.post(
                "/api/chat", json={"message": "Teste falha"}, headers=self.headers
            )
        self.assertEqual(response.status_code, 503)
        conversations = self.client.get("/api/conversations", headers=self.headers).json()
        conversation_id = conversations[0]["id"]
        history = self.client.get(
            f"/api/conversations/{conversation_id}", headers=self.headers
        ).json()
        self.assertEqual(history["messages"][0]["status"], "error")

    def test_project_create_update_and_archive(self):
        created = self.client.post(
            "/api/projects",
            json={"name": "Projeto SERMAX", "description": "Teste", "instructions": "Contexto"},
            headers=self.headers,
        )
        self.assertEqual(created.status_code, 201)
        project_id = created.json()["id"]
        updated = self.client.put(
            f"/api/projects/{project_id}",
            json={"description": "Descrição atualizada"},
            headers=self.headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["description"], "Descrição atualizada")
        archived = self.client.post(
            f"/api/projects/{project_id}/archive", headers=self.headers
        )
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.json()["archived"], 1)
        self.assertEqual(
            self.client.get("/api/projects", headers=self.headers).json(), []
        )
        self.assertEqual(
            self.client.get(f"/api/projects/{project_id}", headers=self.headers).status_code,
            404,
        )

    def test_conversation_is_associated_with_project(self):
        project = self.client.post(
            "/api/projects", json={"name": "Projeto A"}, headers=self.headers
        ).json()
        server.CORE_MODULE = FakeCore
        response = self.client.post(
            "/api/chat",
            json={"message": "Mensagem do projeto", "project_id": project["id"]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]
        history = self.client.get(
            f"/api/conversations/{conversation_id}", headers=self.headers
        ).json()
        self.assertEqual(history["conversation"]["project_id"], project["id"])
        project_conversations = self.client.get(
            f"/api/projects/{project['id']}/conversations", headers=self.headers
        ).json()
        self.assertEqual(project_conversations[0]["id"], conversation_id)

    def test_archived_project_rejects_new_conversation(self):
        project = self.client.post(
            "/api/projects", json={"name": "Projeto arquivado"}, headers=self.headers
        ).json()
        self.client.post(f"/api/projects/{project['id']}/archive", headers=self.headers)
        response = self.client.post(
            "/api/chat",
            json={"message": "Não deve entrar", "project_id": project["id"]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)


    def test_project_instructions_are_scoped_to_project_conversation(self):
        project = self.client.post(
            "/api/projects",
            json={"name": "Projeto Contexto", "instructions": "Use o padrão técnico do Projeto Contexto."},
            headers=self.headers,
        ).json()
        server.CORE_MODULE = FakeCore
        original_session = [{"role": "assistant", "content": "sessão externa preservada"}]
        FakeCore.sessao = original_session.copy()
        response = self.client.post(
            "/api/chat",
            json={"message": "Faça uma análise", "project_id": project["id"]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeCore.sessao, original_session)
        history = self.client.get(
            f"/api/conversations/{response.json()['conversation_id']}",
            headers=self.headers,
        ).json()
        self.assertEqual(history["messages"][0]["content"], "Faça uma análise")

    def test_project_context_does_not_leak_into_unrelated_conversation(self):
        project = self.client.post(
            "/api/projects",
            json={"name": "Projeto Isolado", "instructions": "SEGREDO DO PROJETO"},
            headers=self.headers,
        ).json()
        server.CORE_MODULE = FakeCore
        seen = []
        class InspectingCore:
            sessao = []
            @classmethod
            def perguntar(cls, message):
                seen.append(list(cls.sessao))
                cls.sessao.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": "ok"},
                ])
                return "ok"
        server.CORE_MODULE = InspectingCore
        self.client.post(
            "/api/chat",
            json={"message": "Pergunta privada", "project_id": project["id"]},
            headers=self.headers,
        )
        self.client.post(
            "/api/chat",
            json={"message": "Pergunta geral"},
            headers=self.headers,
        )
        self.assertTrue(any("SEGREDO DO PROJETO" in item.get("content", "") for item in seen[0]))
        self.assertFalse(any("SEGREDO DO PROJETO" in item.get("content", "") for item in seen[1]))


    def test_archived_project_context_remains_on_existing_conversation(self):
        project = self.client.post(
            "/api/projects",
            json={"name": "Projeto Arquivado", "instructions": "CONTEXTO ARQUIVADO"},
            headers=self.headers,
        ).json()
        seen = []
        class InspectingCore:
            sessao = []
            @classmethod
            def perguntar(cls, message):
                seen.append(list(cls.sessao))
                cls.sessao.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": "ok"},
                ])
                return "ok"
        server.CORE_MODULE = InspectingCore
        first = self.client.post(
            "/api/chat",
            json={"message": "Primeira mensagem", "project_id": project["id"]},
            headers=self.headers,
        )
        conversation_id = first.json()["conversation_id"]
        self.client.post(f"/api/projects/{project['id']}/archive", headers=self.headers)
        second = self.client.post(
            "/api/chat",
            json={"message": "Continuar conversa", "conversation_id": conversation_id},
            headers=self.headers,
        )
        self.assertEqual(second.status_code, 200)
        self.assertTrue(any(
            "CONTEXTO ARQUIVADO" in item.get("content", "")
            for item in seen[-1]
        ))


    def test_sqlite_data_survives_service_restart(self):
        project = self.client.post(
            "/api/projects",
            json={"name": "Persistência após reinício", "instructions": "Contexto persistente"},
            headers=self.headers,
        ).json()
        server.CORE_MODULE = FakeCore
        response = self.client.post(
            "/api/chat",
            json={"message": "Mensagem antes do reinício", "project_id": project["id"]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]

        self.client.close()
        # Reabre a aplicação usando o mesmo arquivo SQLite, como em um novo processo.
        server.initialize_database()
        restarted_client = TestClient(server.app, client=("127.0.0.1", 50001))
        try:
            projects = restarted_client.get("/api/projects", headers=self.headers).json()
            self.assertEqual(projects[0]["id"], project["id"])
            history = restarted_client.get(
                f"/api/conversations/{conversation_id}", headers=self.headers
            )
            self.assertEqual(history.status_code, 200)
            saved = history.json()
            self.assertEqual(saved["conversation"]["project_id"], project["id"])
            self.assertEqual(
                [item["content"] for item in saved["messages"]],
                ["Mensagem antes do reinício", "Resposta de teste: Mensagem antes do reinício"],
            )
            self.assertTrue(all(item["status"] == "complete" for item in saved["messages"]))
        finally:
            restarted_client.close()


if __name__ == "__main__":
    unittest.main()
