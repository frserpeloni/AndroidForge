import ctypes
import unittest

import sermax_windows_handle_abi as abi


class WindowsHandleAbiLayoutTests(unittest.TestCase):
    @unittest.skipUnless(
        __import__("os").name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
        "Os layouts abaixo são os contratos ABI de Windows x64.",
    )
    def test_windows_x64_structure_sizes(self):
        self.assertEqual(ctypes.sizeof(abi.UNICODE_STRING), 16)
        self.assertEqual(ctypes.sizeof(abi.OBJECT_ATTRIBUTES), 48)
        self.assertEqual(ctypes.sizeof(abi.IO_STATUS_BLOCK), 16)
        self.assertEqual(ctypes.sizeof(abi.FILE_ID_128), 16)
        self.assertEqual(ctypes.sizeof(abi.FILE_ID_INFO), 24)
        self.assertEqual(ctypes.sizeof(abi.FILE_ATTRIBUTE_TAG_INFO), 8)
        self.assertEqual(ctypes.sizeof(abi.FILE_STANDARD_INFO), 24)

    @unittest.skipUnless(
        __import__("os").name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
        "Os offsets abaixo são os contratos ABI de Windows x64.",
    )
    def test_windows_x64_field_offsets(self):
        self.assertEqual(abi.UNICODE_STRING.Buffer.offset, 8)
        self.assertEqual(abi.OBJECT_ATTRIBUTES.RootDirectory.offset, 8)
        self.assertEqual(abi.OBJECT_ATTRIBUTES.ObjectName.offset, 16)
        self.assertEqual(abi.OBJECT_ATTRIBUTES.Attributes.offset, 24)
        self.assertEqual(abi.OBJECT_ATTRIBUTES.SecurityDescriptor.offset, 32)
        self.assertEqual(abi.OBJECT_ATTRIBUTES.SecurityQualityOfService.offset, 40)
        self.assertEqual(abi.IO_STATUS_BLOCK.Information.offset, 8)
        self.assertEqual(abi.FILE_ID_INFO.FileId.offset, 8)
        self.assertEqual(abi.FILE_STANDARD_INFO.NumberOfLinks.offset, 16)
        self.assertEqual(abi.FILE_STANDARD_INFO.DeletePending.offset, 20)
        self.assertEqual(abi.FILE_STANDARD_INFO.Directory.offset, 21)

    def test_constants_match_documented_file_information_classes(self):
        self.assertEqual(abi.FILE_ATTRIBUTE_TAG_INFO_CLASS, 9)
        self.assertEqual(abi.FILE_ID_BOTH_DIRECTORY_INFO_CLASS, 10)
        self.assertEqual(abi.FILE_ID_INFO_CLASS, 18)
        self.assertEqual(abi.FILE_ID_EXTD_DIRECTORY_INFO_CLASS, 19)
        self.assertEqual(abi.FILE_STANDARD_INFO_CLASS, 1)

    def test_loader_fails_closed_off_windows(self):
        if __import__("os").name != "nt":
            with self.assertRaises(abi.NativeApiError):
                abi.load_native_apis()


if __name__ == "__main__":
    unittest.main()
