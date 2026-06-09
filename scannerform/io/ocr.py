"""OCR con Tesseract (pytesseract).

El OCR es una capacidad OPCIONAL: requiere el binario de Tesseract instalado en
el sistema además del paquete `pytesseract`. `availability()` informa el estado
para que la interfaz muestre un mensaje claro y, si falta, el flujo de PDFs
digitales siga funcionando sin problemas.

Para letra manuscrita Tesseract es poco preciso; el texto resultante alimenta a
los parsers igual que el de un PDF, pero se marca como baja confianza y el
operador revisa contra la vista previa.
"""
from __future__ import annotations

from dataclasses import dataclass

from scannerform import config

try:
    import pytesseract
except ImportError:
    pytesseract = None


@dataclass
class OcrStatus:
    installed: bool          # pytesseract + binario de Tesseract disponibles
    version: str = ""
    message: str = ""


def availability() -> OcrStatus:
    """Comprueba si el OCR está disponible (paquete + binario)."""
    if pytesseract is None:
        return OcrStatus(False, message=(
            "Falta el paquete 'pytesseract'. Instale con:  pip install pytesseract"))
    try:
        version = str(pytesseract.get_tesseract_version())
    except Exception:
        return OcrStatus(False, message=(
            "Tesseract OCR no está instalado o no está en el PATH.\n"
            "Descárguelo de https://github.com/UB-Mannheim/tesseract/wiki "
            "e instálelo para habilitar el escaneo de imágenes."))
    return OcrStatus(True, version=version,
                     message=f"Tesseract {version} disponible.")


def is_available() -> bool:
    return availability().installed


def ocr_image(image, lang: str = config.OCR_LANG) -> str:
    """Ejecuta OCR sobre una imagen PIL y devuelve el texto plano."""
    if pytesseract is None:
        raise ImportError("Se requiere 'pytesseract' para el OCR.")
    return pytesseract.image_to_string(image, lang=lang)


def ocr_images(images, lang: str = config.OCR_LANG) -> str:
    """OCR sobre varias imágenes PIL (multipágina); concatena el texto."""
    return "\n".join(ocr_image(img, lang=lang) for img in images)
