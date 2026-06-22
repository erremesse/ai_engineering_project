"""
Extracción de texto de adjuntos (Camino B — extracción local).

Elección frente al Camino A (Files API multimodal):
- Independiente del proveedor: funciona con cualquier LLM del router.
- Sin coste extra de tokens de carga de fichero en la API.
- Prepara el terreno para chunking y RAG en fases posteriores.
"""

import io
from dataclasses import dataclass

import structlog
from fastapi import UploadFile

logger = structlog.get_logger()

_SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

_ATTACHMENT_SEPARATOR = "--- attachment: {filename} ---"


@dataclass(frozen=True)
class ExtractionResult:
    filename: str
    text: str
    char_count: int


class AttachmentService:
    """Extrae texto de PDFs y documentos Word para inyectarlo en el prompt."""

    def extract_text(self, file: UploadFile) -> ExtractionResult:
        """
        Extrae el texto de un UploadFile (PDF o DOCX).

        Raises:
            ValueError: si el tipo de fichero no está soportado.
        """
        filename = file.filename or "unknown"
        ext = self._extension(filename)

        if ext == ".pdf":
            text = self._extract_pdf(file)
        elif ext == ".docx":
            text = self._extract_docx(file)
        else:
            raise ValueError(
                f"Tipo de fichero no soportado: '{ext}'. "
                f"Formatos aceptados: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}."
            )

        logger.info(
            "attachment_extracted",
            filename=filename,
            ext=ext,
            char_count=len(text),
        )
        return ExtractionResult(filename=filename, text=text, char_count=len(text))

    def build_attachment_block(self, result: ExtractionResult) -> str:
        """Devuelve el bloque de texto con separador listo para concatenar al transcript."""
        separator = _ATTACHMENT_SEPARATOR.format(filename=result.filename)
        return f"\n\n{separator}\n{result.text}"

    def _extension(self, filename: str) -> str:
        dot = filename.rfind(".")
        return filename[dot:].lower() if dot != -1 else ""

    def _extract_pdf(self, file: UploadFile) -> str:
        from pypdf import PdfReader

        data = file.file.read()
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()

    def _extract_docx(self, file: UploadFile) -> str:
        from docx import Document

        data = file.file.read()
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()


attachment_service = AttachmentService()
