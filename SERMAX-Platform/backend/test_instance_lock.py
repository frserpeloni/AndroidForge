import tempfile
import unittest
from pathlib import Path

from instance_lock import InstanceLockError, acquire_instance_lock


class InstanceLockTests(unittest.TestCase):
    def test_rejects_second_instance_until_first_handle_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            first = acquire_instance_lock(data_dir)
            try:
                with self.assertRaises(InstanceLockError):
                    acquire_instance_lock(data_dir)
            finally:
                first.close()
            second = acquire_instance_lock(data_dir)
            second.close()

    def test_lock_file_is_created_inside_platform_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            handle = acquire_instance_lock(data_dir)
            try:
                self.assertTrue((data_dir / "platform-instance.lock").is_file())
            finally:
                handle.close()


if __name__ == "__main__":
    unittest.main()
