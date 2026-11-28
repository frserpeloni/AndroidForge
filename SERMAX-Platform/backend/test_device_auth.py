import tempfile
import unittest
from pathlib import Path

from device_auth import DeviceAuthenticationError, authenticate_device_headers
from lan_security import (
    approve_pairing_locally,
    finalize_pairing,
    generate_pairing_code,
    reserve_pairing,
    revoke,
)


class DeviceAuthHeaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "devices.sqlite3"
        device = "android-browser-01"
        code = generate_pairing_code(device, db_path=self.db)
        reservation = reserve_pairing(device, code, db_path=self.db)
        self.assertIsNotNone(reservation)
        self.assertTrue(approve_pairing_locally(reservation, device, db_path=self.db))
        self.credential = finalize_pairing(reservation, device, db_path=self.db)
        self.assertIsNotNone(self.credential)
        self.device = device

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_bearer_headers_return_device_id(self):
        result = authenticate_device_headers(
            self.device, f"Bearer {self.credential}", db_path=self.db
        )
        self.assertEqual(result, self.device)

    def test_missing_device_is_rejected(self):
        with self.assertRaises(DeviceAuthenticationError):
            authenticate_device_headers(None, f"Bearer {self.credential}", db_path=self.db)

    def test_missing_or_malformed_authorization_is_rejected(self):
        for value in (None, "", "Basic abc", "Bearer", f"Bearer  {self.credential}",
                      f"Bearer {self.credential} extra"):
            with self.subTest(value=value):
                with self.assertRaises(DeviceAuthenticationError):
                    authenticate_device_headers(self.device, value, db_path=self.db)

    def test_unknown_device_and_wrong_credential_are_rejected(self):
        for device, authorization in (
            ("unknown-device", f"Bearer {self.credential}"),
            (self.device, "Bearer wrong-token"),
        ):
            with self.subTest(device=device):
                with self.assertRaises(DeviceAuthenticationError):
                    authenticate_device_headers(device, authorization, db_path=self.db)

    def test_revoked_device_is_rejected(self):
        self.assertTrue(revoke(self.device, db_path=self.db))
        with self.assertRaises(DeviceAuthenticationError):
            authenticate_device_headers(
                self.device, f"Bearer {self.credential}", db_path=self.db
            )

    def test_invalid_device_header_is_rejected(self):
        for device in ("", "  ", "x" * 129):
            with self.subTest(device=device):
                with self.assertRaises(DeviceAuthenticationError):
                    authenticate_device_headers(device, f"Bearer {self.credential}", db_path=self.db)


if __name__ == "__main__":
    unittest.main()
