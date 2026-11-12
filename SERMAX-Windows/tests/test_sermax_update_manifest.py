import base64
import json
import unittest

from sermax_update_manifest import ManifestError, validate_signed_manifest


class SignedManifestTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "schema_version": 1,
            "release_version": "1.2.3",
            "files": [{
                "path": "bin/SERMAX.exe",
                "size": 123,
                "sha256": "a" * 64,
                "classification": "managed",
                "action": "replace",
            }],
            "signature": {
                "algorithm": "Ed25519",
                "key_id": "sermax-release-2026",
                "value": base64.b64encode(b"s" * 64).decode("ascii"),
            },
        }
        self.calls = []

    def verifier(self, key_id, payload, signature):
        self.calls.append((key_id, payload, signature))
        return key_id == "sermax-release-2026" and signature == b"s" * 64

    def raw(self):
        return json.dumps(self.document, ensure_ascii=False).encode("utf-8")

    def test_accepts_valid_manifest_and_canonical_signature_payload(self):
        result = validate_signed_manifest(self.raw(), verify_signature=self.verifier)
        self.assertEqual(result.release_version, "1.2.3")
        self.assertEqual(result.files[0].path, "bin/SERMAX.exe")
        self.assertEqual(result.files[0].action, "replace")
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn(b'"signature"', self.calls[0][1])

    def test_accepts_semver_prerelease_and_build_metadata(self):
        for version in ("1.2.3-alpha.1", "1.2.3+build.7", "1.2.3-rc.1+build.7"):
            with self.subTest(version=version):
                self.document["release_version"] = version
                result = validate_signed_manifest(self.raw(), verify_signature=self.verifier)
                self.assertEqual(result.release_version, version)

    def test_rejects_protected_data_directories(self):
        for path in ("_update/staging/payload.bin", "backups/old.exe",
                     "historico/session.json", "config/settings.json",
                     "voz/model.bin", "models/local.gguf"):
            with self.subTest(path=path):
                self.document["files"][0]["path"] = path
                with self.assertRaises(ManifestError):
                    validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_fails_closed_without_verifier(self):
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=None)

    def test_rejects_invalid_signature(self):
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=lambda *_: False)

    def test_rejects_signature_verifier_exception(self):
        def broken(*_):
            raise RuntimeError("backend unavailable")
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=broken)

    def test_rejects_unsupported_signature_algorithm(self):
        self.document["signature"]["algorithm"] = "RSA"
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_duplicate_json_keys(self):
        raw = b'{"schema_version":1,"schema_version":1}'
        with self.assertRaises(ManifestError):
            validate_signed_manifest(raw, verify_signature=self.verifier)

    def test_rejects_case_insensitive_path_collision(self):
        self.document["files"].append({
            "path": "BIN/sermax.EXE",
            "size": 1,
            "sha256": "b" * 64,
            "classification": "managed",
            "action": "create",
        })
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_protected_memory_destination(self):
        self.document["files"][0]["path"] = "backup/memoria_sermax.json"
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_path_traversal(self):
        self.document["files"][0]["path"] = "../outside.exe"
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_unknown_fields(self):
        self.document["unexpected"] = True
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_boolean_file_size(self):
        self.document["files"][0]["size"] = True
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_non_string_action(self):
        self.document["files"][0]["action"] = ["replace"]
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_unmanaged_classification(self):
        self.document["files"][0]["classification"] = "unknown"
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_invalid_hash(self):
        self.document["files"][0]["sha256"] = "not-a-hash"
        with self.assertRaises(ManifestError):
            validate_signed_manifest(self.raw(), verify_signature=self.verifier)

    def test_rejects_oversized_manifest(self):
        with self.assertRaises(ManifestError):
            validate_signed_manifest(b"x" * (1024 * 1024 + 1), verify_signature=self.verifier)


if __name__ == "__main__":
    unittest.main()
