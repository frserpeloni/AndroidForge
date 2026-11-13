from __future__ import annotations

import ctypes
import sys
import unittest
from unittest import mock

import sermax_windows_acl_inspection as inspection


class FakeDacl:
    def __init__(self, aces):
        self.aces = aces

    def GetAceCount(self):
        return len(self.aces)

    def GetAce(self, index):
        return self.aces[index]


class FakeDescriptor:
    def __init__(self, dacl, control=0):
        self.dacl = dacl
        self.control = control

    def GetOwner(self):
        return "OWNER"

    def GetGroup(self):
        return "GROUP"

    def GetSecurityDescriptorDacl(self):
        return self.dacl

    def GetSecurityDescriptorControl(self):
        return self.control, 1


class AclInspectionTests(unittest.TestCase):
    def setUp(self):
        self.platform = mock.patch.object(inspection.os, "name", "nt")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        self.pointer_size = mock.patch.object(
            inspection.ctypes, "sizeof", return_value=8
        )
        self.pointer_size.start()
        self.addCleanup(self.pointer_size.stop)
        self.metadata = mock.patch(
            "sermax_windows_handle_io.query_handle_metadata",
            return_value={
                "is_directory": True,
                "is_reparse_point": False,
                "delete_pending": False,
            },
        )
        self.metadata.start()
        self.addCleanup(self.metadata.stop)

    def _security_module(self, descriptor):
        module = mock.MagicMock()
        module.OWNER_SECURITY_INFORMATION = 1
        module.GROUP_SECURITY_INFORMATION = 2
        module.DACL_SECURITY_INFORMATION = 4
        module.SE_FILE_OBJECT = 1
        module.GetSecurityInfo.return_value = descriptor
        module.ConvertSidToStringSid.side_effect = {
            "OWNER": "S-1-5-21-100",
            "GROUP": "S-1-5-32-545",
            "USER": "S-1-5-21-200",
        }.__getitem__
        return module

    def test_reports_owner_dacl_and_ace_without_mutation(self):
        descriptor = FakeDescriptor(
            FakeDacl([((0, 3), 0x001F01FF, "USER")]),
            control=inspection.SE_DACL_PROTECTED
            | inspection.SE_DACL_AUTO_INHERITED,
        )
        security = self._security_module(descriptor)
        with mock.patch.dict(sys.modules, {"win32security": security}):
            result = inspection.inspect_directory_acl(123)

        self.assertEqual(result["owner_sid"], "S-1-5-21-100")
        self.assertEqual(result["group_sid"], "S-1-5-32-545")
        self.assertEqual(result["dacl_state"], "present")
        self.assertTrue(result["dacl_protected"])
        self.assertTrue(result["dacl_auto_inherited"])
        self.assertEqual(result["aces"][0]["sid"], "S-1-5-21-200")
        self.assertFalse(result["effective_access_evaluated"])
        self.assertFalse(result["mutated"])
        security.SetSecurityInfo.assert_not_called()

    def test_reports_null_dacl_without_claiming_restriction(self):
        security = self._security_module(FakeDescriptor(None))
        with mock.patch.dict(sys.modules, {"win32security": security}):
            result = inspection.inspect_directory_acl(123)
        self.assertEqual(result["dacl_state"], "null_or_absent")
        self.assertEqual(result["aces"], [])
        security.SetSecurityInfo.assert_not_called()

    def test_rejects_reparse_directory_before_security_query(self):
        with (
            mock.patch(
                "sermax_windows_handle_io.query_handle_metadata",
                return_value={
                    "is_directory": True,
                    "is_reparse_point": True,
                    "delete_pending": False,
                },
            ),
            mock.patch.dict(sys.modules, {"win32security": mock.MagicMock()}),
        ):
            with self.assertRaises(inspection.DirectoryAclInspectionError):
                inspection.inspect_directory_acl(123)

    def test_rejects_null_handle(self):
        with mock.patch.dict(sys.modules, {"win32security": mock.MagicMock()}):
            with self.assertRaisesRegex(
                inspection.DirectoryAclInspectionError, "Handle nulo"
            ):
                inspection.inspect_directory_acl(None)


if __name__ == "__main__":
    unittest.main()

@unittest.skipUnless(
    inspection.os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Inspeção nativa exige Windows x64.",
)
class AclInspectionWindowsIntegrationTests(unittest.TestCase):
    def test_inspects_real_directory_acl_without_mutating_it(self):
        import tempfile
        from ctypes import wintypes

        from sermax_windows_handle_io import close_handle

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE

        with tempfile.TemporaryDirectory() as directory:
            handle = create_file(
                directory,
                0x00020000 | 0x00000080 | 0x00100000,  # READ_CONTROL, READ_ATTRIBUTES, SYNCHRONIZE
                0x00000001 | 0x00000002 | 0x00000004,
                None,
                3,  # OPEN_EXISTING
                0x02000000 | 0x00200000,  # BACKUP_SEMANTICS, OPEN_REPARSE_POINT
                None,
            )
            invalid_handle = ctypes.c_void_p(-1).value
            self.assertNotIn(handle, (None, 0, invalid_handle))
            try:
                result = inspection.inspect_directory_acl(handle)
                self.assertTrue(result["owner_sid"])
                self.assertIn(result["dacl_state"], ("present", "null_or_absent"))
                self.assertIn("aces", result)
                self.assertFalse(result["effective_access_evaluated"])
                self.assertFalse(result["mutated"])
            finally:
                close_handle(handle)

