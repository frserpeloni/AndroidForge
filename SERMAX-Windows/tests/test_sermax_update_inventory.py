import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from sermax_update_inventory import InventoryError, inventory_directory


class TestUpdateInventory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "bin").mkdir()
        (self.root / "bin" / "SERMAX.exe").write_bytes(b"binary-test")
        (self.root / "memoria_sermax.json").write_text('[{"role":"user"}]', encoding="utf-8")
        (self.root / "memoria_neural_pestinha.json").write_text("{}", encoding="utf-8")
        (self.root / "documento-pessoal.txt").write_text("preservar", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_classifies_only_explicit_allowlist_as_managed(self):
        records = inventory_directory(self.root, managed_paths=["bin/SERMAX.exe"])
        by_path = {item["path"]: item for item in records}
        self.assertEqual(by_path["bin/SERMAX.exe"]["classification"], "managed")
        self.assertEqual(by_path["memoria_sermax.json"]["classification"], "protected")
        self.assertEqual(by_path["memoria_neural_pestinha.json"]["classification"], "protected")
        self.assertEqual(by_path["documento-pessoal.txt"]["classification"], "unknown")

    def test_records_sha256_and_size_without_content(self):
        records = inventory_directory(self.root)
        item = next(x for x in records if x["path"] == "bin/SERMAX.exe")
        self.assertEqual(item["sha256"], hashlib.sha256(b"binary-test").hexdigest())
        self.assertEqual(item["size"], len(b"binary-test"))
        self.assertNotIn("content", item)

    def test_inventory_is_deterministic(self):
        first = inventory_directory(self.root)
        second = inventory_directory(self.root)
        self.assertEqual(first, second)

    def test_rejects_missing_root(self):
        with self.assertRaises(InventoryError):
            inventory_directory(self.root / "missing")

    def test_rejects_file_as_root(self):
        with self.assertRaises(InventoryError):
            inventory_directory(self.root / "documento-pessoal.txt")

    def test_rejects_unsafe_allowlist_paths(self):
        for unsafe in ("../outside.txt", "/absolute.txt", "C:/outside.txt", "a//b"):
            with self.subTest(path=unsafe):
                with self.assertRaises(InventoryError):
                    inventory_directory(self.root, managed_paths=[unsafe])

    def test_does_not_follow_symlink(self):
        target = self.root / "outside-target.txt"
        target.write_text("outside", encoding="utf-8")
        link = self.root / "link-out"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Criação de symlink não permitida neste ambiente.")
        records = inventory_directory(self.root)
        item = next(x for x in records if x["path"] == "link-out")
        self.assertEqual(item["type"], "reparse")
        self.assertEqual(item["classification"], "blocked")
        self.assertFalse(any(x["path"].startswith("link-out/") for x in records))


if __name__ == "__main__":
    unittest.main()
