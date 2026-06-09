"""Orquestador de escaneo: archivo -> texto -> EquipmentRecord.

Decide la fuente de texto según el archivo:

  • Imagen (.jpg/.png/…)  -> OCR directo (Tesseract).
  • PDF con capa de texto -> pdfplumber (rápido y fiable; DocuSign).
  • PDF escaneado         -> si el texto es escaso (umbral PDF_TEXT_MIN_CHARS),
                             se rasteriza con pypdfium2 y se hace OCR.

Luego detecta el formulario (N-F-0016 / N-F-033) y delega al parser
correspondiente. El resultado es un EquipmentRecord en esquema canónico.
"""
from __future__ import annotations

import os
import re

from scannerform import config
from scannerform.io import ocr, pdf_reader, raster
from scannerform.model import EquipmentRecord
from scannerform.parsing import form_detector, tag_form, visitor_form

# Líneas de ruido que ensucian la extracción (DocuSign inyecta un envelope ID
# cuyo formato hexadecimal con guiones se confunde con un centro de costo).
_RE_NOISE = re.compile(r"^\s*Docusign Envelope ID:.*$", re.IGNORECASE | re.MULTILINE)


def _strip_noise(text: str) -> str:
    return _RE_NOISE.sub("", text or "")


def scan_file(path: str) -> EquipmentRecord:
    """Escanea un archivo (PDF o imagen) y devuelve el EquipmentRecord."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    ext = os.path.splitext(path)[1].lower()
    if ext not in config.SUPPORTED_EXTS:
        raise ValueError(
            f"Extensión no soportada: {ext}. "
            f"Soportadas: {', '.join(sorted(config.SUPPORTED_EXTS))}")

    if ext in config.IMAGE_EXTS:
        text, layout_text, kind = _read_image(path)
    else:
        text, layout_text, kind = _read_pdf(path)

    text = _strip_noise(text)
    layout_text = _strip_noise(layout_text)
    form_type = form_detector.detect_form_type(text)
    rec = _dispatch(form_type, text, layout_text)
    rec.source_file = path
    rec.source_kind = kind
    rec.form_type = form_type
    if form_type == config.FORM_UNKNOWN:
        rec.warnings.insert(0, (
            "No se reconoció el tipo de formulario (N-F-0016 / N-F-033). "
            "Los datos pueden estar incompletos; revise el texto crudo."))
    return rec


def _dispatch(form_type: str, text: str, layout_text: str) -> EquipmentRecord:
    if form_type == config.FORM_TAG:
        return tag_form.parse(text, layout_text)
    if form_type == config.FORM_VISITOR:
        return visitor_form.parse(text, layout_text)
    # Desconocido: intentar con ambos y quedarse con el que extraiga más.
    tag = tag_form.parse(text, layout_text)
    vis = visitor_form.parse(text, layout_text)
    return tag if _filled_score(tag) >= _filled_score(vis) else vis


def _filled_score(rec: EquipmentRecord) -> int:
    keys = ("fleet_asset_no", "make", "model", "registration_plate",
            "cost_centre", "dispense_limit", "tank_capacity")
    return sum(1 for k in keys if getattr(rec, k))


def _read_image(path: str) -> tuple[str, str, str]:
    """OCR de un archivo de imagen."""
    status = ocr.availability()
    if not status.installed:
        raise RuntimeError(
            "El archivo es una imagen y requiere OCR, pero Tesseract no está "
            "disponible.\n" + status.message)
    img = raster.load_image(path)
    text = ocr.ocr_image(img)
    return text, text, "image-ocr"


def _read_pdf(path: str) -> tuple[str, str, str]:
    """Texto de un PDF; si es escaneado, recurre a OCR."""
    pdf = pdf_reader.read_pdf_text(path)
    if pdf.char_count >= config.PDF_TEXT_MIN_CHARS:
        return pdf.text, pdf.layout_text, "pdf-text"

    # PDF sin (suficiente) capa de texto -> escaneado -> OCR.
    status = ocr.availability()
    if not status.installed:
        # Devolver lo poco que haya, con aviso vía texto.
        note = ("[Aviso] El PDF parece escaneado y Tesseract OCR no está "
                "disponible para leerlo. " + status.message)
        return (pdf.text + "\n" + note), pdf.layout_text, "pdf-text"
    images = raster.render_all_pdf_pages(path)
    text = ocr.ocr_images(images)
    return text, text, "ocr"
