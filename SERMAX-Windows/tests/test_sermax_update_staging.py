from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from unittest import mock
import zipfile
from dataclasses import dataclass
from pathlib import Path

from sermax_update_staging import (
    StagingError, stage_verified_release, stage_verified_release_by_handle,
)


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


class HandleReleaseStagingTests(unittest.TestCase):
    def test_stages_complete_tree_using_only_relative_handles(self):
        files, manifest, archive = make_fixture()
        root_handle = object()
        created = []

        def create_directory(parent, component):
            handle = object()
            created.append((parent, component, handle))
            return handle

        def write_file(parent, name, source, *, expected_size, expected_sha256):
            content = source.read()
            self.assertEqual(len(content), expected_size)
            self.assertEqual(hashlib.sha256(content).hexdigest(), expected_sha256)
            return {"name": name, "size": expected_size, "sha256": expected_sha256}

        with (
            mock.patch(
                "sermax_windows_private_area.create_staging_directory_component",
                side_effect=create_directory,
            ),
            mock.patch(
                "sermax_windows_private_area.validate_private_directory_handle",
                return_value={"valid": True},
            ),
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(),
            ),
            mock.patch(
                "sermax_windows_file_writer.write_verified_file_component",
                side_effect=write_file,
            ) as writer_mock,
            mock.patch("sermax_windows_handle_io.close_handle") as close_handle,
        ):
            staged = stage_verified_release_by_handle(
                archive, manifest, staging_parent_handle=object()
            )
            self.assertTrue(staged.component.startswith("stage-"))
            self.assertEqual(staged.root_handle, created[0][2])
            self.assertEqual(len(staged.files), len(files))
            self.assertEqual(len(created), 3)  # root + bin + core
            self.assertEqual(writer_mock.call_count, 2)
            self.assertEqual(close_handle.call_count, 2)  # nested directories only
            staged.close()
            self.assertEqual(close_handle.call_count, 3)  # root closed by owner

    def test_rejects_file_directory_prefix_collision_before_creating_stage(self):
        payload = b"x"
        digest = hashlib.sha256(payload).hexdigest()
        manifest = Manifest(
            "1.2.3",
            "a" * 64,
            (
                ManifestFile("a", 1, digest),
                ManifestFile("a/b", 1, digest),
            ),
        )
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("a", payload)
            archive.writestr("a/b", payload)

        with mock.patch(
            "sermax_windows_private_area.create_staging_directory_component"
        ) as create_directory:
            with self.assertRaisesRegex(StagingError, "arquivo do manifesto"):
                stage_verified_release_by_handle(
                    stream.getvalue(), manifest, staging_parent_handle=object()
                )
        create_directory.assert_not_called()

    def test_preserves_partial_tree_and_closes_handles_when_file_write_fails(self):
        files, manifest, archive = make_fixture()
        root_handle = object()
        nested_handle = object()
        created = []

        def create_directory(parent, component):
            handle = root_handle if not created else nested_handle
            created.append(handle)
            return handle

        with (
            mock.patch(
                "sermax_windows_private_area.create_staging_directory_component",
                side_effect=create_directory,
            ),
            mock.patch(
                "sermax_windows_private_area.validate_private_directory_handle",
                return_value={"valid": True},
            ),
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(),
            ),
            mock.patch(
                "sermax_windows_file_writer.write_verified_file_component",
                side_effect=RuntimeError("simulated write failure"),
            ),
            mock.patch("sermax_windows_handle_io.close_handle") as close_handle,
        ):
            with self.assertRaisesRegex(StagingError, "árvore parcial preservada"):
                stage_verified_release_by_handle(
                    archive, manifest, staging_parent_handle=object()
                )
        self.assertEqual(close_handle.call_count, 2)
        self.assertCountEqual(close_handle.call_args_list, [mock.call(nested_handle), mock.call(root_handle)])



@unittest.skipUnless(
    __import__("os").name == "nt" and __import__("ctypes").sizeof(__import__("ctypes").c_void_p) == 8,
    "Staging nativo exige Windows x64.",
)
class HandleReleaseStagingWindowsTests(unittest.TestCase):
    def test_stages_nested_release_by_handles_with_real_acl_and_file_readback(self):
        import os
        import shutil
        import ctypes
        from sermax_windows_handle_io import close_handle
        from sermax_windows_private_area import create_private_directory_component

        files, manifest, archive = make_fixture()
        with tempfile.TemporaryDirectory() as parent_path:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p,
            ]
            create_file.restype = ctypes.c_void_p
            close = kernel32.CloseHandle
            close.argtypes = [ctypes.c_void_p]
            close.restype = ctypes.c_int

            parent = create_file(
                parent_path,
                0x0080 | 0x0001 | 0x0004 | 0x00100000,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            self.assertNotEqual(parent, ctypes.c_void_p(-1).value)
            staging_parent = None
            staged = None
            try:
                staging_parent = create_private_directory_component(parent, "_update")
                staged = stage_verified_release_by_handle(
                    archive, manifest, staging_parent_handle=staging_parent
                )
                self.assertEqual(len(staged.files), len(files))
                for relative, expected in files.items():
                    target = os.path.join(
                        parent_path, "_update", staged.component,
                        *relative.split("/"),
                    )
                    with open(target, "rb") as created:
                        self.assertEqual(created.read(), expected)
            finally:
                if staged is not None:
                    staged.close()
                if staging_parent is not None:
                    close_handle(staging_parent)
                self.assertTrue(close(parent))
                shutil.rmtree(parent_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
