from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
import zipfile
from dataclasses import dataclass
from pathlib import Path

from sermax_update_staging import StagingError, stage_verified_release


@dataclass(frozen=True)
class ManifestFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Manifest:
    release_version: str
    manifest_sha256: str
    files: tuple


def make_fixture():
    files = {
        "bin/SERMAX.exe": b"sermax-executable-test",
        "core/module.py": b"VALUE = 42\n",
    }
    manifest = Manifest(
        "1.2.3",
        "a" * 64,
        tuple(
            ManifestFile(path, len(data), hashlib.sha256(data).hexdigest())
            for path, data in files.items()
        ),
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return files, manifest, stream.getvalue()


class ReleaseStagingTests(unittest.TestCase):
    def test_extracts_verified_files_into_new_isolated_directory(self):
        files, manifest, archive = make_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            stage = stage_verified_release(archive, manifest, staging_parent=parent)
            self.assertTrue(stage.is_dir())
            self.assertNotEqual(stage, parent)
            self.assertEqual(
                {path: (stage / path).read_bytes() for path in files},
                files,
            )
            self.assertEqual(len(list(parent.iterdir())), 1)

    def test_rejects_corrupt_archive_without_creating_staging(self):
        _, manifest, _ = make_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(StagingError):
                stage_verified_release(b"not-a-zip", manifest, staging_parent=temporary)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_rejects_symlink_staging_parent(self):
        if not hasattr(Path, "symlink_to"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target = base / "target"
            target.mkdir()
            link = base / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation not permitted")
            _, manifest, archive = make_fixture()
            with self.assertRaises(StagingError):
                stage_verified_release(archive, manifest, staging_parent=link)
            self.assertEqual(list(target.iterdir()), [])

    def test_rejects_file_as_staging_parent(self):
        _, manifest, archive = make_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "not-a-directory"
            parent.write_text("x", encoding="utf-8")
            with self.assertRaises(StagingError):
                stage_verified_release(archive, manifest, staging_parent=parent)

    def test_does_not_touch_any_installation_path(self):
        files, manifest, archive = make_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = root / "SERMAX"
            installation.mkdir()
            protected = installation / "memoria_sermax.json"
            protected.write_bytes(b'{"keep":true}')
            stage_verified_release(archive, manifest, staging_parent=root)
            self.assertEqual(protected.read_bytes(), b'{"keep":true}')
            self.assertEqual(sorted(p.name for p in installation.iterdir()), ["memoria_sermax.json"])


if __name__ == "__main__":
    unittest.main()
