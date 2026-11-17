from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sermax_voz as voice


class WhisperDiscoveryCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sermax = self.root / "SERMAX"
        self.downloads = self.root / "Downloads"
        self.sermax.mkdir()
        self.downloads.mkdir()
        self.cache = patch.multiple(
            voice,
            SERMAX_DIR=self.sermax,
            USER_DOWNLOADS=self.downloads,
            _CACHE_WHISPER=None,
            _CACHE_MODELO=None,
        )
        self.cache.start()
        self.addCleanup(self.cache.stop)
        self.addCleanup(self.temp.cleanup)

    def test_reuses_existing_fallback_paths_without_second_recursive_scan(self):
        whisper = self.downloads / "tools" / "whisper-cli.exe"
        model = self.sermax / "voz" / "modelos" / "ggml-tiny.bin"
        whisper.parent.mkdir(parents=True)
        model.parent.mkdir(parents=True)
        whisper.write_bytes(b"exe")
        model.write_bytes(b"model")

        with patch.object(
            voice, "_arquivos_por_nome", wraps=voice._arquivos_por_nome
        ) as search:
            first = voice.localizar_whisper_e_modelo()
            self.assertEqual(first, (str(whisper), str(model)))
            first_calls = search.call_count
            self.assertEqual(first_calls, 2)

            second = voice.localizar_whisper_e_modelo()
            self.assertEqual(second, first)
            self.assertEqual(search.call_count, first_calls)

    def test_prefers_new_direct_installation_over_cached_fallback(self):
        fallback = self.downloads / "tools" / "whisper-cli.exe"
        model = self.sermax / "voz" / "modelos" / "ggml-tiny.bin"
        fallback.parent.mkdir(parents=True)
        model.parent.mkdir(parents=True)
        fallback.write_bytes(b"exe")
        model.write_bytes(b"model")
        voice.localizar_whisper_e_modelo()

        preferred = self.sermax / "voz" / "whisper" / "Release" / "whisper-cli.exe"
        preferred.parent.mkdir(parents=True)
        preferred.write_bytes(b"new-exe")

        result = voice.localizar_whisper_e_modelo()
        self.assertEqual(result[0], str(preferred))
        self.assertEqual(result[1], str(model))

    def test_invalidated_cache_entry_is_rescanned(self):
        original = self.downloads / "first" / "whisper-cli.exe"
        replacement = self.downloads / "second" / "whisper-cli.exe"
        model = self.downloads / "models" / "ggml-tiny.bin"
        original.parent.mkdir(parents=True)
        replacement.parent.mkdir(parents=True)
        model.parent.mkdir(parents=True)
        original.write_bytes(b"old")
        model.write_bytes(b"model")
        self.assertEqual(voice.localizar_whisper_e_modelo()[0], str(original))

        original.unlink()
        replacement.write_bytes(b"new")
        result = voice.localizar_whisper_e_modelo()
        self.assertEqual(result[0], str(replacement))
        self.assertEqual(result[1], str(model))


if __name__ == "__main__":
    unittest.main()
