# src/ui/tab_table.py
import pandas as pd
from typing import List, Optional, Set

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView,
    QLabel, QHBoxLayout, QComboBox, QTextEdit, QDoubleSpinBox,
    QSizePolicy, QFrame, QToolButton, QMenu
)
from PySide6.QtGui import QAction, QColor

from .common.constants import DEFAULT_FILTERS
from .common.ui_table_utils import DynamicNumericModel, EqualFillSizer


# ---------- Helper: find "YYYY_P1" or "YYYY_R1" columns safely ----------
def _year_cols(df: pd.DataFrame, suffix: str) -> List[str]:
    cols = []
    sfx = suffix.strip()
    for c in df.columns:
        if c.endswith(sfx):
            head = c[: -len(sfx)].rstrip("_")
            if head.isdigit():  # only numeric years
                cols.append(c)
    return cols


class TSETotalsTab(QWidget):
    """
    Per-product totals by TSE (sum of all year columns for P1 and R1, but NOT across products).

    Columns:
      TSE ID
      TSE Name
      <PROD> - P1
      <PROD> - R1
      <PROD> - Diff   (repeated for each selected product)
    """

    def __init__(self):
        super().__init__()
        self.df_full: Optional[pd.DataFrame] = None
        # Holds available products and the current selection (upper-cased)
        self._all_products: List[str] = []
        self._selected_products: Set[str] = set()

        layout = QVBoxLayout(self)

        # --- Filters Row ---
        filter_layout = QHBoxLayout()

        # PRODUCTS multi-select FIRST
        filter_layout.addWidget(QLabel("PRODUCTS:"))
        self.product_button = QToolButton()
        self.product_button.setObjectName("ProductMulti")
        self.product_button.setText("All")
        self.product_button.setPopupMode(QToolButton.InstantPopup)
        self.product_menu = QMenu(self)
        self.product_button.setMenu(self.product_menu)
        self.product_menu.setObjectName("ProductMenu")
        filter_layout.addWidget(self.product_button)

        # Then the rest of filters
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

        filter_layout.addSpacing(16)
        filter_layout.addWidget(QLabel("EQUITY_SHARE:"))
        filter_layout.addWidget(self.filter_equity)
        filter_layout.addSpacing(16)
        filter_layout.addWidget(QLabel("PRODUCT_STREAM:"))
        filter_layout.addWidget(self.filter_product_stream)
        filter_layout.addSpacing(16)
        filter_layout.addWidget(QLabel("UNCERTAINTY:"))
        filter_layout.addWidget(self.filter_uncertainty)
        filter_layout.addSpacing(16)
        filter_layout.addWidget(QLabel("VALUATION:"))
        filter_layout.addWidget(self.filter_valuation)

        # Threshold (%)
        filter_layout.addSpacing(16)
        filter_layout.addWidget(QLabel("THRESHOLD %:"))
        self.threshold_pct = QDoubleSpinBox()
        self.threshold_pct.setRange(0.0, 1000.0)
        self.threshold_pct.setDecimals(1)
        self.threshold_pct.setSingleStep(0.5)
        self.threshold_pct.setValue(5.0)  # default
        self.threshold_pct.setSuffix("%")
        self.threshold_pct.valueChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.threshold_pct)

        layout.addLayout(filter_layout)

        # --- Explanation Box (compact) ---
        self.explanation = QTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setText(
            "<b>Totals Tab (Per-Product):</b><br>"
            "Sums all year columns for P1 and R1 per product and TSE.<br>"
            "<b>Important:</b> No totals across products are shown.<br>"
            "Columns: TSE ID, TSE Name, and for each selected product: "
            "<i>Product - P1</i>, <i>Product - R1</i>, <i>Product - Diff</i>."
        )
        self.explanation.setMaximumHeight(100)
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

        # --- Table ---
        self.table = QTableView()
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)
        self._sizer = EqualFillSizer(self.table, min_col_width=80, reapply_on_resize=True)

    # ============================================================
    # Public: Set data from MainWindow
    # ============================================================
    def set_data(self, df: pd.DataFrame):
        self.df_full = df.copy()
        self._populate_filters()
        self._apply_filters()
        self._update_units_label(self.df_full)
        
    # ============================================================
    # Populate filter dropdowns dynamically (and product menu)
    # ============================================================
    def _populate_filters(self):
        if self.df_full is None:
            return
        df = self.df_full

        # Define combos and columns (order matters)
        combos = [
            (self.filter_product_stream, "PRODUCT_STREAM"),
            (self.filter_equity, "EQUITY_SHARE"),
            (self.filter_uncertainty, "UNCERTAINTY"),
            (self.filter_valuation, "VALUATION"),
        ]

        # Populate each combo WITHOUT "All", uppercase for consistency, and select defaults
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
            # Choose the desired default (if present), otherwise pick the first available
            target = DEFAULT_FILTERS.get(col, "")
            if target and target in values:
                combo.setCurrentText(target)
            elif values:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

        # Build product list (upper-cased for consistency) — default: all selected
        if "PRODUCT" in df.columns:
            prod_series = df["PRODUCT"].dropna().astype(str).str.strip().str.upper()
        else:
            prod_series = pd.Series(dtype=str)
        products = sorted(prod_series.unique().tolist())
        self._all_products = products
        self._selected_products = set(products)

        # Build the multi-select menu
        self._rebuild_product_menu()

    def _rebuild_product_menu(self):
        self.product_menu.clear()

        # Add "Select All" / "Clear All"
        act_all = QAction("Select All", self.product_menu)
        act_all.triggered.connect(self._select_all_products)
        self.product_menu.addAction(act_all)

        act_clear = QAction("Clear All", self.product_menu)
        act_clear.triggered.connect(self._clear_all_products)
        self.product_menu.addAction(act_clear)

        if self._all_products:
            self.product_menu.addSeparator()

        # Add a checkable action for each product
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
    # Apply filters and update the per-product totals table
    # ============================================================
    def _apply_filters(self):
        if self.df_full is None:
            return
        df = self.df_full

        # Apply base filters (no "All": always filter by the selected value)
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
            self._update_units_label(df)
            self._render(pd.DataFrame(columns=["TSE ID", "TSE Name"]))
            return

        # Normalize product for filtering/grouping
        if "PRODUCT" in df.columns:
            prod_str = df["PRODUCT"].astype(str).str.strip().str.upper()
        else:
            prod_str = pd.Series(["N/A"] * len(df), index=df.index)
        df = df.assign(__PRODUCT=prod_str)

        # Apply product multi-select (allow empty -> empty results)
        if len(self._selected_products) < len(self._all_products):
            df = df[df["__PRODUCT"].isin(self._selected_products)]
            if df.empty:
                self._update_units_label(df)
                self._render(pd.DataFrame(columns=["TSE ID", "TSE Name"]))
                return

        # Update Units label from filtered df (if present)
        self._update_units_label(df)

        wide = self._build_per_product_wide(df)
        self._render(wide)

    def _update_units_label(self, df_filtered: pd.DataFrame):
        unit = None
        if "UNITS" in df_filtered.columns:
            vals = df_filtered["UNITS"].dropna().astype(str).str.strip().unique().tolist()
            if len(vals) == 1:
                unit = vals[0]
            elif len(vals) > 1:
                unit = "Multiple"
        self.units_label.setText(f"R1 Unit — {unit or 'N/A'};  P1 Unit — N/A")

    # ============================================================
    # Build per-product wide table (NO totals across products)
    # Columns: TSE ID | TSE Name | <PROD> - P1 | <PROD> - R1 | <PROD> - Diff
    # ============================================================
    def _build_per_product_wide(self, df: pd.DataFrame) -> pd.DataFrame:
        # Identify year columns
        p1_cols = _year_cols(df, "_P1")
        r1_cols = _year_cols(df, "_R1")

        # Row-wise sums across years
        if p1_cols:
            p1_vals = df[p1_cols].apply(pd.to_numeric, errors="coerce")
            p1_row_sum = p1_vals.sum(axis=1, skipna=True)
        else:
            p1_row_sum = pd.Series(0.0, index=df.index)
        if r1_cols:
            r1_vals = df[r1_cols].apply(pd.to_numeric, errors="coerce")
            r1_row_sum = r1_vals.sum(axis=1, skipna=True)
        else:
            r1_row_sum = pd.Series(0.0, index=df.index)

        # Groupers for per-product totals per TSE
        id_col = "TECHNICAL_SUB_ENTITY_ID"
        name_exists = "TECHNICAL_SUB_ENTITY_NAME" in df.columns
        name_col = "TECHNICAL_SUB_ENTITY_NAME" if name_exists else None

        group_idx = [df[id_col]]
        if name_col:
            group_idx.append(df[name_col])
        else:
            group_idx.append(pd.Series(["N/A"] * len(df), index=df.index, name="TECHNICAL_SUB_ENTITY_NAME"))
        group_idx.append(df["__PRODUCT"])

        p1_by_prod = p1_row_sum.groupby(group_idx, dropna=False).sum()
        r1_by_prod = r1_row_sum.groupby(group_idx, dropna=False).sum()
        by_prod = pd.concat([p1_by_prod, r1_by_prod], axis=1)
        by_prod.columns = ["P1", "R1"]
        by_prod["Diff"] = by_prod["P1"] - by_prod["R1"]

        # Pivot to wide per product
        wide_p1 = by_prod["P1"].unstack(level=-1)  # columns = PRODUCT
        wide_r1 = by_prod["R1"].unstack(level=-1)
        wide_diff = by_prod["Diff"].unstack(level=-1)

        # Decide product order: selected set if reduced, else all products found
        products = list(self._selected_products) if self._selected_products else []
        if not products or len(products) == len(self._all_products):
            products = self._all_products[:]  # all, in discovered order

        # Build final frame with columns grouped per product (P1, R1, Diff together)
        base_index = wide_p1.index if wide_p1 is not None else (
            wide_r1.index if wide_r1 is not None else wide_diff.index
        )
        final_wide = pd.DataFrame(index=base_index)
        for prod in products:
            final_wide[f"{prod} - P1"] = wide_p1[prod] if (wide_p1 is not None and prod in wide_p1.columns) else pd.NA
            final_wide[f"{prod} - R1"] = wide_r1[prod] if (wide_r1 is not None and prod in wide_r1.columns) else pd.NA
            final_wide[f"{prod} - Diff"] = wide_diff[prod] if (wide_diff is not None and prod in wide_diff.columns) else pd.NA

        # Reset index to columns
        final_wide = final_wide.reset_index()
        final_wide.rename(
            columns={
                "TECHNICAL_SUB_ENTITY_ID": "TSE ID",
                "TECHNICAL_SUB_ENTITY_NAME": "TSE Name",
            },
            inplace=True,
        )
        return final_wide

    # ============================================================
    # Render into the view with numeric sorting and threshold coloring
    # ============================================================
    def _render(self, df_out: pd.DataFrame):
        numeric_cols = {c for c in df_out.columns if c.endswith(" - P1") or c.endswith(" - R1") or c.endswith(" - Diff")}

        threshold = float(self.threshold_pct.value())

        class TotalsThresholdModel(DynamicNumericModel):
            def __init__(self, df, numeric_cols, fmt="{:,.2f}"):
                super().__init__(df, numeric_cols=numeric_cols, fmt=fmt)
                self._threshold = threshold

            def data(self, index, role=Qt.DisplayRole):
                out = super().data(index, role)
                if role == Qt.BackgroundRole:
                    col = self._df.columns[index.column()]
                    if isinstance(col, str) and col.endswith(" - Diff"):
                        base = col[:-len(" - Diff")]
                        try:
                            diff = float(self._df.iat[index.row(), index.column()])
                        except Exception:
                            return out
                        # read matching R1 cell in same row
                        r1_col = f"{base} - R1"
                        try:
                            r1 = float(self._df.at[self._df.index[index.row()], r1_col])
                        except Exception:
                            r1 = 0.0
                        denom = abs(r1)
                        if denom < 1e-12:
                            rel = 0.0 if abs(diff) < 1e-12 else float("inf")
                        else:
                            rel = abs(diff) * 100.0 / denom
                        if rel > self._threshold:
                            return QColor(255, 150, 150)
                        else:
                            return QColor(204, 255, 229)
                return out

        model = TotalsThresholdModel(df_out, numeric_cols=numeric_cols, fmt="{:,.2f}")
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(model)
        proxy.setSortRole(Qt.UserRole)  # numeric sort via UserRole
        self.table.setModel(proxy)

        # Default sort by the first selected product's Diff, if available
        diff_col_name = None
        if self._selected_products:
            first_prod = next(iter(self._selected_products))
            candidate = f"{first_prod} - Diff"
            if candidate in df_out.columns:
                diff_col_name = candidate
        if diff_col_name:
            diff_col = df_out.columns.get_loc(diff_col_name)
            self.table.sortByColumn(diff_col, Qt.DescendingOrder)

        # Equalize/fill after model is in place (proxy)
        self._sizer.defer_equalize()