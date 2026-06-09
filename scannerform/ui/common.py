"""Utilidades y widgets compartidos de la interfaz."""
from __future__ import annotations

import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
)

# Paleta (alineada con el estilo de los otros proyectos Newmont).
BLUE   = "#1F4E78"
GREEN  = "#2ca02c"
RED    = "#d62728"
AMBER  = "#d9822b"
GREY   = "#6b6b6b"
COPIED = "#e8f5e9"   # fondo de fila ya copiada


def pil_to_pixmap(img) -> QPixmap:
    """Convierte una imagen PIL a QPixmap sin dependencias extra (vía PNG)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pix = QPixmap()
    pix.loadFromData(buf.getvalue(), "PNG")
    return pix


def chip(text: str, color: str = BLUE) -> QLabel:
    """Etiqueta tipo «chip» con color, para estados (formulario, OCR…)."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"QLabel {{ background:{color}; color:white; border-radius:9px; "
        f"padding:2px 10px; font-weight:bold; }}")
    return lbl


def primary_button(text: str, color: str = BLUE) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton{{background:{color};color:white;font-weight:bold;"
        f"padding:6px 16px;border-radius:4px;}}"
        f"QPushButton:hover{{background:#163a5a;}}"
        f"QPushButton:disabled{{background:#b8c4d0;}}")
    return b


class FieldRow(QWidget):
    """Una fila editable del panel de copiar-pegar: etiqueta + valor + «Copiar».

    Emite `copyRequested(key, value)` al pulsar «Copiar» o Enter. Marca la fila
    como copiada (fondo verde) para que el operador siga su progreso mientras
    pega en AdaptIQ.
    """
    copyRequested = Signal(str, str)

    def __init__(self, key: str, label: str, value: str = "",
                 required: bool = False, note: str = ""):
        super().__init__()
        self.key = key
        self._copied = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        text = label + (" *" if required else "")
        self.label = QLabel(text)
        self.label.setMinimumWidth(180)
        self.label.setMaximumWidth(180)
        self.label.setWordWrap(True)
        if required:
            self.label.setStyleSheet("font-weight:bold;")
        if note:
            self.label.setToolTip(note)
        lay.addWidget(self.label)

        self.edit = QLineEdit(value)
        self.edit.setClearButtonEnabled(True)
        self.edit.returnPressed.connect(self._emit_copy)
        if note:
            self.edit.setToolTip(note)
        lay.addWidget(self.edit, stretch=1)

        self.btn = QPushButton("Copiar")
        self.btn.setFixedWidth(78)
        self.btn.clicked.connect(self._emit_copy)
        lay.addWidget(self.btn)

    def value(self) -> str:
        return self.edit.text()

    def set_value(self, value: str) -> None:
        self.edit.setText(value)
        self.set_copied(False)

    def _emit_copy(self) -> None:
        self.copyRequested.emit(self.key, self.edit.text())
        self.set_copied(True)

    def set_copied(self, copied: bool) -> None:
        self._copied = copied
        if copied:
            self.setStyleSheet(f"FieldRow {{ background:{COPIED}; border-radius:4px; }}")
            self.btn.setText("Copiado ✓")
        else:
            self.setStyleSheet("")
            self.btn.setText("Copiar")
