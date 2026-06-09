"""Helpers de normalización de texto y valores compartidos por los parsers."""
from __future__ import annotations

import re

from scannerform import config


def clean(s: str | None) -> str:
    """Colapsa espacios y recorta. Devuelve '' para None."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def first_match(pattern: str, text: str, group: int = 1, flags: int = re.IGNORECASE) -> str:
    """Devuelve el grupo `group` del primer match, o '' si no hay."""
    m = re.search(pattern, text, flags)
    return clean(m.group(group)) if m else ""


def parse_number(text: str) -> str:
    """Extrae el primer número de un texto (quita 'L', '%', comas). '' si no hay.

    Se devuelve como string para preservar el formato original al copiar y no
    introducir ruido de coma flotante (igual que hace la API de AdaptIQ).
    """
    if not text:
        return ""
    m = re.search(r"-?[\d][\d,]*\.?\d*", str(text))
    if not m:
        return ""
    return m.group(0).replace(",", "")


def normalize_status(request_type: str) -> str:
    """Tipo de solicitud del formulario -> código de estado de AdaptIQ."""
    return config.REQUEST_TO_STATUS.get(request_type, config.STATUS_INS)


def guess_interval_type(equipment_type: str, make: str = "", model: str = "") -> str:
    """Sugiere hrs/kms según el tipo de equipo (horómetro vs. odómetro)."""
    blob = " ".join((equipment_type, make, model)).lower()
    for kw in config.INTERVAL_HINTS_KMS:
        if kw in blob:
            return config.INTERVAL_KMS
    for kw in config.INTERVAL_HINTS_HRS:
        if kw in blob:
            return config.INTERVAL_HRS
    return ""   # desconocido: que el operador elija


def split_equipment_and_fleet(equipment_type: str, fleet: str) -> tuple[str, str]:
    """Limpia el par (tipo, fleet) de artefactos comunes del OCR/extracción."""
    return clean(equipment_type), clean(fleet)
