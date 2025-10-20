# src/ui/tab_ae_overview.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView
from PySide6.QtCore import Qt
import pandas as pd

class AEOverviewTab(QWidget):
    """
    AE Overview: aggregated volumes at Activity Entity level (P1 AE vs R1).
    Enabled when P1 AE and R1 are loaded. Placeholder until loaders are ready.
    """
    def __init__(self):
        super().__init__()
        self.paths = {"p1_ae": None, "r1": None}
        layout = QVBoxLayout(self)

        title = QLabel("Activity Entity Overview (P1 AE vs R1)")
        title.setObjectName("AEOverviewTitle")
        layout.addWidget(title)

        self.info = QLabel("Load P1 AE and ResourceOne to see AE-level totals.")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.table = QTableView()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.reset_view()

    def set_sources(self, p1_ae: str, r1: str):
        pass

    def reset_view(self):
        pass