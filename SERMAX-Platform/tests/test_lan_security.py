"""Testes isolados do ciclo de pareamento e credenciais de dispositivos."""

import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# O diretório backend é inserido no sys.path pelo runner do projeto.
import lan_security


class LanSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "security.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def issue(self, device="phone", **kwargs):
        return lan_security.generate_pairing_code(device, db_path=self.db, **kwargs)

    def test_pairing_code_is_single_use_and_credential_persists(self):
        code = self.issue()
        credential = lan_security.complete_pairing("phone", code, self.db)
        self.assertIsInstance(credential, str)
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))
        self.assertIsNone(lan_security.complete_pairing("phone", code, self.db))

    def test_wrong_device_consumes_attempt_and_cannot_pair(self):
        code = self.issue(max_attempts=1)
        self.assertIsNone(lan_security.complete_pairing("intruder", code, self.db))
        self.assertIsNone(lan_security.complete_pairing("phone", code, self.db))

    def test_expired_code_is_rejected(self):
        code = self.issue(ttl_seconds=1)
        with patch.object(lan_security.time, "time", return_value=10**12):
            self.assertIsNone(lan_security.complete_pairing("phone", code, self.db))

    def test_failed_attempts_exhaust_code(self):
        code = self.issue(max_attempts=2)
        self.assertIsNone(lan_security.complete_pairing("wrong", code, self.db))
        self.assertIsNone(lan_security.complete_pairing("wrong", code, self.db))
        self.assertIsNone(lan_security.complete_pairing("phone", code, self.db))

    def test_hash_is_stored_not_plaintext(self):
        code = self.issue()
        credential = lan_security.complete_pairing("phone", code, self.db)
        with sqlite3.connect(self.db) as conn:
            stored_hash, salt = conn.execute(
                "SELECT credential_hash, salt FROM device_credentials WHERE device='phone'"
            ).fetchone()
        self.assertNotEqual(stored_hash, credential.encode())
        self.assertNotIn(credential.encode(), stored_hash)
        self.assertEqual(len(salt), lan_security.SALT_LENGTH)

    def test_revocation_denies_future_authentication(self):
        code = self.issue()
        credential = lan_security.complete_pairing("phone", code, self.db)
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))
        self.assertTrue(lan_security.revoke("phone", self.db))
        self.assertFalse(lan_security.authenticate("phone", credential, self.db))
        self.assertFalse(lan_security.revoke("phone", self.db))

    def test_unknown_device_and_wrong_credential_are_rejected(self):
        code = self.issue()
        credential = lan_security.complete_pairing("phone", code, self.db)
        self.assertFalse(lan_security.authenticate("tablet", credential, self.db))
        self.assertFalse(lan_security.authenticate("phone", "incorrect", self.db))

    def test_concurrent_pairing_code_consumption_is_atomic(self):
        code = self.issue()
        def consume():
            return lan_security.complete_pairing("phone", code, self.db)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: consume(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        credential = next(result for result in results if result is not None)
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))

    def test_parameters_are_validated(self):
        for kwargs in (
            {"ttl_seconds": 0},
            {"ttl_seconds": True},
            {"ttl_seconds": lan_security.MAX_TTL_SECONDS + 1},
            {"max_attempts": 0},
            {"max_attempts": True},
            {"max_attempts": lan_security.MAX_ATTEMPTS + 1},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    self.issue(**kwargs)
        with self.assertRaises(ValueError):
            lan_security.generate_pairing_code(" ", db_path=self.db)
        with self.assertRaises(ValueError):
            lan_security.generate_pairing_code("x" * 129, db_path=self.db)

    def test_pairing_secret_is_not_printed_or_logged(self):
        code = self.issue()
        credential = lan_security.complete_pairing("phone", code, self.db)
        self.assertNotIn(credential, repr(lan_security))
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))

    def test_repair_replaces_previous_device_credential(self):
        first_code = self.issue()
        first = lan_security.complete_pairing("phone", first_code, self.db)
        second_code = self.issue()
        second = lan_security.complete_pairing("phone", second_code, self.db)
        self.assertFalse(lan_security.authenticate("phone", first, self.db))
        self.assertTrue(lan_security.authenticate("phone", second, self.db))

    def test_cleanup_removes_expired_pairings(self):
        code = self.issue(ttl_seconds=1)
        with patch.object(lan_security.time, "time", return_value=10**12):
            self.assertEqual(lan_security.cleanup_expired(self.db), 1)
        self.assertIsNone(lan_security.complete_pairing("phone", code, self.db))


if __name__ == "__main__":
    unittest.main()
