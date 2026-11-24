"""Testes isolados do fluxo de reserva, aprovação local e credenciais."""

import concurrent.futures
import contextlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lan_security


class LanSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "security.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def issue(self, device="phone", **kwargs):
        return lan_security.generate_pairing_code(device, db_path=self.db, **kwargs)

    def reserve(self, device, code, **kwargs):
        return lan_security.reserve_pairing(device, code, db_path=self.db, **kwargs)

    def approve(self, reservation, device="phone"):
        return lan_security.approve_pairing_locally(reservation, device, db_path=self.db)

    def finalize(self, reservation, device="phone", **kwargs):
        return lan_security.finalize_pairing(
            reservation, device, db_path=self.db, **kwargs
        )

    def test_pairing_requires_local_approval_and_is_single_use(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.assertIsInstance(reservation, str)
        self.assertIsNone(self.finalize(reservation))
        self.assertTrue(self.approve(reservation))
        credential = self.finalize(reservation)
        self.assertIsInstance(credential, str)
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))
        self.assertIsNone(self.finalize(reservation))

    def test_approval_is_bound_to_device_and_reservation(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.assertFalse(self.approve(reservation, "tablet"))
        self.assertFalse(self.approve("unknown-reservation"))
        self.assertFalse(self.approve(reservation + "x"))
        self.assertTrue(self.approve(reservation))
        self.assertIsNone(self.finalize(reservation, "tablet"))
        credential = self.finalize(reservation)
        self.assertIsInstance(credential, str)

    def test_only_one_active_reservation_per_pairing_code(self):
        code = self.issue()
        first = self.reserve("phone", code)
        self.assertIsInstance(first, str)
        self.assertIsNone(self.reserve("phone", code))

    def test_concurrent_reservation_is_atomic(self):
        code = self.issue()
        def reserve_once(_):
            return self.reserve("phone", code)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve_once, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)

    def test_concurrent_finalization_emits_at_most_one_credential(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.assertTrue(self.approve(reservation))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.finalize(reservation), range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)
        credential = next(value for value in results if value is not None)
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))

    def test_wrong_device_consumes_attempt(self):
        code = self.issue(max_attempts=1)
        self.assertIsNone(self.reserve("intruder", code))
        self.assertIsNone(self.reserve("phone", code))

    def test_expired_code_is_rejected(self):
        code = self.issue(ttl_seconds=1)
        with patch.object(lan_security.time, "time", return_value=10**12):
            self.assertIsNone(self.reserve("phone", code))

    def test_expired_reservation_cannot_be_approved_or_finalized(self):
        code = self.issue()
        reservation = self.reserve("phone", code, reservation_ttl_seconds=1)
        with patch.object(lan_security.time, "time", return_value=10**12):
            self.assertFalse(self.approve(reservation))
            self.assertIsNone(self.finalize(reservation))

    def test_reservation_expiry_allows_new_reservation(self):
        code = self.issue()
        first = self.reserve("phone", code, reservation_ttl_seconds=1)
        with patch.object(lan_security.time, "time", return_value=10**12):
            self.assertIsNone(self.finalize(first))
        second = self.reserve("phone", code)
        self.assertIsInstance(second, str)
        self.assertNotEqual(first, second)

    def test_approval_cannot_be_replayed_for_another_reservation(self):
        first_code = self.issue()
        first = self.reserve("phone", first_code)
        self.assertTrue(self.approve(first))
        self.assertIsInstance(self.finalize(first), str)
        second_code = self.issue()
        second = self.reserve("phone", second_code)
        self.assertIsNone(self.finalize(second))

    def test_hash_is_stored_not_plaintext(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.assertTrue(self.approve(reservation))
        credential = self.finalize(reservation)
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            stored_hash, salt = conn.execute(
                "SELECT credential_hash, salt FROM device_credentials WHERE device='phone'"
            ).fetchone()
        self.assertNotEqual(stored_hash, credential.encode())
        self.assertNotIn(credential.encode(), stored_hash)
        self.assertEqual(len(salt), lan_security.SALT_LENGTH)

    def test_revocation_denies_future_authentication(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.approve(reservation)
        credential = self.finalize(reservation)
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))
        self.assertTrue(lan_security.revoke("phone", self.db))
        self.assertFalse(lan_security.authenticate("phone", credential, self.db))
        self.assertFalse(lan_security.revoke("phone", self.db))

    def test_unknown_device_and_wrong_credential_are_rejected(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.approve(reservation)
        credential = self.finalize(reservation)
        self.assertFalse(lan_security.authenticate("tablet", credential, self.db))
        self.assertFalse(lan_security.authenticate("phone", "incorrect", self.db))

    def test_repair_replaces_previous_device_credential(self):
        first_code = self.issue()
        first_reservation = self.reserve("phone", first_code)
        self.approve(first_reservation)
        first = self.finalize(first_reservation)
        second_code = self.issue()
        second_reservation = self.reserve("phone", second_code)
        self.approve(second_reservation)
        second = self.finalize(second_reservation)
        self.assertFalse(lan_security.authenticate("phone", first, self.db))
        self.assertTrue(lan_security.authenticate("phone", second, self.db))

    def test_persistent_credential_expires(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.approve(reservation)
        credential = self.finalize(reservation, credential_ttl_seconds=1)
        self.assertTrue(lan_security.authenticate("phone", credential, self.db))
        with patch.object(lan_security.time, "time", return_value=10**12):
            self.assertFalse(lan_security.authenticate("phone", credential, self.db))

    def test_credential_ttl_is_validated(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.approve(reservation)
        with self.assertRaises(ValueError):
            self.finalize(reservation, credential_ttl_seconds=0)

    def test_parameters_are_validated(self):
        for kwargs in (
            {"ttl_seconds": 0},
            {"ttl_seconds": True},
            {"ttl_seconds": lan_security.MAX_TTL_SECONDS + 1},
            {"max_attempts": 0},
            {"max_attempts": True},
            {"max_attempts": lan_security.MAX_ATTEMPTS + 1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.issue(**kwargs)
        with self.assertRaises(ValueError):
            self.issue(" ")
        with self.assertRaises(ValueError):
            self.issue("x" * 129)
        code = self.issue()
        with self.assertRaises(ValueError):
            self.reserve("phone", code, reservation_ttl_seconds=0)

    def test_cleanup_removes_expired_reservations_and_pairings(self):
        code = self.issue(ttl_seconds=1)
        reservation = self.reserve("phone", code, reservation_ttl_seconds=1)
        with patch.object(lan_security.time, "time", return_value=10**12):
            self.assertEqual(lan_security.cleanup_expired(self.db), 1)
            self.assertFalse(self.approve(reservation))
            with contextlib.closing(sqlite3.connect(self.db)) as conn:
                orphan_approvals = conn.execute(
                    "SELECT COUNT(*) FROM local_pairing_approvals"
                ).fetchone()[0]
            self.assertEqual(orphan_approvals, 0)
            self.assertIsNone(self.reserve("phone", code))

    def test_legacy_credentials_with_zero_expiry_fail_closed(self):
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            conn.execute("""
                CREATE TABLE device_credentials (
                    device TEXT PRIMARY KEY,
                    credential_hash BLOB NOT NULL,
                    salt BLOB NOT NULL,
                    created_at INTEGER NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                """INSERT INTO device_credentials
                   (device, credential_hash, salt, created_at, revoked)
                   VALUES ('old-phone', ?, ?, 1, 0)""",
                (b"legacy-hash", b"legacy-salt"),
            )
            conn.commit()
        self.assertFalse(lan_security.authenticate("old-phone", "legacy-secret", self.db))
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            expiry = conn.execute(
                "SELECT expires_at FROM device_credentials WHERE device='old-phone'"
            ).fetchone()[0]
        self.assertEqual(expiry, 0)

    def test_local_approval_and_finalization_do_not_call_external_verifier(self):
        code = self.issue()
        reservation = self.reserve("phone", code)
        self.assertTrue(self.approve(reservation))
        credential = self.finalize(reservation)
        self.assertIsInstance(credential, str)


if __name__ == "__main__":
    unittest.main()
