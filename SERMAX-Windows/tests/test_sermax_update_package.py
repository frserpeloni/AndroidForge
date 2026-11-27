from __future__ import annotations

import hashlib
import io
import unittest
import zipfile
from dataclasses import dataclass

from sermax_update_package import PackageError, validate_release_archive


@dataclass(frozen=True)
class File:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Manifest:
    release_version: str
    manifest_sha256: str
    files: tuple


def make_manifest(files):
    entries = tuple(
        File(path, len(data), hashlib.sha256(data).hexdigest())
        for path, data in files.items()
    )
    return Manifest("1.2.3", "a" * 64, entries)


def make_zip(files, *, compression=zipfile.ZIP_DEFLATED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


class ReleasePackageValidationTests(unittest.TestCase):
    def setUp(self):
        self.files = {"bin/SERMAX.exe": b"binary-content", "core/module.py": b"print('ok')"}
        self.manifest = make_manifest(self.files)
        self.archive = make_zip(self.files)

    def test_accepts_exact_package_and_returns_digests(self):
        result = validate_release_archive(self.archive, self.manifest)
        self.assertEqual(result.release_version, "1.2.3")
        self.assertEqual(result.file_count, 2)
        self.assertEqual(result.total_uncompressed_size, sum(map(len, self.files.values())))
        self.assertEqual(result.archive_sha256, hashlib.sha256(self.archive).hexdigest())

    def test_accepts_stored_zip(self):
        result = validate_release_archive(
            make_zip(self.files, compression=zipfile.ZIP_STORED), self.manifest
        )
        self.assertEqual(result.file_count, 2)

    def test_rejects_empty_or_non_bytes_input(self):
        for value in (b"", "not bytes", None):
            with self.subTest(value=value):
                with self.assertRaises(PackageError):
                    validate_release_archive(value, self.manifest)

    def test_rejects_archive_size_limit(self):
        with self.assertRaises(PackageError):
            validate_release_archive(self.archive, self.manifest, max_archive_bytes=2)

    def test_rejects_invalid_limits(self):
        for value in (0, -1, True, "10"):
            with self.subTest(value=value):
                with self.assertRaises(PackageError):
                    validate_release_archive(self.archive, self.manifest, max_archive_bytes=value)

    def test_rejects_corrupt_zip(self):
        with self.assertRaises(PackageError):
            validate_release_archive(b"PK-not-a-valid-zip", self.manifest)

    def test_rejects_missing_file(self):
        archive = make_zip({"bin/SERMAX.exe": self.files["bin/SERMAX.exe"]})
        with self.assertRaises(PackageError):
            validate_release_archive(archive, self.manifest)

    def test_rejects_unlisted_extra_file(self):
        files = dict(self.files)
        files["extra.txt"] = b"extra"
        with self.assertRaises(PackageError):
            validate_release_archive(make_zip(files), self.manifest)

    def test_rejects_duplicate_zip_names(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("bin/SERMAX.exe", self.files["bin/SERMAX.exe"])
            archive.writestr("bin/SERMAX.exe", self.files["bin/SERMAX.exe"])
            archive.writestr("core/module.py", self.files["core/module.py"])
        with self.assertRaises(PackageError):
            validate_release_archive(stream.getvalue(), self.manifest)

    def test_rejects_case_collision(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("bin/SERMAX.exe", self.files["bin/SERMAX.exe"])
            archive.writestr("BIN/sermax.EXE", self.files["bin/SERMAX.exe"])
        with self.assertRaises(PackageError):
            validate_release_archive(stream.getvalue(), self.manifest)

    def test_rejects_path_traversal(self):
        manifest = make_manifest({"../escape.txt": b"x"})
        with self.assertRaises(PackageError):
            validate_release_archive(make_zip({"../escape.txt": b"x"}), manifest)

    def test_rejects_absolute_path(self):
        manifest = make_manifest({"/escape.txt": b"x"})
        with self.assertRaises(PackageError):
            validate_release_archive(make_zip({"/escape.txt": b"x"}), manifest)

    def test_rejects_size_mismatch(self):
        bad = Manifest("1.2.3", "a" * 64, (File("bin/SERMAX.exe", 999, "a" * 64), File("core/module.py", 10, "b" * 64)))
        with self.assertRaises(PackageError):
            validate_release_archive(self.archive, bad)

    def test_rejects_content_hash_mismatch(self):
        bad = Manifest("1.2.3", "a" * 64, (File("bin/SERMAX.exe", len(self.files["bin/SERMAX.exe"]), "0" * 64), File("core/module.py", len(self.files["core/module.py"]), hashlib.sha256(self.files["core/module.py"]).hexdigest())))
        with self.assertRaises(PackageError):
            validate_release_archive(self.archive, bad)

    def test_rejects_encrypted_entry(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            info = zipfile.ZipInfo("bin/SERMAX.exe")
            info.flag_bits |= 0x1
            archive.writestr(info, self.files["bin/SERMAX.exe"])
            archive.writestr("core/module.py", self.files["core/module.py"])
        # Python's ZIP writer clears the encryption bit; patch the local and central flags.
        payload = bytearray(stream.getvalue())
        payload[6:8] = (1).to_bytes(2, "little")
        central = payload.find(b"PK\x01\x02")
        if central >= 0:
            payload[central + 8:central + 10] = (1).to_bytes(2, "little")
        with self.assertRaises(PackageError):
            validate_release_archive(bytes(payload), self.manifest)

    def test_rejects_directory_entries(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("bin/", b"")
            archive.writestr("bin/SERMAX.exe", self.files["bin/SERMAX.exe"])
            archive.writestr("core/module.py", self.files["core/module.py"])
        with self.assertRaises(PackageError):
            validate_release_archive(stream.getvalue(), self.manifest)

    def test_rejects_special_symlink_entry(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            info = zipfile.ZipInfo("bin/SERMAX.exe")
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            archive.writestr(info, self.files["bin/SERMAX.exe"])
            archive.writestr("core/module.py", self.files["core/module.py"])
        with self.assertRaises(PackageError):
            validate_release_archive(stream.getvalue(), self.manifest)

    def test_rejects_total_uncompressed_limit(self):
        with self.assertRaises(PackageError):
            validate_release_archive(self.archive, self.manifest, max_total_uncompressed=2)

    def test_rejects_compression_ratio_limit(self):
        repeated = b"A" * 2_000_000
        files = {"payload.bin": repeated}
        archive = make_zip(files)
        manifest = make_manifest(files)
        with self.assertRaises(PackageError):
            validate_release_archive(archive, manifest)

    def test_rejects_unsupported_compression(self):
        # BZIP2 is valid ZIP but intentionally outside the supported release profile.
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_BZIP2) as archive:
            for name, data in self.files.items():
                archive.writestr(name, data)
        with self.assertRaises(PackageError):
            validate_release_archive(stream.getvalue(), self.manifest)


if __name__ == "__main__":
    unittest.main()
