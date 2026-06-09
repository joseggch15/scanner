"""Modelos de datos de scannerForm.

`EquipmentRecord` es el resultado canónico de escanear un formulario: reúne los
datos del equipo independientemente del formulario de origen (N-F-0016 o N-F-033)
y de la fuente (texto de PDF u OCR). Desde aquí, `mapping.adaptiq` construye la
lista de campos de AdaptIQ lista para copiar-pegar.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnabledProduct:
    """Un producto habilitado en el formulario (Diesel, aceites, refrigerante…)."""
    code: str                       # código Newmont (p. ej. 'Diesel', 'R4X15W40')
    label: str = ""                 # nombre legible
    dispense_limit: str = ""        # límite de despacho (L), si aparece
    sfl: str = ""                   # safe fill level / capacidad de tanque (L)


@dataclass
class Operator:
    """Una fila de la tabla de operadores del formulario."""
    badge: str = ""
    first_name: str = ""
    last_name: str = ""
    dni: str = ""
    badge_code: str = ""


@dataclass
class EquipmentRecord:
    """Datos extraídos de un formulario FMS, en esquema canónico.

    Los campos vacíos ('') indican «no detectado»; el operador los completa en la
    interfaz antes de copiar. Nada aquí asume un formato de AdaptIQ todavía: la
    traducción a estado/intervalo/etc. ocurre en `mapping.adaptiq`.
    """
    # Procedencia
    form_type: str = ""             # config.FORM_TAG / FORM_VISITOR / FORM_UNKNOWN
    source_file: str = ""
    source_kind: str = ""           # 'pdf-text' | 'ocr' | 'image-ocr'
    request_type: str = ""          # New / Removal / Replacement (solo N-F-0016)

    # Identificación del equipo
    equipment_type: str = ""        # Excavator, Dozer, Truck, Bucket Truck…
    fleet_asset_no: str = ""        # 3441 / S-04 / R-1467
    make: str = ""                  # Hitachi / DAF / FORD / John Deere / Liebherr
    model: str = ""                 # ZX 470 / RANGER / 1050K / PR776
    registration_plate: str = ""    # 08-36 HV / 02-42 KV

    # Patrocinio / costos
    sponsor_department: str = ""    # Mine Ops (feeder) / TSF / PRM
    sponsor_subdepartment: str = ""
    cost_centre: str = ""           # 14385 / 630100 / 10001519-4C-2040.83000

    # Combustible / tanque
    dispense_limit: str = ""        # L
    tank_capacity: str = ""         # L
    enabled_products: list[EnabledProduct] = field(default_factory=list)

    # Contrato / contacto
    contract_no: str = ""
    contract_start: str = ""
    contract_end: str = ""
    responsible_contact: str = ""
    email: str = ""
    phone: str = ""

    # Solo visitante (N-F-033)
    business_partner: str = ""

    # Tablas
    operators: list[Operator] = field(default_factory=list)

    # Diagnóstico
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)

    # -- derivados ----------------------------------------------------------

    def description_guess(self) -> str:
        """Descripción sugerida: «Tipo Fleet» (p. ej. «Excavator 3441»)."""
        parts = [p for p in (self.equipment_type, self.fleet_asset_no) if p]
        return " ".join(parts).strip()

    def enabled_products_text(self) -> str:
        """Resumen legible de los productos habilitados para mostrar/copiar."""
        if not self.enabled_products:
            return ""
        chunks = []
        for p in self.enabled_products:
            name = p.label or p.code
            extra = []
            if p.dispense_limit:
                extra.append(f"límite {p.dispense_limit} L")
            if p.sfl:
                extra.append(f"tanque {p.sfl} L")
            chunks.append(name + (f" ({', '.join(extra)})" if extra else ""))
        return " | ".join(chunks)
