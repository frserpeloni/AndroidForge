"""Teste local real de OCR em imagem sintética e PDF digitalizado, sem arquivos externos."""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from PIL import Image, ImageDraw, ImageFont
from ocr_service import get_ocr_engine_status, ocr_image_bytes, ocr_pdf_pages


SAMPLE_TEXT = "SERMAX OCR TESTE 2026 12345"


def build_sample_image() -> Image.Image:
    image = Image.new("RGB", (1600, 300), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=84)
    bounds = draw.textbbox((0, 0), SAMPLE_TEXT, font=font)
    x = (image.width - (bounds[2] - bounds[0])) // 2
    y = (image.height - (bounds[3] - bounds[1])) // 2 - bounds[1]
    draw.text((x, y), SAMPLE_TEXT, fill="black", font=font)
    return image


def normalized(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def main() -> int:
    engine = get_ocr_engine_status()
    if engine["status"] != "ready":
        print(json.dumps({"engine": engine, "status": "blocked"}, ensure_ascii=False, indent=2))
        return 2

    try:
        import pypdfium2  # noqa: F401
    except ImportError:
        print(json.dumps({
            "engine": engine,
            "status": "renderer_unavailable",
            "detail": "Instale pypdfium2 no ambiente Python ativo.",
        }, ensure_ascii=False, indent=2))
        return 3

    sample = build_sample_image()
    image_buffer = io.BytesIO()
    sample.save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    image_text, image_status = ocr_image_bytes(image_bytes)

    pdf_buffer = io.BytesIO()
    sample.save(pdf_buffer, format="PDF", resolution=150)
    pdf_text, pdf_status = ocr_pdf_pages(pdf_buffer.getvalue(), [0])
    sample.close()

    image_text = image_text or ""
    pdf_result = pdf_text.get(0, "")
    image_ok = image_status == "completed" and "SERMAX" in normalized(image_text) and "12345" in normalized(image_text)
    pdf_ok = pdf_status == "completed" and "SERMAX" in normalized(pdf_result) and "12345" in normalized(pdf_result)
    report = {
        "engine": engine,
        "image": {"status": image_status, "recognized_text": image_text, "passed": image_ok},
        "scanned_pdf": {"status": pdf_status, "recognized_text": pdf_result, "passed": pdf_ok},
        "overall": "passed" if image_ok and pdf_ok else "failed",
        "data_source": "synthetic in-memory sample; no personal files read or written",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if image_ok and pdf_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
