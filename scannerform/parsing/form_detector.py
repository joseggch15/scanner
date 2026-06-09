"""Detección del tipo de formulario a partir del texto extraído.

Se basa en marcadores robustos del encabezado:

  • N-F-0016 → «TAG INSTALLATION» y/o el código «N-F-0016».
  • N-F-033  → «VISITOR FUEL AUTHORIZATION» y/o el código «N-F-033».

Funciona tanto con texto de PDF digital como con OCR (se ignoran mayúsculas y
espacios sobrantes).
"""
from __future__ import annotations

import re

from scannerform import config


def detect_form_type(text: str) -> str:
    """Devuelve config.FORM_TAG / FORM_VISITOR / FORM_UNKNOWN."""
    t = re.sub(r"\s+", " ", (text or "")).upper()

    # 1) Código del formulario (lo más fiable cuando el OCR lo capta).
    if "N-F-0016" in t or "N F 0016" in t:
        return config.FORM_TAG
    if "N-F-033" in t or "N F 033" in t:
        return config.FORM_VISITOR

    # 2) Título del formulario.
    if "TAG INSTALLATION" in t or "TAG INSTALLATION/REMOVAL" in t:
        return config.FORM_TAG
    if "VISITOR FUEL AUTHORIZATION" in t or "VISITOR FUEL" in t:
        return config.FORM_VISITOR

    return config.FORM_UNKNOWN
