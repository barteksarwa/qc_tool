import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QTextEdit, QHBoxLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Signal, Qt


class DataInputTab(QWidget):
    data_loaded = Signal(dict)

    def __init__(self):
        super().__init__()
        self.p1_path = None
        self.r1_path = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # --- Logo ---
        logo_path = r"C:\Users\Lenovo\Documents\python_projects\qc_tool\src\ui\resources\images\logo.jpg"
        logo_label = QLabel()
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaledToWidth(160, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(logo_label, alignment=Qt.AlignHCenter)

        # --- Instructions ---
        self.instructions = QTextEdit()
        self.instructions.setReadOnly(True)
        self.instructions.setText(
            "📘 **Instructions:**\n\n"
            "1. Click the buttons below to load your **P1 (Excel)** and **R1 (CSV)** data files.\n"
            "2. Once both files are loaded, the comparison will run automatically.\n"
            "3. Use the tabs above to explore summaries and forecasts."
        )
        self.instructions.setMaximumHeight(180)
        layout.addWidget(self.instructions)

        # --- Buttons + Status ---
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignCenter)

        self.btn_load_r1 = QPushButton("📄 Load R1 (Visualizer CSV)")
        self.btn_load_p1 = QPushButton("📘 Load P1 (Technical Sub-Entity Excel)")

        self.btn_load_r1.clicked.connect(self.load_r1)
        self.btn_load_p1.clicked.connect(self.load_p1)

        # Group each button with its status label
        btn_r1_layout = QVBoxLayout()
        btn_r1_layout.addWidget(self.btn_load_r1, alignment=Qt.AlignHCenter)
        self.label_r1 = QLabel("⚠️ No R1 file loaded.")
        self.label_r1.setAlignment(Qt.AlignHCenter)
        btn_r1_layout.addWidget(self.label_r1)

        btn_p1_layout = QVBoxLayout()
        btn_p1_layout.addWidget(self.btn_load_p1, alignment=Qt.AlignHCenter)
        self.label_p1 = QLabel("⚠️ No P1 file loaded.")
        self.label_p1.setAlignment(Qt.AlignHCenter)
        btn_p1_layout.addWidget(self.label_p1)

        button_layout.addLayout(btn_r1_layout)
        button_layout.addItem(QSpacerItem(40, 10, QSizePolicy.Fixed, QSizePolicy.Minimum))
        button_layout.addLayout(btn_p1_layout)
        layout.addLayout(button_layout)
        layout.addStretch()

    # --- File loaders ---
    def load_r1(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select R1 Visualizer CSV", "", "CSV Files (*.csv)"
        )
        if file_path:
            self.r1_path = file_path
            self.label_r1.setText(f"✅ R1 Loaded: {os.path.basename(file_path)}")
            self._emit_data()

    def load_p1(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select P1 Technical Sub-Entity Excel", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.p1_path = file_path
            self.label_p1.setText(f"✅ P1 Loaded: {os.path.basename(file_path)}")
            self._emit_data()

    def _emit_data(self):
        payload = {}
        if self.p1_path:
            payload['p1_path'] = self.p1_path
        if self.r1_path:
            payload['r1_path'] = self.r1_path
        if payload:
            self.data_loaded.emit(payload)
