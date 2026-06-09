# -*- coding: utf-8 -*-
"""Pruebas de scannerForm (detección, parsers, normalización y mapeo).

Usan texto sintético que reproduce la salida real de pdfplumber para no depender
de archivos externos. Ejecutar con pytest o directamente:

    pytest tests/
    python tests/test_scannerform.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scannerform import config
from scannerform.mapping import adaptiq
from scannerform.parsing import form_detector, normalize as N, tag_form, visitor_form
from scannerform.scanner import _strip_noise

# Texto sintético equivalente a la extracción real de un N-F-033.
VISITOR_TEXT = """Docusign Envelope ID: 5E90DE10-9DB1-4644-89E9-E05FC66B5AE8
Code/Ver. N-F-033 Ver.3
FMS VISITOR FUEL AUTHORIZATION REQUEST
1 R-1467 FORD RANGER 02-07-2026 02-21-2026 02-42 KV DIESEL SUSTAINING CAPEX 10001519-4C-2040.83000 60 AP&G CONSULTANCY
2. OPERATORS
1 FT0245 Elbregt Mahes
"""

# Texto sintético equivalente a un N-F-0016 (formulario de tag).
TAG_TEXT = """Docusign Envelope ID: 82C31579-8389-4FA7-B6C8-463D95A93883
FMS TAG INSTALLATION/REMOVAL/REPLACEMENT FORM Code/Ver. N-F-0016 Ver.4
New X
Truck S-04 DAF 08-36 HV TSF 2
Diesel X
300 L
"""


# ---------------------------------------------------------------------------
# Detección de formulario
# ---------------------------------------------------------------------------

def test_detect_visitor_by_code():
    assert form_detector.detect_form_type("algo Code/Ver. N-F-033 Ver.3") == config.FORM_VISITOR


def test_detect_tag_by_title():
    assert form_detector.detect_form_type(
        "FMS TAG INSTALLATION/REMOVAL/REPLACEMENT FORM") == config.FORM_TAG


def test_detect_unknown():
    assert form_detector.detect_form_type("documento cualquiera") == config.FORM_UNKNOWN


# ---------------------------------------------------------------------------
# Limpieza de ruido
# ---------------------------------------------------------------------------

def test_strip_docusign_noise():
    out = _strip_noise(VISITOR_TEXT)
    assert "Docusign Envelope ID" not in out
    assert "R-1467" in out


# ---------------------------------------------------------------------------
# Parser de visitante (N-F-033)
# ---------------------------------------------------------------------------

def test_visitor_parse_core_fields():
    rec = visitor_form.parse(_strip_noise(VISITOR_TEXT))
    assert rec.fleet_asset_no == "R-1467"
    assert rec.make == "FORD"
    assert rec.model == "RANGER"
    assert rec.registration_plate == "02-42 KV"
    assert rec.cost_centre == "10001519-4C-2040.83000"
    assert rec.dispense_limit == "60"
    assert rec.sponsor_department == "SUSTAINING CAPEX"
    assert rec.business_partner == "AP&G CONSULTANCY"
    assert rec.contract_start == "02-07-2026"
    assert rec.contract_end == "02-21-2026"
    assert rec.enabled_products and rec.enabled_products[0].code == "Diesel"


def test_visitor_parse_operators():
    rec = visitor_form.parse(_strip_noise(VISITOR_TEXT))
    assert any(op.badge == "FT0245" for op in rec.operators)


# ---------------------------------------------------------------------------
# Parser de tag (N-F-0016)
# ---------------------------------------------------------------------------

def test_tag_parse_core_fields():
    rec = tag_form.parse(_strip_noise(TAG_TEXT))
    assert rec.request_type == config.REQUEST_NEW
    assert rec.equipment_type == "Truck"
    assert rec.fleet_asset_no == "S-04"
    assert rec.make == "DAF"
    assert rec.registration_plate == "08-36 HV"
    assert rec.sponsor_department == "TSF"
    assert rec.dispense_limit == "300"
    assert rec.enabled_products and rec.enabled_products[0].code == "Diesel"


def test_tag_cost_centre_not_docusign():
    """El envelope ID de DocuSign no debe colarse como centro de costo."""
    rec = tag_form.parse(_strip_noise(TAG_TEXT))
    assert "463D95A93883" not in rec.cost_centre


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def test_normalize_status():
    assert N.normalize_status(config.REQUEST_NEW) == config.STATUS_INS
    assert N.normalize_status(config.REQUEST_REMOVAL) == config.STATUS_OUTS


def test_guess_interval_type():
    assert N.guess_interval_type("Excavator", "Hitachi", "ZX470") == config.INTERVAL_HRS
    assert N.guess_interval_type("Truck", "DAF", "") == config.INTERVAL_KMS
    assert N.guess_interval_type("", "Volvo", "EC480") == ""   # ambiguo: sin sugerencia


def test_parse_number():
    assert N.parse_number("1,100 L") == "1100"
    assert N.parse_number("300 L") == "300"
    assert N.parse_number("sin numero") == ""


# ---------------------------------------------------------------------------
# Mapeo a AdaptIQ
# ---------------------------------------------------------------------------

def test_adaptiq_field_count_and_order():
    rec = visitor_form.parse(_strip_noise(VISITOR_TEXT))
    fields = adaptiq.build_fields(rec)
    assert len(fields) == len(config.ADAPTIQ_FIELDS)
    assert fields[0].key == "equipment_id"
    assert fields[0].value == "R-1467"
    # El primer campo es obligatorio.
    assert fields[0].required is True


def test_adaptiq_status_label():
    rec = tag_form.parse(_strip_noise(TAG_TEXT))
    fields = {f.key: f.value for f in adaptiq.build_fields(rec)}
    assert fields["status"] == "In Service"
    assert fields["service_interval_type"] == "kms"
    assert fields["volume_unit"] == config.VOLUME_UNIT_DEFAULT


def test_adaptiq_tsv_skips_empty():
    rec = visitor_form.parse(_strip_noise(VISITOR_TEXT))
    tsv = adaptiq.to_tsv(adaptiq.build_fields(rec))
    assert "Equipment ID\tR-1467" in tsv
    # Group está vacío -> no aparece.
    assert "Group\t" not in tsv


# ---------------------------------------------------------------------------
# Runner directo
# ---------------------------------------------------------------------------

def _run() -> int:
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} pruebas OK")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
