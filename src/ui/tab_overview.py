import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView,
    QLabel, QHBoxLayout, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


# ----------------------------------------------------------------
# Custom Table Model with Color Coding
# ----------------------------------------------------------------
class ColorPandasModel(QAbstractTableModel):
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
        value = str(self._df.iat[index.row(), index.column()])
        if role == Qt.DisplayRole:
            return value
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        if role == Qt.BackgroundRole and value in ["Yes", "No"]:
            from PySide6.QtGui import QColor
            # Red = mismatch (Yes), Green = aligned (No)
            return QColor(255, 102, 102) if value == "Yes" else QColor(102, 255, 178)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(section)
        return None


# ----------------------------------------------------------------
# TSE Summary Tab
# ----------------------------------------------------------------
class TSESummaryTab(QWidget):
    def __init__(self):
        super().__init__()
        self.df_full = None

        layout = QVBoxLayout(self)

        # --- Filters Row ---
        filter_layout = QHBoxLayout()
        self.filter_equity = QComboBox()
        self.filter_product_stream = QComboBox()
        self.filter_uncertainty = QComboBox()
        self.filter_valuation = QComboBox()

        # Initialize dropdowns
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

        # --- Explanation Box ---
        self.explanation = QTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setText(
            "<b>Legend:</b><br>"
            "✅ <b>No</b> → P1 and R1 are aligned<br>"
            "❌ <b>Yes</b> → Differences found between P1 and R1<br><br>"
            "Use filters above to view differences for specific EQUITY_SHARE, PRODUCT_STREAM, "
            "UNCERTAINTY, and VALUATION combinations."
        )
        layout.addWidget(self.explanation)

        # --- Table ---
        self.table = QTableView()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    # ============================================================
    # Public: Set data from MainWindow
    # ============================================================
    def set_data(self, df: pd.DataFrame):
        self.df_full = df.copy()
        self._populate_filters()
        self._apply_filters()

    # ============================================================
    # Populate filter dropdowns dynamically
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
    # Apply filters and update the summary table
    # ============================================================
    def _apply_filters(self):
        if self.df_full is None:
            return

        df = self.df_full.copy()

        # Apply all active filters
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
            self.table.setModel(ColorPandasModel(pd.DataFrame()))
            return

        self._update_summary(df)

    # ============================================================
    # Build summary table (Yes/No per product)
    # ============================================================
    def _update_summary(self, df):
        diff_cols = [c for c in df.columns if c.endswith("_Diff")]

        summary_rows = []
        for tse_id, group in df.groupby("TECHNICAL_SUB_ENTITY_ID", dropna=False):
            tse_name = (
                group["TECHNICAL_SUB_ENTITY_NAME"].iloc[0]
                if "TECHNICAL_SUB_ENTITY_NAME" in group.columns
                else "N/A"
            )
            row = {"TSE ID": tse_id, "TSE Name": tse_name}

            for product in ["GAS", "OIL", "NGL", "COND"]:
                mask = group["PRODUCT"].astype(str).str.contains(product, case=False, na=False)
                has_diff = (group.loc[mask, diff_cols].abs().sum().sum() != 0)
                row[product] = "Yes" if has_diff else "No"

            summary_rows.append(row)

        df_summary = pd.DataFrame(summary_rows)
        self.table.setModel(ColorPandasModel(df_summary))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
