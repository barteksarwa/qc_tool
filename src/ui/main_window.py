# src/ui/main_window.py
import os
import sys
import pandas as pd
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPalette, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QMessageBox
)

# UI tabs (existing)
from src.ui.tab_input import DataInputTab
from src.ui.tab_overview import TSESummaryTab
from src.ui.tab_table import TSETotalsTab
from src.ui.tab_forecast import TSEForecastTab
from src.ui.tab_hierarchy_health import HierarchyHealthTab
from src.ui.tab_hierarchy_compare import HierarchyCompareTab
from src.ui.tab_ae_overview import AEOverviewTab
from src.ui.tab_ae_annual import AEAnnualTab

# New small, testable app-logic modules
from src.core.orchestrator import DataOrchestrator
from src.core.tab_policy import InputsReady, tabs_to_enable
from src.core.publish import publish_tse, publish_hierarchy


class MainWindow(QMainWindow):
    """
    Slim MainWindow:
      • Loads each file once (no reload loops).
      • Builds TSE compare only when P1 TSE + R1 exist.
      • Builds Hierarchy compare only when P1 Hierarchy + R1 exist.
      • Ignores Anaplan for now.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("P1–R1 QC Tool")
        self.resize(970, 600)

        # Look & feel
        self._bg_path = r"src\\ui\\resources\\images\\bg1.jpg"
        self._qss_path = r"src\\ui\\resources\\styles.qss"
        self._bg_pixmap = QPixmap(self._bg_path)
        self._last_sz = None
        self._load_stylesheet()
        self._apply_background(force=True)

        # Orchestrator (pure logic, no Qt)
        self.orch = DataOrchestrator()

        # Tabs
        self._init_tabs()

    # ---------- UI init ----------
    def _init_tabs(self):
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(root)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)

        # Input
        self.tab_input = DataInputTab()
        self.tab_input.data_loaded.connect(self._on_data_loaded)
        self.tab_input.clear_requested.connect(self._on_clear_all)
        self.tabs.addTab(self.tab_input, "📥 Data Input")

        # Hierarchy
        self.tab_hier_health = HierarchyHealthTab()
        self.tabs.addTab(self.tab_hier_health, "✅ Hierarchy Health")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_hier_health), False)

        self.tab_hier_compare = HierarchyCompareTab()
        self.tabs.addTab(self.tab_hier_compare, "🧭 Hierarchy Comparison")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_hier_compare), False)

        # AE (optional)
        self.tab_ae_overview = AEOverviewTab()
        self.tabs.addTab(self.tab_ae_overview, "📚 AE Overview")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_ae_overview), False)

        self.tab_ae_annual = AEAnnualTab()
        self.tabs.addTab(self.tab_ae_annual, "📉 AE Annual")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_ae_annual), False)

        # TSE
        self.tab_summary = TSESummaryTab()
        self.tabs.addTab(self.tab_summary, "📋 TSE Summary")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_summary), False)

        self.tab_totals = TSETotalsTab()
        self.tabs.addTab(self.tab_totals, "📈 TSE Totals")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_totals), False)

        self.tab_forecast = TSEForecastTab()
        self.tabs.addTab(self.tab_forecast, "📊 TSE Annual")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.tab_forecast), False)

    # ---------- look & feel ----------
    def _load_stylesheet(self):
        if os.path.exists(self._qss_path):
            with open(self._qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            print(f"✅ Stylesheet loaded: {self._qss_path}")

    def _apply_background(self, force=False):
        if self._bg_pixmap.isNull():
            return
        sz = self.size()
        if not force and self._last_sz and abs(sz.width() - self._last_sz.width()) < 40:
            return
        self._last_sz = sz
        scaled = self._bg_pixmap.scaled(sz, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        pal = self.palette()
        pal.setBrush(QPalette.Window, QBrush(scaled))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_background()

    # ---------- clear ----------
    def _on_clear_all(self):
        self.orch = DataOrchestrator()  # reset logic/state

        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(i, self.tabs.widget(i) is self.tab_input)

        # Clear data in views
        try:
            empty = pd.DataFrame()
            self.tab_summary.set_data(empty)
            self.tab_totals.set_data(empty)
            self.tab_forecast.set_data(empty)
        except Exception:
            pass
        self.tab_hier_health.reset_view()
        self.tab_hier_compare.reset_view()
        self.tab_ae_overview.reset_view()
        self.tab_ae_annual.reset_view()

        self.tabs.setCurrentWidget(self.tab_input)

    # ---------- data events from Input tab ----------
    def _on_data_loaded(self, data: dict):
        # 1) Apply path/sheet updates (orchestrator clears caches if paths changed)
        if "p1_path" in data:               self.orch.set_p1_tse(data["p1_path"])
        if "p1_ae_path" in data:            pass  # keep for later if needed
        if "p1_hierarchy_path" in data:     self.orch.set_p1_hierarchy(data["p1_hierarchy_path"], data.get("p1_hierarchy_sheet", 0))
        if "p1_hierarchy_sheet" in data and self.orch.p1_hier_path:  # sheet change retriggers load
            self.orch.set_p1_hierarchy(self.orch.p1_hier_path, data["p1_hierarchy_sheet"])
        if "r1_path" in data:               self.orch.set_r1(data["r1_path"])
        if "sdfp_path" in data:             pass  # not used now

        # 2) Load changed sources (each loader has a no‑reload guard)
        try:
            if "p1_path" in data:               self.orch.load_p1_tse()
            if ("p1_hierarchy_path" in data) or ("p1_hierarchy_sheet" in data and self.orch.p1_hier_path):
                self.orch.load_p1_hierarchy()
            if "r1_path" in data:               self.orch.load_r1()
        except Exception as e:
            self._error("Load failed", e); return

        # 3) Derived – TSE compare only when P1 TSE + R1
        try:
            tse_df = self.orch.build_tse_compare()
            if tse_df is not None:
                publish_tse(self, tse_df)
        except Exception as e:
            self._error("TSE comparison failed", e)

        # 4) Derived – HIERARCHY compare only when P1 Hierarchy + R1
        try:
            hc_model, hc_df = self.orch.build_hierarchy_compare()
            
            if hc_df is not None:
                print("Hierarchy DF columns:", list(hc_df.columns)[:20], "…")
                print("Hierarchy DF sample:\n", hc_df.head(3))

            if hc_model is not None and hc_df is not None:
                publish_hierarchy(self, hc_model, hc_df)
        except Exception as e:
            self._error("Hierarchy comparison failed", e)

        # 5) Enable tabs via policy (ignoring Anaplan)
        ready = InputsReady(
            p1_tse=self.orch.df_p1_tse is not None,
            p1_hier=self.orch.df_p1_hier is not None,
            r1=self.orch.df_r1_raw is not None
        )
        enable_map = tabs_to_enable(ready)
        self._apply_tab_enable(enable_map)

    # ---------- helpers ----------
    def _apply_tab_enable(self, m: dict[str, bool]):
        def set_enabled(widget, key):
            idx = self.tabs.indexOf(widget)
            if idx >= 0:
                self.tabs.setTabEnabled(idx, bool(m.get(key, False)))

        set_enabled(self.tab_summary,      "TSE_SUMMARY")
        set_enabled(self.tab_totals,       "TSE_TOTALS")
        set_enabled(self.tab_forecast,     "TSE_ANNUAL")
        set_enabled(self.tab_hier_compare, "HIER_COMPARE")
        set_enabled(self.tab_hier_health,  "HIER_HEALTH")
        set_enabled(self.tab_ae_overview,  "AE_OVERVIEW")
        set_enabled(self.tab_ae_annual,    "AE_ANNUAL")

    def _error(self, title: str, e: Exception):
        import traceback
        traceback.print_exc()
        QMessageBox.critical(self, "Error", f"{title}:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())