import os
import sys
import tempfile
import unittest
from pathlib import Path

# Importa o módulo de lock
from backend.instance_lock import acquire_instance_lock, InstanceLockError

class TestInstanceLock(unittest.TestCase):
    def setUp(self):
        # Cria um diretório temporário para cada teste
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        # Remove o diretório temporário após o teste
        try:
            for child in self.temp_dir.iterdir():
                child.unlink()
            self.temp_dir.rmdir()
        except Exception:
            pass

    def test_lock_acquisition_and_release(self):
        # Primeiro lock deve ser obtido com sucesso
        handle1 = acquire_instance_lock(self.temp_dir)
        self.assertIsNotNone(handle1)

        # Tentativa de segundo lock no mesmo diretório deve falhar
        with self.assertRaises(InstanceLockError):
            acquire_instance_lock(self.temp_dir)

        # Fechando o primeiro handle libera o lock
        handle1.close()

        # Agora o lock pode ser adquirido novamente
        handle2 = acquire_instance_lock(self.temp_dir)
        self.assertIsNotNone(handle2)
        handle2.close()

    def test_lock_acquisition_on_different_dirs(self):
        # Locks em diretórios diferentes não interferem
        dir1 = self.temp_dir / "dir1"
        dir2 = self.temp_dir / "dir2"
        handle1 = acquire_instance_lock(dir1)
        handle2 = acquire_instance_lock(dir2)
        self.assertIsNotNone(handle1)
        self.assertIsNotNone(handle2)
        handle1.close()
        handle2.close()

if __name__ == "__main__":
    unittest.main()
