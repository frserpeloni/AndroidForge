"""Testes da política de acesso remoto atrás de proxy confiável."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from lan_security import approve_pairing_locally, finalize_pairing, generate_pairing_code, reserve_pairing


PUBLIC_HOST = "sermax-test.example.ts.net"
PUBLIC_ORIGIN = "https://" + PUBLIC_HOST


class RemoteAccessGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "platform.sqlite3"
        server.SECURITY_DB_PATH = server.DATA_DIR / "device_security.sqlite3"
        server.initialize_database()
        self.client = TestClient(server.app, client=("127.0.0.1", 51234))
        self.local_headers = {"host": "127.0.0.1:8765"}
        self.proxy_headers = {
            "host": PUBLIC_HOST,
            "origin": PUBLIC_ORIGIN,
            "x-forwarded-proto": "https",
        }
        self.env = patch.dict(os.environ, {
            "SERMAX_REMOTE_ACCESS_ENABLED": "1",
            "SERMAX_PUBLIC_HOST": PUBLIC_HOST,
            "SERMAX_TRUSTED_PROXY_IPS": "127.0.0.1,::1",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()
        self.temp.cleanup()

    def _credential(self):
        device = "android-remote-test"
        code = generate_pairing_code(device, db_path=server.SECURITY_DB_PATH)
        reservation = reserve_pairing(device, code, db_path=server.SECURITY_DB_PATH)
        self.assertIsNotNone(reservation)
        self.assertTrue(approve_pairing_locally(reservation, device, db_path=server.SECURITY_DB_PATH))
        credential = finalize_pairing(reservation, device, db_path=server.SECURITY_DB_PATH)
        self.assertTrue(credential)
        return device, credential

    def test_local_loopback_interface_remains_available(self):
        with patch.dict(os.environ, {"SERMAX_REMOTE_ACCESS_ENABLED": "0"}):
            response = self.client.get("/api/health", headers=self.local_headers)
        self.assertEqual(response.status_code, 200)

    def test_remote_data_routes_require_individual_device_credential(self):
        missing = self.client.get("/api/projects", headers=self.proxy_headers)
        self.assertEqual(missing.status_code, 401)

        device, credential = self._credential()
        headers = {
            **self.proxy_headers,
            "cookie": f"sermax_device_id={device}; sermax_device_credential={credential}",
        }
        accepted = self.client.get("/api/projects", headers=headers)
        self.assertEqual(accepted.status_code, 200)

    def test_remote_mutations_require_exact_origin(self):
        headers = {key: value for key, value in self.proxy_headers.items() if key != "origin"}
        response = self.client.post("/api/device/pairing/reserve", json={
            "device_id": "phone", "code": "invalid"
        }, headers=headers)
        self.assertEqual(response.status_code, 403)

    def test_authenticated_device_session_uses_cookie_identity(self):
        device, credential = self._credential()
        headers = {
            **self.proxy_headers,
            "cookie": f"sermax_device_id={device}; sermax_device_credential={credential}",
        }
        response = self.client.get("/api/device/session", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": True, "device_id": device})

    def test_remote_admin_routes_remain_forbidden_even_with_valid_credential(self):
        device, credential = self._credential()
        headers = {
            **self.proxy_headers,
            "cookie": f"sermax_device_id={device}; sermax_device_credential={credential}",
        }
        response = self.client.get("/api/local/pairings/pending", headers=headers)
        self.assertEqual(response.status_code, 403)

    def test_remote_request_requires_exact_public_host_and_https_assertion(self):
        wrong_host = self.client.get(
            "/api/projects", headers={**self.proxy_headers, "host": "attacker.example"}
        )
        self.assertEqual(wrong_host.status_code, 403)

        no_https = self.client.get(
            "/api/projects", headers={k: v for k, v in self.proxy_headers.items()
                                      if k != "x-forwarded-proto"}
        )
        self.assertEqual(no_https.status_code, 403)

        wrong_origin = self.client.get(
            "/api/projects", headers={**self.proxy_headers, "origin": "https://attacker.example"}
        )
        self.assertEqual(wrong_origin.status_code, 403)

    def test_remote_access_is_closed_when_feature_flag_is_off(self):
        with patch.dict(os.environ, {"SERMAX_REMOTE_ACCESS_ENABLED": "0"}):
            response = self.client.get("/api/health", headers=self.proxy_headers)
        self.assertEqual(response.status_code, 403)

    def test_untrusted_network_peer_is_rejected_even_with_proxy_headers(self):
        external = TestClient(server.app, client=("192.0.2.40", 51235))
        try:
            response = external.get("/api/health", headers=self.proxy_headers)
            self.assertEqual(response.status_code, 403)
        finally:
            external.close()


if __name__ == "__main__":
    unittest.main()
