import ctypes
import hashlib
import unittest
from ctypes import wintypes
from unittest.mock import patch

import sermax_windows_file_hash as file_hash


def metadata(*, size=6, file_id="abc", links=1, directory=False,
             reparse=False, pending=False, attributes=0x20):
    return {
        "volume_serial_number": 7,
        "file_id_128": file_id,
        "end_of_file": size,
        "number_of_links": links,
        "attributes": attributes,
        "is_directory": directory,
        "is_reparse_point": reparse,
        "delete_pending": pending,
    }


def reader_for(payload):
    offset = 0

    def read(_handle, buffer_ptr, capacity, count_ptr, _overlapped):
        nonlocal offset
        count = min(capacity, len(payload) - offset)
        if count:
            ctypes.memmove(buffer_ptr, payload[offset:offset + count], count)
            offset += count
        ctypes.cast(count_ptr, ctypes.POINTER(wintypes.DWORD)).contents.value = count
        return 1

    return read


class HandleFileHashTests(unittest.TestCase):
    def test_hashes_exact_bytes_and_returns_size(self):
        payload = b"SERMAX"
        with patch.object(file_hash, "query_handle_metadata",
                          side_effect=(metadata(size=len(payload)), metadata(size=len(payload)))):
            digest, size = file_hash._hash_handle(
                123, chunk_size=4096, read_file=reader_for(payload)
            )
        self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
        self.assertEqual(size, len(payload))

    def test_rejects_hardlinks_before_reading(self):
        with patch.object(file_hash, "query_handle_metadata",
                          return_value=metadata(links=2)):
            with self.assertRaises(file_hash.HandleIoError):
                file_hash._hash_handle(123, read_file=reader_for(b"SERMAX"))

    def test_rejects_reparse_file_before_reading(self):
        with patch.object(file_hash, "query_handle_metadata",
                          return_value=metadata(reparse=True)):
            with self.assertRaises(file_hash.HandleIoError):
                file_hash._hash_handle(123, read_file=reader_for(b"SERMAX"))

    def test_detects_identity_change_after_read(self):
        with patch.object(file_hash, "query_handle_metadata",
                          side_effect=(metadata(), metadata(file_id="changed"))):
            with self.assertRaises(file_hash.HandleIoError):
                file_hash._hash_handle(123, chunk_size=4096,
                                       read_file=reader_for(b"SERMAX"))

    def test_detects_truncated_read(self):
        with patch.object(file_hash, "query_handle_metadata",
                          side_effect=(metadata(), metadata())):
            with self.assertRaises(file_hash.HandleIoError):
                file_hash._hash_handle(123, chunk_size=4096,
                                       read_file=reader_for(b"SER"))

    def test_rejects_invalid_chunk_size(self):
        with self.assertRaises(file_hash.HandleIoError):
            file_hash._hash_handle(123, chunk_size=1, read_file=reader_for(b""))

    def test_component_handle_is_always_closed(self):
        with patch.object(file_hash, "open_relative_component", return_value=456) as opened, \
             patch.object(file_hash, "_hash_handle", return_value=("digest", 6)) as hashed, \
             patch.object(file_hash, "close_handle") as closed:
            result = file_hash.hash_file_component(123, "SERMAX.exe")
        self.assertEqual(result, ("digest", 6))
        opened.assert_called_once_with(123, "SERMAX.exe", directory=False,
                                       desired_access=file_hash.FILE_READ_DATA)
        hashed.assert_called_once_with(456, chunk_size=file_hash.DEFAULT_CHUNK_SIZE)
        closed.assert_called_once_with(456)

    def test_component_handle_closes_after_hash_failure(self):
        with patch.object(file_hash, "open_relative_component", return_value=456), \
             patch.object(file_hash, "_hash_handle",
                          side_effect=file_hash.HandleIoError("read failed")), \
             patch.object(file_hash, "close_handle") as closed:
            with self.assertRaises(file_hash.HandleIoError):
                file_hash.hash_file_component(123, "SERMAX.exe")
        closed.assert_called_once_with(456)


if __name__ == "__main__":
    unittest.main()
