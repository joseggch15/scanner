"""Ventana principal de scannerForm.

Flujo de trabajo:

    1.  El operador abre un PDF o una imagen del formulario (o pega una foto del
        portapapeles).
    2.  scannerForm detecta el formulario (N-F-0016 / N-F-033), extrae el texto
        (pdfplumber u OCR) y lo mapea a los campos de AdaptIQ.
    3.  El panel derecho muestra los campos en el MISMO orden que la pantalla
        «New Equipment Item»; cada uno con su valor (editable) y un botón
        «Copiar».
    4.  El operador copia campo por campo y pega en AdaptIQ. Las filas copiadas
        se marcan en verde para seguir el avance.

La pestaña «Texto extraído» muestra el texto crudo como red de seguridad.
"""
from __future__ import annotations

import os
import tempfile
import traceback

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from scannerform import __version__, config
from scannerform.io import ocr, raster
from scannerform.mapping import adaptiq
from scannerform.model import EquipmentRecord
from scannerform.scanner import scan_file
from scannerform.ui import common
from scannerform.ui.common import FieldRow


class ScanWorker(QThread):
    """Ejecuta el escaneo (posible OCR) fuera del hilo de la interfaz."""
    finished = Signal(object)   # EquipmentRecord
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            rec = scan_file(self._path)
            self.finished.emit(rec)
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"scannerForm — Newmont Merian FMS  ·  v{__version__}")
        self.resize(1380, 880)
        self.setMinimumSize(1100, 700)
        self.setAcceptDrops(True)

        self._worker: ScanWorker | None = None
        self._record: EquipmentRecord | None = None
        self._field_rows: list[FieldRow] = []
        self._current_path: str = ""

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setSpacing(6)
        lay.addWidget(self._build_toolbar())
        lay.addWidget(self._build_body(), stretch=1)

        self._refresh_ocr_chip()
        self.statusBar().showMessage(
            "Abra un PDF o imagen del formulario, o arrástrelo aquí.")

    # -----------------------------------------------------------------------
    # Construcción de la interfaz
    # -----------------------------------------------------------------------

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(2, 2, 2, 2)

        self.btn_open = common.primary_button("📂  Abrir archivo…")
        self.btn_open.clicked.connect(self._on_open)
        h.addWidget(self.btn_open)

        self.btn_paste = QPushButton("📋  Pegar imagen")
        self.btn_paste.setToolTip("Escanear una imagen copiada al portapapeles (foto del formulario).")
        self.btn_paste.clicked.connect(self._on_paste_image)
        h.addWidget(self.btn_paste)

        h.addSpacing(16)
        self.chip_form = common.chip("Sin documento", common.GREY)
        self.chip_source = common.chip("—", common.GREY)
        self.chip_ocr = common.chip("OCR", common.GREY)
        h.addWidget(self.chip_form)
        h.addWidget(self.chip_source)
        h.addWidget(self.chip_ocr)

        h.addStretch(1)
        self.lbl_file = QLabel("")
        self.lbl_file.setStyleSheet(f"color:{common.GREY};")
        h.addWidget(self.lbl_file)
        return bar

    def _build_body(self) -> QWidget:
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._build_preview())
        split.addWidget(self._build_tabs())
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 5)
        split.setSizes([560, 760])
        return split

    def _build_preview(self) -> QWidget:
        box = QGroupBox("Documento")
        v = QVBoxLayout(box)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_label = QLabel("Vista previa del documento")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color:#999;")
        self.preview_scroll.setWidget(self.preview_label)
        v.addWidget(self.preview_scroll)
        return box

    def _build_tabs(self) -> QWidget:
        self.tabs = QTabWidget()

        # --- Tab campos de AdaptIQ ---
        fields_tab = QWidget()
        fv = QVBoxLayout(fields_tab)
        topbar = QHBoxLayout()
        self.btn_copy_all = common.primary_button("Copiar todo (TSV)", common.BLUE)
        self.btn_copy_all.clicked.connect(self._on_copy_all)
        self.btn_copy_all.setEnabled(False)
        self.btn_reset = QPushButton("Reiniciar marcas")
        self.btn_reset.clicked.connect(self._on_reset_marks)
        self.btn_reset.setEnabled(False)
        topbar.addWidget(self.btn_copy_all)
        topbar.addWidget(self.btn_reset)
        topbar.addStretch(1)
        fv.addLayout(topbar)

        self.fields_scroll = QScrollArea()
        self.fields_scroll.setWidgetResizable(True)
        self.fields_host = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_host)
        self.fields_layout.setAlignment(Qt.AlignTop)
        self.fields_layout.addWidget(QLabel(
            "Abra un documento para extraer los campos."))
        self.fields_scroll.setWidget(self.fields_host)
        fv.addWidget(self.fields_scroll, stretch=1)
        self.tabs.addTab(fields_tab, "Campos AdaptIQ")

        # --- Tab texto extraído ---
        text_tab = QWidget()
        tv = QVBoxLayout(text_tab)
        self.raw_text = QPlainTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setStyleSheet("font-family:Consolas,monospace; font-size:12px;")
        btn_copy_text = QPushButton("Copiar texto")
        btn_copy_text.clicked.connect(
            lambda: self._copy_to_clipboard(self.raw_text.toPlainText(), "texto extraído"))
        tv.addWidget(self.raw_text, stretch=1)
        tv.addWidget(btn_copy_text)
        self.tabs.addTab(text_tab, "Texto extraído")

        # --- Tab operadores ---
        self.ops_table = QTableWidget(0, 5)
        self.ops_table.setHorizontalHeaderLabels(
            ["Badge", "Nombre", "Apellido", "DNI", "Badge code"])
        self.ops_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.ops_table, "Operadores")

        return self.tabs

    # -----------------------------------------------------------------------
    # Acciones
    # -----------------------------------------------------------------------

    def _on_open(self) -> None:
        start = config.DEFAULT_OPEN_FOLDER if os.path.isdir(config.DEFAULT_OPEN_FOLDER) else ""
        exts = " ".join(f"*{e}" for e in sorted(config.SUPPORTED_EXTS))
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir formulario FMS", start,
            f"Formularios ({exts});;Todos los archivos (*.*)")
        if path:
            self._scan(path)

    def _on_paste_image(self) -> None:
        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.information(
                self, "Portapapeles vacío",
                "No hay ninguna imagen en el portapapeles.\n"
                "Copie una foto del formulario y vuelva a intentarlo.")
            return
        tmp = os.path.join(tempfile.gettempdir(), "scannerform_clip.png")
        image.save(tmp, "PNG")
        self._scan(tmp)

    def _scan(self, path: str) -> None:
        self._current_path = path
        self.lbl_file.setText(os.path.basename(path))
        self._show_preview(path)
        self.btn_open.setEnabled(False)
        self.statusBar().showMessage(f"Procesando «{os.path.basename(path)}»…")
        QApplication.setOverrideCursor(Qt.WaitCursor)

        self._worker = ScanWorker(path)
        self._worker.finished.connect(self._on_scan_done)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _on_scan_done(self, rec: EquipmentRecord) -> None:
        QApplication.restoreOverrideCursor()
        self.btn_open.setEnabled(True)
        self._record = rec
        self._populate_fields(rec)
        self._populate_text(rec)
        self._populate_operators(rec)
        self._update_chips(rec)
        self.btn_copy_all.setEnabled(True)
        self.btn_reset.setEnabled(True)
        msg = config.FORM_TITLES.get(rec.form_type, rec.form_type)
        if rec.warnings:
            msg += f"  ·  {len(rec.warnings)} aviso(s) — revise el texto crudo."
        self.statusBar().showMessage(msg)

    def _on_scan_failed(self, error: str) -> None:
        QApplication.restoreOverrideCursor()
        self.btn_open.setEnabled(True)
        self.statusBar().showMessage("Error al procesar el documento.")
        QMessageBox.critical(self, "Error al escanear", error)

    def _on_copy_all(self) -> None:
        if not self._field_rows:
            return
        from scannerform.mapping.adaptiq import AdaptIQField
        fields = [AdaptIQField(r.key, r.label.text().rstrip(" *"), r.value())
                  for r in self._field_rows]
        tsv = adaptiq.to_tsv(fields)
        self._copy_to_clipboard(tsv, "todos los campos")
        for r in self._field_rows:
            r.set_copied(bool(r.value()))

    def _on_reset_marks(self) -> None:
        for r in self._field_rows:
            r.set_copied(False)

    # -----------------------------------------------------------------------
    # Poblado de paneles
    # -----------------------------------------------------------------------

    def _populate_fields(self, rec: EquipmentRecord) -> None:
        # Limpiar contenido previo.
        self._field_rows.clear()
        while self.fields_layout.count():
            item = self.fields_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.fields_layout.addWidget(self._group_header(
            "Pantalla «New Equipment Item»"))
        for f in adaptiq.build_fields(rec):
            self._add_field_row(f)

        self.fields_layout.addSpacing(8)
        self.fields_layout.addWidget(self._group_header(
            "Datos adicionales del formulario"))
        for f in adaptiq.build_extra_fields(rec):
            self._add_field_row(f)

    def _add_field_row(self, f) -> None:
        row = FieldRow(f.key, f.label, f.value, f.required, f.note)
        row.copyRequested.connect(self._on_field_copy)
        self.fields_layout.addWidget(row)
        self._field_rows.append(row)

    def _group_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-weight:bold; color:{common.BLUE}; "
            f"border-bottom:2px solid {common.BLUE}; padding:4px 0;")
        return lbl

    def _populate_text(self, rec: EquipmentRecord) -> None:
        lines = []
        if rec.warnings:
            lines.append("⚠ AVISOS:")
            lines.extend(f"  • {w}" for w in rec.warnings)
            lines.append("")
        lines.append(rec.raw_text or "(sin texto)")
        self.raw_text.setPlainText("\n".join(lines))

    def _populate_operators(self, rec: EquipmentRecord) -> None:
        self.ops_table.setRowCount(0)
        for op in rec.operators:
            r = self.ops_table.rowCount()
            self.ops_table.insertRow(r)
            for c, val in enumerate(
                    [op.badge, op.first_name, op.last_name, op.dni, op.badge_code]):
                self.ops_table.setItem(r, c, QTableWidgetItem(val))
        n = len(rec.operators)
        self.tabs.setTabText(2, f"Operadores ({n})" if n else "Operadores")

    def _update_chips(self, rec: EquipmentRecord) -> None:
        color = common.GREEN if rec.form_type != config.FORM_UNKNOWN else common.RED
        self.chip_form.setText(rec.form_type)
        self.chip_form.setStyleSheet(
            f"QLabel {{ background:{color}; color:white; border-radius:9px; "
            f"padding:2px 10px; font-weight:bold; }}")
        src_label = {"pdf-text": "PDF (texto)", "ocr": "PDF (OCR)",
                     "image-ocr": "Imagen (OCR)"}.get(rec.source_kind, rec.source_kind)
        self.chip_source.setText(src_label)
        self.chip_source.setStyleSheet(
            f"QLabel {{ background:{common.BLUE}; color:white; border-radius:9px; "
            f"padding:2px 10px; font-weight:bold; }}")

    def _refresh_ocr_chip(self) -> None:
        status = ocr.availability()
        color = common.GREEN if status.installed else common.AMBER
        text = "OCR ✓" if status.installed else "OCR no disponible"
        self.chip_ocr.setText(text)
        self.chip_ocr.setToolTip(status.message)
        self.chip_ocr.setStyleSheet(
            f"QLabel {{ background:{color}; color:white; border-radius:9px; "
            f"padding:2px 10px; font-weight:bold; }}")

    # -----------------------------------------------------------------------
    # Vista previa
    # -----------------------------------------------------------------------

    def _show_preview(self, path: str) -> None:
        try:
            if raster.is_pdf(path):
                img = raster.render_pdf_page(path, 0)
            else:
                img = raster.load_image(path)
            pix = common.pil_to_pixmap(img)
            # Escalar al ancho disponible del panel (sin agrandar de más).
            w = max(420, self.preview_scroll.viewport().width() - 24)
            pix = pix.scaledToWidth(min(w, pix.width() * 2), Qt.SmoothTransformation)
            self.preview_label.setPixmap(pix)
            self.preview_label.setMinimumSize(pix.size())
        except Exception as exc:  # noqa: BLE001
            self.preview_label.clear()
            self.preview_label.setText(f"No se pudo mostrar la vista previa:\n{exc}")

    # -----------------------------------------------------------------------
    # Portapapeles
    # -----------------------------------------------------------------------

    def _on_field_copy(self, key: str, value: str) -> None:
        self._copy_to_clipboard(value, key)

    def _copy_to_clipboard(self, text: str, what: str) -> None:
        QApplication.clipboard().setText(text or "")
        self.statusBar().showMessage(f"Copiado: {what}", 2500)

    # -----------------------------------------------------------------------
    # Arrastrar y soltar
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if os.path.splitext(url.toLocalFile())[1].lower() in config.SUPPORTED_EXTS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.splitext(path)[1].lower() in config.SUPPORTED_EXTS:
                self._scan(path)
                break


def launch() -> int:
    """Crea la QApplication y muestra la ventana. Devuelve el código de salida."""
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()
