import struct
import unittest

import sermax_windows_handle_enum as enum_io


def _entry(name, *, next_offset=0, attributes=0x10, file_id=123):
    encoded = name.encode("utf-16-le")
    size = enum_io._FILE_NAME_OFFSET + len(encoded)
    total = next_offset or size
    data = bytearray(total)
    struct.pack_into("<I", data, 0, next_offset)
    struct.pack_into("<I", data, enum_io._FILE_ATTRIBUTES_OFFSET, attributes)
    struct.pack_into("<I", data, enum_io._FILE_NAME_LENGTH_OFFSET, len(encoded))
    struct.pack_into("<Q", data, enum_io._FILE_ID_OFFSET, file_id)
    data[enum_io._FILE_NAME_OFFSET:enum_io._FILE_NAME_OFFSET + len(encoded)] = encoded
    return data


class DirectoryBufferParsingTests(unittest.TestCase):
    def test_parses_single_entry(self):
        parsed = enum_io._parse_directory_buffer(_entry("pasta"))
        self.assertEqual(parsed, [{
            "name": "pasta", "attributes": 0x10, "file_id_64": 123,
        }])

    def test_parses_multiple_aligned_entries(self):
        first = _entry("um", next_offset=112)
        second = _entry("dois")
        parsed = enum_io._parse_directory_buffer(first + second)
        self.assertEqual([item["name"] for item in parsed], ["um", "dois"])

    def test_skips_dot_entries(self):
        self.assertEqual(enum_io._parse_directory_buffer(_entry(".")), [])

    def test_rejects_odd_utf16_length(self):
        data = _entry("a")
        struct.pack_into("<I", data, enum_io._FILE_NAME_LENGTH_OFFSET, 1)
        with self.assertRaises(enum_io.DirectoryEnumerationError):
            enum_io._parse_directory_buffer(data)

    def test_rejects_out_of_bounds_next_offset(self):
        data = _entry("a", next_offset=4096)
        with self.assertRaises(enum_io.DirectoryEnumerationError):
            enum_io._parse_directory_buffer(data)

    def test_rejects_unaligned_next_offset(self):
        data = _entry("a", next_offset=105)
        with self.assertRaises(enum_io.DirectoryEnumerationError):
            enum_io._parse_directory_buffer(data)

    def test_rejects_invalid_utf16(self):
        data = _entry("a")
        data[enum_io._FILE_NAME_OFFSET:enum_io._FILE_NAME_OFFSET + 2] = b"\x00\xd8"
        with self.assertRaises(enum_io.DirectoryEnumerationError):
            enum_io._parse_directory_buffer(data)

    def test_loader_fails_closed_off_windows(self):
        import os
        if os.name != "nt":
            with self.assertRaises(enum_io.DirectoryEnumerationError):
                enum_io.enumerate_directory_handle(1)


if __name__ == "__main__":
    unittest.main()
