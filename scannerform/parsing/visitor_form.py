"""Parser del formulario N-F-033 — FMS Visitor Fuel Authorization Request.

Estructura (una fila de datos por vehículo visitante):

  Equipment | Fleet/asset No. | Manufacturer/Model | Start date | End date |
  Registration/Plate | Dispensing product | Sponsor department | Cost Center/SAP |
  Enabled dispense limit (L) | Tank Capacity (L) | Business partner

En PDF digital la fila suele extraerse como una sola línea limpia, p. ej.:

  1 R-1467 FORD RANGER 02-07-2026 02-21-2026 02-42 KV DIESEL SUSTAINING CAPEX
    10001519-4C-2040.83000 60 AP&G CONSULTANCY

Se extraen los valores por anclas robustas (fechas, placa, producto, centro de
costo) en vez de por posición fija, porque los campos tienen un número variable
de palabras. Todo queda editable en la interfaz; el texto crudo es la red de
seguridad.
"""
from __future__ import annotations

import re

from scannerform import config
from scannerform.model import EnabledProduct, EquipmentRecord
from scannerform.parsing import normalize as N

# Patrones reutilizables.
# Fechas: aceptan uno o dos dígitos en día/mes (p. ej. 9-2-2026 o 02-07-2026).
_RE_DATE  = re.compile(r"\b\d{1,2}-\d{1,2}-\d{4}\b")
# Placas de Surinam: NN-NN XX (los dígitos pueden ser 1-2, las letras 2).
_RE_PLATE = re.compile(r"\b\d{1,2}-\d{1,2}[\s-]?[A-Z]{2}\b")
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_RE_PHONE = re.compile(r"\+?\d[\d\s/().-]{6,}\d")
_RE_PRODUCT = re.compile(
    r"\b(DIESEL|PETROL|GASOLINE|GASOIL|ULP|UNLEADED|BENZINE)\b", re.IGNORECASE)
# Centro de costo: bloque con dígitos y separadores (-, /, .) p. ej.
# 10001519-4C-2040.83000  /  14420-440000.
_RE_COSTCTR = re.compile(r"\b\d{4,}[-/][\w.\-]*\d\b")


def parse(text: str, layout_text: str = "") -> EquipmentRecord:
    rec = EquipmentRecord(form_type=config.FORM_VISITOR)
    blob = text or ""

    # -- contacto responsable ----------------------------------------------
    rec.email = N.first_match(_RE_EMAIL.pattern, blob, 0)
    rec.phone = N.first_match(r"Contact Number\(s\)\*?\s*([+\d][\d\s/().-]{6,}\d)", blob)
    if not rec.phone:
        m = _RE_PHONE.search(blob)
        rec.phone = N.clean(m.group(0)) if m else ""
    # Nombre del contacto: lo que precede a «Contract No.» en el bloque de usuario.
    rec.responsible_contact = N.first_match(
        r"(?:person\*?|BP:)\s*\n?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})\s+Contract No",
        blob)

    # -- fila de datos del vehículo ----------------------------------------
    row = _find_data_row(blob)
    if row:
        _parse_data_row(row, rec)
    else:
        rec.warnings.append(
            "No se localizó la fila de datos del vehículo; revise el texto crudo.")

    # -- operadores ---------------------------------------------------------
    rec.operators = _parse_operators(blob)

    rec.raw_text = blob
    return rec


def _find_data_row(text: str) -> str:
    """Devuelve la línea de datos (la que contiene las dos fechas o la placa)."""
    best = ""
    for line in text.splitlines():
        if len(_RE_DATE.findall(line)) >= 1 and _RE_PLATE.search(line):
            return line.strip()
        # Respaldo: línea con placa y un producto.
        if _RE_PLATE.search(line) and _RE_PRODUCT.search(line):
            best = line.strip()
    return best


def _parse_data_row(row: str, rec: EquipmentRecord) -> None:
    # Fechas.
    dates = _RE_DATE.findall(row)
    if dates:
        rec.contract_start = dates[0]
    if len(dates) > 1:
        rec.contract_end = dates[1]

    # Placa.
    mp = _RE_PLATE.search(row)
    rec.registration_plate = N.clean(mp.group(0)) if mp else ""

    # Producto de despacho (texto tal cual aparece en la fila).
    mpr = _RE_PRODUCT.search(row)
    product_txt = mpr.group(0) if mpr else ""

    # Centro de costo (el bloque alfanumérico más largo con separadores).
    costs = _RE_COSTCTR.findall(row)
    rec.cost_centre = max(costs, key=len) if costs else ""

    # Fleet / make / model: tokens antes de la primera fecha o de la placa.
    head_end = len(row)
    if dates:
        head_end = row.find(dates[0])
    elif mp:
        head_end = mp.start()
    head = row[:head_end].split()
    # Quitar un índice de fila inicial (1-2 dígitos puros) si hay más tokens.
    if len(head) >= 2 and re.fullmatch(r"\d{1,2}", head[0]):
        head = head[1:]
    # Fleet con prefijo + número separados por espacio (p. ej. «LV 004»).
    if len(head) >= 2 and re.fullmatch(r"[A-Z]{1,3}", head[0]) and re.fullmatch(r"\d+", head[1]):
        rec.fleet_asset_no = f"{head[0]} {head[1]}"
        head = head[2:]
    elif head:
        rec.fleet_asset_no = head[0]
        head = head[1:]
    if head:
        rec.make = head[0]
    if len(head) >= 2:
        rec.model = " ".join(head[1:])

    # Lo que sigue al producto contiene: departamento, centro de costo, límite,
    # capacidad y business partner.
    after = row[mpr.end():] if mpr else ""

    # Departamento: hasta el centro de costo o, si no hay, hasta el primer número.
    if rec.cost_centre and rec.cost_centre in after:
        dept, _, rest = after.partition(rec.cost_centre)
    else:
        m = re.search(r"\d", after)
        if m:
            dept, rest = after[:m.start()], after[m.start():]
        else:
            dept, rest = after, ""
    rec.sponsor_department = N.clean(dept)

    # Límite de despacho y capacidad de tanque: enteros tras el departamento.
    nums = re.findall(r"\b\d{1,4}\b", rest)
    if nums:
        rec.dispense_limit = nums[0]
    if len(nums) > 1:
        rec.tank_capacity = nums[1]
    elif nums:
        rec.warnings.append(
            "Solo se detectó un valor numérico de combustible; verifique cuál es "
            "el límite de despacho y cuál la capacidad del tanque.")

    # Business partner: texto tras el último número (quitando la unidad «L»).
    bp = re.sub(r".*\b\d{1,4}\b", "", rest).strip()
    bp = re.sub(r"^L\b\s*", "", bp).strip()
    rec.business_partner = N.clean(bp)

    # Producto habilitado.
    if product_txt:
        name = product_txt.title()
        rec.enabled_products = [EnabledProduct(
            code=name, label=name,
            dispense_limit=rec.dispense_limit, sfl=rec.tank_capacity)]


def _parse_operators(text: str) -> list:
    """Extrae filas de operadores: badge + nombre (best-effort)."""
    from scannerform.model import Operator
    ops = []
    # Badges típicos: FT0245, TP00736, etc. seguidos de nombre.
    for m in re.finditer(r"\b([A-Z]{2}\d{3,6})\s+([A-Z][a-zA-Z]+)(?:\s+([A-Z][a-zA-Z]+))?", text):
        ops.append(Operator(
            badge=m.group(1), first_name=m.group(2), last_name=m.group(3) or ""))
    return ops
