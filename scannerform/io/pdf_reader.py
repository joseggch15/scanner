"""Lectura de texto de PDFs con pdfplumber.

Extrae el texto de cada página en dos variantes:

  • `text`        — extracción estándar (palabras en orden de lectura).
  • `layout_text` — extracción con `layout=True`, que conserva mejor la
    alineación en columnas de los formularios tabulares (útil para los parsers).

Si el PDF es un escaneo sin capa de texto, `extract_text()` devuelve casi nada;
el llamador detecta ese caso (umbral `PDF_TEXT_MIN_CHARS`) y recurre al OCR.
"""
from __future__ import annotations

from dataclasses import dataclass, field

try:
    import pdfplumber
except ImportError:  # se valida con is_available()
    pdfplumber = None


@dataclass
class PdfText:
    """Texto extraído de un PDF."""
    pages: list[str] = field(default_factory=list)         # texto estándar por página
    layout_pages: list[str] = field(default_factory=list)  # texto con layout por página
    page_count: int = 0

    @property
    def text(self) -> str:
        return "\n".join(self.pages)

    @property
    def layout_text(self) -> str:
        return "\n".join(self.layout_pages)

    @property
    def char_count(self) -> int:
        return len(self.text.strip())


def is_available() -> bool:
    return pdfplumber is not None


def read_pdf_text(path: str) -> PdfText:
    """Extrae el texto de todas las páginas de un PDF."""
    if pdfplumber is None:
        raise ImportError(
            "Se requiere 'pdfplumber' para leer PDFs.\n"
            "Instale con:  pip install pdfplumber")

    result = PdfText()
    with pdfplumber.open(path) as pdf:
        result.page_count = len(pdf.pages)
        for page in pdf.pages:
            result.pages.append(page.extract_text() or "")
            try:
                result.layout_pages.append(
                    page.extract_text(layout=True, x_density=6, y_density=12) or "")
            except Exception:
                # `layout=True` puede fallar en páginas raras; no es crítico.
                result.layout_pages.append(result.pages[-1])
    return result
