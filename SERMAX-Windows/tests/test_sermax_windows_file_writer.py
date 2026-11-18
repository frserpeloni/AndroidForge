from __future__ import annotations

import ctypes
import hashlib
import io
import os
import tempfile
import unittest
from unittest import mock

import sermax_windows_file_writer as writer
import sermax_windows_private_area as private_area


class HandleFileWriterTests(unittest.TestCase):
    def setUp(self):
        self.platform = mock.patch.object(writer.os, "name", "nt")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        self.pointer_size = mock.patch.object(writer.ctypes, "sizeof", return_value=8)
        self.pointer_size.start()
        self.addCleanup(self.pointer_size.stop)
        self.data = b"SERMAX verified staging payload"
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.token_closer = mock.Mock()
        self.security_buffer = ctypes.create_string_buffer(b"descriptor")
        self.security_patch = mock.patch.object(
            private_area,
            "_prepare_private_security_descriptor",
            return_value=(777, self.token_closer, self.security_buffer, "S-1-5-21-100"),
        )
        self.security_patch.start()
        self.addCleanup(self.security_patch.stop)

    def metadata(self, **changes):
        value = {
            "is_directory": False,
            "is_reparse_point": False,
            "delete_pending": False,
            "number_of_links": 1,
            "volume_serial_number": 1234,
            "file_id_128": "b" * 32,
            "end_of_file": len(self.data),
        }
        value.update(changes)
        return value

    def run_writer(self, *, source=None, expected_sha=None, metadata=None):
        calls = []
        def native_create(out_handle, access, attributes, io_status, allocation,
                          file_attributes, share, disposition, options, ea, ea_length):
            calls.append({
                "access": access,
                "root": attributes._obj.RootDirectory,
                "name": attributes._obj.ObjectName.contents.Buffer,
                "security": attributes._obj.SecurityDescriptor,
                "attributes": file_attributes,
                "share": share,
                "disposition": disposition,
                "options": options,
            })
            out_handle._obj.value = 200
            return 0

        metadata_values = metadata or [
            {"is_directory": True, "is_reparse_point": False,
             "delete_pending": False, "volume_serial_number": 1234},
            self.metadata(),
            self.metadata(),
            self.metadata(),
        ]
        with (
            mock.patch.object(writer, "query_handle_metadata", side_effect=metadata_values),
            mock.patch.object(writer, "_native_api", return_value=(native_create, None, None)),
            mock.patch.object(writer, "_write_apis", return_value=(mock.Mock(), mock.Mock(), mock.Mock(return_value=1), mock.Mock(return_value=1))),
            mock.patch.object(writer, "_validate_file_acl") as acl,
            mock.patch.object(writer, "_write_all") as write_all,
            mock.patch.object(writer, "_readback", return_value=(self.digest, len(self.data))) as readback,
            mock.patch.object(writer, "close_handle") as close,
        ):
            result = writer.write_verified_file_component(
                100, "payload.bin", source or io.BytesIO(self.data),
                expected_size=len(self.data),
                expected_sha256=expected_sha or self.digest,
            )
        return result, calls, acl, write_all, readback, close

    def test_creates_exclusively_relative_to_parent_and_verifies_readback(self):
        result, calls, acl, write_all, readback, close = self.run_writer()
        self.assertEqual(result["sha256"], self.digest)
        self.assertTrue(result["acl_validated"])
        self.assertTrue(result["authz_validated"])
        self.assertTrue(result["flushed"])
        self.assertTrue(result["readback_validated"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["root"], 100)
        self.assertEqual(calls[0]["name"], "payload.bin")
        self.assertIsNotNone(calls[0]["security"])
        self.assertEqual(calls[0]["disposition"], writer.FILE_CREATE)
        self.assertEqual(
            calls[0]["options"],
            writer.FILE_NON_DIRECTORY_FILE
            | writer.FILE_OPEN_REPARSE_POINT
            | writer.FILE_SYNCHRONOUS_IO_NONALERT,
        )
        acl.assert_called_once()
        write_all.assert_called_once()
        readback.assert_called_once()
        close.assert_called_once_with(200)
        self.token_closer.assert_called_once_with(777)

    def test_rejects_parent_reparse_point_before_native_create(self):
        with (
            mock.patch.object(
                writer, "query_handle_metadata",
                return_value={"is_directory": True, "is_reparse_point": True,
                              "delete_pending": False, "volume_serial_number": 1234},
            ),
            mock.patch.object(writer, "_native_api") as native,
        ):
            with self.assertRaisesRegex(writer.HandleFileWriterError, "pai"):
                writer.write_verified_file_component(
                    100, "payload.bin", io.BytesIO(self.data),
                    expected_size=len(self.data), expected_sha256=self.digest,
                )
        native.assert_not_called()

    def test_rejects_invalid_component_before_native_create(self):
        with mock.patch.object(writer, "_native_api") as native:
            with self.assertRaises(writer.HandleFileWriterError):
                writer.write_verified_file_component(
                    100, "../payload.bin", io.BytesIO(self.data),
                    expected_size=len(self.data), expected_sha256=self.digest,
                )
        native.assert_not_called()

    def test_hash_mismatch_aborts_before_flush_and_preserves_partial_file(self):
        calls = []
        def native_create(out_handle, *args):
            out_handle._obj.value = 200
            return 0
        flush = mock.Mock(return_value=1)
        with (
            mock.patch.object(
                writer, "query_handle_metadata",
                side_effect=[
                    {"is_directory": True, "is_reparse_point": False,
                     "delete_pending": False, "volume_serial_number": 1234},
                    self.metadata(),
                ],
            ),
            mock.patch.object(writer, "_native_api", return_value=(native_create, None, None)),
            mock.patch.object(writer, "_write_apis", return_value=(mock.Mock(), mock.Mock(), flush, mock.Mock())),
            mock.patch.object(writer, "_validate_file_acl"),
            mock.patch.object(writer, "_write_all"),
            mock.patch.object(writer, "close_handle") as close,
        ):
            with self.assertRaisesRegex(writer.HandleFileWriterError, "SHA-256"):
                writer.write_verified_file_component(
                    100, "payload.bin", io.BytesIO(self.data),
                    expected_size=len(self.data), expected_sha256="0" * 64,
                )
        flush.assert_not_called()
        close.assert_called_once_with(200)
        self.token_closer.assert_called_once_with(777)

    def test_rejects_hardlink_metadata(self):
        with (
            mock.patch.object(
                writer, "query_handle_metadata",
                side_effect=[
                    {"is_directory": True, "is_reparse_point": False,
                     "delete_pending": False, "volume_serial_number": 1234},
                    self.metadata(number_of_links=2),
                ],
            ),
            mock.patch.object(writer, "_native_api") as native,
        ):
            with self.assertRaisesRegex(writer.HandleFileWriterError, "hardlinks"):
                writer.write_verified_file_component(
                    100, "payload.bin", io.BytesIO(self.data),
                    expected_size=len(self.data), expected_sha256=self.digest,
                )
        native.assert_called_once()


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Teste nativo exige Windows x64.",
)
class HandleFileWriterWindowsTests(unittest.TestCase):
    def test_creates_acl_protected_file_and_reads_back_exact_content(self):
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
                0x0080 | 0x0001 | 0x0002 | 0x0004 | 0x00020000 | 0x00100000,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            self.assertNotEqual(parent, ctypes.c_void_p(-1).value)
            payload = b"SERMAX native Windows file writer integration test"
            try:
                result = writer.write_verified_file_component(
                    parent, "native-test.bin", io.BytesIO(payload),
                    expected_size=len(payload),
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                )
                self.assertEqual(result["size"], len(payload))
                self.assertTrue(result["acl_validated"])
                self.assertEqual(
                    open(os.path.join(parent_path, "native-test.bin"), "rb").read(),
                    payload,
                )
            finally:
                self.assertTrue(close(parent))


if __name__ == "__main__":
    unittest.main()
