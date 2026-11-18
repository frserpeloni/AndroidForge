import unittest
from unittest import mock

from sermax_windows_directory_enum import DirectoryEntry
import sermax_windows_update_area as update_area
from sermax_windows_security import DirectorySecurityError


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
                return_value=tuple(entries),
            ),
            mock.patch.object(
                update_area, "open_verified_child_component",
                return_value=200,
            ),
            mock.patch.object(
                update_area, "read_security_by_handle",
                return_value=self.security if security is None else security,
            ),
        )

    def test_opens_exact_update_directory_with_read_control_only(self):
        patches = self._patch_common([directory_entry()])
        with patches[0], patches[1], patches[2] as opener, patches[3]:
            result = update_area.inspect_update_area_by_handle(100)
        self.assertEqual(result.handle, 200)
        self.assertEqual(result.metadata, self.child_metadata)
        self.assertEqual(result.security, self.security)
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
            security=DirectorySecurityError("security read failure"),
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


if __name__ == "__main__":
    unittest.main()
