import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sermax_update_signature import build_ed25519_verifier


class Ed25519VerifierTests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        self.public_bytes = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.verifier = build_ed25519_verifier({
            "sermax-test-2026": self.public_bytes,
        })
        self.payload = b'{"schema_version":1,"release_version":"1.2.3"}'
        self.signature = self.private_key.sign(self.payload)

    def test_accepts_valid_ed25519_signature(self):
        self.assertIs(
            self.verifier("sermax-test-2026", self.payload, self.signature),
            True,
        )

    def test_rejects_tampered_payload(self):
        self.assertIs(
            self.verifier("sermax-test-2026", self.payload + b" ", self.signature),
            False,
        )

    def test_rejects_unknown_key_id(self):
        self.assertIs(
            self.verifier("unknown-key", self.payload, self.signature),
            False,
        )

    def test_rejects_malformed_signature_length(self):
        self.assertIs(
            self.verifier("sermax-test-2026", self.payload, b"short"),
            False,
        )

    def test_rejects_non_bytes_payload(self):
        self.assertIs(
            self.verifier("sermax-test-2026", "payload", self.signature),
            False,
        )

    def test_rejects_invalid_public_key_length_at_configuration(self):
        with self.assertRaises(ValueError):
            build_ed25519_verifier({"bad-key": b"short"})

    def test_rejects_invalid_key_id_at_configuration(self):
        with self.assertRaises(ValueError):
            build_ed25519_verifier({"../release": self.public_bytes})

    def test_requires_mapping_for_trusted_keys(self):
        with self.assertRaises(TypeError):
            build_ed25519_verifier([])


if __name__ == "__main__":
    unittest.main()
