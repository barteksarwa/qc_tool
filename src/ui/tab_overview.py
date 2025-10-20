import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QLabel, QHBoxLayout, QComboBox, QTextEdit,
    QSizePolicy, QFrame
)
from PySide6.QtCore import Qt

from .common.constants import DEFAULT_FILTERS
from .common.ui_table_utils import ColorPandasModel, EqualFillSizer


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
            "<b>Overview Tab:</b><br>"
            "<b>Legend:</b><br>"
            "✅ → P1 and R1 are aligned<br>"
            "❌ → Differences found between P1 and R1<br><br>"
            "Use filters above to view differences for specific EQUITY_SHARE, PRODUCT_STREAM, "
            "UNCERTAINTY, and VALUATION combinations."
        )
        self.explanation.setMaximumHeight(140)
        self.explanation.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.explanation.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.explanation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.explanation.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self.explanation)

        # --- Table ---
        self.table = QTableView()
        layout.addWidget(self.table)
        self._sizer = EqualFillSizer(self.table, min_col_width=80, reapply_on_resize=True)

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

        # Define combos and target columns (order matters)
        combos = [
            (self.filter_product_stream, "PRODUCT_STREAM"),
            (self.filter_equity, "EQUITY_SHARE"),
            (self.filter_uncertainty, "UNCERTAINTY"),
            (self.filter_valuation, "VALUATION"),
        ]

        for combo, col in combos:
            combo.blockSignals(True)
            combo.clear()
            if col in df.columns:
                values = (
                    df[col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .str.upper()
                    .unique()
                    .tolist()
                )
                values = sorted(values)
            else:
                values = []
            # Populate WITHOUT "All"
            combo.addItems(values)
            # Select default if present, else first available
            wanted = DEFAULT_FILTERS.get(col, "")
            if wanted and wanted in values:
                combo.setCurrentText(wanted)
            elif values:
                combo.setCurrentIndex(0)
            # else: leave empty if no values
            combo.blockSignals(False)

    # ============================================================
    # Apply filters and update the summary table
    # ============================================================
    def _apply_filters(self):
        if self.df_full is None:
            return
        df = self.df_full.copy()

        # Always filter by the selected value (no "All")
        for combo, col in [
            (self.filter_product_stream, "PRODUCT_STREAM"),
            (self.filter_equity, "EQUITY_SHARE"),
            (self.filter_uncertainty, "UNCERTAINTY"),
            (self.filter_valuation, "VALUATION"),
        ]:
            if col in df.columns:
                sel = combo.currentText().strip().upper()
                if sel:
                    df = df[
                        df[col]
                        .astype(str)
                        .str.strip()
                        .str.upper()
                        .eq(sel)
                    ]

        if df.empty:
            self.table.setModel(ColorPandasModel(pd.DataFrame()))
            self._sizer.defer_equalize()
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
            tolerance = 1e-6
            for product in ["GAS", "OIL", "NGL", "COND"]:
                mask = group["PRODUCT"].astype(str).str.contains(product, case=False, na=False)
                has_diff = (group.loc[mask, diff_cols].abs().sum().sum() > tolerance) if diff_cols else False
                row[product] = "❌" if has_diff else "✅"
            summary_rows.append(row)

        df_summary = pd.DataFrame(summary_rows)
        model = ColorPandasModel(df_summary)
        self.table.setModel(model)
        self._sizer.defer_equalize()