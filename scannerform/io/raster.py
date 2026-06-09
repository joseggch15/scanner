"""Rasterización de páginas de PDF y carga de imágenes a objetos PIL.

Para la vista previa y para el OCR de documentos escaneados se necesita una
imagen de mapa de bits. Se usa `pypdfium2` (sin dependencias del sistema como
Poppler o ImageMagick) para renderizar páginas de PDF, y Pillow para abrir
archivos de imagen directamente.
"""
from __future__ import annotations

import os

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

from scannerform import config


def image_backend_available() -> bool:
    return Image is not None


def pdf_raster_available() -> bool:
    return pdfium is not None and Image is not None


def load_image(path: str):
    """Abre un archivo de imagen como objeto PIL en RGB."""
    if Image is None:
        raise ImportError("Se requiere 'Pillow' para abrir imágenes.")
    img = Image.open(path)
    return img.convert("RGB")


def render_pdf_page(path: str, page_index: int = 0, dpi: int = config.RASTER_DPI):
    """Renderiza una página de PDF a una imagen PIL (RGB) a la resolución dada."""
    if pdfium is None or Image is None:
        raise ImportError(
            "Se requiere 'pypdfium2' y 'Pillow' para rasterizar PDFs.\n"
            "Instale con:  pip install pypdfium2 Pillow")
    pdf = pdfium.PdfDocument(path)
    try:
        n = len(pdf)
        page_index = max(0, min(page_index, n - 1))
        page = pdf[page_index]
        scale = dpi / 72.0                 # pypdfium usa escala relativa a 72 DPI
        bitmap = page.render(scale=scale)
        return bitmap.to_pil().convert("RGB")
    finally:
        pdf.close()


def render_all_pdf_pages(path: str, dpi: int = config.OCR_DPI):
    """Renderiza todas las páginas de un PDF a imágenes PIL (para OCR multipágina)."""
    if pdfium is None or Image is None:
        raise ImportError("Se requiere 'pypdfium2' y 'Pillow'.")
    out = []
    pdf = pdfium.PdfDocument(path)
    try:
        scale = dpi / 72.0
        for i in range(len(pdf)):
            out.append(pdf[i].render(scale=scale).to_pil().convert("RGB"))
    finally:
        pdf.close()
    return out


def is_pdf(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in config.PDF_EXTS


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in config.IMAGE_EXTS
