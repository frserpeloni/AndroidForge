import base64
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sermax_update_inventory_contract import (
    InventoryContractError,
    build_inventory_plan,
    classify_inventory,
)
from sermax_update_manifest import ManifestFile
from sermax_update_signature import build_ed25519_verifier


_TEST_PRIVATE_KEY = Ed25519PrivateKey.generate()
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
_TEST_VERIFIER = build_ed25519_verifier({"inventory-contract-test": _TEST_PUBLIC_KEY})


def manifest(*items):
    document = {
        "schema_version": 1,
        "release_version": "1.2.3",
        "files": [{
            "path": item.path,
            "size": item.size,
            "sha256": item.sha256,
            "classification": "managed",
            "action": item.action,
        } for item in items],
    }
    payload = json.dumps(
        document, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    document["signature"] = {
        "algorithm": "Ed25519",
        "key_id": "inventory-contract-test",
        "value": base64.b64encode(_TEST_PRIVATE_KEY.sign(payload)).decode("ascii"),
    }
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def build_plan(inventory, raw_manifest):
    return build_inventory_plan(
        inventory,
        raw_manifest,
        verify_signature=_TEST_VERIFIER,
    )


def file_item(path, action="replace"):
    return ManifestFile(path, 10, "b" * 64, action)


def record(path, *, entry_type="file", classification="managed",
           size=10, digest="c" * 64, file_id="00112233445566778899aabbccddeeff"):
    return {
        "path": path,
        "type": entry_type,
        "classification": classification,
        "size": size,
        "sha256": digest,
        "file_id": file_id,
    }


class InventoryContractTests(unittest.TestCase):
    def test_allowlist_marks_only_regular_files_as_managed(self):
        raw = [
            record("bin", entry_type="directory", classification="unknown",
                   size=None, digest=None, file_id=None),
            record("bin/SERMAX.exe", classification="unknown"),
            record("notes.txt", classification="unknown"),
        ]
        classified = classify_inventory(raw, ["bin/SERMAX.exe"])
        by_path = {item["path"]: item["classification"] for item in classified}
        self.assertEqual(by_path["bin"], "unknown")
        self.assertEqual(by_path["bin/SERMAX.exe"], "managed")
        self.assertEqual(by_path["notes.txt"], "unknown")
        self.assertEqual(raw[1]["classification"], "unknown")

    def test_allowlist_rejects_missing_and_protected_paths(self):
        with self.assertRaises(InventoryContractError):
            classify_inventory([record("notes.txt")], ["missing.exe"])
        with self.assertRaises(InventoryContractError):
            classify_inventory([record("memoria_sermax.json")],
                               ["memoria_sermax.json"])

    def test_allowlist_rejects_non_file_target(self):
        with self.assertRaises(InventoryContractError):
            classify_inventory(
                [record("target", entry_type="directory", size=None,
                        digest=None, file_id=None)],
                ["target"],
            )

    def test_rejects_manifest_with_invalid_signature(self):
        raw = json.loads(manifest(file_item("target", "create")))
        raw["signature"]["value"] = base64.b64encode(b"x" * 64).decode("ascii")
        with self.assertRaises(InventoryContractError):
            build_plan([], json.dumps(raw).encode("utf-8"))

    def test_rejects_plan_without_signature_verifier(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan([], manifest(file_item("target", "create")))

    def test_replace_existing_regular_file(self):
        result = build_plan(
            [record("bin/SERMAX.exe")],
            manifest(file_item("bin/SERMAX.exe")),
        )
        self.assertEqual(result.release_version, "1.2.3")
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].action, "replace")
        self.assertEqual(result.entries[0].current_file_id, "00112233445566778899aabbccddeeff")

    def test_create_requires_absent_destination(self):
        result = build_plan(
            [record("bin", entry_type="directory", size=None, digest=None)],
            manifest(file_item("bin/new.exe", "create")),
        )
        self.assertEqual(result.entries[0].action, "create")
        self.assertIsNone(result.entries[0].current_file_id)

    def test_create_rejects_existing_destination(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("bin/new.exe")],
                manifest(file_item("bin/new.exe", "create")),
            )

    def test_replace_rejects_missing_destination(self):
        with self.assertRaises(InventoryContractError):
            build_plan([], manifest(file_item("missing.exe")))

    def test_replace_rejects_directory_and_reparse_destinations(self):
        for entry_type, classification in (
            ("directory", "unknown"),
            ("reparse", "blocked"),
            ("special", "blocked"),
        ):
            with self.subTest(entry_type=entry_type):
                with self.assertRaises(InventoryContractError):
                    build_plan(
                        [record("target", entry_type=entry_type,
                                classification=classification)],
                        manifest(file_item("target")),
                    )

    def test_rejects_inventory_case_collision(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("Bin/SERMAX.exe"), record("bin/sermax.EXE")],
                manifest(file_item("bin/SERMAX.exe")),
            )

    def test_rejects_protected_path_even_if_misclassified(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("memoria_sermax.json", classification="unknown")],
                manifest(file_item("bin/SERMAX.exe", "create")),
            )

    def test_rejects_target_under_existing_file_ancestor(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("bin", entry_type="file")],
                manifest(file_item("bin/SERMAX.exe", "create")),
            )

    def test_rejects_unicode_normalization_ancestor_collision(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("café/child.txt")],
                manifest(file_item("cafe\u0301", "create")),
            )

    def test_rejects_target_that_is_ancestor_of_existing_entry(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("bin/SERMAX.exe")],
                manifest(file_item("bin", "create")),
            )

    def test_rejects_unknown_file_for_replace(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("target", classification="unknown")],
                manifest(file_item("target")),
            )

    def test_rejects_missing_current_hash_for_replace(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("target", digest=None)],
                manifest(file_item("target")),
            )

    def test_rejects_missing_128_bit_file_identity_for_replace(self):
        with self.assertRaises(InventoryContractError):
            build_plan(
                [record("target", file_id=None)],
                manifest(file_item("target")),
            )


if __name__ == "__main__":
    unittest.main()
