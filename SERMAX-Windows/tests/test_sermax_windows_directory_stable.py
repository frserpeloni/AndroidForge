import unittest
from unittest.mock import patch

from sermax_windows_directory_enum import DirectoryEntry
import sermax_windows_directory_handle as native_enum


def entry(name="file.txt", *, file_id=10, size=12, write_time=100):
    return DirectoryEntry(
        name=name,
        file_index=1,
        creation_time=1,
        last_access_time=2,
        last_write_time=write_time,
        change_time=4,
        end_of_file=size,
        allocation_size=16,
        attributes=0x20,
        ea_size=0,
        short_name="",
        file_id=file_id,
    )


class StableDirectoryEnumerationTests(unittest.TestCase):
    def test_runs_two_independent_passes_and_returns_verified_entries(self):
        first = (entry("a.txt", file_id=1), entry("b.txt", file_id=2))
        second = (entry("b.txt", file_id=2), entry("a.txt", file_id=1))
        with patch.object(
            native_enum,
            "enumerate_directory_handle",
            side_effect=(first, second),
        ) as enumerate_once:
            result = native_enum.enumerate_stable_directory_handle(
                123, buffer_size=8192
            )
        self.assertEqual([item.name for item in result], ["a.txt", "b.txt"])
        self.assertEqual(enumerate_once.call_count, 2)
        self.assertEqual(
            enumerate_once.call_args_list[0].args, (123,)
        )
        self.assertEqual(
            enumerate_once.call_args_list[1].args, (123,)
        )
        self.assertEqual(
            [call.kwargs["buffer_size"] for call in enumerate_once.call_args_list],
            [8192, 8192],
        )

    def test_aborts_when_namespace_changes_between_passes(self):
        first = (entry("before.txt", file_id=1),)
        second = (entry("after.txt", file_id=1),)
        with patch.object(
            native_enum,
            "enumerate_directory_handle",
            side_effect=(first, second),
        ):
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_stable_directory_handle(123)

    def test_aborts_when_file_identity_or_metadata_changes(self):
        first = (entry("file.txt", file_id=10, size=12),)
        second = (entry("file.txt", file_id=11, size=13),)
        with patch.object(
            native_enum,
            "enumerate_directory_handle",
            side_effect=(first, second),
        ):
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_stable_directory_handle(123)

    def test_does_not_run_second_pass_when_first_pass_fails(self):
        with patch.object(
            native_enum,
            "enumerate_directory_handle",
            side_effect=native_enum.HandleIoError("native failure"),
        ) as enumerate_once:
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_stable_directory_handle(123)
        self.assertEqual(enumerate_once.call_count, 1)


if __name__ == "__main__":
    unittest.main()
