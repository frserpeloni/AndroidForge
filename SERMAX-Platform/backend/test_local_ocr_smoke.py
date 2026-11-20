import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_local_ocr


class LocalOcrSmokeTests(unittest.TestCase):
    def test_smoke_test_reports_image_and_scanned_pdf_results(self):
        output = io.StringIO()
        with patch.object(check_local_ocr, "get_ocr_engine_status", return_value={
            "status": "ready", "languages": ["eng", "por"], "missing_languages": [], "detail": "ready"
        }), patch.object(check_local_ocr, "ocr_image_bytes", return_value=(
            "SERMAX OCR TESTE 2026 12345", "completed"
        )), patch.object(check_local_ocr, "ocr_pdf_pages", return_value=(
            {0: "SERMAX OCR TESTE 2026 12345"}, "completed"
        )), contextlib.redirect_stdout(output):
            result = check_local_ocr.main()

        self.assertEqual(result, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["overall"], "passed")
        self.assertTrue(report["image"]["passed"])
        self.assertTrue(report["scanned_pdf"]["passed"])
        self.assertIn("no personal files", report["data_source"])

    def test_smoke_test_stops_when_local_engine_is_not_ready(self):
        output = io.StringIO()
        with patch.object(check_local_ocr, "get_ocr_engine_status", return_value={
            "status": "engine_unavailable", "languages": [], "missing_languages": ["por", "eng"],
            "detail": "Tesseract não encontrado."
        }), patch.object(check_local_ocr, "ocr_image_bytes") as image_ocr, \
             contextlib.redirect_stdout(output):
            result = check_local_ocr.main()

        self.assertEqual(result, 2)
        image_ocr.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
