import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTableView, QTextEdit, QHeaderView
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


# ----------------------------------------------------------------
# Simple Pandas Table Model for numeric data
# ----------------------------------------------------------------
class PandasModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        value = self._df.iat[index.row(), index.column()]
        if role == Qt.DisplayRole:
            # Format floats cleanly
            if isinstance(value, float):
                return f"{value:,.2f}"
            return str(value)
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(section)
        return None


# ----------------------------------------------------------------
# Annual Forecast Tab
# ----------------------------------------------------------------
class TSEForecastTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.setStyleSheet("QLabel { color: #222; } QTextEdit { color: #222; }")

        # ============================================================
        # Filters Row
        # ============================================================
        filter_layout = QHBoxLayout()
        self.filter_equity = QComboBox()
        self.filter_product_stream = QComboBox()
        self.filter_uncertainty = QComboBox()
        self.filter_valuation = QComboBox()

        for box in [
            self.filter_equity,
            self.filter_product_stream,
            self.filter_uncertainty,
            self.filter_valuation,
        ]:
            box.addItem("All")
            box.currentIndexChanged.connect(self._apply_filters)

        filter_layout.addWidget(QLabel("EQUITY_SHARE:"))
        filter_layout.addWidget(self.filter_equity)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("PRODUCT_STREAM:"))
        filter_layout.addWidget(self.filter_product_stream)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("UNCERTAINTY:"))
        filter_layout.addWidget(self.filter_uncertainty)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("VALUATION:"))
        filter_layout.addWidget(self.filter_valuation)
        layout.addLayout(filter_layout)

        # ============================================================
        # Explanation Box
        # ============================================================
        self.explanation = QTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setText(
            "<b>Annual Forecasts:</b><br>"
            "Displays annual production volumes (e.g., GAS, OIL, NGL, COND) "
            "side-by-side for each year.<br>"
            "Use filters above to refine by EQUITY_SHARE, PRODUCT_STREAM, UNCERTAINTY, and VALUATION."
        )
        layout.addWidget(self.explanation)

        # ============================================================
        # Table View
        # ============================================================
        self.table = QTableView()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.df_full = None

    # ============================================================
    # Public: Set data from MainWindow
    # ============================================================
    def set_data(self, df: pd.DataFrame):
        """
        Expected df: columns like
        ['TECHNICAL_SUB_ENTITY_ID', 'TECHNICAL_SUB_ENTITY_NAME',
         'PRODUCT', 'EQUITY_SHARE', 'PRODUCT_STREAM', 'UNCERTAINTY',
         'VALUATION', '2023', '2024', '2025', ...]
        """
        self.df_full = df.copy()
        self._populate_filters()
        self._apply_filters()

    # ============================================================
    # Populate filters dynamically
    # ============================================================
    def _populate_filters(self):
        if self.df_full is None:
            return
        df = self.df_full

        combos = [
            (self.filter_equity, "EQUITY_SHARE"),
            (self.filter_product_stream, "PRODUCT_STREAM"),
            (self.filter_uncertainty, "UNCERTAINTY"),
            (self.filter_valuation, "VALUATION"),
        ]

        for combo, col in combos:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("All")
            if col in df.columns:
                values = sorted(df[col].dropna().astype(str).unique())
                combo.addItems(values)
            combo.blockSignals(False)

    # ============================================================
    # Apply active filters and rebuild the table
    # ============================================================
    def _apply_filters(self):
        if self.df_full is None:
            return

        df = self.df_full.copy()

        for combo, col in [
            (self.filter_equity, "EQUITY_SHARE"),
            (self.filter_product_stream, "PRODUCT_STREAM"),
            (self.filter_uncertainty, "UNCERTAINTY"),
            (self.filter_valuation, "VALUATION"),
        ]:
            val = combo.currentText()
            if val != "All" and col in df.columns:
                df = df[df[col].astype(str) == val]

        if df.empty:
            self.table.setModel(PandasModel(pd.DataFrame()))
            return

        self._update_table(df)

    # ============================================================
    # Pivot to show years side-by-side by TSE + Product
    # ============================================================
    def _update_table(self, df):
        # Collect year columns automatically (numeric or string like '2025')
        year_cols = [c for c in df.columns if str(c).isdigit()]
        meta_cols = [
            c for c in ["TECHNICAL_SUB_ENTITY_ID", "TECHNICAL_SUB_ENTITY_NAME", "PRODUCT"]
            if c in df.columns
        ]
        display_cols = meta_cols + year_cols

        df_display = df[display_cols].copy()
        df_display = df_display.sort_values(meta_cols)

        self.table.setModel(PandasModel(df_display))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
