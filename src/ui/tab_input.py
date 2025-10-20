import os
from typing import Optional, Union

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QTextEdit,
    QHBoxLayout, QGroupBox, QSizePolicy
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Signal, Qt


class DataInputTab(QWidget):
    data_loaded = Signal(dict)
    clear_requested = Signal()

    def __init__(self):
        super().__init__()

        # Stored paths (None = not selected)
        self.anaplan_metadata_path: Optional[str] = None
        self.anaplan_prod_path: Optional[str] = None
        self.p1_path: Optional[str] = None           # P1 TSE
        self.p1_ae_path: Optional[str] = None        # P1 AE (future)
        self.p1_hierarchy_path: Optional[str] = None # P1 AE–TE–TSE
        self.r1_path: Optional[str] = None
        self.sdfp_path: Optional[str] = None
        # Optional: user-provided sheet name/index for P1 hierarchy
        self.p1_hierarchy_sheet: Optional[Union[str, int]] = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        logo_path = os.path.normpath(r"src/ui/resources/images/logo.jpg")
        logo = QLabel()
        if os.path.exists(logo_path):
            pm = QPixmap(logo_path)
            logo.setPixmap(pm.scaledToWidth(160, Qt.SmoothTransformation))
            logo.setAlignment(Qt.AlignHCenter)
            layout.addWidget(logo, alignment=Qt.AlignHCenter)

        self.instructions = QTextEdit()
        self.instructions.setReadOnly(True)
        self.instructions.setMaximumHeight(250)
        self.instructions.setText(
            "Load the inputs needed for analysis.\n\n"
            "• Anaplan: Metadata and Production (CSV/XLSX)\n"
            "• P1 files: TSE, AE, and optional AE–TE–TSE Hierarchy (XLSX)\n"
            "• R1 Visualizer: CSV\n"
            "• SDFP: CSV/XLSX\n\n"
            "Tip: If your P1 hierarchy workbook has multiple sheets, provide the sheet (index or name)."
        )
        layout.addWidget(self.instructions)

        # Group box with columns
        box = QGroupBox("Load Inputs")
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        box_layout = QHBoxLayout()
        box_layout.setSpacing(24)
        box.setLayout(box_layout)
        layout.addWidget(box)

        BTN_H = 56

        def make_column():
            col_widget = QWidget()
            col_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            v = QVBoxLayout(col_widget)
            v.setSpacing(8)
            v.setAlignment(Qt.AlignTop)
            return col_widget, v

        # ----- Column 1: Anaplan -----
        col1_w, col1 = make_column()
        self.btn_anaplan_meta = QPushButton("🧭 Load Anaplan Metadata")
        self.btn_anaplan_meta.setFixedHeight(BTN_H)
        self.btn_anaplan_meta.clicked.connect(self.load_anaplan_metadata)
        col1.addWidget(self.btn_anaplan_meta)
        self.lab_anaplan_meta = QLabel("⚠️ Future Version.")
        self.lab_anaplan_meta.setAlignment(Qt.AlignHCenter)
        col1.addWidget(self.lab_anaplan_meta)

        self.btn_anaplan_prod = QPushButton("🏭 Load Anaplan Production")
        self.btn_anaplan_prod.setFixedHeight(BTN_H)
        self.btn_anaplan_prod.clicked.connect(self.load_anaplan_production)
        col1.addWidget(self.btn_anaplan_prod)
        self.lab_anaplan_prod = QLabel("⚠️ Future Version.")
        self.lab_anaplan_prod.setAlignment(Qt.AlignHCenter)
        col1.addWidget(self.lab_anaplan_prod)

        # ----- Column 2: P1 files -----
        col2_w, col2 = make_column()
        self.btn_p1_tse = QPushButton("🧩 Load P1 TSE")
        self.btn_p1_tse.setFixedHeight(BTN_H)
        self.btn_p1_tse.clicked.connect(self.load_p1_tse)
        col2.addWidget(self.btn_p1_tse)
        self.lab_p1_tse = QLabel("⚠️ No P1 TSE file loaded.")
        self.lab_p1_tse.setAlignment(Qt.AlignHCenter)
        col2.addWidget(self.lab_p1_tse)

        self.btn_p1_ae = QPushButton("🗒️ Load P1 AE")
        self.btn_p1_ae.setFixedHeight(BTN_H)
        self.btn_p1_ae.clicked.connect(self.load_p1_ae)
        col2.addWidget(self.btn_p1_ae)
        self.lab_p1_ae = QLabel("⚠️ Coming Soon.")
        self.lab_p1_ae.setAlignment(Qt.AlignHCenter)
        col2.addWidget(self.lab_p1_ae)

        self.btn_p1_hier = QPushButton("🌳 Load P1 Hierarchy (AE–TE–TSE)")
        self.btn_p1_hier.setFixedHeight(BTN_H)
        self.btn_p1_hier.clicked.connect(self.load_p1_hierarchy)
        col2.addWidget(self.btn_p1_hier)
        self.lab_p1_hier = QLabel("⚠️ No P1 Hierarchy file loaded.")
        self.lab_p1_hier.setAlignment(Qt.AlignHCenter)
        col2.addWidget(self.lab_p1_hier)

        # ----- Column 3: R1 & SDFP -----
        col3_w, col3 = make_column()
        self.btn_r1 = QPushButton("📄 Load R1 Visualizer (CSV)")
        self.btn_r1.setFixedHeight(BTN_H)
        self.btn_r1.clicked.connect(self.load_r1)
        col3.addWidget(self.btn_r1)
        self.lab_r1 = QLabel("⚠️ No R1 Visualizer file loaded.")
        self.lab_r1.setAlignment(Qt.AlignHCenter)
        col3.addWidget(self.lab_r1)

        self.btn_sdfp = QPushButton("📥 Load SDFP.")
        self.btn_sdfp.setFixedHeight(BTN_H)
        self.btn_sdfp.clicked.connect(self.load_sdfp)
        col3.addWidget(self.btn_sdfp)
        self.lab_sdfp = QLabel("⚠️ Coming soon.")
        self.lab_sdfp.setAlignment(Qt.AlignHCenter)
        col3.addWidget(self.lab_sdfp)
        col3.addStretch(1)

        box_layout.addWidget(col1_w)
        box_layout.addWidget(col2_w)
        box_layout.addWidget(col3_w)
        box_layout.setStretch(0, 1)
        box_layout.setStretch(1, 1)
        box_layout.setStretch(2, 1)

        layout.addStretch(1)

        self.btn_clear = QPushButton("🧹 Allow new load")
        self.btn_clear.setObjectName("BtnClearAll")
        self.btn_clear.setFixedHeight(40)
        self.btn_clear.clicked.connect(self._clear_all)
        layout.addWidget(self.btn_clear, alignment=Qt.AlignHCenter)

    # ------------------------ Load handlers ------------------------
    def load_anaplan_metadata(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Anaplan Metadata", "", "CSV/Excel (*.csv *.xlsx *.xls)"
        )
        if path:
            self.anaplan_metadata_path = path
            self.lab_anaplan_meta.setText(f"✅ Anaplan Metadata: {os.path.basename(path)}")
            self._emit_data()

    def load_anaplan_production(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Anaplan Production", "", "CSV/Excel (*.csv *.xlsx *.xls)"
        )
        if path:
            self.anaplan_prod_path = path
            self.lab_anaplan_prod.setText(f"✅ Anaplan Production: {os.path.basename(path)}")
            self._emit_data()

    def load_p1_tse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select P1 (Technical Sub-Entity)", "", "Excel Files (*.xlsx *.xls)"
        )
        if path:
            self.p1_path = path
            self.lab_p1_tse.setText(f"✅ P1 TSE: {os.path.basename(path)}")
            self._emit_data()

    def load_p1_ae(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select P1 (Activity Entity)", "", "Excel Files (*.xlsx *.xls)"
        )
        if path:
            self.p1_ae_path = path
            self.lab_p1_ae.setText(f"✅ P1 AE: {os.path.basename(path)}")
            self._emit_data()

    def load_p1_hierarchy(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select P1 Hierarchy (AE–TE–TSE)", "", "Excel Files (*.xlsx *.xls)"
        )
        if path:
            self.p1_hierarchy_path = path
            self.lab_p1_hier.setText(f"✅ P1 Hierarchy: {os.path.basename(path)}")
            # If you later add a sheet field, set self.p1_hierarchy_sheet accordingly here.
            self._emit_data()

    def load_r1(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select ResourceOne Visualizer (CSV)", "", "CSV Files (*.csv)"
        )
        if path:
            self.r1_path = path
            self.lab_r1.setText(f"✅ R1 Visualizer: {os.path.basename(path)}")
            self._emit_data()

    def load_sdfp(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SDFP (Std. Data Feeder - Production)", "", "CSV/Excel (*.csv *.xlsx *.xls)"
        )
        if path:
            self.sdfp_path = path
            self.lab_sdfp.setText(f"✅ SDFP: {os.path.basename(path)}")
            self._emit_data()

    # --------------------- Clear + emit helpers --------------------
    def _clear_all(self):
        # Reset paths
        self.anaplan_metadata_path = None
        self.anaplan_prod_path = None
        self.p1_path = None
        self.p1_ae_path = None
        self.p1_hierarchy_path = None
        self.p1_hierarchy_sheet = None
        self.r1_path = None
        self.sdfp_path = None

        # Reset labels
        self.lab_anaplan_meta.setText("⚠️ Future Version")
        self.lab_anaplan_prod.setText("⚠️ Future Version")
        self.lab_p1_tse.setText("⚠️ No P1 TSE file loaded.")
        self.lab_p1_ae.setText("⚠️ Future Version")
        self.lab_p1_hier.setText("⚠️ No P1 Hierarchy file loaded.")
        self.lab_r1.setText("⚠️ No R1 Visualizer file loaded.")
        self.lab_sdfp.setText("⚠️ Future Version")

        # Notify main window
        self.clear_requested.emit()

    def _emit_data(self):
        payload = {}
        if self.anaplan_metadata_path:
            payload["anaplan_metadata_path"] = self.anaplan_metadata_path
        if self.anaplan_prod_path:
            payload["anaplan_prod_path"] = self.anaplan_prod_path
        if self.p1_path:
            payload["p1_path"] = self.p1_path
        if self.p1_ae_path:
            payload["p1_ae_path"] = self.p1_ae_path
        if self.p1_hierarchy_path:
            payload["p1_hierarchy_path"] = self.p1_hierarchy_path
        if self.p1_hierarchy_sheet is not None:
            payload["p1_hierarchy_sheet"] = self.p1_hierarchy_sheet
        if self.r1_path:
            payload["r1_path"] = self.r1_path
        if self.sdfp_path:
            payload["sdfp_path"] = self.sdfp_path

        if payload:
            self.data_loaded.emit(payload)