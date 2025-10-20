# src/ui/tab_ae_annual.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView
from PySide6.QtCore import Qt
import pandas as pd

class AEAnnualTab(QWidget):
    """
    AE Annual comparison (per year, per product triplets) similar to TSE Forecast but at AE level.
    Enabled when P1 AE and R1 are loaded. Placeholder until loaders are ready.
    """
    def __init__(self):
        super().__init__()
        self.paths = {"p1_ae": None, "r1": None}
        layout = QVBoxLayout(self)

        title = QLabel("Activity Entity Annual (P1 AE vs R1)")
        title.setObjectName("AEAnnualTitle")
        layout.addWidget(title)

        self.info = QLabel("Load P1 AE and ResourceOne to see annual AE-level comparisons.")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.table = QTableView()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        self.reset_view()

    def set_sources(self, p1_ae: str, r1: str):
        pass

    def reset_view(self):
        pass