import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sermax_installer_core import PackageError, install_package, load_package, preflight


def write_package(root: Path, files: dict[str, str], preserve=None):
    entries = []
    for name, content in files.items():
        path = root / "payload" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        entries.append({
            "source": f"payload/{name}",
            "target": name,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "version": "0.1.0-test",
        "files": entries,
        "preserve_paths": preserve or ["data", "memoria_sermax.json"],
    }), encoding="utf-8")


class InstallerCoreTests(unittest.TestCase):
    def test_preflight_validates_package_without_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/start.txt": "SERMAX"})
            result = preflight(package, destination)
            self.assertEqual(result["file_count"], 1)
            self.assertFalse((destination / "app/start.txt").exists())

    def test_install_copies_only_manifest_files_and_preserves_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/start.txt": "new version"})
            (destination / "data").mkdir(parents=True)
            (destination / "data" / "history.db").write_text("keep", encoding="utf-8")
            (destination / "memoria_sermax.json").write_text("memory", encoding="utf-8")
            result = install_package(package, destination)
            self.assertEqual(result["status"], "success")
            self.assertEqual((destination / "app/start.txt").read_text(), "new version")
            self.assertEqual((destination / "data" / "history.db").read_text(), "keep")
            self.assertEqual((destination / "memoria_sermax.json").read_text(), "memory")

    def test_existing_program_file_is_backed_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/core.txt": "new"})
            target = destination / "app/core.txt"
            target.parent.mkdir(parents=True)
            target.write_text("old", encoding="utf-8")
            result = install_package(package, destination)
            self.assertEqual(target.read_text(), "new")
            backup = Path(result["backup_directory"]) / "app/core.txt"
            self.assertEqual(backup.read_text(), "old")

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            write_package(package, {"app.txt": "x"})
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["files"][0]["target"] = "../outside.txt"
            (package / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(PackageError):
                load_package(package)

    def test_rejects_modified_package_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            write_package(package, {"app.txt": "original"})
            (package / "payload" / "app.txt").write_text("tampered")
            with self.assertRaises(PackageError):
                load_package(package)


if __name__ == "__main__":
    unittest.main()
