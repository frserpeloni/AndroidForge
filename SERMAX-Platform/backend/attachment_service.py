"""Armazenamento e validação de anexos locais por conversa."""
from __future__ import annotations

import hashlib
import io
import os
import re
import threading
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from docx import Document
from pypdf import PdfReader

router = APIRouter()
UPLOAD_LOCK = threading.Lock()
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_CONVERSATION = 5
MAX_TOTAL_BYTES_PER_CONVERSATION = 25 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_EXTRACTED_CHARS = 100_000
MAX_IMAGE_PIXELS = 20_000_000
MAX_DOCX_ENTRIES = 2_000
MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"}
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
MIME_BY_KIND = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
    "jpg": "image/jpeg",
    "png": "image/png",
}


def _server():
    import server
    return server


def _storage_root() -> Path:
    root = (_server().DATA_DIR / "attachments").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def initialize_attachment_schema() -> None:
    server = _server()
    with server.database() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                original_name TEXT NOT NULL,
                extension TEXT NOT NULL,
                detected_mime TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
                sha256 TEXT NOT NULL,
                storage_name TEXT NOT NULL UNIQUE,
                extracted_text TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attachments_conversation ON attachments(conversation_id, created_at)")


def _safe_display_name(filename: str | None) -> str:
    raw = (filename or "arquivo").replace("\\", "/").split("/")[-1]
    cleaned = CONTROL_CHARS.sub("", raw).strip().strip(".")
    if not cleaned or cleaned in {".", ".."}:
        cleaned = "arquivo"
    return cleaned[:180]


def _kind_from_bytes(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if b"\x00" not in data:
        try:
            data.decode("utf-8", errors="strict")
            return "txt"
        except UnicodeDecodeError:
            pass
    raise HTTPException(status_code=415, detail="Formato não permitido ou assinatura inválida.")


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise HTTPException(status_code=422, detail="PDF criptografado não é aceito.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise HTTPException(status_code=413, detail="PDF excede o limite de 100 páginas.")
        chunks, total = [], 0
        for page in reader.pages:
            text = page.extract_text() or ""
            remaining = MAX_EXTRACTED_CHARS - total
            if remaining <= 0:
                break
            chunks.append(text[:remaining])
            total += min(len(text), remaining)
        return "\n".join(chunks)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="PDF inválido ou corrompido.") from exc


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise HTTPException(status_code=413, detail="DOCX contém entradas demais.")
            total_uncompressed, names = 0, set()
            for entry in entries:
                name = entry.filename
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name:
                    raise HTTPException(status_code=422, detail="DOCX contém caminho interno inválido.")
                if entry.flag_bits & 0x1:
                    raise HTTPException(status_code=422, detail="DOCX criptografado não é aceito.")
                total_uncompressed += entry.file_size
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED:
                    raise HTTPException(status_code=413, detail="DOCX excede o limite de descompactação.")
                names.add(name)
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise HTTPException(status_code=415, detail="O pacote ZIP não é um documento DOCX válido.")
            if any("vbaproject" in name.casefold() for name in names):
                raise HTTPException(status_code=415, detail="Documentos com macros não são aceitos.")
            for name in names:
                if name.endswith(".rels") and b'TargetMode="External"' in archive.read(name):
                    raise HTTPException(status_code=415, detail="DOCX com relacionamentos externos não é aceito.")
        document = Document(io.BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)[:MAX_EXTRACTED_CHARS]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="DOCX inválido ou corrompido.") from exc


def _validate_and_extract(data: bytes, display_name: str) -> tuple[str, str | None]:
    kind = _kind_from_bytes(data)
    suffix = Path(display_name).suffix.casefold()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Extensão não permitida.")
    expected = ".jpg" if kind == "jpg" and suffix == ".jpeg" else f".{kind}"
    if suffix != expected:
        raise HTTPException(status_code=415, detail="A extensão não corresponde ao conteúdo do arquivo.")
    if kind == "pdf":
        return MIME_BY_KIND[kind], _extract_pdf(data)
    if kind == "docx":
        return MIME_BY_KIND[kind], _extract_docx(data)
    if kind == "txt":
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="TXT deve estar codificado em UTF-8.") from exc
        if "\x00" in text:
            raise HTTPException(status_code=415, detail="TXT contém bytes NUL.")
        return MIME_BY_KIND[kind], text[:MAX_EXTRACTED_CHARS]
    try:
        with Image.open(io.BytesIO(data)) as image:
            expected_format = "JPEG" if kind == "jpg" else "PNG"
            if image.format != expected_format:
                raise HTTPException(status_code=415, detail="Assinatura e formato da imagem divergem.")
            width, height = image.size
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="Imagem excede o limite de dimensões.")
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=422, detail="Imagem inválida ou corrompida.") from exc
    return MIME_BY_KIND[kind], None


def _stored_path(storage_name: str) -> Path:
    root = _storage_root()
    candidate = (root / storage_name).resolve()
    if candidate.parent != root or candidate.name != storage_name:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    return candidate


def _metadata(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"], "conversation_id": row["conversation_id"],
        "name": row["original_name"], "extension": row["extension"],
        "mime": row["detected_mime"], "size_bytes": row["size_bytes"],
        "sha256": row["sha256"], "has_extracted_text": row["extracted_text"] is not None,
        "created_at": row["created_at"],
    }


@router.post("/api/conversations/{conversation_id}/attachments", status_code=201)
async def upload_attachment(conversation_id: str, file: UploadFile = File(...)):
    server = _server()
    display_name = _safe_display_name(file.filename)
    if Path(display_name).suffix.casefold() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Extensão não permitida.")
    data = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    if not data:
        raise HTTPException(status_code=422, detail="Arquivo vazio.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Cada arquivo deve ter no máximo 10 MiB.")
    mime, extracted = _validate_and_extract(data, display_name)
    extension = Path(display_name).suffix.casefold()
    attachment_id, storage_name = str(uuid.uuid4()), str(uuid.uuid4())
    root = _storage_root()
    target = _stored_path(storage_name)
    temporary = _stored_path(storage_name + ".tmp")

    with UPLOAD_LOCK:
        with server.database() as conn:
            if conn.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Conversa não encontrada.")
            totals = conn.execute(
                "SELECT COUNT(*) AS count, COALESCE(SUM(size_bytes),0) AS total FROM attachments WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if totals["count"] >= MAX_FILES_PER_CONVERSATION:
                raise HTTPException(status_code=413, detail="A conversa já atingiu o limite de 5 anexos.")
            if totals["total"] + len(data) > MAX_TOTAL_BYTES_PER_CONVERSATION:
                raise HTTPException(status_code=413, detail="A conversa excederia o limite total de 25 MiB.")
            try:
                with temporary.open("xb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
                conn.execute(
                    "INSERT INTO attachments(id,conversation_id,original_name,extension,detected_mime,size_bytes,sha256,storage_name,extracted_text,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (attachment_id, conversation_id, display_name, extension, mime, len(data),
                     hashlib.sha256(data).hexdigest(), storage_name, extracted, server.utc_now()),
                )
                row = conn.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()
            except Exception:
                temporary.unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                raise
    return _metadata(row)


@router.get("/api/conversations/{conversation_id}/attachments")
def list_attachments(conversation_id: str):
    server = _server()
    with server.database() as conn:
        if conn.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")
        rows = conn.execute("SELECT * FROM attachments WHERE conversation_id=? ORDER BY created_at,id", (conversation_id,)).fetchall()
    return [_metadata(row) for row in rows]


def _get_attachment(conversation_id: str, attachment_id: str):
    server = _server()
    with server.database() as conn:
        row = conn.execute("SELECT * FROM attachments WHERE id=? AND conversation_id=?", (attachment_id, conversation_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    path = _stored_path(row["storage_name"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo do anexo não está disponível.")
    return row, path


@router.get("/api/conversations/{conversation_id}/attachments/{attachment_id}")
def download_attachment(conversation_id: str, attachment_id: str):
    row, path = _get_attachment(conversation_id, attachment_id)
    return FileResponse(path, media_type="application/octet-stream", filename=row["original_name"], content_disposition_type="attachment")


@router.get("/api/conversations/{conversation_id}/attachments/{attachment_id}/content")
def read_attachment_content(conversation_id: str, attachment_id: str):
    row, _ = _get_attachment(conversation_id, attachment_id)
    if row["extracted_text"] is None:
        raise HTTPException(status_code=415, detail="Este formato não possui texto extraído nesta versão.")
    return {"attachment_id": attachment_id, "name": row["original_name"], "text": row["extracted_text"], "read_only": True}


@router.delete("/api/conversations/{conversation_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(conversation_id: str, attachment_id: str):
    server = _server()
    row, path = _get_attachment(conversation_id, attachment_id)
    tombstone = path.with_name(path.name + ".deleting")
    try:
        os.replace(path, tombstone)
        with server.database() as conn:
            conn.execute("DELETE FROM attachments WHERE id=? AND conversation_id=?", (attachment_id, conversation_id))
        tombstone.unlink(missing_ok=True)
    except Exception as exc:
        if tombstone.exists() and not path.exists():
            os.replace(tombstone, path)
        raise HTTPException(status_code=503, detail="Falha ao excluir o anexo com segurança.") from exc
