from __future__ import annotations

import ctypes
import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from unittest import mock

import sermax_update_transaction as transaction
from sermax_update_manifest import ManifestFile, ValidatedManifest


def make_release():
    files = {
        "bin/engine.dll": b"SERMAX replacement payload",
        "bin/new-engine.dll": b"SERMAX new component",
    }
    archive_stream = io.BytesIO()
    with zipfile.ZipFile(archive_stream, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, payload in files.items():
            package.writestr(name, payload)
    archive = archive_stream.getvalue()
    manifest = ValidatedManifest(
        release_version="1.2.3",
        files=(
            ManifestFile(
                path="bin/engine.dll",
                size=len(files["bin/engine.dll"]),
                sha256=hashlib.sha256(files["bin/engine.dll"]).hexdigest(),
                action="replace",
            ),
            ManifestFile(
                path="bin/new-engine.dll",
                size=len(files["bin/new-engine.dll"]),
                sha256=hashlib.sha256(files["bin/new-engine.dll"]).hexdigest(),
                action="create",
            ),
        ),
        key_id="test-key",
        manifest_sha256="a" * 64,
    )
    return archive, manifest, files


class TransactionPreparationUnitTests(unittest.TestCase):
    def test_rejects_unvalidated_manifest_type_before_package_io(self):
        with mock.patch.object(transaction, "validate_release_archive") as validate:
            with self.assertRaisesRegex(
                transaction.TransactionPreparationError, "ValidatedManifest"
            ):
                transaction.prepare_update_transaction_by_handle(
                    b"zip", object(),
                    active_root_handle=1,
                    backups_parent_handle=2,
                    staging_parent_handle=3,
                    journal_parent_handle=4,
                )
        validate.assert_not_called()

    def test_invalid_package_fails_before_creating_journal(self):
        _archive, manifest, _files = make_release()
        with (
            mock.patch.object(
                transaction, "validate_release_archive",
                side_effect=ValueError("invalid package"),
            ),
            mock.patch.object(transaction, "create_journal_transaction_by_handle") as create,
        ):
            with self.assertRaisesRegex(
                transaction.TransactionPreparationError, "validação integral"
            ):
                transaction.prepare_update_transaction_by_handle(
                    b"invalid", manifest,
                    active_root_handle=1,
                    backups_parent_handle=2,
                    staging_parent_handle=3,
                    journal_parent_handle=4,
                )
        create.assert_not_called()


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Preparação transacional nativa exige Windows x64.",
)
class TransactionPreparationWindowsTests(unittest.TestCase):
    def test_prepares_backup_staging_and_journal_without_installing(self):
        from sermax_windows_handle_io import close_handle
        from sermax_windows_private_area import create_private_directory_component

        archive, manifest, files = make_release()
        with tempfile.TemporaryDirectory(prefix="sermax-transaction-prepare-") as root:
            active_path = os.path.join(root, "active")
            os.makedirs(os.path.join(active_path, "bin"))
            original = b"SERMAX original active payload"
            active_file = os.path.join(active_path, "bin", "engine.dll")
            with open(active_file, "wb") as stream:
                stream.write(original)

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
            invalid = ctypes.c_void_p(-1).value
            share = 0x00000001 | 0x00000002 | 0x00000004
            flags = 0x02000000 | 0x00200000

            root_handle = create_file(
                root, 0x0001 | 0x0004 | 0x0080 | 0x00100000,
                share, None, 3, flags, None,
            )
            self.assertNotIn(root_handle, (None, 0, invalid))
            active_handle = create_file(
                active_path, 0x0001 | 0x0080 | 0x00100000,
                share, None, 3, flags, None,
            )
            self.assertNotIn(active_handle, (None, 0, invalid))

            private_handles = []
            prepared = None
            try:
                backups_handle = create_private_directory_component(root_handle, "backups")
                private_handles.append(backups_handle)
                staging_handle = create_private_directory_component(root_handle, "staging")
                private_handles.append(staging_handle)
                journal_handle = create_private_directory_component(root_handle, "journal")
                private_handles.append(journal_handle)

                prepared = transaction.prepare_update_transaction_by_handle(
                    archive,
                    manifest,
                    active_root_handle=active_handle,
                    backups_parent_handle=backups_handle,
                    staging_parent_handle=staging_handle,
                    journal_parent_handle=journal_handle,
                )
                events = prepared.journal.read_events()
                self.assertEqual(
                    [event["event"] for event in events],
                    ["PREPARED", "BACKUP_COMPLETE", "STAGING_COMPLETE"],
                )
                self.assertTrue(prepared.backup.component.startswith("backup-"))
                self.assertTrue(prepared.staging.component.startswith("stage-"))
                self.assertEqual(prepared.package.file_count, 2)

                staged_path = os.path.join(
                    root, "staging", prepared.staging.component,
                    "bin", "new-engine.dll",
                )
                with open(staged_path, "rb") as staged:
                    self.assertEqual(staged.read(), files["bin/new-engine.dll"])

                with open(active_file, "rb") as active:
                    self.assertEqual(active.read(), original)
                self.assertFalse(
                    os.path.exists(os.path.join(active_path, "bin", "new-engine.dll"))
                )

                prepared.begin_install()
                self.assertEqual(
                    prepared.journal.read_events()[-1]["event"], "INSTALL_STARTED"
                )
                # begin_install registra o estado, mas não instala nem altera arquivos.
                with open(active_file, "rb") as active:
                    self.assertEqual(active.read(), original)
                self.assertFalse(
                    os.path.exists(os.path.join(active_path, "bin", "new-engine.dll"))
                )

                installed = transaction.install_prepared_update_by_handle(
                    prepared, active_handle, backups_handle
                )
                self.assertTrue(installed["valid"])
                self.assertEqual(installed["installed_count"], 2)
                self.assertEqual(installed["journal_last_event"], "COMMITTED")
                with open(active_file, "rb") as active:
                    self.assertEqual(active.read(), files["bin/engine.dll"])
                with open(
                    os.path.join(active_path, "bin", "new-engine.dll"), "rb"
                ) as active:
                    self.assertEqual(active.read(), files["bin/new-engine.dll"])
                self.assertEqual(
                    prepared.journal.read_events()[-1]["event"], "COMMITTED"
                )
            finally:
                if prepared is not None:
                    prepared.close()
                for handle in reversed(private_handles):
                    close_handle(handle)
                self.assertTrue(close(active_handle))
                self.assertTrue(close(root_handle))


    def test_rollback_restores_replace_and_removes_create_after_partial_install(self):
        from sermax_windows_handle_io import close_handle
        from sermax_windows_private_area import create_private_directory_component

        archive, manifest, files = make_release()
        with tempfile.TemporaryDirectory(prefix="sermax-transaction-rollback-") as root:
            active_path = os.path.join(root, "active")
            os.makedirs(os.path.join(active_path, "bin"))
            original = b"SERMAX original active payload"
            active_file = os.path.join(active_path, "bin", "engine.dll")
            with open(active_file, "wb") as stream:
                stream.write(original)

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
            invalid = ctypes.c_void_p(-1).value
            share = 0x00000001 | 0x00000002 | 0x00000004
            flags = 0x02000000 | 0x00200000

            root_handle = create_file(
                root, 0x0001 | 0x0004 | 0x0080 | 0x00100000,
                share, None, 3, flags, None,
            )
            self.assertNotIn(root_handle, (None, 0, invalid))
            active_handle = create_file(
                active_path, 0x0001 | 0x0080 | 0x00100000,
                share, None, 3, flags, None,
            )
            self.assertNotIn(active_handle, (None, 0, invalid))

            private_handles = []
            prepared = None
            try:
                backups_handle = create_private_directory_component(root_handle, "backups")
                private_handles.append(backups_handle)
                staging_handle = create_private_directory_component(root_handle, "staging")
                private_handles.append(staging_handle)
                journal_handle = create_private_directory_component(root_handle, "journal")
                private_handles.append(journal_handle)

                prepared = transaction.prepare_update_transaction_by_handle(
                    archive,
                    manifest,
                    active_root_handle=active_handle,
                    backups_parent_handle=backups_handle,
                    staging_parent_handle=staging_handle,
                    journal_parent_handle=journal_handle,
                )
                prepared.begin_install()

                append_event = prepared.journal.append_event
                replaced_paths = []

                def interrupt_after_second_replacement(event, payload):
                    result = append_event(event, payload)
                    if event == "FILE_REPLACED":
                        replaced_paths.append(payload["path"])
                        if payload["path"] == "bin/new-engine.dll":
                            raise RuntimeError("simulated interruption after second FILE_REPLACED")
                    return result

                with mock.patch.object(
                    prepared.journal,
                    "append_event",
                    side_effect=interrupt_after_second_replacement,
                ):
                    with self.assertRaisesRegex(
                        transaction.TransactionPreparationError,
                        "Instalação interrompida",
                    ):
                        transaction.install_prepared_update_by_handle(
                            prepared, active_handle, backups_handle
                        )

                self.assertEqual(
                    replaced_paths,
                    ["bin/engine.dll", "bin/new-engine.dll"],
                )
                interrupted_events = prepared.journal.read_events()
                self.assertEqual(interrupted_events[-1]["event"], "RECOVERY_REQUIRED")
                with open(active_file, "rb") as active:
                    self.assertEqual(active.read(), files["bin/engine.dll"])
                created_file = os.path.join(active_path, "bin", "new-engine.dll")
                with open(created_file, "rb") as active:
                    self.assertEqual(active.read(), files["bin/new-engine.dll"])

                rolled_back = transaction.rollback_prepared_update_by_handle(
                    prepared, active_handle, backups_handle
                )
                self.assertTrue(rolled_back["valid"])
                self.assertEqual(rolled_back["journal_last_event"], "ROLLED_BACK")
                self.assertEqual(rolled_back["removed_count"], 1)
                self.assertEqual(rolled_back["restored_count"], 1)

                with open(active_file, "rb") as active:
                    self.assertEqual(active.read(), original)
                self.assertFalse(os.path.exists(created_file))
                final_events = prepared.journal.read_events()
                final_names = [event["event"] for event in final_events]
                self.assertIn("FILE_REMOVED", final_names)
                self.assertIn("FILE_RESTORED", final_names)
                self.assertEqual(final_names[-1], "ROLLED_BACK")
                self.assertIsNone(prepared.backup.root_handle)
                self.assertTrue(
                    os.path.isdir(os.path.join(root, "backups", prepared.backup.component))
                )
            finally:
                if prepared is not None:
                    prepared.close()
                for handle in reversed(private_handles):
                    close_handle(handle)
                self.assertTrue(close(active_handle))
                self.assertTrue(close(root_handle))


if __name__ == "__main__":
    unittest.main()
