import ctypes
import os
import struct
import unittest
from unittest.mock import patch

import sermax_windows_directory_handle as native_enum
from sermax_windows_directory_enum import HEADER_SIZE


def make_entry(name, file_id):
    encoded = name.encode("utf-16-le")
    data = bytearray(HEADER_SIZE + len(encoded))
    struct.pack_into("<II", data, 0, 0, 0)
    struct.pack_into("<qqqqqq", data, 8, 1, 2, 3, 4, 8, 8)
    struct.pack_into("<III", data, 56, 0, len(encoded), 0)
    struct.pack_into("<q", data, 96, file_id)
    data[104:] = encoded
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
            ctypes.memmove(output, result.ljust(size, b"\\x00"), size)
            return 1

        with patch.object(native_enum.os, "name", "nt"), \\
             patch.object(native_enum.ctypes, "sizeof", return_value=8), \\
             patch.object(native_enum, "query_handle_metadata", return_value={
                 "is_directory": True,
                 "is_reparse_point": False,
                 "delete_pending": False,
             }), \\
             patch.object(native_enum, "_native_api", return_value=(None, query, None)), \\
             patch.object(native_enum.ctypes, "get_last_error", return_value=18):
            result = native_enum.enumerate_directory_handle(123, buffer_size=4096)
        return result, calls

    def test_starts_with_restart_class_and_continues_with_info_class(self):
        first = make_entry("first.txt", 1)
        second = make_entry("second.txt", 2)
        result, calls = self._invoke([first, second])
        self.assertEqual([entry.name for entry in result],
                         ["first.txt", "second.txt"])
        self.assertEqual(calls, [11, 10, 10])

    def test_rejects_reparse_or_non_directory_handle(self):
        for metadata in (
            {"is_directory": False, "is_reparse_point": False, "delete_pending": False},
            {"is_directory": True, "is_reparse_point": True, "delete_pending": False},
            {"is_directory": True, "is_reparse_point": False, "delete_pending": True},
        ):
            with self.subTest(metadata=metadata), patch.object(
                native_enum.os, "name", "nt"
            ), patch.object(native_enum.ctypes, "sizeof", return_value=8), patch.object(
                native_enum, "query_handle_metadata", return_value=metadata
            ), self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_directory_handle(123, buffer_size=4096)

    def test_rejects_invalid_buffer_size(self):
        with patch.object(native_enum.os, "name", "nt"), patch.object(
            native_enum.ctypes, "sizeof", return_value=8
        ), patch.object(native_enum, "query_handle_metadata", return_value={
            "is_directory": True, "is_reparse_point": False, "delete_pending": False
        }):
            for size in (0, 1024, 4097, 2 * 1024 * 1024):
                with self.subTest(size=size), self.assertRaises(native_enum.HandleIoError):
                    native_enum.enumerate_directory_handle(123, buffer_size=size)

    def test_rejects_duplicate_names(self):
        duplicate = make_entry("same.txt", 1)
        calls = {"count": 0}

        def query(handle, info_class, output, size):
            calls["count"] += 1
            ctypes.memmove(output, duplicate.ljust(size, b"\\x00"), size)
            return 1

        with patch.object(native_enum.os, "name", "nt"), patch.object(
            native_enum.ctypes, "sizeof", return_value=8
        ), patch.object(native_enum, "query_handle_metadata", return_value={
            "is_directory": True, "is_reparse_point": False, "delete_pending": False
        }), patch.object(native_enum, "_native_api", return_value=(None, query, None)):
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_directory_handle(123, buffer_size=4096)
        self.assertEqual(calls["count"], 2)

    def test_fails_closed_off_windows(self):
        if os.name != "nt":
            with self.assertRaises(native_enum.HandleIoError):
                native_enum.enumerate_directory_handle(123)


if __name__ == "__main__":
    unittest.main()
