"""scannerForm — extractor de datos de formularios FMS de Newmont Merian.

Escanea PDFs digitales (DocuSign) y fotos/escaneos de los formularios:

  • N-F-0016  FMS Tag Installation/Removal/Replacement Form
  • N-F-033   FMS Visitor Fuel Authorization Request

…extrae los datos del equipo y los presenta mapeados a los campos del alta de
equipos de AdaptIQ (pantalla «New Equipment Item» / mutation createEquipmentItem)
para copiar-pegar con un clic, sin transcribir a mano.
"""
from __future__ import annotations

__version__ = "0.1.0"
