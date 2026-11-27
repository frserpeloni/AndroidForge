import sys
import types
import unittest
from unittest import mock

import sermax_windows_security as security


class FakeDacl:
    def __init__(self, aces):
        self.aces = aces

    def GetAceCount(self):
        return len(self.aces)

    def GetAce(self, index):
        return self.aces[index]


class FakeDescriptor:
    def __init__(self, dacl, control=0x1004):
        self.dacl = dacl
        self.control = control

    def GetSecurityDescriptorOwner(self):
        return "S-1-5-18", False

    def GetSecurityDescriptorGroup(self):
        return "S-1-5-32-544", False

    def GetSecurityDescriptorDacl(self):
        return self.dacl

    def GetSecurityDescriptorControl(self):
        return self.control, 1


class ReadSecurityByHandleTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "is_directory": True,
            "is_reparse_point": False,
            "delete_pending": False,
            "volume_serial_number": 123,
            "file_id_128": "00112233445566778899aabbccddeeff",
            "number_of_links": 1,
        }
        self.win32security = types.SimpleNamespace(
            SE_FILE_OBJECT=1,
            ConvertSidToStringSid=lambda sid: sid,
            GetSecurityInfo=mock.Mock(),
        )
        self.modules = mock.patch.dict(
            sys.modules, {"win32security": self.win32security}
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def _run(self, descriptor):
        self.win32security.GetSecurityInfo.return_value = descriptor
        with (
            mock.patch.object(security.os, "name", "nt"),
            mock.patch.object(security.ctypes, "sizeof", return_value=8),
            mock.patch.object(
                security, "query_handle_metadata", return_value=self.metadata
            ),
        ):
            return security.read_security_by_handle(1234)

    def test_reads_owner_group_dacl_and_ace_without_modifying_it(self):
        dacl = FakeDacl([
            ((0, 0x03), 0x001F01FF, "S-1-5-18"),
            ((1, 0x00), 0x00000002, "S-1-5-21-1000"),
        ])
        result = self._run(FakeDescriptor(dacl))
        self.assertEqual(result["owner_sid"], "S-1-5-18")
        self.assertEqual(result["group_sid"], "S-1-5-32-544")
        self.assertEqual(result["dacl_state"], "present")
        self.assertTrue(result["dacl_protected"])
        self.assertEqual(len(result["aces"]), 2)
        self.assertTrue(result["aces"][0]["supported_for_policy"])
        self.assertEqual(result["aces"][1]["trustee_sid"], "S-1-5-21-1000")
        self.win32security.GetSecurityInfo.assert_called_once()

    def test_reads_sid_from_callback_ace_with_trailing_application_data(self):
        dacl = FakeDacl([
            ((9, 0x00), 0x00000002, "S-1-5-21-1000", b"callback-data"),
        ])
        result = self._run(FakeDescriptor(dacl))
        self.assertEqual(result["aces"][0]["trustee_sid"], "S-1-5-21-1000")
        self.assertFalse(result["aces"][0]["supported_for_policy"])

    def test_reports_null_or_absent_dacl_as_unsafe_state_for_later_policy(self):
        result = self._run(FakeDescriptor(None, control=0))
        self.assertEqual(result["dacl_state"], "null_or_absent")
        self.assertEqual(result["aces"], [])

    def test_rejects_non_directory_handle(self):
        metadata = dict(self.metadata, is_directory=False)
        with (
            mock.patch.object(security.os, "name", "nt"),
            mock.patch.object(security.ctypes, "sizeof", return_value=8),
            mock.patch.object(
                security, "query_handle_metadata", return_value=metadata
            ),
        ):
            with self.assertRaises(security.DirectorySecurityError):
                security.read_security_by_handle(1234)
        self.win32security.GetSecurityInfo.assert_not_called()

    def test_rejects_reparse_point(self):
        metadata = dict(self.metadata, is_reparse_point=True)
        with (
            mock.patch.object(security.os, "name", "nt"),
            mock.patch.object(security.ctypes, "sizeof", return_value=8),
            mock.patch.object(
                security, "query_handle_metadata", return_value=metadata
            ),
        ):
            with self.assertRaises(security.DirectorySecurityError):
                security.read_security_by_handle(1234)
        self.win32security.GetSecurityInfo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
