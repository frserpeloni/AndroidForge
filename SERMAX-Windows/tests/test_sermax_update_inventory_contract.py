import unittest

from sermax_update_inventory_contract import (
    InventoryContractError,
    build_inventory_plan,
)
from sermax_update_manifest import ManifestFile, ValidatedManifest


def manifest(*items):
    return ValidatedManifest(
        release_version="1.2.3",
        files=tuple(items),
        key_id="test-key",
        manifest_sha256="a" * 64,
    )


def file_item(path, action="replace"):
    return ManifestFile(path, 10, "b" * 64, action)


def record(path, *, entry_type="file", classification="unknown",
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
    def test_replace_existing_regular_file(self):
        result = build_inventory_plan(
            [record("bin/SERMAX.exe")],
            manifest(file_item("bin/SERMAX.exe")),
        )
        self.assertEqual(result.release_version, "1.2.3")
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].action, "replace")
        self.assertEqual(result.entries[0].current_file_id, "00112233445566778899aabbccddeeff")

    def test_create_requires_absent_destination(self):
        result = build_inventory_plan(
            [record("bin", entry_type="directory", size=None, digest=None)],
            manifest(file_item("bin/new.exe", "create")),
        )
        self.assertEqual(result.entries[0].action, "create")
        self.assertIsNone(result.entries[0].current_file_id)

    def test_create_rejects_existing_destination(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan(
                [record("bin/new.exe")],
                manifest(file_item("bin/new.exe", "create")),
            )

    def test_replace_rejects_missing_destination(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan([], manifest(file_item("missing.exe")))

    def test_replace_rejects_directory_and_reparse_destinations(self):
        for entry_type, classification in (
            ("directory", "unknown"),
            ("reparse", "blocked"),
            ("special", "blocked"),
        ):
            with self.subTest(entry_type=entry_type):
                with self.assertRaises(InventoryContractError):
                    build_inventory_plan(
                        [record("target", entry_type=entry_type,
                                classification=classification)],
                        manifest(file_item("target")),
                    )

    def test_rejects_inventory_case_collision(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan(
                [record("Bin/SERMAX.exe"), record("bin/sermax.EXE")],
                manifest(file_item("bin/SERMAX.exe")),
            )

    def test_rejects_protected_path_even_if_misclassified(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan(
                [record("memoria_sermax.json", classification="unknown")],
                manifest(file_item("bin/SERMAX.exe", "create")),
            )

    def test_rejects_target_under_existing_file_ancestor(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan(
                [record("bin", entry_type="file")],
                manifest(file_item("bin/SERMAX.exe", "create")),
            )

    def test_rejects_target_that_is_ancestor_of_existing_entry(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan(
                [record("bin/SERMAX.exe")],
                manifest(file_item("bin", "create")),
            )

    def test_rejects_missing_current_hash_for_replace(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan(
                [record("target", digest=None)],
                manifest(file_item("target")),
            )

    def test_rejects_missing_128_bit_file_identity_for_replace(self):
        with self.assertRaises(InventoryContractError):
            build_inventory_plan(
                [record("target", file_id=None)],
                manifest(file_item("target")),
            )


if __name__ == "__main__":
    unittest.main()
