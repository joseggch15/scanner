"""Constantes de dominio para scannerForm.

Reúne en un solo lugar:

  • Identificación de los dos formularios de origen (códigos N-F-0016 / N-F-033).
  • El catálogo de productos Newmont que aparece en el formulario de tags y su
    traducción a un nombre legible.
  • Los enums de AdaptIQ (estado, tipo de intervalo de servicio, fuente de SMU).
  • La definición ordenada de los campos del alta de equipos de AdaptIQ, tal como
    aparecen en la pantalla «New Equipment Item», para construir el panel de
    copiar-pegar.
  • Rutas por defecto y configuración del OCR.

Referencia del destino: «AdaptIQ Customer Facing GraphQL APIs (July 2023)»,
mutation `createEquipmentItem` y tipo Equipment Item.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Formularios de origen
# ---------------------------------------------------------------------------
FORM_TAG     = "N-F-0016"   # FMS Tag Installation/Removal/Replacement Form
FORM_VISITOR = "N-F-033"    # FMS Visitor Fuel Authorization Request
FORM_UNKNOWN = "DESCONOCIDO"

FORM_TITLES = {
    FORM_TAG:     "Tag Installation / Removal / Replacement (N-F-0016)",
    FORM_VISITOR: "Visitor Fuel Authorization Request (N-F-033)",
    FORM_UNKNOWN: "Formulario no reconocido",
}

# Tipo de solicitud (solo N-F-0016).
REQUEST_NEW         = "New"
REQUEST_REMOVAL     = "Removal"
REQUEST_REPLACEMENT = "Replacement"

# ---------------------------------------------------------------------------
# Enums de AdaptIQ (valores que acepta la mutation / espera la pantalla)
# ---------------------------------------------------------------------------
# equipmentStatusCode
STATUS_INS    = "INS"      # In Service
STATUS_OUTS   = "OUTS"     # Out of Service
STATUS_DECOMM = "DECOMM"   # Decommissioned

STATUS_LABELS = {
    STATUS_INS:    "In Service",
    STATUS_OUTS:   "Out of Service",
    STATUS_DECOMM: "Decommissioned",
}

# Tipo de solicitud del formulario -> estado sugerido en AdaptIQ.
REQUEST_TO_STATUS = {
    REQUEST_NEW:         STATUS_INS,
    REQUEST_REPLACEMENT: STATUS_INS,
    REQUEST_REMOVAL:     STATUS_OUTS,
}

# serviceIntervalType (la pantalla muestra hrs / kms / kWh).
INTERVAL_HRS = "hrs"
INTERVAL_KMS = "kms"
INTERVAL_KWH = "kWh"

# smuValueSource
SMU_NONE     = "none"
SMU_OTHER    = "other"
SMU_ADAPTSMU = "adaptsmu"
SMU_DEFAULT  = SMU_OTHER

VOLUME_UNIT_DEFAULT = "Litres"

# Heurística tipo de equipo -> tipo de intervalo de servicio.
# Equipos con horómetro (hrs) vs. vehículos con odómetro (kms). Es solo una
# sugerencia: el campo queda editable porque el formulario no siempre lo indica.
INTERVAL_HINTS_HRS = (
    "excavator", "dozer", "loader", "drill", "generator", "genset", "pump",
    "compressor", "grader", "shovel", "crusher", "dragline", "backhoe",
)
INTERVAL_HINTS_KMS = (
    "truck", "ranger", "pickup", "pick-up", "ute", "van", "bus",
    "vehicle", "hilux", "land cruiser", "landcruiser", "bucket truck",
)

# ---------------------------------------------------------------------------
# Catálogo de productos del formulario N-F-0016 (columna «Enabled products»)
# ---------------------------------------------------------------------------
# El formulario lista códigos Newmont; aquí los traducimos a un nombre legible.
# El producto principal (y casi siempre el único habilitado) es Diesel.
PRODUCT_CODES = {
    "Diesel":    "Diesel",
    "R4X15W40":  "Aceite motor 15W40",
    "S2A80W90":  "Aceite transmisión 80W90",
    "S4CX10W":   "Hidráulico 10W",
    "S4CX30":    "SAE 30",
    "S5CFDM60":  "Aceite SAE 60",
    "S3M46":     "Hidráulico 46",
    "ELC Coolant": "Refrigerante ELC",
    "Other":     "Otro",
}
# Orden en que aparecen las filas de producto en el formulario.
PRODUCT_ORDER = list(PRODUCT_CODES.keys())

# ---------------------------------------------------------------------------
# Campos del alta de equipos de AdaptIQ (pantalla «New Equipment Item»)
# ---------------------------------------------------------------------------
# Cada entrada: (key interno, etiqueta visible, requerido?, nota/ayuda).
# El orden replica el de la pantalla de AdaptIQ para que copiar-pegar sea de
# arriba hacia abajo, campo por campo.
#
# `key` es el atributo de EquipmentRecord (o derivado) que alimenta el valor.
ADAPTIQ_FIELDS = [
    ("equipment_id",      "Equipment ID",        True,  "Fleet / asset No. del formulario. Único por sitio."),
    ("description",       "Description",         True,  "Descripción del equipo (tipo + fleet)."),
    ("status",            "Status",              True,  "Sugerido por el tipo de solicitud (New → In Service)."),
    ("volume_unit",       "Volume Unit",         False, "Litres por defecto."),
    ("group",             "Group",               True,  "Grupo de equipo en AdaptIQ — verificar/seleccionar."),
    ("category",          "Category",            True,  "Categoría de equipo en AdaptIQ — verificar/seleccionar."),
    ("smu_value_source",  "SMU value source",    False, "none / other / adaptsmu (other por defecto)."),
    ("service_interval_type", "Service interval type", True, "hrs / kms / kWh — sugerido por el tipo de equipo."),
    ("service_interval",  "Service interval",    False, "Horas o km hasta el siguiente servicio (si aplica)."),
    ("field_id",          "Field ID",            False, "ID de campo (si el sitio lo usa)."),
    ("field_description", "Field description",   False, ""),
    ("zone",              "Zone",                False, ""),
    ("gps_coordinates",   "GPS Coordinates",     False, ""),
    ("registration_plate","Registration number", False, "Matrícula / placa del formulario."),
    ("make",              "Make",                False, "Fabricante (máx. 30 car.)."),
    ("model",             "Model",               False, "Modelo (máx. 30 car.)."),
    ("fill_point_location","Fill point location", False, ""),
]

# Campos adicionales útiles del formulario que no están en la primera pantalla
# pero el operador suele necesitar (Cost Centre, Department, límites, productos).
ADAPTIQ_EXTRA_FIELDS = [
    ("cost_centre",     "Cost Centre / SAP",        "Centro de costo / SAP del formulario."),
    ("department",      "Department (Sponsor)",     "Departamento patrocinador."),
    ("dispense_limit",  "Enabled dispense limit (L)", "Límite de despacho habilitado."),
    ("tank_capacity",   "Tank Capacity (L)",        "Capacidad del tanque del equipo (SFL)."),
    ("enabled_products","Enabled products",         "Productos habilitados detectados."),
    ("business_partner","Business partner",         "Solo N-F-033 (visitante)."),
    ("contract_no",     "Contract No.",             ""),
    ("contract_start",  "Contract start date",      ""),
    ("contract_end",    "Contract end date",        ""),
]

# ---------------------------------------------------------------------------
# Extensiones de archivo soportadas
# ---------------------------------------------------------------------------
PDF_EXTS   = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SUPPORTED_EXTS = PDF_EXTS | IMAGE_EXTS

# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
# Si un PDF devuelve menos de este número de caracteres de texto «real», se
# considera escaneado y se intenta OCR sobre la página rasterizada.
PDF_TEXT_MIN_CHARS = 80
# Resolución (DPI) al rasterizar páginas de PDF para vista previa / OCR.
RASTER_DPI = 200
OCR_DPI    = 300
# Idiomas de Tesseract (los formularios están en inglés).
OCR_LANG = "eng"

# ---------------------------------------------------------------------------
# Rutas por defecto (punto de partida del diálogo de archivo)
# ---------------------------------------------------------------------------
DEFAULT_OPEN_FOLDER = (
    r"C:\Users\USER\OneDrive - PLG-Industrial & Mining Solutions"
    r"\Newmont\Newmont Merian FMS Installation"
    r"\2. Data Analysis and Reporting NWT\2. Tag Installations"
)
