import unittest
from unittest.mock import patch

from sermax_windows_directory_enum import DirectoryEntry
import sermax_windows_handle_inventory as inventory


def entry(name, *, file_id="00112233445566778899aabbccddeeff",
          attributes=0x20, size=6):
    return DirectoryEntry(
        name=name,
        file_index=1,
        creation_time=1,
        last_access_time=2,
        last_write_time=3,
        change_time=4,
        end_of_file=size,
        allocation_size=size,
        attributes=attributes,
        ea_size=0,
        short_name="",
        file_id=file_id,
    )


class HandleInventoryTests(unittest.TestCase):
    def _root_metadata(self):
        return {
            "is_directory": True,
            "is_reparse_point": False,
            "delete_pending": False,
        }

    def test_hashes_file_from_stable_directory(self):
        item = entry("sermax.exe")
        with (
            patch.object(inventory, "query_handle_metadata",
                         return_value=self._root_metadata()),
            patch.object(inventory, "enumerate_stable_directory_handle",
                         side_effect=((item,), (item,))) as enumerate_dir,
            patch.object(inventory, "hash_file_component",
                         return_value=("abc123", 6)) as hash_file,
        ):
            records = inventory.inventory_directory_handle(100)
        self.assertEqual(records, [{
            "path": "sermax.exe",
            "type": "file",
            "size": 6,
            "sha256": "abc123",
            "file_id": item.file_id,
            "classification": "unknown",
        }])
        self.assertEqual(enumerate_dir.call_count, 2)
        hash_file.assert_called_once_with(100, item)


    def test_protected_memory_files_are_never_read_or_hashed(self):
        personal = entry("MEMORIA_SERMAX.JSON", size=4096)
        neural = entry("memoria_neural_pestinha.json", size=8192,
                       file_id="ff" * 16)
        with (
            patch.object(inventory, "query_handle_metadata",
                         return_value=self._root_metadata()),
            patch.object(inventory, "enumerate_stable_directory_handle",
                         side_effect=((personal, neural), (personal, neural))),
            patch.object(inventory, "hash_file_component") as hash_file,
        ):
            records = inventory.inventory_directory_handle(100)
        self.assertEqual(
            [(item["classification"], item["size"], item["sha256"])
             for item in records],
            [("protected", None, None), ("protected", None, None)],
        )
        hash_file.assert_not_called()


    def test_protected_directory_is_not_opened_or_traversed(self):
        protected = entry("BACKUPS", attributes=0x10, size=0)
        with (
            patch.object(inventory, "query_handle_metadata",
                         return_value=self._root_metadata()),
            patch.object(inventory, "enumerate_stable_directory_handle",
                         side_effect=((protected,), (protected,))) as enumerate_dir,
            patch.object(inventory, "open_verified_child_component") as opened,
            patch.object(inventory, "hash_file_component") as hashed,
        ):
            records = inventory.inventory_directory_handle(100)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["classification"], "protected")
        self.assertEqual(records[0]["type"], "directory")
        self.assertEqual(enumerate_dir.call_count, 2)
        opened.assert_not_called()
        hashed.assert_not_called()

    def test_reparse_point_is_blocked_without_opening(self):
        item = entry("junction", attributes=0x410, size=0)
        with (
            patch.object(inventory, "query_handle_metadata",
                         return_value=self._root_metadata()),
            patch.object(inventory, "enumerate_stable_directory_handle",
                         side_effect=((item,), (item,))),
            patch.object(inventory, "open_verified_child_component") as opened,
            patch.object(inventory, "hash_file_component") as hashed,
        ):
            records = inventory.inventory_directory_handle(100)
        self.assertEqual(records[0]["classification"], "blocked")
        self.assertEqual(records[0]["type"], "reparse")
        opened.assert_not_called()
        hashed.assert_not_called()

    def test_recurses_into_directory_and_closes_child_handle(self):
        directory = entry("sub", attributes=0x10, size=0)
        leaf = entry("inside.txt")
        with (
            patch.object(inventory, "query_handle_metadata",
                         return_value=self._root_metadata()),
            patch.object(inventory, "enumerate_stable_directory_handle",
                         side_effect=((directory,), (leaf,), (leaf,), (directory,))),
            patch.object(inventory, "open_verified_child_component",
                         return_value=200),
            patch.object(inventory, "hash_file_component",
                         return_value=("digest", 6)),
            patch.object(inventory, "close_handle") as close,
        ):
            records = inventory.inventory_directory_handle(100)
        self.assertEqual([item["path"] for item in records],
                         ["sub", "sub/inside.txt"])
        close.assert_called_once_with(200)

    def test_aborts_if_directory_changes_after_processing(self):
        first = entry("before.txt")
        changed = entry("after.txt", file_id="ff" * 16)
        with (
            patch.object(inventory, "query_handle_metadata",
                         return_value=self._root_metadata()),
            patch.object(inventory, "enumerate_stable_directory_handle",
                         side_effect=((first,), (changed,))),
            patch.object(inventory, "hash_file_component",
                         return_value=("digest", 6)),
        ):
            with self.assertRaises(inventory.HandleIoError):
                inventory.inventory_directory_handle(100)

    def test_rejects_invalid_root_handle(self):
        with patch.object(inventory, "query_handle_metadata",
                          return_value={
                              "is_directory": False,
                              "is_reparse_point": False,
                              "delete_pending": False,
                          }):
            with self.assertRaises(inventory.HandleIoError):
                inventory.inventory_directory_handle(100)

    def test_enforces_depth_limit(self):
        directory = entry("sub", attributes=0x10, size=0)
        with (
            patch.object(inventory, "query_handle_metadata",
                         return_value=self._root_metadata()),
            patch.object(inventory, "enumerate_stable_directory_handle",
                         return_value=(directory,)),
            patch.object(inventory, "open_verified_child_component",
                         return_value=200),
            patch.object(inventory, "close_handle"),
        ):
            with self.assertRaises(inventory.HandleIoError):
                inventory.inventory_directory_handle(100, max_depth=0)

    def test_rejects_boolean_limits(self):
        with patch.object(inventory, "query_handle_metadata",
                          return_value=self._root_metadata()):
            with self.assertRaises(inventory.HandleIoError):
                inventory.inventory_directory_handle(100, max_entries=True)


if __name__ == "__main__":
    unittest.main()
