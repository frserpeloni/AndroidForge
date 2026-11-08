import ctypes
import os
import unittest

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


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Abertura nativa exige Windows x64.",
)
class DriveRootWindowsIntegrationTests(unittest.TestCase):
    def test_opens_and_validates_windows_system_root(self):
        import ctypes.wintypes as wintypes

        buffer = ctypes.create_unicode_buffer(260)
        length = ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer))
        self.assertGreater(length, 0)
        drive = buffer.value[:2]
        handle = root.open_drive_root(drive + "\\\\")
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
