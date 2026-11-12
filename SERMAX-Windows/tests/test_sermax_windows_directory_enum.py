import struct
import unittest

from sermax_windows_directory_enum import (
    DirectoryBufferError,
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    HEADER_SIZE,
    parse_file_id_both_dir_info,
)


def make_entry(name, *, next_offset=0, file_id=7, attributes=0,
               eof=12, short_name=""):
    encoded = name.encode("utf-16-le")
    short = short_name.encode("utf-16-le")
    size = HEADER_SIZE + len(encoded)
    total = next_offset or size
    if next_offset and next_offset < size:
        total = next_offset
    data = bytearray(total)
    struct.pack_into("<II", data, 0, next_offset, 3)
    struct.pack_into("<qqqqqq", data, 8, 1, 2, 3, 4, eof, 16)
    struct.pack_into("<III", data, 56, attributes, len(encoded), 0)
    data[68] = len(short)
    data[70:70 + len(short)] = short
    struct.pack_into("<q", data, 96, file_id)
    data[104:104 + len(encoded)] = encoded
    return bytes(data)


class DirectoryBufferParserTests(unittest.TestCase):
    def test_parses_single_entry(self):
        result = parse_file_id_both_dir_info(make_entry("SERMAX.exe"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "SERMAX.exe")
        self.assertEqual(result[0].file_id, 7)
        self.assertEqual(result[0].end_of_file, 12)
        self.assertFalse(result[0].is_directory)

    def test_parses_directory_and_reparse_attributes(self):
        result = parse_file_id_both_dir_info(make_entry(
            "junction", attributes=FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT
        ))[0]
        self.assertTrue(result.is_directory)
        self.assertTrue(result.is_reparse_point)

    def test_parses_short_name(self):
        result = parse_file_id_both_dir_info(make_entry(
            "LongFileName.txt", short_name="LONGFI~1.TXT"
        ))[0]
        self.assertEqual(result.short_name, "LONGFI~1.TXT")

    def test_parses_multiple_aligned_entries(self):
        first_name = "alpha"
        first_size = HEADER_SIZE + len(first_name.encode("utf-16-le"))
        first_offset = (first_size + 7) & ~7
        first = make_entry(first_name, next_offset=first_offset, file_id=11)
        first = first + bytes(first_offset - len(first))
        second = make_entry("beta", file_id=12)
        result = parse_file_id_both_dir_info(first + second)
        self.assertEqual([item.name for item in result], ["alpha", "beta"])
        self.assertEqual([item.file_id for item in result], [11, 12])

    def test_empty_buffer_returns_empty_tuple(self):
        self.assertEqual(parse_file_id_both_dir_info(b""), ())

    def test_rejects_non_bytes_input(self):
        with self.assertRaises(TypeError):
            parse_file_id_both_dir_info("not bytes")

    def test_rejects_truncated_header(self):
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(b"\x00" * (HEADER_SIZE - 1))

    def test_rejects_odd_or_zero_filename_length(self):
        for length in (0, 1, 3):
            data = bytearray(make_entry("x"))
            struct.pack_into("<I", data, 60, length)
            with self.subTest(length=length), self.assertRaises(DirectoryBufferError):
                parse_file_id_both_dir_info(data)

    def test_rejects_name_length_over_255_utf16_units(self):
        data = bytearray(make_entry("x"))
        struct.pack_into("<I", data, 60, 512)
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(data)

    def test_rejects_name_past_buffer(self):
        data = bytearray(make_entry("x"))
        struct.pack_into("<I", data, 60, 40)
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(data)

    def test_rejects_misaligned_next_offset(self):
        first = bytearray(make_entry("a", next_offset=112))
        struct.pack_into("<I", first, 0, 111)
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(first + make_entry("b"))

    def test_rejects_next_offset_overlapping_name(self):
        first = bytearray(make_entry("alpha", next_offset=112))
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(first + make_entry("b"))

    def test_rejects_next_offset_outside_buffer(self):
        first = bytearray(make_entry("a", next_offset=112))
        struct.pack_into("<I", first, 0, 4096)
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(first + make_entry("b"))

    def test_rejects_truncated_next_header(self):
        first = bytearray(make_entry("a", next_offset=112))
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(first + b"\x00" * 8)

    def test_rejects_invalid_short_name_length(self):
        data = bytearray(make_entry("x"))
        data[68] = 25
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(data)

    def test_rejects_unpaired_surrogate(self):
        data = bytearray(make_entry("x"))
        data[104:106] = b"\x00\xd8"
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(data)

    def test_rejects_embedded_nul(self):
        data = bytearray(make_entry("x"))
        data[104:108] = "a\x00".encode("utf-16-le")
        struct.pack_into("<I", data, 60, 4)
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(data)

    def test_rejects_non_nfc_name(self):
        name = "e\u0301"
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(make_entry(name))

    def test_rejects_negative_file_size(self):
        data = bytearray(make_entry("x"))
        struct.pack_into("<q", data, 40, -1)
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(data)

    def test_rejects_negative_allocation_size(self):
        data = bytearray(make_entry("x"))
        struct.pack_into("<q", data, 48, -1)
        with self.assertRaises(DirectoryBufferError):
            parse_file_id_both_dir_info(data)


if __name__ == "__main__":
    unittest.main()
