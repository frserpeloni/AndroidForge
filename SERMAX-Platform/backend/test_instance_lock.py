import multiprocessing
import tempfile
import unittest
from pathlib import Path

from instance_lock import InstanceLockError, acquire_instance_lock


def _attempt_lock_in_child_process(data_dir: str, result_queue) -> None:
    """Tenta adquirir o mesmo lock em um processo independente."""
    try:
        handle = acquire_instance_lock(Path(data_dir))
    except InstanceLockError:
        result_queue.put("blocked")
    else:
        handle.close()
        result_queue.put("acquired")


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

    def test_lock_is_exclusive_across_independent_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            first = acquire_instance_lock(data_dir)
            context = multiprocessing.get_context("spawn")
            result_queue = context.Queue()
            process = context.Process(
                target=_attempt_lock_in_child_process,
                args=(str(data_dir), result_queue),
            )
            try:
                process.start()
                process.join(timeout=15)
                self.assertFalse(process.is_alive(), "Child process timed out.")
                self.assertEqual(process.exitcode, 0)
                self.assertEqual(result_queue.get(timeout=3), "blocked")
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                first.close()
                result_queue.close()
                result_queue.join_thread()

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
