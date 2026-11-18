"""OCR local opcional para imagens e páginas PDF digitalizadas."""
from __future__ import annotations

import io
import os
import shutil
import threading
from pathlib import Path
from typing import Iterable

from PIL import Image

OCR_TIMEOUT_SECONDS = 8
MAX_OCR_IMAGE_PIXELS = 9_000_000
MAX_OCR_IMAGE_SIDE = 3_000
MAX_OCR_PDF_PAGES = 5
PDF_RENDER_DPI = 150
OCR_LANGUAGE = "por+eng"
OCR_LOCK = threading.Lock()


def _tesseract_path() -> str | None:
    configured = os.environ.get("SERMAX_TESSERACT_CMD", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        return None
    return shutil.which("tesseract")


def _run_tesseract(image: Image.Image) -> tuple[str, str]:
    executable = _tesseract_path()
    if not executable:
        return "", "engine_unavailable"
    try:
        import pytesseract
    except ImportError:
        return "", "dependency_unavailable"

    with OCR_LOCK:
        previous_command = pytesseract.pytesseract.tesseract_cmd
        pytesseract.pytesseract.tesseract_cmd = executable
        try:
            text = pytesseract.image_to_string(
                image,
                lang=OCR_LANGUAGE,
                config="--psm 6",
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except pytesseract.TesseractNotFoundError:
            return "", "engine_unavailable"
        except pytesseract.TesseractError as exc:
            message = str(exc).casefold()
            if "traineddata" in message or "failed loading language" in message:
                return "", "language_unavailable"
            return "", "failed"
        except RuntimeError as exc:
            if "timeout" in str(exc).casefold():
                return "", "timeout"
            return "", "failed"
        except Exception:
            return "", "failed"
        finally:
            pytesseract.pytesseract.tesseract_cmd = previous_command

    cleaned = text.strip()
    return (cleaned[:100_000], "completed") if cleaned else ("", "no_text")


def _prepare_image(image: Image.Image) -> Image.Image:
    prepared = image.convert("L")
    if (
        prepared.width * prepared.height > MAX_OCR_IMAGE_PIXELS
        or max(prepared.size) > MAX_OCR_IMAGE_SIDE
    ):
        prepared.thumbnail(
            (MAX_OCR_IMAGE_SIDE, MAX_OCR_IMAGE_SIDE),
            Image.Resampling.LANCZOS,
        )
    return prepared


def ocr_image_bytes(data: bytes) -> tuple[str | None, str]:
    """Executa OCR local em JPEG/PNG, sem falhar o upload se o motor faltar."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            prepared = _prepare_image(source)
            try:
                text, status = _run_tesseract(prepared)
            finally:
                prepared.close()
    except Exception:
        return None, "failed"
    return (text, status) if text else (None, status)


def ocr_pdf_pages(
    data: bytes,
    page_indexes: Iterable[int],
) -> tuple[dict[int, str], str]:
    """Renderiza e reconhece no máximo cinco páginas sem texto nativo."""
    indexes = list(page_indexes)
    if not indexes:
        return {}, "not_needed"
    if not _tesseract_path():
        return {}, "engine_unavailable"
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return {}, "renderer_unavailable"

    recognized: dict[int, str] = {}
    statuses: list[str] = []
    document = None
    try:
        document = pdfium.PdfDocument(data)
        for page_index in indexes[:MAX_OCR_PDF_PAGES]:
            page = None
            bitmap = None
            prepared = None
            try:
                page = document[page_index]
                width, height = page.get_size()
                if width <= 0 or height <= 0:
                    statuses.append("failed")
                    continue
                scale = min(PDF_RENDER_DPI / 72, MAX_OCR_IMAGE_SIDE / max(width, height))
                bitmap = page.render(scale=scale)
                source = bitmap.to_pil()
                try:
                    prepared = _prepare_image(source)
                finally:
                    source.close()
                text, status = _run_tesseract(prepared)
                statuses.append(status)
                if text:
                    recognized[page_index] = text
            except Exception:
                statuses.append("failed")
            finally:
                if prepared is not None:
                    prepared.close()
                if bitmap is not None:
                    bitmap.close()
                if page is not None:
                    page.close()
    except Exception:
        return recognized, "render_failed"
    finally:
        if document is not None:
            document.close()

    if len(indexes) > MAX_OCR_PDF_PAGES:
        statuses.append("page_limit")
    if recognized and (any(status != "completed" for status in statuses) or len(indexes) > MAX_OCR_PDF_PAGES):
        return recognized, "partial"
    if recognized:
        return recognized, "completed"
    if statuses:
        return {}, statuses[0] if len(set(statuses)) == 1 else "failed"
    return {}, "no_text"
