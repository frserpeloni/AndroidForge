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
            "\\\\?\\C:\\", "C:\\\\", "1:\\", None,
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


if __name__ == "__main__":
    unittest.main()
