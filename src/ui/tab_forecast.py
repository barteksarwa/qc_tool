# src/ui/tab_forecast.py
import pandas as pd
from typing import List, Optional, Set, Dict

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView,
    QLabel, QHBoxLayout, QComboBox, QTextEdit, QDoubleSpinBox,
    QSizePolicy, QFrame, QToolButton, QMenu
)
from PySide6.QtGui import QAction, QColor

from .common.constants import DEFAULT_FILTERS
from .common.ui_table_utils import EqualFillSizer


# ---------- Helpers ----------
def _year_cols(df: pd.DataFrame, suffix: str) -> List[str]:
    """
    Return a list of year strings 'YYYY' for columns like 'YYYY_P1' or 'YYYY_R1'.
    """
    years = []
    sfx = suffix.strip()
    for c in df.columns:
        if c.endswith(sfx):
            head = c[: -len(sfx)].rstrip("_")
            if head.isdigit():
                years.append(head)
    return years


# ---------- Table model for annual comparison ----------
class AnnualComparisonModel(QAbstractTableModel):
    """
    DataFrame columns:
      Year | <PROD> - P1 | <PROD> - R1 | <PROD> - Diff | ...
    Colors Diff by relative % vs R1 using a threshold.
    """
    def __init__(self, df: pd.DataFrame, threshold_pct: float = 5.0):
        super().__init__()
        self._df = df.copy()
        self._numeric_cols = set(self._df.columns) - {"Year"}
        self._threshold = float(threshold_pct)

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(section + 1)
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = self._df.columns[index.column()]
        value = self._df.iat[index.row(), index.column()]
        is_num = col in self._numeric_cols

        if role == Qt.DisplayRole:
            if is_num:
                try:
                    return f"{float(value):,.2f}"
                except Exception:
                    return ""
            return "" if pd.isna(value) else str(value)

        if role == Qt.UserRole:
            # Raw values for sorting: numeric -> float, Year -> int
            try:
                if is_num:
                    return float(value)
                if col == "Year":
                    return int(value)
                return value
            except Exception:
                return 0

        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight if is_num else Qt.AlignLeft

        # ✅ Background color coding for Diff cells using relative percentage vs R1
        if role == Qt.BackgroundRole and isinstance(col, str) and col.endswith(" - Diff"):
            base = col[:-len(" - Diff")]
            row = index.row()
            try:
                diff = float(self._df.iat[row, index.column()])
            except Exception:
                return None
            r1_col = f"{base} - R1"
            try:
                r1 = float(self._df.at[self._df.index[row], r1_col])
            except Exception:
                r1 = 0.0
            denom = abs(r1)
            if denom < 1e-12:
                rel = 0.0 if abs(diff) < 1e-12 else float("inf")
            else:
                rel = abs(diff) * 100.0 / denom
            return QColor(255, 150, 150) if rel > self._threshold else QColor(204, 255, 229)

        return None


# ---------- TSE Forecast Tab ----------
class TSEForecastTab(QWidget):
    """
    Annual volumes comparison per selected TSE:
      - Choose TSE ID from a dropdown.
      - Fixed defaults: PRODUCT_STREAM/EQUITY_SHARE/UNCERTAINTY/VALUATION.
      - Multi-select PRODUCT (side-by-side P1/R1/Diff per product).
      - First column is Year, then product triplets.
    """
    def __init__(self):
        super().__init__()
        self.df_full: Optional[pd.DataFrame] = None

        # Cached lists / selections
        self._tse_display_to_id: Dict[str, str] = {}  # "27557 — NAME" -> "27557"
        self._all_products: List[str] = []
        self._selected_products: Set[str] = set()

        layout = QVBoxLayout(self)

        # ----- Filters row -----
        filter_layout = QHBoxLayout()

        # TSE selector (first)
        filter_layout.addWidget(QLabel("TSE:"))
        self.filter_tse = QComboBox()
        self.filter_tse.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.filter_tse)

        # PRODUCTS multi-select
        filter_layout.addSpacing(16)
        filter_layout.addWidget(QLabel("PRODUCTS:"))
        self.product_button = QToolButton()
        self.product_button.setObjectName("ProductMulti")  # for QSS styling
        self.product_button.setText("All")
        self.product_button.setPopupMode(QToolButton.InstantPopup)
        self.product_menu = QMenu(self)
        self.product_menu.setObjectName("ProductMenu")  # for QSS styling
        self.product_button.setMenu(self.product_menu)
        filter_layout.addWidget(self.product_button)

        # Other filters (always-on defaults)
        filter_layout.addSpacing(16)
        self.filter_product_stream = QComboBox()
        self.filter_equity = QComboBox()
        self.filter_uncertainty = QComboBox()
        self.filter_valuation = QComboBox()
        for box in [
            self.filter_product_stream,
            self.filter_equity,
            self.filter_uncertainty,
            self.filter_valuation,
        ]:
            box.currentIndexChanged.connect(self._apply_filters)

        filter_layout.addWidget(QLabel("PRODUCT_STREAM:"))
        filter_layout.addWidget(self.filter_product_stream)
        filter_layout.addSpacing(12)
        filter_layout.addWidget(QLabel("EQUITY_SHARE:"))
        filter_layout.addWidget(self.filter_equity)
        filter_layout.addSpacing(12)
        filter_layout.addWidget(QLabel("UNCERTAINTY:"))
        filter_layout.addWidget(self.filter_uncertainty)
        filter_layout.addSpacing(12)
        filter_layout.addWidget(QLabel("VALUATION:"))
        filter_layout.addWidget(self.filter_valuation)

        # Threshold (%)
        filter_layout.addSpacing(16)
        filter_layout.addWidget(QLabel("THRESHOLD %:"))
        self.threshold_pct = QDoubleSpinBox()
        self.threshold_pct.setRange(0.0, 1000.0)
        self.threshold_pct.setDecimals(1)
        self.threshold_pct.setSingleStep(0.5)
        self.threshold_pct.setValue(5.0)
        self.threshold_pct.setSuffix("%")
        self.threshold_pct.valueChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.threshold_pct)

        layout.addLayout(filter_layout)

        # ----- Explanation (compact) -----
        self.explanation = QTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setText(
            "<b>Annual Comparison:</b><br>"
            "Select a TSE, choose PRODUCTS (multi‑select), and fixed filters (AFS/GES/BEST/PR).<br>"
            "Table shows <i>Year</i> and, for each selected product, "
            "<i>Product - P1</i>, <i>Product - R1</i>, <i>Product - Diff</i>."
        )
        self.explanation.setMaximumHeight(96)
        self.explanation.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.explanation.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.explanation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.explanation.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self.explanation)

        # Units label (R1 only)
        self.units_label = QLabel("")
        self.units_label.setObjectName("UnitsInfo")
        self.units_label.setStyleSheet("color: #666; margin-left: 2px;")
        layout.addWidget(self.units_label)

        # ----- Table -----
        self.table = QTableView()
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Equalize columns to fill the viewport (and keep it on container resize)
        self._sizer = EqualFillSizer(self.table, min_col_width=80, reapply_on_resize=True)

    # ============================================================
    # Public API
    # ============================================================
    def set_data(self, df: pd.DataFrame):
        """Provide the comparison DataFrame. Triggers filter population and first render."""
        self.df_full = df.copy()
        self._populate_filters()
        self._apply_filters()
        self._update_units_label(self.df_full if isinstance(self.df_full, pd.DataFrame) else pd.DataFrame())

    # ============================================================
    # Populate filters and menus
    # ============================================================
    def _populate_filters(self):
        if self.df_full is None or self.df_full.empty:
            # Reset controls
            self.filter_tse.clear()
            self.filter_product_stream.clear()
            self.filter_equity.clear()
            self.filter_uncertainty.clear()
            self.filter_valuation.clear()
            self.product_menu.clear()
            self.product_button.setText("All")
            self._tse_display_to_id.clear()
            self._all_products = []
            self._selected_products = set()
            return

        df = self.df_full

        # TSE list
        ids = df["TECHNICAL_SUB_ENTITY_ID"].astype(str)
        has_name = "TECHNICAL_SUB_ENTITY_NAME" in df.columns
        names = df["TECHNICAL_SUB_ENTITY_NAME"].astype(str) if has_name else pd.Series(["N/A"] * len(df), index=df.index)

        tse_pairs = (
            pd.DataFrame({"id": ids, "name": names})
            .drop_duplicates()
            .sort_values(by=["id", "name"])
        )
        self.filter_tse.blockSignals(True)
        self.filter_tse.clear()
        self._tse_display_to_id.clear()
        for _, row in tse_pairs.iterrows():
            display = f"{row['id']} — {row['name']}"
            self.filter_tse.addItem(display)
            self._tse_display_to_id[display] = row["id"]
        if self.filter_tse.count() > 0:
            self.filter_tse.setCurrentIndex(0)
        self.filter_tse.blockSignals(False)

        # Fixed filters (defaults, no "All")
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
            combo.addItems(values)
            wanted = DEFAULT_FILTERS.get(col, "")
            if wanted and wanted in values:
                combo.setCurrentText(wanted)
            elif values:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

        # Product multi-select
        if "PRODUCT" in df.columns:
            prod_series = df["PRODUCT"].dropna().astype(str).str.strip().str.upper()
        else:
            prod_series = pd.Series(dtype=str)
        products = sorted(prod_series.unique().tolist())
        self._all_products = products
        self._selected_products = set(products)  # default: all selected
        self._rebuild_product_menu()

    def _rebuild_product_menu(self):
        self.product_menu.clear()
        act_all = QAction("Select All", self.product_menu)
        act_all.triggered.connect(self._select_all_products)
        self.product_menu.addAction(act_all)

        act_clear = QAction("Clear All", self.product_menu)
        act_clear.triggered.connect(self._clear_all_products)
        self.product_menu.addAction(act_clear)

        if self._all_products:
            self.product_menu.addSeparator()

        for prod in self._all_products:
            act = QAction(prod, self.product_menu)
            act.setCheckable(True)
            act.setChecked(prod in self._selected_products)
            act.toggled.connect(lambda checked, p=prod: self._toggle_product(p, checked))
            self.product_menu.addAction(act)

        self._update_product_button_label()

    def _select_all_products(self):
        self._selected_products = set(self._all_products)
        self._rebuild_product_menu()
        self._apply_filters()

    def _clear_all_products(self):
        # True clear: empty selection
        self._selected_products = set()
        self._rebuild_product_menu()
        self._apply_filters()

    def _toggle_product(self, product: str, checked: bool):
        if checked:
            self._selected_products.add(product)
        else:
            self._selected_products.discard(product)
        self._update_product_button_label()
        self._apply_filters()

    def _update_product_button_label(self):
        if not self._all_products:
            self.product_button.setText("None")
        elif len(self._selected_products) == len(self._all_products):
            self.product_button.setText("All")
        elif len(self._selected_products) == 0:
            self.product_button.setText("None")
        elif len(self._selected_products) == 1:
            self.product_button.setText(next(iter(self._selected_products)))
        else:
            self.product_button.setText(f"{len(self._selected_products)} selected")

    # ============================================================
    # Apply filters and render
    # ============================================================
    def _apply_filters(self):
        if self.df_full is None or self.df_full.empty:
            self._update_units_label(self.df_full if isinstance(self.df_full, pd.DataFrame) else pd.DataFrame())
            self._render(pd.DataFrame(columns=["Year"]))
            return

        df = self.df_full

        # TSE filter (required)
        sel_display = self.filter_tse.currentText()
        sel_tse_id = self._tse_display_to_id.get(sel_display, "")
        if sel_tse_id:
            df = df[df["TECHNICAL_SUB_ENTITY_ID"].astype(str) == str(sel_tse_id)]

        # Always-on base filters (uppercased, no "All")
        for combo, col in [
            (self.filter_product_stream, "PRODUCT_STREAM"),
            (self.filter_equity, "EQUITY_SHARE"),
            (self.filter_uncertainty, "UNCERTAINTY"),
            (self.filter_valuation, "VALUATION"),
        ]:
            if col in df.columns:
                sel = combo.currentText().strip().upper()
                if sel:
                    df = df[df[col].astype(str).str.strip().str.upper().eq(sel)]

        if df.empty:
            self._update_units_label(df)
            self._render(pd.DataFrame(columns=["Year"]))
            return

        # Normalize product
        if "PRODUCT" in df.columns:
            prod_str = df["PRODUCT"].astype(str).str.strip().str.upper()
        else:
            prod_str = pd.Series(["N/A"] * len(df), index=df.index)
        df = df.assign(__PRODUCT=prod_str)

        # Product multi-select (allow empty -> results empty)
        if len(self._selected_products) < len(self._all_products):
            df = df[df["__PRODUCT"].isin(self._selected_products)]
            if df.empty:
                self._update_units_label(df)
                self._render(pd.DataFrame(columns=["Year"]))
                return

        # Update Units label from filtered df (if present)
        self._update_units_label(df)

        # Build annual comparison table
        annual = self._build_annual_per_product(df)
        self._render(annual)

    def _update_units_label(self, df_filtered: pd.DataFrame):
        unit = None
        if isinstance(df_filtered, pd.DataFrame) and "UNITS" in df_filtered.columns:
            vals = df_filtered["UNITS"].dropna().astype(str).str.strip().unique().tolist()
            if len(vals) == 1:
                unit = vals[0]
            elif len(vals) > 1:
                unit = "Multiple"
        self.units_label.setText(f"R1 Unit — {unit or 'N/A'};  P1 Unit — N/A")

    # Build annual table: Year rows, per-product triplets (no cross-product totals)
    def _build_annual_per_product(self, df: pd.DataFrame) -> pd.DataFrame:
        # Determine years present (intersection ensures both P1 and R1 exist)
        p1_years = set(_year_cols(df, "_P1"))
        r1_years = set(_year_cols(df, "_R1"))
        years = sorted(p1_years.intersection(r1_years), key=lambda y: int(y))
        if not years:
            return pd.DataFrame(columns=["Year"])

        # Decide product order for columns
        products = list(self._selected_products) if self._selected_products else []
        if not products or len(products) == len(self._all_products):
            products = self._all_products[:]  # all in discovered order

        # Prepare result frame indexed by years
        out = pd.DataFrame({"Year": [int(y) for y in years]})
        out.set_index("Year", inplace=True)

        # For each product, sum per year across matching rows
        for prod in products:
            sub = df[df["__PRODUCT"] == prod]
            if sub.empty:
                out[f"{prod} - P1"] = pd.NA
                out[f"{prod} - R1"] = pd.NA
                out[f"{prod} - Diff"] = pd.NA
                continue

            # Build matrices for P1 and R1 (columns in year order)
            p1_cols = [f"{y}_P1" for y in years if f"{y}_P1" in sub.columns]
            r1_cols = [f"{y}_R1" for y in years if f"{y}_R1" in sub.columns]
            p1_vals = sub[p1_cols].apply(pd.to_numeric, errors="coerce") if p1_cols else pd.DataFrame(index=sub.index)
            r1_vals = sub[r1_cols].apply(pd.to_numeric, errors="coerce") if r1_cols else pd.DataFrame(index=sub.index)

            p1_year_sum = p1_vals.sum(axis=0, skipna=True) if not p1_vals.empty else pd.Series([0] * len(years), index=[f"{y}_P1" for y in years])
            r1_year_sum = r1_vals.sum(axis=0, skipna=True) if not r1_vals.empty else pd.Series([0] * len(years), index=[f"{y}_R1" for y in years])

            # Align to all years (in case some are missing)
            p1_series = pd.Series(index=years, dtype="float64")
            r1_series = pd.Series(index=years, dtype="float64")
            for y in years:
                p1_series[y] = float(p1_year_sum.get(f"{y}_P1", 0.0))
                r1_series[y] = float(r1_year_sum.get(f"{y}_R1", 0.0))
            diff_series = p1_series - r1_series

            # Attach to output
            out[f"{prod} - P1"] = p1_series.values
            out[f"{prod} - R1"] = r1_series.values
            out[f"{prod} - Diff"] = diff_series.values

        out = out.reset_index()  # bring Year back as first column
        return out

    # ============================================================
    # Render table with proxy for numeric sorting
    # ============================================================
    def _render(self, df_out: pd.DataFrame):
        model = AnnualComparisonModel(df_out, threshold_pct=float(self.threshold_pct.value()))
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(model)
        proxy.setSortRole(Qt.UserRole)
        self.table.setModel(proxy)

        # Default sort by Year ascending (col 0)
        if not df_out.empty and "Year" in df_out.columns:
            self.table.sortByColumn(0, Qt.AscendingOrder)

        # Equalize/fill after model is in place (proxy)
        self._sizer.defer_equalize()