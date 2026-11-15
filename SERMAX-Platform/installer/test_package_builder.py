import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sermax_package_builder import BuildError, build_package, parse_mapping


class PackageBuilderTests(unittest.TestCase):
    def test_builds_manifest_with_real_hashes_and_only_selected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app.py").write_text("print('SERMAX')", encoding="utf-8")
            (source / "private.db").write_text("must not ship", encoding="utf-8")
            output = root / "package"
            result = build_package(source, output, "1.2.3", [(Path("app.py"), Path("Platform/app.py"))])
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            packaged = output / manifest["files"][0]["source"]
            expected = hashlib.sha256(packaged.read_bytes()).hexdigest()
            self.assertEqual(manifest["files"][0]["sha256"], expected)
            self.assertEqual(result["file_count"], 1)
            self.assertFalse((output / "payload" / "private.db").exists())

    def test_rejects_output_inside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app.py").write_text("x", encoding="utf-8")
            with self.assertRaises(BuildError):
                build_package(source, source / "package", "1", [(Path("app.py"), Path("app.py"))])

    def test_rejects_duplicate_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "a").write_text("a", encoding="utf-8")
            (source / "b").write_text("b", encoding="utf-8")
            with self.assertRaises(BuildError):
                build_package(source, root / "package", "1", [
                    (Path("a"), Path("app/file")),
                    (Path("b"), Path("app/file")),
                ])

    def test_rejects_parent_traversal_mapping(self):
        with self.assertRaises(BuildError):
            parse_mapping("../secrets.txt=secret.txt")

    def test_refuses_to_overwrite_existing_package_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app").write_text("x", encoding="utf-8")
            output = root / "package"
            output.mkdir()
            with self.assertRaises(BuildError):
                build_package(source, output, "1", [(Path("app"), Path("app"))])


if __name__ == "__main__":
    unittest.main()
