from dataclasses import replace
import unittest

from sermax_windows_directory_enum import DirectoryEntry
from sermax_windows_directory_snapshot import (
    DirectorySnapshotError,
    compare_directory_snapshots,
)


def entry(
    name="file.txt",
    *,
    file_id=10,
    size=12,
    write_time=100,
    attributes=0x20,
    short_name="",
    file_index=1,
):
    return DirectoryEntry(
        name=name,
        file_index=file_index,
        creation_time=1,
        last_access_time=2,
        last_write_time=write_time,
        change_time=4,
        end_of_file=size,
        allocation_size=16,
        attributes=attributes,
        ea_size=0,
        short_name=short_name,
        file_id=file_id,
    )


class DirectorySnapshotComparisonTests(unittest.TestCase):
    def test_equal_snapshots_ignore_order_and_file_index(self):
        first = (entry("a.txt", file_id=1), entry("b.txt", file_id=2))
        second = (
            entry("b.txt", file_id=2, file_index=99),
            entry("a.txt", file_id=1, file_index=88),
        )
        result = compare_directory_snapshots(first, second)
        self.assertEqual([item.name for item in result], ["a.txt", "b.txt"])

    def test_detects_creation_removal_and_rename(self):
        baseline = (entry("old.txt"),)
        for changed in (
            (entry("old.txt"), entry("new.txt", file_id=11)),
            (),
            (entry("renamed.txt"),),
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(DirectorySnapshotError):
                    compare_directory_snapshots(baseline, changed)

    def test_detects_size_time_attributes_and_file_id_changes(self):
        baseline = (entry(),)
        mutations = (
            replace(entry(), end_of_file=13),
            replace(entry(), last_write_time=101),
            replace(entry(), attributes=0x10),
            replace(entry(), file_id=11),
            replace(entry(), short_name="OTHER~1.TXT"),
        )
        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaises(DirectorySnapshotError):
                    compare_directory_snapshots(baseline, (changed,))

    def test_rejects_casefold_and_nfkc_collisions(self):
        collisions = (
            (entry("Readme"), entry("README", file_id=11)),
            (entry("Ａ.txt"), entry("A.txt", file_id=11)),
        )
        for entries in collisions:
            with self.subTest(entries=entries):
                with self.assertRaises(DirectorySnapshotError):
                    compare_directory_snapshots(entries, entries)

    def test_rejects_short_name_alias_collision(self):
        entries = (
            entry("first-long-name.txt", file_id=1, short_name="SHARED~1.TXT"),
            entry("second-long-name.txt", file_id=2, short_name="shared~1.txt"),
        )
        with self.assertRaises(DirectorySnapshotError):
            compare_directory_snapshots(entries, entries)

    def test_rejects_invalid_record_type(self):
        with self.assertRaises(DirectorySnapshotError):
            compare_directory_snapshots((object(),), (object(),))


if __name__ == "__main__":
    unittest.main()
