import ctypes
import os
import unittest

import sermax_windows_handle_io as handle_io


class WindowsHandleIoValidationTests(unittest.TestCase):
    def test_accepts_single_component(self):
        for name in ("SERMAX.exe", "pasta", "arquivo ç.txt"):
            with self.subTest(name=name):
                handle_io._validate_component(name)

    def test_rejects_empty_or_multi_component_names(self):
        for name in ("", ".", "..", "a/b", r"a\b", "C:arquivo", "arquivo:stream", "x\x00y"):
            with self.subTest(name=name):
                with self.assertRaises(handle_io.HandleIoError):
                    handle_io._validate_component(name)

    def test_rejects_windows_ambiguous_names(self):
        for name in ("CON", "CON.txt", "NUL", "COM1.log", "LPT9", "arquivo.", "arquivo "):
            with self.subTest(name=name):
                with self.assertRaises(handle_io.HandleIoError):
                    handle_io._validate_component(name)

    def test_rejects_component_over_255_utf16_units(self):
        with self.assertRaises(handle_io.HandleIoError):
            handle_io._validate_component("a" * 256)

    def test_accepts_decomposed_unicode_filename(self):
        handle_io._validate_component("e" + chr(0x0301) + ".txt")

    def test_rejects_unpaired_surrogates(self):
        with self.assertRaises(handle_io.HandleIoError):
            handle_io._validate_component(chr(0xD800))

    def test_rejects_control_characters(self):
        with self.assertRaises(handle_io.HandleIoError):
            handle_io._validate_component("arquivo\n.txt")

    def test_native_api_fails_closed_off_windows(self):
        if os.name != "nt":
            with self.assertRaises(Exception):
                handle_io._native_api()

    @unittest.skipUnless(
        os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
        "Estruturas nativas exigem Windows x64.",
    )
    def test_metadata_structures_match_windows_x64(self):
        self.assertEqual(ctypes.sizeof(handle_io.FILE_ATTRIBUTE_TAG_INFO), 8)
        self.assertEqual(ctypes.sizeof(handle_io.FILE_STANDARD_INFO), 24)
        self.assertEqual(handle_io.FILE_STANDARD_INFO.NumberOfLinks.offset, 16)
        self.assertEqual(handle_io.FILE_STANDARD_INFO.DeletePending.offset, 20)
        self.assertEqual(handle_io.FILE_STANDARD_INFO.Directory.offset, 21)


if __name__ == "__main__":
    unittest.main()
