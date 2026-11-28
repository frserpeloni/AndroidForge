"""Testes das rotas locais e do fluxo HTTP de pareamento SERMAX."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import server
import device_pairing_api


class DevicePairingApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "platform.sqlite3"
        server.SECURITY_DB_PATH = server.DATA_DIR / "device_security.sqlite3"
        self.client = TestClient(server.app, client=("127.0.0.1", 51000))
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_pairing_requires_local_approval_then_issues_credential(self):
        created = self.client.post(
            "/api/local/pairings",
            json={"device_id": "android-phone"},
            headers=self.headers,
        )
        self.assertEqual(created.status_code, 201)
        code = created.json()["code"]

        reserved = self.client.post(
            "/api/device/pairing/reserve",
            json={"device_id": "android-phone", "code": code},
            headers=self.headers,
        )
        self.assertEqual(reserved.status_code, 202)
        reservation_id = reserved.json()["reservation_id"]

        pending = self.client.get("/api/local/pairings/pending", headers=self.headers)
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.json()["items"][0]["device"], "android-phone")
        self.assertNotIn("code", pending.text)

        blocked = self.client.post(
            "/api/device/pairing/finalize",
            json={"device_id": "android-phone", "reservation_id": reservation_id},
            headers=self.headers,
        )
        self.assertEqual(blocked.status_code, 403)

        approved = self.client.post(
            f"/api/local/pairings/{reservation_id}/approve",
            json={"device_id": "android-phone"},
            headers=self.headers,
        )
        self.assertEqual(approved.status_code, 200)

        finalized = self.client.post(
            "/api/device/pairing/finalize",
            json={"device_id": "android-phone", "reservation_id": reservation_id},
            headers=self.headers,
        )
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.json(), {
            "device_id": "android-phone", "authenticated": True
        })
        self.assertNotIn("credential", finalized.json())
        set_cookie = finalized.headers.get_list("set-cookie")
        self.assertEqual(len(set_cookie), 2)
        self.assertTrue(all("httponly" in value.lower() for value in set_cookie))
        self.assertTrue(all("secure" in value.lower() for value in set_cookie))
        self.assertTrue(all("samesite=strict" in value.lower() for value in set_cookie))

    def test_remote_client_is_still_blocked_by_loopback_guard(self):
        external = TestClient(server.app, client=("192.0.2.20", 51001))
        try:
            response = external.post(
                "/api/device/pairing/reserve",
                json={"device_id": "phone", "code": "invalid"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 403)
        finally:
            external.close()

    def test_pairing_reservation_endpoint_limits_repeated_attempts(self):
        for attempt in range(8):
            response = self.client.post(
                "/api/device/pairing/reserve",
                json={"device_id": "android-phone", "code": "invalid-code"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 400, msg=f"attempt {attempt + 1}")
        limited = self.client.post(
            "/api/device/pairing/reserve",
            json={"device_id": "android-phone", "code": "invalid-code"},
            headers=self.headers,
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers.get("retry-after"), "60")

    def test_invalid_pairing_code_does_not_create_reservation(self):
        response = self.client.post(
            "/api/device/pairing/reserve",
            json={"device_id": "phone", "code": "not-a-valid-code"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
