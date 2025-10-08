import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QMessageBox
)
from PySide6.QtGui import QPixmap, QPalette, QBrush
from PySide6.QtCore import Qt
from src.ui.tab_input import DataInputTab
from src.ui.tab_overview import TSESummaryTab
from src.ui.tab_forecast import TSEForecastTab
from src.data.models import P1R1Comparator


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("P1–R1 QC Tool")
        self.resize(970, 600)

        self.bg_path = r"C:\Users\Lenovo\Documents\python_projects\qc_tool\src\ui\resources\images\bg1.jpg"
        self.qss_path = r"C:\Users\Lenovo\Documents\python_projects\qc_tool\src\ui\resources\styles.qss"

        # Load stylesheet and background once
        self.load_stylesheet()
        self.bg_pixmap = QPixmap(self.bg_path)
        self._last_size = None
        self._apply_background(force=True)

        # ============================================================
        # Setup Core Layout
        # ============================================================
        self.p1_path = None
        self.r1_path = None
        self.df_comparison = None

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_input = DataInputTab()
        self.tab_input.data_loaded.connect(self._on_data_loaded)
        self.tabs.addTab(self.tab_input, "📥 Data Input")

        self.tab_summary = TSESummaryTab()
        self.tabs.addTab(self.tab_summary, "📋 TSE Summary")
        self.tabs.setTabEnabled(1, False)

        self.tab_forecast = TSEForecastTab()
        self.tabs.addTab(self.tab_forecast, "📊 TSE Annual")
        self.tabs.setTabEnabled(2, False)

    # ============================================================
    # Stylesheet + Background
    # ============================================================
    def load_stylesheet(self):
        if os.path.exists(self.qss_path):
            with open(self.qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            print(f"✅ Stylesheet loaded: {self.qss_path}")
        else:
            print(f"⚠️ Stylesheet not found at {self.qss_path}")

    def _apply_background(self, force=False):
        """Apply background only if window size meaningfully changes."""
        if self.bg_pixmap.isNull():
            print(f"⚠️ Could not load background image: {self.bg_path}")
            return

        current_size = self.size()
        if not force and self._last_size and abs(current_size.width() - self._last_size.width()) < 40:
            return  # Skip tiny resizes to avoid reloading often

        self._last_size = current_size
        scaled = self.bg_pixmap.scaled(
            current_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        palette = self.palette()
        palette.setBrush(QPalette.Window, QBrush(scaled))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        print(f"✅ Background applied (scaled {current_size.width()}x{current_size.height()})")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_background()

    # ============================================================
    # Data handling
    # ============================================================
    def _on_data_loaded(self, data: dict):
        if 'p1_path' in data:
            self.p1_path = data['p1_path']
        if 'r1_path' in data:
            self.r1_path = data['r1_path']

        if self.p1_path and self.r1_path:
            self._run_comparison()

    def _run_comparison(self):
        try:
            comparator = P1R1Comparator(self.p1_path, self.r1_path)
            self.df_comparison = comparator.compare()

            self.tab_summary.set_data(self.df_comparison)
            self.tabs.setTabEnabled(1, True)
            self.tabs.setCurrentIndex(1)

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Comparison failed:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
