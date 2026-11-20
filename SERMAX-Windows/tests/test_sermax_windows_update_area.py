import sys
import types
import unittest
from unittest import mock

from sermax_windows_directory_enum import DirectoryEntry
import sermax_windows_update_area as update_area


def directory_entry(name="_update", *, attributes=0x10):
    return DirectoryEntry(
        name=name,
        file_index=7,
        creation_time=1,
        last_access_time=2,
        last_write_time=3,
        change_time=4,
        end_of_file=0,
        allocation_size=0,
        attributes=attributes,
        ea_size=0,
        short_name="",
        file_id="00112233445566778899aabbccddeeff",
    )


class UpdateAreaInspectionTests(unittest.TestCase):
    def setUp(self):
        self.parent_metadata = {
            "is_directory": True,
            "is_reparse_point": False,
            "delete_pending": False,
            "volume_serial_number": 123,
        }
        self.child_metadata = {
            "is_directory": True,
            "is_reparse_point": False,
            "delete_pending": False,
            "volume_serial_number": 123,
            "file_id_128": "00112233445566778899aabbccddeeff",
            "number_of_links": 1,
        }
        self.acl_inspection = {
            "owner_sid": "S-1-5-18",
            "dacl_state": "present",
            "aces": [],
        }

    def _patch_common(self, entries, *, acl_error=None):
        return (
            mock.patch.object(
                update_area, "query_handle_metadata",
                side_effect=[self.parent_metadata, self.child_metadata],
            ),
            mock.patch.object(
                update_area, "enumerate_stable_directory_handle",
                side_effect=[tuple(entries), tuple()],
            ),
            mock.patch.object(
                update_area, "open_verified_child_component",
                return_value=200,
            ),
            mock.patch.object(
                update_area, "inspect_directory_acl",
                side_effect=acl_error,
                return_value=self.acl_inspection,
            ),
        )

    def test_opens_exact_update_directory_with_read_control_only(self):
        patches = self._patch_common([directory_entry()])
        with patches[0], patches[1], patches[2] as opener, patches[3]:
            result = update_area.inspect_update_area_by_handle(100)
        self.assertEqual(result.handle, 200)
        self.assertEqual(result.metadata, self.child_metadata)
        self.assertEqual(result.acl_inspection, self.acl_inspection)
        self.assertEqual(result.directory_entries, [])
        opener.assert_called_once_with(
            100, mock.ANY, desired_access=update_area.READ_CONTROL
        )
        with mock.patch.object(update_area, "close_handle") as close:
            result.close()
            close.assert_called_once_with(200)
        self.assertIsNone(result.handle)

    def test_missing_update_directory_is_rejected(self):
        patches = self._patch_common([])
        with patches[0], patches[1], patches[2] as opener, patches[3]:
            with self.assertRaises(update_area.UpdateAreaError):
                update_area.inspect_update_area_by_handle(100)
        opener.assert_not_called()

    def test_noncanonical_case_is_rejected(self):
        patches = self._patch_common([directory_entry("_UPDATE")])
        with patches[0], patches[1], patches[2] as opener, patches[3]:
            with self.assertRaisesRegex(update_area.UpdateAreaError, "grafia"):
                update_area.inspect_update_area_by_handle(100)
        opener.assert_not_called()

    def test_reparse_point_is_rejected_before_open(self):
        patches = self._patch_common([directory_entry(attributes=0x410)])
        with patches[0], patches[1], patches[2] as opener, patches[3]:
            with self.assertRaises(update_area.UpdateAreaError):
                update_area.inspect_update_area_by_handle(100)
        opener.assert_not_called()

    def test_file_named_update_is_rejected_before_open(self):
        patches = self._patch_common([directory_entry(attributes=0x20)])
        with patches[0], patches[1], patches[2] as opener, patches[3]:
            with self.assertRaises(update_area.UpdateAreaError):
                update_area.inspect_update_area_by_handle(100)
        opener.assert_not_called()

    def test_closes_child_handle_when_acl_read_fails(self):
        patches = self._patch_common(
            [directory_entry()],
            acl_error=update_area.DirectoryAclInspectionError("ACL read failure"),
        )
        with (
            patches[0], patches[1], patches[2],
            patches[3],
            mock.patch.object(update_area, "close_handle") as close,
        ):
            with self.assertRaisesRegex(update_area.UpdateAreaError, "ACL read failure"):
                update_area.inspect_update_area_by_handle(100)
        close.assert_called_once_with(200)

    def test_rejects_parent_reparse_point(self):
        metadata = dict(self.parent_metadata, is_reparse_point=True)
        with (
            mock.patch.object(update_area, "query_handle_metadata", return_value=metadata),
            mock.patch.object(update_area, "enumerate_stable_directory_handle") as enumerate_dir,
        ):
            with self.assertRaises(update_area.UpdateAreaError):
                update_area.inspect_update_area_by_handle(100)
        enumerate_dir.assert_not_called()


class UpdateAreaPolicyValidationTests(unittest.TestCase):
    def setUp(self):
        self.token_sid = "S-1-5-21-100-200-300-1001"
        self.win32security = types.SimpleNamespace(
            TokenUser=1,
            GetTokenInformation=mock.Mock(return_value=("token-user-sid",)),
            ConvertSidToStringSid=mock.Mock(return_value=self.token_sid),
        )
        self.modules = mock.patch.dict(
            sys.modules, {"win32security": self.win32security}
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)

        self.inspection = update_area.UpdateAreaInspection(
            handle=200,
            metadata={
                "volume_serial_number": 123,
                "file_id_128": "00112233445566778899aabbccddeeff",
            },
            acl_inspection={"dacl_state": "present"},
            directory_entries=[],
        )
        self.policy = mock.patch.object(
            update_area, "validate_private_area_acl",
            return_value={"valid": True},
        )
        self.policy_mock = self.policy.start()
        self.addCleanup(self.policy.stop)
        self.descriptor = mock.patch.object(
            update_area, "read_security_descriptor_binary",
            return_value=b"descriptor",
        )
        self.descriptor.start()
        self.addCleanup(self.descriptor.stop)

    def _patch_authz(self, *, denied_name=None):
        def evaluate(token, descriptor, mask):
            name = next(
                key for key, value in update_area._REQUIRED_EFFECTIVE_RIGHTS.items()
                if value == mask
            )
            return {
                "api_success": True,
                "granted": name != denied_name,
                "token_source": "real_kernel_token",
                "mutated": False,
                "performed_io": False,
            }

        evaluator = mock.patch.object(
            update_area, "evaluate_access_for_token", side_effect=evaluate
        )
        evaluator.start()
        self.addCleanup(evaluator.stop)

    def test_validates_acl_policy_and_all_required_effective_rights(self):
        self._patch_authz()
        result = update_area.validate_update_area_acl_policy(
            self.inspection, token_handle=300
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["owner_sid"], self.token_sid)
        self.assertEqual(
            set(result["effective_rights"]),
            set(update_area._REQUIRED_EFFECTIVE_RIGHTS),
        )
        self.assertFalse(result["mutated"])
        self.assertFalse(result["performed_io"])
        self.policy_mock.assert_called_once()
        self.assertEqual(
            self.policy_mock.call_args.kwargs["expected_owner_sid"], self.token_sid
        )

    def test_rejects_token_when_a_required_effective_right_is_denied(self):
        self._patch_authz(denied_name="add_file")
        with self.assertRaisesRegex(update_area.UpdateAreaError, "add_file"):
            update_area.validate_update_area_acl_policy(
                self.inspection, token_handle=300
            )

    def test_rejects_closed_inspection_before_token_access(self):
        self.inspection.handle = None
        with self.assertRaises(update_area.UpdateAreaError):
            update_area.validate_update_area_acl_policy(
                self.inspection, token_handle=300
            )
        self.win32security.GetTokenInformation.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class UpdateAreaNativeWindowsIntegrationTests(unittest.TestCase):
    def test_inspects_and_validates_real_private_area_on_same_retained_handle(self):
        import ctypes
        import os
        import tempfile
        from ctypes import wintypes

        if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
            self.skipTest("Integração nativa exige Windows x64.")

        import win32api
        import win32security

        from sermax_windows_handle_io import close_handle

        with tempfile.TemporaryDirectory(prefix="sermax-update-area-") as parent_path:
            update_path = os.path.join(parent_path, "_update")
            os.mkdir(update_path)

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                wintypes.HANDLE,
            ]
            create_file.restype = wintypes.HANDLE
            close = kernel32.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL

            share = 0x00000001 | 0x00000002 | 0x00000004
            flags = 0x02000000 | 0x00200000
            invalid = ctypes.c_void_p(-1).value

            parent_handle = create_file(
                parent_path,
                0x0001 | 0x0080 | 0x00100000,
                share, None, 3, flags, None,
            )
            self.assertNotIn(parent_handle, (None, 0, invalid))

            writable_child = None
            token = None
            inspection = None
            try:
                writable_child = create_file(
                    update_path,
                    0x0001 | 0x0080 | 0x00020000 | 0x00040000
                    | 0x00080000 | 0x00100000,
                    share, None, 3, flags, None,
                )
                self.assertNotIn(writable_child, (None, 0, invalid))
                native_child = (
                    writable_child.value
                    if isinstance(writable_child, ctypes.c_void_p)
                    else writable_child
                )

                token = win32security.OpenProcessToken(
                    win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
                )
                token_user = win32security.GetTokenInformation(
                    token, win32security.TokenUser
                )[0]
                owner_sid = win32security.ConvertSidToStringSid(token_user)
                system_sid = win32security.ConvertStringSidToSid("S-1-5-18")
                admins_sid = win32security.ConvertStringSidToSid("S-1-5-32-544")

                win32security.SetSecurityInfo(
                    native_child,
                    win32security.SE_FILE_OBJECT,
                    win32security.OWNER_SECURITY_INFORMATION,
                    token_user, None, None, None,
                )

                dacl = win32security.ACL()
                for sid in (token_user, system_sid, admins_sid):
                    dacl.AddAccessAllowedAceEx(
                        win32security.ACL_REVISION,
                        0x01 | 0x02,
                        0x001F01FF,
                        sid,
                    )
                win32security.SetSecurityInfo(
                    native_child,
                    win32security.SE_FILE_OBJECT,
                    (
                        win32security.DACL_SECURITY_INFORMATION
                        | win32security.PROTECTED_DACL_SECURITY_INFORMATION
                    ),
                    None, None, dacl, None,
                )

                self.assertTrue(close(writable_child))
                writable_child = None

                inspection = update_area.inspect_update_area_by_handle(
                    parent_handle
                )
                self.assertEqual(
                    inspection.acl_inspection["owner_sid"], owner_sid
                )
                result = update_area.validate_update_area_acl_policy(
                    inspection, token_handle=token
                )
                self.assertTrue(result["valid"])
                self.assertTrue(result["acl_policy"]["directory_empty"])
                self.assertEqual(
                    set(result["effective_rights"]),
                    set(update_area._REQUIRED_EFFECTIVE_RIGHTS),
                )
                self.assertFalse(result["mutated"])
                self.assertFalse(result["performed_io"])
            finally:
                if inspection is not None:
                    inspection.close()
                if token is not None:
                    win32api.CloseHandle(token)
                if writable_child is not None:
                    self.assertTrue(close(writable_child))
                self.assertTrue(close(parent_handle))
