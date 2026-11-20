from __future__ import annotations

import ctypes
import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import dataclass
from unittest import mock

import sermax_windows_backup as backup


@dataclass(frozen=True)
class Item:
    path: str
    action: str


@dataclass(frozen=True)
class Manifest:
    files: tuple[Item, ...]


class HandleBackupUnitTests(unittest.TestCase):
    def test_catalog_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(backup.BackupError, "duplicada"):
            backup._reject_duplicate_json_keys((("schema_version", 1), ("schema_version", 1)))

    def test_catalog_rejects_nonstandard_json_constants(self):
        with self.assertRaisesRegex(backup.BackupError, "não permitida"):
            backup._reject_json_constant("NaN")

    def test_restore_attribute_preflight_accepts_supported_attributes(self):
        attributes = (
            backup.FILE_ATTRIBUTE_READONLY
            | backup.FILE_ATTRIBUTE_HIDDEN
            | backup.FILE_ATTRIBUTE_ARCHIVE
        )
        self.assertEqual(
            backup._validate_restorable_attributes(attributes), attributes
        )

    def test_restore_attribute_preflight_rejects_compressed_or_reparse_flags(self):
        for attributes in (0x00000800, 0x00000400, 0x00004000):
            with self.subTest(attributes=attributes):
                with self.assertRaisesRegex(backup.BackupError, "não suportados"):
                    backup._validate_restorable_attributes(attributes)

    def test_schema_v1_catalog_remains_valid_without_timestamp_fields(self):
        descriptor = b"SERMAX legacy security descriptor"
        descriptor_hash = hashlib.sha256(descriptor).hexdigest()
        content_hash = hashlib.sha256(b"data").hexdigest()
        record = {
            "path": "bin/engine.dll",
            "source_file_id_128": "a" * 32,
            "source_volume_serial_number": 123,
            "source_attributes": backup.FILE_ATTRIBUTE_ARCHIVE,
            "source_security_descriptor_b64": __import__("base64").b64encode(descriptor).decode("ascii"),
            "source_security_descriptor_sha256": descriptor_hash,
            "size": 4,
            "sha256": content_hash,
            "backup_file_id_128": "b" * 32,
            "backup_volume_serial_number": 123,
            "backup_number_of_links": 1,
            "backup_size": 4,
            "backup_sha256": content_hash,
        }
        catalog = {
            "schema_version": 1,
            "backup_component": "backup-" + "c" * 24,
            "files": [record],
        }
        self.assertEqual(
            backup._validate_backup_catalog(catalog, catalog["backup_component"], 123),
            (record,),
        )

    def test_schema_v2_catalog_requires_timestamp_fields(self):
        descriptor = b"SERMAX legacy security descriptor"
        descriptor_hash = hashlib.sha256(descriptor).hexdigest()
        content_hash = hashlib.sha256(b"data").hexdigest()
        record = {
            "path": "bin/engine.dll",
            "source_file_id_128": "a" * 32,
            "source_volume_serial_number": 123,
            "source_attributes": backup.FILE_ATTRIBUTE_ARCHIVE,
            "source_security_descriptor_b64": __import__("base64").b64encode(descriptor).decode("ascii"),
            "source_security_descriptor_sha256": descriptor_hash,
            "size": 4,
            "sha256": content_hash,
            "backup_file_id_128": "b" * 32,
            "backup_volume_serial_number": 123,
            "backup_number_of_links": 1,
            "backup_size": 4,
            "backup_sha256": content_hash,
        }
        catalog = {
            "schema_version": 2,
            "backup_component": "backup-" + "c" * 24,
            "files": [record],
        }
        with self.assertRaisesRegex(backup.BackupError, "campos ausentes"):
            backup._validate_backup_catalog(catalog, catalog["backup_component"], 123)

    def test_file_timestamp_validation_accepts_windows_filetime_values(self):
        values = {
            "creation_time": 132223104000000000,
            "last_access_time": 132223104010000000,
            "last_write_time": 132223104020000000,
        }
        self.assertEqual(backup._validate_file_timestamps(values), values)

    def test_file_timestamp_validation_rejects_missing_zero_bool_and_overflow(self):
        valid = {
            "creation_time": 132223104000000000,
            "last_access_time": 132223104010000000,
            "last_write_time": 132223104020000000,
        }
        cases = (
            {},
            {**valid, "last_write_time": 0},
            {**valid, "last_access_time": True},
            {**valid, "creation_time": -1},
            {**valid, "last_write_time": 0x8000000000000000},
            {**valid, "extra": 1},
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(backup.BackupError):
                    backup._validate_file_timestamps(value)

    def test_rejects_source_with_multiple_hardlinks(self):
        metadata = {
            "is_directory": False,
            "is_reparse_point": False,
            "delete_pending": False,
            "volume_serial_number": 123,
            "number_of_links": 2,
            "file_id_128": "a" * 32,
        }
        with self.assertRaisesRegex(backup.BackupError, "hardlinks"):
            backup._validate_regular_source(metadata, 123)

    def test_rejects_source_volume_mismatch(self):
        metadata = {
            "is_directory": False,
            "is_reparse_point": False,
            "delete_pending": False,
            "volume_serial_number": 999,
            "number_of_links": 1,
            "file_id_128": "a" * 32,
        }
        with self.assertRaisesRegex(backup.BackupError, "volume"):
            backup._validate_regular_source(metadata, 123)

    def test_hash_and_rewind_reads_full_source_and_resets_stream(self):
        class Reader:
            def __init__(self):
                self.position = 0
                self.data = b"SERMAX backup stream"
                self.seeks = 0

            def seek_start(self):
                self.position = 0
                self.seeks += 1

            def read(self, size):
                chunk = self.data[self.position:self.position + size]
                self.position += len(chunk)
                return chunk

        reader = Reader()
        digest = backup._hash_and_rewind(reader, len(reader.data))
        self.assertEqual(digest, hashlib.sha256(reader.data).hexdigest())
        self.assertEqual(reader.position, 0)
        self.assertEqual(reader.seeks, 2)

    def test_preflight_rejects_missing_replace_before_backup_creation(self):
        manifest = Manifest((Item("bin/engine.dll", "replace"),))
        with mock.patch.object(
            backup, "_open_source_file", return_value=(None, [], None)
        ):
            with self.assertRaisesRegex(backup.BackupError, "não existe"):
                backup._preflight_targets(100, manifest, 123)

    def test_preflight_rejects_existing_create_target(self):
        manifest = Manifest((Item("bin/new.dll", "create"),))
        metadata = {
            "file_id_128": "a" * 32,
            "volume_serial_number": 123,
            "end_of_file": 10,
            "number_of_links": 1,
        }
        with mock.patch.object(
            backup, "_open_source_file", return_value=(200, [], metadata)
        ), mock.patch.object(backup, "_close_source") as close:
            with self.assertRaisesRegex(backup.BackupError, "já existe"):
                backup._preflight_targets(100, manifest, 123)
        close.assert_called_once_with(200, [])


    def test_rejects_protected_update_area_before_opening_any_handle(self):
        manifest = Manifest((Item("_update/journal.bin", "replace"),))
        with mock.patch.object(backup, "query_handle_metadata") as query:
            with self.assertRaisesRegex(backup.BackupError, "protegido"):
                backup.backup_existing_files_by_handle(100, 200, manifest)
        query.assert_not_called()


    def test_rejects_reserved_backup_catalog_destination_before_io(self):
        manifest = Manifest((Item("__sermax_backup_catalog__.json", "replace"),))
        with mock.patch.object(backup, "query_handle_metadata") as query:
            with self.assertRaisesRegex(backup.BackupError, "reservado"):
                backup.backup_existing_files_by_handle(100, 200, manifest)
        query.assert_not_called()

    def test_no_replace_files_does_not_create_empty_backup(self):
        manifest = Manifest((Item("bin/new.dll", "create"),))
        with (
            mock.patch.object(backup, "query_handle_metadata", return_value={
                "is_directory": True, "is_reparse_point": False,
                "delete_pending": False, "volume_serial_number": 123,
            }),
            mock.patch(
                "sermax_windows_private_area.validate_private_directory_handle",
                return_value={"valid": True},
            ),
            mock.patch.object(backup, "_real_entries", return_value=()),
            mock.patch.object(backup, "_preflight_targets", return_value={
                "bin/new.dll": None,
            }),
            mock.patch(
                "sermax_windows_private_area.create_backup_directory_component"
            ) as create_backup,
        ):
            result = backup.backup_existing_files_by_handle(100, 200, manifest)
        self.assertIsNone(result.component)
        self.assertIsNone(result.root_handle)
        self.assertEqual(result.files, ())
        create_backup.assert_not_called()


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Backup nativo exige Windows x64.",
)
class HandleBackupWindowsIntegrationTests(unittest.TestCase):
    def test_backs_up_replaced_file_and_leaves_active_tree_unchanged(self):
        import shutil
        from sermax_windows_handle_io import close_handle
        from sermax_windows_private_area import create_private_directory_component
        from sermax_windows_journal import create_journal_transaction_by_handle

        with tempfile.TemporaryDirectory(prefix="sermax-backup-native-") as root:
            active_path = os.path.join(root, "active")
            os.makedirs(os.path.join(active_path, "bin"))
            source = b"SERMAX active release file, preserve before replacement"
            source_path = os.path.join(active_path, "bin", "engine.dll")
            with open(source_path, "wb") as stream:
                stream.write(source)

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

            parent_handle = create_file(
                root,
                0x0001 | 0x0004 | 0x0080 | 0x00100000,
                share, None, 3, flags, None,
            )
            self.assertNotIn(parent_handle, (None, 0, invalid))
            active_handle = create_file(
                active_path,
                0x0001 | 0x0080 | 0x00100000,
                share, None, 3, flags, None,
            )
            self.assertNotIn(active_handle, (None, 0, invalid))
            source_file_handle = create_file(
                source_path,
                0x00000080 | 0x00000100 | 0x00100000,
                share, None, 3, 0x00000080, None,
            )
            self.assertNotIn(source_file_handle, (None, 0, invalid))
            expected_timestamps = backup._set_file_timestamps_by_handle(
                source_file_handle,
                {
                    "creation_time": 132223104000000000,
                    "last_access_time": 132223104010000000,
                    "last_write_time": 132223104020000000,
                },
            )

            backups_handle = None
            journal_handle = None
            journal_session = None
            snapshot = None
            try:
                backups_handle = create_private_directory_component(
                    parent_handle, "backups"
                )
                manifest = Manifest((
                    Item("bin/engine.dll", "replace"),
                    Item("bin/new-engine.dll", "create"),
                ))
                snapshot = backup.backup_existing_files_by_handle(
                    active_handle, backups_handle, manifest
                )
                self.assertTrue(snapshot.component.startswith("backup-"))
                self.assertEqual(len(snapshot.files), 1)
                self.assertEqual(snapshot.files[0]["path"], "bin/engine.dll")
                self.assertEqual(snapshot.files[0]["sha256"], hashlib.sha256(source).hexdigest())
                self.assertTrue(snapshot.files[0]["source_stable_after_copy"])
                self.assertIsNotNone(snapshot.catalog)

                backup_path = os.path.join(
                    root, "backups", snapshot.component, "bin", "engine.dll"
                )
                with open(backup_path, "rb") as saved:
                    self.assertEqual(saved.read(), source)
                with open(source_path, "rb") as active:
                    self.assertEqual(active.read(), source)
                catalog_path = os.path.join(
                    root, "backups", snapshot.component,
                    "__sermax_backup_catalog__.json",
                )
                with open(catalog_path, "r", encoding="utf-8") as catalog_file:
                    catalog = json.load(catalog_file)
                self.assertEqual(catalog["schema_version"], 2)
                self.assertEqual(catalog["files"][0]["path"], "bin/engine.dll")
                self.assertEqual(
                    catalog["files"][0]["source_timestamps"], expected_timestamps
                )
                self.assertEqual(
                    catalog["files"][0]["sha256"],
                    hashlib.sha256(source).hexdigest(),
                )
                self.assertTrue(
                    catalog["files"][0]["source_security_descriptor_b64"]
                )

                expected_catalog_hash = snapshot.catalog["sha256"]
                snapshot.close()
                verified = backup.verify_backup_by_handle(
                    backups_handle,
                    snapshot.component,
                    expected_catalog_sha256=expected_catalog_hash,
                )
                self.assertTrue(verified["valid"])
                self.assertTrue(verified["namespace_exact"])
                self.assertTrue(verified["acl_validated"])
                self.assertTrue(verified["authz_validated"])
                self.assertTrue(verified["read_only"])
                self.assertEqual(verified["file_count"], 1)

                journal_handle = create_private_directory_component(
                    parent_handle, "journal"
                )
                journal_session = create_journal_transaction_by_handle(journal_handle)
                journal_session.append_event(
                    "PREPARED",
                    {"release_version": "test-restore", "manifest_sha256": "a" * 64},
                )
                journal_session.append_event(
                    "BACKUP_COMPLETE",
                    {
                        "backup_component": snapshot.component,
                        "catalog_sha256": expected_catalog_hash,
                    },
                )
                journal_session.append_event(
                    "STAGING_COMPLETE",
                    {
                        "staging_component": "stage-" + "b" * 24,
                        "archive_sha256": "c" * 64,
                    },
                )
                journal_session.append_event("INSTALL_STARTED", {})
                journal_session.append_event(
                    "ROLLBACK_STARTED", {"reason": "native restoration integration test"}
                )

                changed = b"SERMAX deliberately changed after simulated update"
                with open(source_path, "wb") as active:
                    active.write(changed)
                restored = backup.restore_backup_files_by_handle(
                    active_handle,
                    backups_handle,
                    snapshot.component,
                    journal_session,
                )
                self.assertEqual(restored["restored_count"], 1)
                self.assertEqual(restored["journal_last_event"], "FILE_RESTORED")
                with open(source_path, "rb") as active:
                    self.assertEqual(active.read(), source)
                self.assertEqual(
                    backup._query_file_timestamps_by_handle(source_file_handle),
                    expected_timestamps,
                )
                # A leitura usada para conferir o conteúdo pode atualizar LastAccessTime.
                backup._set_file_timestamps_by_handle(
                    source_file_handle, expected_timestamps
                )

                repeated = backup.restore_backup_files_by_handle(
                    active_handle,
                    backups_handle,
                    snapshot.component,
                    journal_session,
                )
                self.assertEqual(repeated["restored_count"], 0)
                self.assertEqual(repeated["already_restored_count"], 1)
            finally:
                if journal_session is not None:
                    journal_session.close()
                if journal_handle is not None:
                    close_handle(journal_handle)
                if snapshot is not None:
                    snapshot.close()
                if backups_handle is not None:
                    close_handle(backups_handle)
                if source_file_handle is not None:
                    self.assertTrue(close(source_file_handle))
                self.assertTrue(close(active_handle))
                self.assertTrue(close(parent_handle))
                shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
