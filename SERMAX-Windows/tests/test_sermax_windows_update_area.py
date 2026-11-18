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
        self.security = {
            "owner_sid": "S-1-5-18",
            "dacl_state": "present",
            "aces": [],
        }

    def _patch_common(self, entries, *, security=None):
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
                side_effect=security if isinstance(security, Exception) else None,
                return_value=self.security if security is None or isinstance(security, Exception) else security,
            ),
        )

    def test_opens_exact_update_directory_with_read_control_only(self):
        patches = self._patch_common([directory_entry()])
        with patches[0], patches[1], patches[2] as opener, patches[3]:
            result = update_area.inspect_update_area_by_handle(100)
        self.assertEqual(result.handle, 200)
        self.assertEqual(result.metadata, self.child_metadata)
        self.assertEqual(result.acl_inspection, self.security)
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

    def test_closes_child_handle_when_security_read_fails(self):
        patches = self._patch_common(
            [directory_entry()],
            security=update_area.DirectoryAclInspectionError("security read failure"),
        )
        with (
            patches[0], patches[1], patches[2],
            patches[3],
            mock.patch.object(update_area, "close_handle") as close,
        ):
            with self.assertRaisesRegex(update_area.UpdateAreaError, "security read failure"):
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
        import sys
        import types

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

    def _mock_policy_and_authz(self, *, denied_name=None):
        mock.patch.object(
            update_area, "validate_private_area_acl",
            return_value={"valid": True},
        ).start()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(
            update_area, "read_security_descriptor_binary",
            return_value=b"descriptor",
        ).start()

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

    def test_validates_existing_acl_policy_and_all_required_effective_rights(self):
        self._mock_policy_and_authz()
        with mock.patch.object(
            update_area, "validate_private_area_acl",
            return_value={"valid": True},
        ) as policy:
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
        policy.assert_called_once()
        self.assertEqual(
            policy.call_args.kwargs["expected_owner_sid"], self.token_sid
        )

    def test_rejects_token_when_a_required_effective_right_is_denied(self):
        self._mock_policy_and_authz(denied_name="add_file")
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
