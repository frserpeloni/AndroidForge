import ctypes
import os
import struct
import unittest
from unittest.mock import patch

import sermax_windows_directory_handle as native_enum
from sermax_windows_directory_enum import FILE_ID_EXTD_HEADER_SIZE


def make_entry(name, file_id):
    encoded = name.encode("utf-16-le")
    data = bytearray(FILE_ID_EXTD_HEADER_SIZE + len(encoded))
    struct.pack_into("<II", data, 0, 0, 0)
    struct.pack_into("<qqqqqq", data, 8, 1, 2, 3, 4, 8, 8)
    struct.pack_into("<III", data, 56, 0, len(encoded), 0)
    struct.pack_into("<I", data, 68, 0)
    data[72:88] = int(file_id).to_bytes(16, "little", signed=False)
    data[88:] = encoded
    return bytes(data)


class DirectoryHandleEnumerationControlTests(unittest.TestCase):
    def _invoke(self, query_results):
        calls = []
        cursor = {"value": 0}

        def query(handle, info_class, output, size):
            calls.append(info_class)
            index = cursor["value"]
            cursor["value"] += 1
            if index >= len(query_results):
                return 0
            result = query_results[index]
            ctypes.memmove(output, result.ljust(size, b"\x00"), size)
            return 1

        with (
            patch.object(native_enum.os, "name", "nt"),
            patch.object(native_enum.ctypes, "sizeof", return_value=8),
            patch.object(
                native_enum,
                "query_handle_metadata",
                return_value={
                    "is_directory": True,
                    "is_reparse_point": False,
                    "delete_pending": False,
                },
            ),
            patch.object(
                native_enum, "_native_api", return_value=(None, query, None)
            ),
            patch.object(native_enum.ctypes, "get_last_error", return_value=18),
        ):
            result = native_enum.enumerate_directory_handle(123, buffer_size=4096)
        return result, calls

    def test_starts_with_restart_class_and_continues_with_info_class(self):
        first = make_entry("first.txt", 1)
        second = make_entry("second.txt", 2)
        result, calls = self._invoke([first, second])
        self.assertEqual(
            [entry.name for entry in result], ["first.txt", "second.txt"]
        )
        self.assertEqual(calls, [20, 19, 19])

    def test_rejects_reparse_or_non_directory_handle(self):
        metadata_values = (
            {
                "is_directory": False,
                "is_reparse_point": False,
                "delete_pending": False,
            },
            {
                "is_directory": True,
                "is_reparse_point": True,
                "delete_pending": False,
            },
            {
                "is_directory": True,
                "is_reparse_point": False,
                "delete_pending": True,
            },
        )
        for metadata in metadata_values:
            with self.subTest(metadata=metadata):
                with (
                    patch.object(native_enum.os, "name", "nt"),
                    patch.object(native_enum.ctypes, "sizeof", return_value=8),
                    patch.object(
                        native_enum, "query_handle_metadata", return_value=metadata
                    ),
                    self.assertRaises(native_enum.HandleIoError),
                ):
                    native_enum.enumerate_directory_handle(123, buffer_size=4096)

    def test_rejects_invalid_buffer_size(self):
        with (
            patch.object(native_enum.os, "name", "nt"),
            patch.object(native_enum.ctypes, "sizeof", return_value=8),
            patch.object(
                native_enum,
                "query_handle_metadata",
                return_value={
                    "is_directory": True,
                    "is_reparse_point": False,
                    "delete_pending": False,
                },
            ),
        ):
            for size in (0, 1024, 4097, 2 * 1024 * 1024):
                with self.subTest(size=size):
                    with self.assertRaises(native_enum.HandleIoError):
                        native_enum.enumerate_directory_handle(123, buffer_size=size)

    def test_rejects_duplicate_names(self):
        duplicate = make_entry("same.txt", 1)
        calls = {"count": 0}

        def query(handle, info_class, output, size):
            calls["count"] += 1
            ctypes.memmove(output, duplicate.ljust(size, b"\x00"), size)
            return 1

        with (
            patch.object(native_enum.os, "name", "nt"),
            patch.object(native_enum.ctypes, "sizeof", return_value=8),
            patch.object(
                native_enum,
                "query_handle_metadata",
                return_value={
                    "is_directory": True,
                    "is_reparse_point": False,
                    "delete_pending": False,
                },
            ),
            patch.object(native_enum, "_native_api", return_value=(None, query, None)),
        ):
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_directory_handle(123, buffer_size=4096)
        self.assertEqual(calls["count"], 2)

    def test_fails_closed_off_windows(self):
        if os.name != "nt":
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_directory_handle(123)



def directory_entry(name="file.bin", *, file_id="00112233445566778899aabbccddeeff",
                   attributes=0x20, size=12):
    from sermax_windows_directory_enum import DirectoryEntry
    return DirectoryEntry(
        name=name,
        file_index=1,
        creation_time=1,
        last_access_time=2,
        last_write_time=3,
        change_time=4,
        end_of_file=size,
        allocation_size=16,
        attributes=attributes,
        ea_size=0,
        short_name="",
        file_id=file_id,
    )


def handle_metadata(*, volume=7, file_id="00112233445566778899aabbccddeeff",
                    attributes=0x20, size=12, directory=False,
                    reparse=False, pending=False):
    return {
        "volume_serial_number": volume,
        "file_id_128": file_id,
        "attributes": attributes,
        "end_of_file": size,
        "is_directory": directory,
        "is_reparse_point": reparse,
        "delete_pending": pending,
    }


class VerifiedChildHandleTests(unittest.TestCase):
    def test_opens_and_validates_file_against_128_bit_id(self):
        entry = directory_entry()
        with (
            patch.object(native_enum, "query_handle_metadata",
                         side_effect=(handle_metadata(directory=True, attributes=0x10, size=0),
                                      handle_metadata())),
            patch.object(native_enum, "open_relative_component", return_value=456) as opened,
            patch.object(native_enum, "close_handle") as closed,
        ):
            result = native_enum.open_verified_child_component(123, entry)
        self.assertEqual(result, 456)
        opened.assert_called_once_with(123, "file.bin", directory=False,
                                       desired_access=None)
        closed.assert_not_called()

    def test_requests_list_directory_access_for_directory_child(self):
        entry = directory_entry(
            name="subdir", attributes=0x10, size=0
        )
        with (
            patch.object(native_enum, "query_handle_metadata",
                         side_effect=(handle_metadata(directory=True, attributes=0x10, size=0),
                                      handle_metadata(directory=True, attributes=0x10, size=0))),
            patch.object(native_enum, "open_relative_component", return_value=456) as opened,
            patch.object(native_enum, "close_handle"),
        ):
            native_enum.open_verified_child_component(123, entry)
        opened.assert_called_once_with(123, "subdir", directory=True,
                                       desired_access=native_enum.FILE_LIST_DIRECTORY)

    def test_rejects_file_id_mismatch_and_closes_child(self):
        entry = directory_entry()
        with (
            patch.object(native_enum, "query_handle_metadata",
                         side_effect=(handle_metadata(directory=True, attributes=0x10, size=0),
                                      handle_metadata(file_id="ff" * 16))),
            patch.object(native_enum, "open_relative_component", return_value=456),
            patch.object(native_enum, "close_handle") as closed,
        ):
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.open_verified_child_component(123, entry)
        closed.assert_called_once_with(456)

    def test_rejects_volume_mismatch_and_closes_child(self):
        entry = directory_entry()
        with (
            patch.object(native_enum, "query_handle_metadata",
                         side_effect=(handle_metadata(directory=True, attributes=0x10, size=0),
                                      handle_metadata(volume=8))),
            patch.object(native_enum, "open_relative_component", return_value=456),
            patch.object(native_enum, "close_handle") as closed,
        ):
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.open_verified_child_component(123, entry)
        closed.assert_called_once_with(456)

    def test_rejects_reparse_entry_before_opening(self):
        entry = directory_entry(attributes=0x400)
        with patch.object(native_enum, "open_relative_component") as opened:
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.open_verified_child_component(123, entry)
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
