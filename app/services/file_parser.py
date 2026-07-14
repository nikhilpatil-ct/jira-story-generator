import io

import docx
from pypdf import PdfReader


class FileParseError(Exception):
    pass


def extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".txt") or name.endswith(".md"):
        return content.decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        return _extract_docx(content)
    if name.endswith(".pdf"):
        return _extract_pdf(content)
    raise FileParseError(f"Unsupported file type: {filename}. Use .txt, .docx, or .pdf.")


def _extract_docx(content: bytes) -> str:
    document = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()
