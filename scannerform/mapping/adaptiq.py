"""Construye la lista ordenada de campos de AdaptIQ a partir del EquipmentRecord.

La interfaz usa esta lista para renderizar el panel de copiar-pegar en el MISMO
orden que la pantalla «New Equipment Item» de AdaptIQ, de modo que el operador
vaya campo por campo de arriba hacia abajo. Cada campo trae su valor sugerido
(editable), si es obligatorio y una nota de ayuda.
"""
from __future__ import annotations

from dataclasses import dataclass

from scannerform import config
from scannerform.model import EquipmentRecord
from scannerform.parsing import normalize as N


@dataclass
class AdaptIQField:
    key: str
    label: str
    value: str
    required: bool = False
    note: str = ""


def build_fields(rec: EquipmentRecord) -> list[AdaptIQField]:
    """Campos de la pantalla principal de alta de equipos (en orden)."""
    values = _computed_values(rec)
    out = []
    for key, label, required, note in config.ADAPTIQ_FIELDS:
        out.append(AdaptIQField(
            key=key, label=label, value=values.get(key, ""),
            required=required, note=note))
    return out


def build_extra_fields(rec: EquipmentRecord) -> list[AdaptIQField]:
    """Campos adicionales del formulario (Cost Centre, Department, productos…)."""
    values = _computed_values(rec)
    out = []
    for key, label, note in config.ADAPTIQ_EXTRA_FIELDS:
        out.append(AdaptIQField(
            key=key, label=label, value=values.get(key, ""), note=note))
    return out


def _computed_values(rec: EquipmentRecord) -> dict[str, str]:
    """Traduce el record a los valores que espera AdaptIQ."""
    status_code = N.normalize_status(rec.request_type)
    interval = N.guess_interval_type(rec.equipment_type, rec.make, rec.model)
    return {
        # Pantalla principal
        "equipment_id":          rec.fleet_asset_no,
        "description":           rec.description_guess(),
        "status":                config.STATUS_LABELS.get(status_code, ""),
        "volume_unit":           config.VOLUME_UNIT_DEFAULT,
        "group":                 "",
        "category":              "",
        "smu_value_source":      config.SMU_DEFAULT,
        "service_interval_type": interval,
        "service_interval":      "",
        "field_id":              "",
        "field_description":     "",
        "zone":                  "",
        "gps_coordinates":       "",
        "registration_plate":    rec.registration_plate,
        "make":                  rec.make,
        "model":                 rec.model,
        "fill_point_location":   "",
        # Extras
        "cost_centre":           rec.cost_centre,
        "department":            rec.sponsor_department,
        "dispense_limit":        rec.dispense_limit,
        "tank_capacity":         rec.tank_capacity,
        "enabled_products":      rec.enabled_products_text(),
        "business_partner":      rec.business_partner,
        "contract_no":           rec.contract_no,
        "contract_start":        rec.contract_start,
        "contract_end":          rec.contract_end,
    }


def to_tsv(fields: list[AdaptIQField]) -> str:
    """Vuelca etiqueta<TAB>valor por línea (para «copiar todo»)."""
    return "\n".join(f"{f.label}\t{f.value}" for f in fields if f.value)
