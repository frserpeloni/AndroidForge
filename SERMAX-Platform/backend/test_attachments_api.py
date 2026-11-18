import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from docx import Document
from pypdf import PdfWriter
from unittest.mock import patch
import attachment_service
import ocr_service
import server


class AttachmentApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "attachments.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        from attachment_service import initialize_attachment_schema
        initialize_attachment_schema()
        self.client = TestClient(server.app, client=("127.0.0.1", 50211))
        self.headers = {"host": "127.0.0.1:8765"}
        with server.database() as conn:
            conn.execute(
                "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                ("conversation-a", "Teste", server.utc_now(), server.utc_now()),
            )
            conn.execute(
                "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                ("conversation-b", "Outra conversa", server.utc_now(), server.utc_now()),
            )

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def upload(self, name, data, conversation="conversation-a"):
        return self.client.post(
            f"/api/conversations/{conversation}/attachments",
            files={"file": (name, data, "application/octet-stream")},
            headers=self.headers,
        )

    def test_txt_upload_persists_metadata_and_readonly_extracted_text(self):
        response = self.upload("anotacoes.txt", "SERMAX anexo de teste".encode())
        self.assertEqual(response.status_code, 201, response.text)
        attachment = response.json()
        self.assertEqual(attachment["name"], "anotacoes.txt")
        self.assertEqual(attachment["mime"], "text/plain; charset=utf-8")
        self.assertTrue(attachment["has_extracted_text"])

        listing = self.client.get(
            "/api/conversations/conversation-a/attachments", headers=self.headers
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()), 1)

        content = self.client.get(
            f"/api/conversations/conversation-a/attachments/{attachment['id']}/content",
            headers=self.headers,
        )
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.json()["text"], "SERMAX anexo de teste")

        download = self.client.get(
            f"/api/conversations/conversation-a/attachments/{attachment['id']}",
            headers=self.headers,
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"SERMAX anexo de teste")
        self.assertEqual(download.headers["content-type"], "application/octet-stream")

    def test_extension_mismatch_and_disallowed_types_are_rejected(self):
        mismatch = self.upload("foto.png", b"texto simples")
        self.assertEqual(mismatch.status_code, 415)
        blocked = self.upload("script.py", b"print('no')")
        self.assertEqual(blocked.status_code, 415)
        listing = self.client.get(
            "/api/conversations/conversation-a/attachments", headers=self.headers
        )
        self.assertEqual(listing.json(), [])

    def test_empty_and_oversized_uploads_are_rejected(self):
        empty = self.upload("empty.txt", b"")
        self.assertEqual(empty.status_code, 422)
        oversized = self.upload("large.txt", b"x" * (10 * 1024 * 1024 + 1))
        self.assertEqual(oversized.status_code, 413)

    def test_upload_requires_existing_conversation(self):
        response = self.upload("note.txt", b"ok", "missing-conversation")
        self.assertEqual(response.status_code, 404)

    def test_another_conversation_cannot_read_download_or_delete_attachment(self):
        response = self.upload("private.txt", b"conteudo privado")
        attachment_id = response.json()["id"]
        other_list = self.client.get(
            "/api/conversations/conversation-b/attachments", headers=self.headers
        )
        self.assertEqual(other_list.json(), [])
        url = f"/api/conversations/conversation-b/attachments/{attachment_id}"
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get(url + "/content", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 404)

    def test_image_upload_survives_missing_ocr_engine(self):
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buffer, format="PNG")
        with patch.object(ocr_service, "_tesseract_path", return_value=None):
            response = self.upload("pixel.png", buffer.getvalue())
        self.assertEqual(response.status_code, 201, response.text)
        self.assertFalse(response.json()["has_extracted_text"])
        self.assertEqual(response.json()["extraction_method"], "none")
        self.assertEqual(response.json()["extraction_status"], "engine_unavailable")
        content = self.client.get(
            f"/api/conversations/conversation-a/attachments/{response.json()['id']}/content",
            headers=self.headers,
        )
        self.assertEqual(content.status_code, 415)

    def test_image_ocr_text_is_stored_and_available_to_context(self):
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buffer, format="PNG")
        with patch.object(ocr_service, "_run_tesseract", return_value=("Texto reconhecido na imagem", "completed")):
            response = self.upload("documento.png", buffer.getvalue())
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["extraction_method"], "ocr")
        self.assertEqual(response.json()["extraction_status"], "completed")
        content = self.client.get(
            f"/api/conversations/conversation-a/attachments/{response.json()['id']}/content",
            headers=self.headers,
        )
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.json()["text"], "Texto reconhecido na imagem")

    def test_delete_removes_metadata_and_file(self):
        response = self.upload("remove.txt", b"apagar")
        attachment_id = response.json()["id"]
        with server.database() as conn:
            row = conn.execute("SELECT storage_name FROM attachments WHERE id=?", (attachment_id,)).fetchone()
        stored_path = (server.DATA_DIR / "attachments" / row["storage_name"]).resolve()
        self.assertTrue(stored_path.is_file())

        deleted = self.client.delete(
            f"/api/conversations/conversation-a/attachments/{attachment_id}",
            headers=self.headers,
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(stored_path.exists())
        self.assertEqual(
            self.client.get(
                "/api/conversations/conversation-a/attachments", headers=self.headers
            ).json(),
            [],
        )


    def test_docx_and_pdf_are_parsed_and_persisted(self):
        docx_buffer = io.BytesIO()
        document = Document()
        document.add_paragraph("Conteúdo DOCX de teste.")
        document.save(docx_buffer)
        docx_response = self.upload("relatorio.docx", docx_buffer.getvalue())
        self.assertEqual(docx_response.status_code, 201, docx_response.text)
        docx_content = self.client.get(
            f"/api/conversations/conversation-a/attachments/{docx_response.json()['id']}/content",
            headers=self.headers,
        )
        self.assertEqual(docx_content.status_code, 200)
        self.assertIn("Conteúdo DOCX de teste.", docx_content.json()["text"])

        pdf_buffer = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(pdf_buffer)
        with patch.object(attachment_service, "ocr_pdf_pages", return_value=({}, "engine_unavailable")):
            pdf_response = self.upload("folha.pdf", pdf_buffer.getvalue())
        self.assertEqual(pdf_response.status_code, 201, pdf_response.text)
        self.assertFalse(pdf_response.json()["has_extracted_text"])
        self.assertEqual(pdf_response.json()["extraction_status"], "engine_unavailable")

    def test_corrupt_docx_and_encrypted_pdf_are_rejected(self):
        corrupt = self.upload("quebrado.docx", bytes([0x50, 0x4B, 0x03, 0x04]) + b"nao-e-zip")
        self.assertEqual(corrupt.status_code, 422)

        pdf_buffer = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.encrypt("senha")
        writer.write(pdf_buffer)
        encrypted = self.upload("protegido.pdf", pdf_buffer.getvalue())
        self.assertEqual(encrypted.status_code, 422)


    def test_scanned_pdf_ocr_uses_local_renderer_with_mocked_engine(self):
        pdf_buffer = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(pdf_buffer)
        with patch.object(ocr_service, "_tesseract_path", return_value="C:/fake/tesseract.exe"), \
             patch.object(ocr_service, "_run_tesseract", return_value=("Texto reconhecido na página", "completed")):
            response = self.upload("digitalizado.pdf", pdf_buffer.getvalue())
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["extraction_method"], "ocr")
        self.assertEqual(response.json()["extraction_status"], "completed")
        content = self.client.get(
            f"/api/conversations/conversation-a/attachments/{response.json()['id']}/content",
            headers=self.headers,
        )
        self.assertEqual(content.status_code, 200)
        self.assertIn("[OCR página 1]", content.json()["text"])
        self.assertIn("Texto reconhecido na página", content.json()["text"])


    def test_schema_migration_adds_extraction_metadata_for_existing_images(self):
        with server.database() as conn:
            conn.execute("DROP TABLE attachments")
            conn.execute("""
                CREATE TABLE attachments (
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
            conn.execute(
                "INSERT INTO attachments(id,conversation_id,original_name,extension,detected_mime,size_bytes,sha256,storage_name,extracted_text,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("legacy-image", "conversation-a", "old.png", ".png", "image/png", 8, "abc", "legacy.bin", None, server.utc_now()),
            )
        attachment_service.initialize_attachment_schema()
        with server.database() as conn:
            row = conn.execute(
                "SELECT extraction_method,extraction_status FROM attachments WHERE id=?",
                ("legacy-image",),
            ).fetchone()
        self.assertEqual(row["extraction_method"], "none")
        self.assertEqual(row["extraction_status"], "not_processed")

    def test_pdf_ocr_page_limit_is_enforced(self):
        pdf_buffer = io.BytesIO()
        writer = PdfWriter()
        for _ in range(6):
            writer.add_blank_page(width=72, height=72)
        writer.write(pdf_buffer)
        with patch.object(ocr_service, "_tesseract_path", return_value="C:/fake/tesseract.exe"), \
             patch.object(ocr_service, "_run_tesseract", return_value=("texto", "completed")) as recognize:
            pages, status = ocr_service.ocr_pdf_pages(pdf_buffer.getvalue(), range(6))
        self.assertEqual(len(pages), 5)
        self.assertEqual(recognize.call_count, 5)
        self.assertEqual(status, "partial")

    def test_sixth_attachment_is_rejected(self):
        for index in range(5):
            response = self.upload(f"{index}.txt", f"item {index}".encode())
            self.assertEqual(response.status_code, 201, response.text)
        sixth = self.upload("sixth.txt", b"extra")
        self.assertEqual(sixth.status_code, 413)


if __name__ == "__main__":
    unittest.main()
