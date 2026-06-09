"""Parser del formulario N-F-0016 — FMS Tag Installation/Removal/Replacement.

Es el formulario de alta/baja/reemplazo de tags sobre equipos de flota. Datos
relevantes para crear el equipo en AdaptIQ:

  • Tipo de solicitud (New / Removal / Replacement) → estado sugerido.
  • Equipment + Fleet/asset No. → Equipment ID / Description.
  • Manufacturer / machine Model → Make / Model.
  • Vehicle Registration/Plate No. → Registration number.
  • Sponsor department → Department.
  • Cost Center/SAP, Enabled dispense limit (L), Tank Capacity (L).
  • Enabled products (Diesel y aceites marcados con «X»).

El texto de pdfplumber aplana la tabla, así que se trabaja por anclas (placa,
etiquetas, marcas «X») y no por posición. Los campos quedan editables.
"""
from __future__ import annotations

import re

from scannerform import config
from scannerform.model import EnabledProduct, Operator, EquipmentRecord
from scannerform.parsing import normalize as N

_RE_PLATE = re.compile(r"\b\d{1,2}-\d{1,2}[\s-]?[A-Z]{2}\b")
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")

# Tipos de equipo conocidos para anclar la fila de datos.
_EQUIP_TYPES = (
    "Excavator", "Dozer", "Truck", "Loader", "Grader", "Drill", "Generator",
    "Pump", "Compressor", "Shovel", "Backhoe", "Bucket Truck", "Crane",
    "Forklift", "Roller", "Bus", "Vehicle",
)
_RE_EQUIP = re.compile(r"\b(" + "|".join(_EQUIP_TYPES) + r")\b", re.IGNORECASE)


def parse(text: str, layout_text: str = "") -> EquipmentRecord:
    rec = EquipmentRecord(form_type=config.FORM_TAG)
    blob = text or ""

    # -- contacto -----------------------------------------------------------
    rec.email = N.first_match(_RE_EMAIL.pattern, blob, 0)
    rec.responsible_contact = N.first_match(
        r"person\*?\s*\n?\s*([A-Z][a-zA-Z.]+(?:\s+[A-Z][a-zA-Z.]+){0,2})", blob)
    rec.phone = N.first_match(
        r"Contact Number\(s\)\*?\s*([+\d][\d\s/().-]{6,}\d)", blob)

    # -- tipo de solicitud (cuál tiene la «X») -----------------------------
    rec.request_type = _detect_request_type(blob)

    # -- contrato -----------------------------------------------------------
    rec.contract_no = N.first_match(r"Contract No\.?\s*[:.]?\s*([A-Z]{1,3}\d{4,})", blob)
    rec.contract_start, rec.contract_end = _contract_dates(blob)

    # -- fila de datos del equipo ------------------------------------------
    row = _find_equipment_row(blob)
    if row:
        _parse_equipment_row(row, rec)
    else:
        rec.warnings.append(
            "No se localizó la fila del equipo; revise el texto crudo.")

    # -- centro de costo / límites / capacidad -----------------------------
    rec.cost_centre = _cost_centre(blob)
    rec.dispense_limit = _dispense_limit(blob)
    rec.tank_capacity = _tank_capacity(blob)

    # -- productos habilitados ---------------------------------------------
    rec.enabled_products = _enabled_products(blob, rec)

    # -- operadores ---------------------------------------------------------
    rec.operators = _parse_operators(blob)

    rec.raw_text = blob
    return rec


def _detect_request_type(text: str) -> str:
    """Determina cuál de New/Removal/Replacement está marcado con «X»."""
    for label, value in (("New", config.REQUEST_NEW),
                          ("Removal", config.REQUEST_REMOVAL),
                          ("Replacement", config.REQUEST_REPLACEMENT)):
        # «New X», «X New» o el label con una X muy cerca.
        if re.search(rf"\b{label}\b\s*X\b", text, re.IGNORECASE) or \
           re.search(rf"\bX\s*{label}\b", text, re.IGNORECASE):
            return value
    # Respaldo: si solo aparece una «X» y «New» está presente, asumir New.
    if re.search(r"\bNew\b", text) and text.count("X") == 1:
        return config.REQUEST_NEW
    return config.REQUEST_NEW   # por defecto, alta nueva


def _contract_dates(text: str) -> tuple[str, str]:
    """Fechas de inicio/fin de contrato (formatos '1 Nov 2023' o '01-11-2023')."""
    months = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    pat = rf"\d{{1,2}}\s*{months}\.?\s*\d{{4}}|\d{{2}}-\d{{2}}-\d{{4}}"
    found = re.findall(pat, text, re.IGNORECASE)
    start = found[0] if found else ""
    end = found[1] if len(found) > 1 else ""
    return N.clean(start), N.clean(end)


def _find_equipment_row(text: str) -> str:
    """Línea que contiene el tipo de equipo y/o la placa (datos del equipo)."""
    candidate = ""
    for line in text.splitlines():
        if _RE_PLATE.search(line) and _RE_EQUIP.search(line):
            return line.strip()
        if _RE_EQUIP.search(line) and not candidate:
            candidate = line.strip()
    return candidate


def _parse_equipment_row(row: str, rec: EquipmentRecord) -> None:
    me = _RE_EQUIP.search(row)
    if me:
        rec.equipment_type = me.group(1).title()

    mp = _RE_PLATE.search(row)
    rec.registration_plate = N.clean(mp.group(0)) if mp else ""

    # Tokens entre el tipo de equipo y la placa: fleet + make + model.
    start = me.end() if me else 0
    end = mp.start() if mp else len(row)
    middle = row[start:end].split()
    if middle:
        rec.fleet_asset_no = middle[0]
    if len(middle) >= 2:
        rec.make = middle[1]
    if len(middle) >= 3:
        rec.model = " ".join(middle[2:])

    # Departamento patrocinador: lo que sigue a la placa (p. ej. «TSF»).
    if mp:
        after = row[mp.end():].split()
        # Descartar números sueltos (índices de fila).
        dept = [t for t in after if not re.fullmatch(r"\d+", t)]
        if dept:
            rec.sponsor_department = dept[0]


def _cost_centre(text: str) -> str:
    """Centro de costo / SAP. En estos formularios suelen ser dos números
    (p. ej. 14385 y 630100) o un bloque tipo 10001519-4C-2040.83000."""
    m = re.search(r"\b\d{4,}[-/][\w.\-]*\d\b", text)
    if m:
        return N.clean(m.group(0))
    # Dos números de centro de costo cercanos (handwritten: 14385 / 630100).
    nums = re.findall(r"\b\d{5,6}\b", text)
    return " / ".join(nums[:2]) if nums else ""


def _dispense_limit(text: str) -> str:
    """Límite de despacho habilitado: el número con sufijo «L» (p. ej. «300 L»)."""
    m = re.search(r"\b(\d{2,4})\s*L\b", text)
    return N.parse_number(m.group(1)) if m else ""


def _tank_capacity(text: str) -> str:
    """Capacidad del tanque: número junto a la etiqueta «Tank Capacity».

    No se usa el respaldo de «NNN L» porque ese valor es el límite de despacho;
    si el formulario no trae la capacidad cerca de su etiqueta se deja vacío
    para que el operador la complete (es frecuente en los PDFs digitales)."""
    m = re.search(r"Tank\s*Capacity[^\d]{0,40}?(\d[\d,]*)", text, re.IGNORECASE)
    return N.parse_number(m.group(1)) if m else ""


def _enabled_products(text: str, rec: EquipmentRecord) -> list:
    """Productos marcados con «X». Diesel es el principal; detecta también los
    aceites/refrigerante si el formulario los marca."""
    products = []
    for code in config.PRODUCT_ORDER:
        if code == "Other":
            continue
        # Buscar el código (o «Diesel») con una «X» en la misma zona del texto.
        pat = re.escape(code) + r"[^\n]{0,10}X|X[^\n]{0,10}" + re.escape(code)
        if re.search(pat, text, re.IGNORECASE):
            products.append(EnabledProduct(code=code, label=config.PRODUCT_CODES[code]))
    # Si nada se marcó pero el formulario es de combustible, asumir Diesel.
    if not products and re.search(r"\bDiesel\b", text, re.IGNORECASE):
        products.append(EnabledProduct(code="Diesel", label="Diesel"))
    # Adjuntar límite/capacidad al Diesel.
    for p in products:
        if p.code == "Diesel":
            p.dispense_limit = rec.dispense_limit
            p.sfl = rec.tank_capacity
    return products


def _parse_operators(text: str) -> list:
    ops = []
    for m in re.finditer(r"\b([A-Z]{2}\d{3,6})\s+([A-Z][a-zA-Z]+)(?:\s+([A-Z][a-zA-Z]+))?", text):
        ops.append(Operator(badge=m.group(1), first_name=m.group(2),
                            last_name=m.group(3) or ""))
    return ops
