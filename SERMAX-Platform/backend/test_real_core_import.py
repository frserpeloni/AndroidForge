import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RealCoreImportSmokeTests(unittest.TestCase):
    def test_real_core_imports_without_touching_user_memory_or_starting_a_model(self):
        repository_root = Path(__file__).resolve().parents[2]
        core_dir = repository_root / "SERMAX-Windows"
        self.assertTrue((core_dir / "sermax_core.py").is_file())

        with tempfile.TemporaryDirectory(prefix="sermax-core-smoke-") as isolated_root:
            isolated_memory = Path(isolated_root) / "memoria_sermax.json"
            with patch.dict(
                os.environ,
                {
                    "SERMAX_ROOT": isolated_root,
                    "SERMAX_CORE_DIR": str(core_dir),
                },
            ):
                sys.path.insert(0, str(core_dir))
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                try:
                    import server

                    server.CORE_MODULE = None
                    server.CORE_ERROR = None
                    core = server.load_core()

                    self.assertTrue(callable(core.perguntar))
                    self.assertIsInstance(core.sessao, list)
                    self.assertEqual(Path(core.ARQUIVO_MEMORIA), isolated_memory)
                    self.assertFalse(isolated_memory.exists())
                finally:
                    sys.path.remove(str(Path(__file__).resolve().parent))
                    sys.path.remove(str(core_dir))


if __name__ == "__main__":
    unittest.main()
