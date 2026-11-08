import ctypes
import os
import unittest
from unittest import mock

import sermax_windows_root as root


class DriveRootValidationTests(unittest.TestCase):
    def test_accepts_only_exact_drive_root_syntax(self):
        for value in ("C:\\", "d:\\", "Z:\\"):
            with self.subTest(value=value):
                self.assertEqual(root._DRIVE_ROOT.fullmatch(value).group(), value)

    def test_rejects_non_root_and_non_local_forms(self):
        for value in (
            "", "C:", "C:\\SERMAX", "C:/", "\\\\server\\share\\",
            "\\\\?\\C:\\", "C:\\", "1:\\", None,
        ):
            with self.subTest(value=value):
                with self.assertRaises(root.RootOpenError):
                    root._validate_drive_root(value)

    def test_fails_closed_off_windows(self):
        if os.name != "nt":
            with self.assertRaises(root.RootOpenError):
                root._validate_drive_root("C:\\")


class ManagedDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.platform = mock.patch.object(root, "_require_windows_x64")
        self.platform.start()
        self.addCleanup(self.platform.stop)

    def test_opens_sermax_relative_and_accepts_same_volume(self):
        parent = object()
        child = object()
        metadata = {
            "is_directory": True,
            "is_reparse_point": False,
            "delete_pending": False,
            "volume_serial_number": 1234,
        }
        with (
            mock.patch.object(root, "query_handle_metadata", side_effect=[metadata, metadata]),
            mock.patch.object(root, "open_relative_component", return_value=child) as opener,
            mock.patch.object(root, "close_handle") as closer,
        ):
            result = root.open_sermax_directory(parent)
        self.assertIs(result, child)
        opener.assert_called_once_with(parent, "SERMAX", directory=True)
        closer.assert_not_called()

    def test_rejects_parent_reparse_point_before_opening_child(self):
        parent = object()
        parent_metadata = {
            "is_directory": True,
            "is_reparse_point": True,
            "delete_pending": False,
            "volume_serial_number": 1234,
        }
        with (
            mock.patch.object(root, "query_handle_metadata", return_value=parent_metadata),
            mock.patch.object(root, "open_relative_component") as opener,
        ):
            with self.assertRaises(root.RootOpenError):
                root.open_sermax_directory(parent)
        opener.assert_not_called()

    def test_rejects_cross_volume_child_and_closes_it(self):
        parent, child = object(), object()
        parent_metadata = {
            "is_directory": True, "is_reparse_point": False,
            "delete_pending": False, "volume_serial_number": 1234,
        }
        child_metadata = {
            "is_directory": True, "is_reparse_point": False,
            "delete_pending": False, "volume_serial_number": 5678,
        }
        with (
            mock.patch.object(root, "query_handle_metadata",
                              side_effect=[parent_metadata, child_metadata]),
            mock.patch.object(root, "open_relative_component", return_value=child),
            mock.patch.object(root, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(root.RootOpenError, "outro volume"):
                root.open_sermax_directory(parent)
        closer.assert_called_once_with(child)

    def test_rejects_non_directory_parent(self):
        parent_metadata = {
            "is_directory": False, "is_reparse_point": False,
            "delete_pending": False, "volume_serial_number": 1234,
        }
        with (
            mock.patch.object(root, "query_handle_metadata", return_value=parent_metadata),
            mock.patch.object(root, "open_relative_component") as opener,
        ):
            with self.assertRaises(root.RootOpenError):
                root.open_sermax_directory(object())
        opener.assert_not_called()

    def test_only_sermax_component_is_allowed(self):
        with self.assertRaises(root.RootOpenError):
            root.open_managed_directory(object(), "Windows")


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Abertura nativa exige Windows x64.",
)
class DriveRootWindowsIntegrationTests(unittest.TestCase):
    def test_opens_and_validates_windows_system_root(self):
        buffer = ctypes.create_unicode_buffer(260)
        get_windows_directory = ctypes.windll.kernel32.GetWindowsDirectoryW
        get_windows_directory.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        get_windows_directory.restype = ctypes.c_uint
        length = get_windows_directory(buffer, len(buffer))
        self.assertGreater(length, 0)
        drive = buffer.value[:2]
        handle = root.open_drive_root(drive + "\\")
        try:
            metadata = root.query_handle_metadata(handle)
            self.assertTrue(metadata["is_directory"])
            self.assertFalse(metadata["is_reparse_point"])
            self.assertFalse(metadata["delete_pending"])
            self.assertEqual(len(metadata["file_id_128"]), 32)
        finally:
            root.close_handle(handle)

    def test_opens_sermax_child_relative_to_temporary_parent_handle(self):
        import tempfile

        with tempfile.TemporaryDirectory() as parent_path:
            child_path = os.path.join(parent_path, "SERMAX")
            os.mkdir(child_path)

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
                parent_path, 0x0080 | 0x0001 | 0x00100000,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            self.assertNotEqual(parent, root.INVALID_HANDLE_VALUE)
            try:
                child = root.open_sermax_directory(parent)
                try:
                    metadata = root.query_handle_metadata(child)
                    self.assertTrue(metadata["is_directory"])
                    self.assertFalse(metadata["is_reparse_point"])
                    self.assertEqual(
                        metadata["volume_serial_number"],
                        root.query_handle_metadata(parent)["volume_serial_number"],
                    )
                finally:
                    root.close_handle(child)
            finally:
                self.assertTrue(close(parent))


class DriveRootHandleLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.platform = mock.patch.object(root, "_require_windows_x64")
        self.platform.start()
        self.addCleanup(self.platform.stop)

    def _fake_kernel32(self, handle):
        def create_file(*args):
            return handle

        return mock.Mock(CreateFileW=create_file)

    def test_returns_validated_root_handle_without_closing_it(self):
        handle = 123456
        kernel32 = self._fake_kernel32(handle)
        metadata = {
            "is_directory": True,
            "is_reparse_point": False,
            "delete_pending": False,
        }
        with (
            mock.patch.object(root.ctypes, "WinDLL", return_value=kernel32),
            mock.patch.object(root, "query_handle_metadata", return_value=metadata),
            mock.patch.object(root, "close_handle") as closer,
        ):
            result = root.open_drive_root("C:\\")
        self.assertEqual(result, handle)
        closer.assert_not_called()
        kernel32.CreateFileW.assert_called_once()

    def test_closes_root_handle_when_metadata_rejects_object(self):
        handle = 123456
        kernel32 = self._fake_kernel32(handle)
        metadata = {
            "is_directory": True,
            "is_reparse_point": True,
            "delete_pending": False,
        }
        with (
            mock.patch.object(root.ctypes, "WinDLL", return_value=kernel32),
            mock.patch.object(root, "query_handle_metadata", return_value=metadata),
            mock.patch.object(root, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(root.RootOpenError, "reparse point"):
                root.open_drive_root("C:\\")
        closer.assert_called_once_with(handle)

    def test_closes_root_handle_when_metadata_query_fails(self):
        handle = 123456
        kernel32 = self._fake_kernel32(handle)
        with (
            mock.patch.object(root.ctypes, "WinDLL", return_value=kernel32),
            mock.patch.object(root, "query_handle_metadata",
                              side_effect=RuntimeError("metadata failure")),
            mock.patch.object(root, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(RuntimeError, "metadata failure"):
                root.open_drive_root("C:\\")
        closer.assert_called_once_with(handle)


if __name__ == "__main__":
    unittest.main()
