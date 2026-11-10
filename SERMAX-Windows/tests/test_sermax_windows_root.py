import ctypes
import os
import unittest
from unittest import mock

import sermax_windows_root as root
from sermax_windows_handle_io import HandleIoError


class DriveRootValidationTests(unittest.TestCase):
    def test_accepts_only_exact_drive_root_syntax(self):
        for value in ("C:\\", "d:\\", "Z:\\"):
            with self.subTest(value=value):
                self.assertEqual(root._DRIVE_ROOT.fullmatch(value).group(), value)

    def test_rejects_non_root_and_non_local_forms(self):
        for value in (
            "", "C:", "C:\\SERMAX", "C:/", "\\\\server\\share\\",
            "\\\\?\\C:\\", "1:\\", None,
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


    def test_managed_directory_handle_preserves_identity_after_parent_rename(self):
        import tempfile

        with tempfile.TemporaryDirectory() as parent_path:
            child_path = os.path.join(parent_path, "SERMAX")
            renamed_path = os.path.join(parent_path, "SERMAX-renamed")
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
                managed = root.open_sermax_directory(parent)
                try:
                    before = root.query_handle_metadata(managed)
                    os.rename(child_path, renamed_path)
                    after = root.query_handle_metadata(managed)

                    self.assertFalse(os.path.exists(child_path))
                    self.assertTrue(os.path.isdir(renamed_path))
                    self.assertEqual(
                        before["volume_serial_number"],
                        after["volume_serial_number"],
                    )
                    self.assertEqual(before["file_id_128"], after["file_id_128"])

                    reopened = root.open_relative_component(
                        parent, "SERMAX-renamed", directory=True
                    )
                    try:
                        reopened_info = root.query_handle_metadata(reopened)
                        self.assertEqual(
                            after["volume_serial_number"],
                            reopened_info["volume_serial_number"],
                        )
                        self.assertEqual(after["file_id_128"], reopened_info["file_id_128"])
                    finally:
                        root.close_handle(reopened)
                finally:
                    root.close_handle(managed)
            finally:
                self.assertTrue(close(parent))

    def test_managed_directory_handle_share_mode_does_not_lock_child_entries(self):
        import tempfile

        with tempfile.TemporaryDirectory() as parent_path:
            child_path = os.path.join(parent_path, "SERMAX")
            os.mkdir(child_path)
            entry_path = os.path.join(child_path, "probe.tmp")

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
                managed = root.open_sermax_directory(parent)
                try:
                    # Share modes govern opens of the same object. They do not
                    # prevent creating a new entry inside that directory.
                    created = create_file(
                        entry_path, 0x40000000,
                        0x00000001 | 0x00000002 | 0x00000004,
                        None, 1, 0x00000080, None,
                    )
                    self.assertNotEqual(created, root.INVALID_HANDLE_VALUE)
                    self.assertTrue(close(created))
                    self.assertTrue(os.path.isfile(entry_path))
                finally:
                    root.close_handle(managed)
            finally:
                self.assertTrue(close(parent))

    def test_rejects_junction_named_sermax(self):
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as parent_path, tempfile.TemporaryDirectory() as target_path:
            junction_path = os.path.join(parent_path, "SERMAX")
            result = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", junction_path, target_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(
                    "Runner não criou junction: "
                    + (result.stderr.strip() or result.stdout.strip() or str(result.returncode))
                )

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
                with self.assertRaisesRegex(HandleIoError, "diretório regular"):
                    root.open_sermax_directory(parent)
            finally:
                self.assertTrue(close(parent))
                os.rmdir(junction_path)

    def test_rejects_symlink_named_sermax(self):
        import tempfile

        with tempfile.TemporaryDirectory() as parent_path, tempfile.TemporaryDirectory() as target_path:
            link_path = os.path.join(parent_path, "SERMAX")
            try:
                os.symlink(target_path, link_path, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Runner sem privilégio para criar symlink: {exc}")

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
                with self.assertRaisesRegex(HandleIoError, "diretório regular"):
                    root.open_sermax_directory(parent)
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

        return mock.Mock(CreateFileW=mock.Mock(side_effect=create_file))

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


    def test_rejects_regular_file_named_sermax(self):
        import tempfile

        with tempfile.TemporaryDirectory() as parent_path:
            file_path = os.path.join(parent_path, "SERMAX")
            with open(file_path, "w", encoding="utf-8") as stream:
                stream.write("not a directory")

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
                with self.assertRaisesRegex(HandleIoError, "diretório regular"):
                    root.open_sermax_directory(parent)
            finally:
                self.assertTrue(close(parent))


    def test_directory_acl_can_deny_child_file_and_subdirectory_creation(self):
        import tempfile
        import win32api
        import win32security

        with tempfile.TemporaryDirectory() as parent_path:
            managed_path = os.path.join(parent_path, "SERMAX")
            os.mkdir(managed_path)

            user_sid, _, _ = win32security.LookupAccountName(
                None, win32api.GetUserName()
            )

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
            create_directory = kernel32.CreateDirectoryW
            create_directory.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
            create_directory.restype = ctypes.c_int

            parent = create_file(
                parent_path, 0x0080 | 0x0001 | 0x00100000,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            self.assertNotEqual(parent, root.INVALID_HANDLE_VALUE)
            managed = None
            try:
                managed = root.open_managed_directory_for_acl(parent)
                native_managed = (
                    managed.value if isinstance(managed, ctypes.c_void_p) else managed
                )
                before_dacl = win32security.GetSecurityInfo(
                    native_managed,
                    win32security.SE_FILE_OBJECT,
                    win32security.DACL_SECURITY_INFORMATION,
                ).GetSecurityDescriptorDacl()

                def allowed_entries(dacl):
                    entries = []
                    for index in range(dacl.GetAceCount()):
                        ace = dacl.GetAce(index)
                        if ace[0][0] == win32security.ACCESS_ALLOWED_ACE_TYPE:
                            entries.append((
                                ace[0][0],
                                ace[0][1],
                                ace[1],
                                win32security.ConvertSidToStringSid(ace[2]),
                            ))
                    return sorted(entries)

                before_allowed = allowed_entries(before_dacl)
                self.assertTrue(root.deny_child_creation_for_sid(managed, user_sid))
                after_dacl = win32security.GetSecurityInfo(
                    native_managed,
                    win32security.SE_FILE_OBJECT,
                    win32security.DACL_SECURITY_INFORMATION,
                ).GetSecurityDescriptorDacl()
                self.assertEqual(allowed_entries(after_dacl), before_allowed)
                self.assertFalse(root.deny_child_creation_for_sid(managed, user_sid))

                file_path = os.path.join(managed_path, "denied.tmp")
                ctypes.set_last_error(0)
                file_handle = create_file(
                    file_path, 0x40000000,
                    0x00000001 | 0x00000002 | 0x00000004,
                    None, 1, 0x00000080, None,
                )
                self.assertEqual(file_handle, root.INVALID_HANDLE_VALUE)
                self.assertEqual(ctypes.get_last_error(), 5)

                nested_path = os.path.join(managed_path, "denied-dir")
                ctypes.set_last_error(0)
                self.assertFalse(create_directory(nested_path, None))
                self.assertEqual(ctypes.get_last_error(), 5)
            finally:
                if managed is not None:
                    root.close_handle(managed)
                self.assertTrue(close(parent))



class AceInheritanceMatchingTests(unittest.TestCase):
    def setUp(self):
        self.security = mock.Mock()
        self.security.ACCESS_DENIED_ACE_TYPE = 1
        self.security.ConvertSidToStringSid.side_effect = str
        self.sid = "S-1-5-21-1000"

    def test_effective_inheritable_deny_matches_directory_and_children(self):
        ace = ((1, root.OBJECT_INHERIT_ACE | root.CONTAINER_INHERIT_ACE),
               root.FILE_ADD_FILE | root.FILE_ADD_SUBDIRECTORY,
               self.sid)
        self.assertTrue(
            root._ace_denies_child_creation_on_directory(
                ace, self.sid, self.security
            )
        )

    def test_inherit_only_deny_does_not_match_current_directory(self):
        ace = ((1, root.OBJECT_INHERIT_ACE | root.CONTAINER_INHERIT_ACE
                | root.INHERIT_ONLY_ACE),
               root.FILE_ADD_FILE | root.FILE_ADD_SUBDIRECTORY,
               self.sid)
        self.assertFalse(
            root._ace_denies_child_creation_on_directory(
                ace, self.sid, self.security
            )
        )

    def test_deny_for_another_sid_does_not_match(self):
        ace = ((1, root.OBJECT_INHERIT_ACE | root.CONTAINER_INHERIT_ACE),
               root.FILE_ADD_FILE | root.FILE_ADD_SUBDIRECTORY,
               "S-1-5-21-2000")
        self.assertFalse(
            root._ace_denies_child_creation_on_directory(
                ace, self.sid, self.security
            )
        )


if __name__ == "__main__":
    unittest.main()
