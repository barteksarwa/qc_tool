# src/ui/tab_hierarchy_compare.py
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QToolButton,
    QTableView
)
from PySide6.QtCore import Qt
import pandas as pd

from .common.ui_table_utils import ColorPandasModel, EqualFillSizer


class HierarchyCompareTab(QWidget):
    """
    Focused view of the merged hierarchy comparison (P1 vs R1 by TSE).

    Shown columns (in this order):
      AE (P1), AE (R1), TE (P1), TE (R1), TSE (P1), TSE (R1), Same
    - "Same" = ✅ when all 3 name pairs match (case-insensitive, trimmed); else ❌.
    - A dropdown (combo box) filters rows by UNIQUE_FIELD_NAME (not shown in the table).
    - Columns are user-resizable; an "Auto-fit" button sizes to contents.

    Accepts either:
      set_model(hc, df_compare=None)
      set_data(df)
    """

    # Source columns from the merged DF
    _AE_P1 = "ACTIVITY_ENTITY_NAME_P1"
    _AE_R1 = "ACTIVITY_ENTITY_NAME_R1"
    _TE_P1 = "TECHNICAL_ENTITY_NAME_P1"
    _TE_R1 = "TECHNICAL_ENTITY_NAME_R1"
    _TSE_P1 = "TECHNICAL_SUB_ENTITY_NAME_P1"
    _TSE_R1 = "TECHNICAL_SUB_ENTITY_NAME_R1"
    _UFN = "UNIQUE_FIELD_NAME"

    # Display names (rename mapping)
    _DISPLAY_RENAME = {
        _AE_P1: "AE (P1)",
        _AE_R1: "AE (R1)",
        _TE_P1: "TE (P1)",
        _TE_R1: "TE (R1)",
        _TSE_P1: "TSE (P1)",
        _TSE_R1: "TSE (R1)",
        "Same": "Same",
    }

    def __init__(self):
        super().__init__()

        # Data holders
        self._df_raw: pd.DataFrame = pd.DataFrame()         # full merged DF from model
        self._df_view_full: pd.DataFrame = pd.DataFrame()   # view DF incl. UNIQUE_FIELD_NAME (hidden)
        self._df_view_shown: pd.DataFrame = pd.DataFrame()  # what we render (without UFN)

        # ---- UI ----
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Hierarchy Comparison (P1 vs R1) — AE/TE/TSE")
        title.setObjectName("HierarchyCompareTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(title)

        # Filter row (UNIQUE_FIELD_NAME dropdown + auto-fit)
        filt_row = QHBoxLayout()
        filt_row.setSpacing(8)
        self._lab_ufn = QLabel("UNIQUE_FIELD_NAME:")
        self._cmb_ufn = QComboBox()
        self._cmb_ufn.currentIndexChanged.connect(self._apply_filter)
        self._btn_fit = QToolButton()
        self._btn_fit.setText("Auto‑fit")
        self._btn_fit.clicked.connect(self._auto_fit_columns)
        filt_row.addWidget(self._lab_ufn)
        filt_row.addWidget(self._cmb_ufn, stretch=1)
        filt_row.addWidget(self._btn_fit, stretch=0, alignment=Qt.AlignRight)
        root.addLayout(filt_row)

        # Table
        self.table = QTableView()
        root.addWidget(self.table)
        self._sizer = EqualFillSizer(self.table, min_col_width=80, reapply_on_resize=True)

        self.reset_view()

    # ---- Public API ----
    def reset_view(self):
        self._df_raw = pd.DataFrame()
        self._df_view_full = pd.DataFrame()
        self._df_view_shown = pd.DataFrame()
        self._set_table(self._df_view_shown)
        self._cmb_ufn.clear()
        self._cmb_ufn.setEnabled(False)
        self._lab_ufn.setText("UNIQUE_FIELD_NAME:")

    def set_model(self, hc, df_compare=None):
        """Accepts the HierarchyComparison model and optional built DF."""
        try:
            df = df_compare if isinstance(df_compare, pd.DataFrame) else getattr(hc, "df_out", None)
            self._handle_new_df(df)
        except Exception:
            import traceback
            print("⚠️ HierarchyCompareTab.set_model failed:")
            traceback.print_exc()
            self.reset_view()

    def set_data(self, df: pd.DataFrame):
        """Directly accept the merged comparison dataframe."""
        try:
            self._handle_new_df(df)
        except Exception:
            import traceback
            print("⚠️ HierarchyCompareTab.set_data failed:")
            traceback.print_exc()
            self.reset_view()

    # ---- Internals ----
    def _handle_new_df(self, df: pd.DataFrame | None):
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            self.reset_view()
            return

        self._df_raw = df.copy()

        # Build the full view DF (with UNIQUE_FIELD_NAME kept internally)
        self._df_view_full = self._build_view_df(self._df_raw)

        # Populate dropdown from UNIQUE_FIELD_NAME (sorted)
        if self._UFN in self._df_view_full.columns:
            values = (
                self._df_view_full[self._UFN]
                .dropna()
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )
            values = sorted(values, key=lambda s: s.lower())
            self._cmb_ufn.blockSignals(True)
            self._cmb_ufn.clear()
            self._cmb_ufn.addItem("All")  # first item = no filter
            for v in values:
                self._cmb_ufn.addItem(v)
            self._cmb_ufn.blockSignals(False)
            self._cmb_ufn.setEnabled(True)
            self._lab_ufn.setText("UNIQUE_FIELD_NAME:")
        else:
            # Column missing: disable filter, keep hint
            self._cmb_ufn.clear()
            self._cmb_ufn.setEnabled(False)
            self._lab_ufn.setText("UNIQUE_FIELD_NAME: (column not present)")

        # Apply current filter (initially "All")
        self._apply_filter()

        # Initial auto-fit so it looks good on first render
        self._auto_fit_columns(initial=True)

    @staticmethod
    def _norm_text(val) -> str:
        return "" if pd.isna(val) else str(val).strip().lower()

    def _build_view_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep UNIQUE_FIELD_NAME (for filter), the six comparison columns, and 'Same'."""
        want = []
        if self._UFN in df.columns:
            want.append(self._UFN)
        for c in (self._AE_P1, self._AE_R1, self._TE_P1, self._TE_R1, self._TSE_P1, self._TSE_R1):
            if c in df.columns:
                want.append(c)
        if not want:
            return pd.DataFrame()

        out = df.loc[:, want].copy()

        # Compute "Same" = all 3 pairs equal (case-insensitive, trimmed)
        def same_row(row) -> str:
            pairs = [
                (self._AE_P1, self._AE_R1),
                (self._TE_P1, self._TE_R1),
                (self._TSE_P1, self._TSE_R1),
            ]
            ok = True
            for a, b in pairs:
                if a in row and b in row:
                    va = self._norm_text(row[a])
                    vb = self._norm_text(row[b])
                    ok = ok and (va == vb)
            return "✅" if ok else "❌"

        out["Same"] = out.apply(same_row, axis=1)

        # Ensure preferred order (UFN first if present, then AE/TE/TSE pairs, then Same)
        ordered = []
        if self._UFN in out.columns:
            ordered.append(self._UFN)
        for c in (self._AE_P1, self._AE_R1, self._TE_P1, self._TE_R1, self._TSE_P1, self._TSE_R1, "Same"):
            if c in out.columns:
                ordered.append(c)
        out = out.loc[:, ordered]
        return out

    def _apply_filter(self):
        """Filter by UNIQUE_FIELD_NAME via the combo box. 'All' shows all rows."""
        try:
            if self._df_view_full.empty:
                self._set_table(pd.DataFrame())
                return

            df = self._df_view_full
            if (self._UFN not in df.columns) or (not self._cmb_ufn.isEnabled()):
                shown = df.copy()
            else:
                sel = self._cmb_ufn.currentText()
                if not sel or sel == "All":
                    shown = df.copy()
                else:
                    mask = df[self._UFN].astype(str).str.strip() == sel
                    shown = df.loc[mask].copy()

            # Drop the UFN column from presentation and rename headers
            if self._UFN in shown.columns:
                shown = shown.drop(columns=[self._UFN])
            shown = shown.rename(columns=self._DISPLAY_RENAME)
            shown.columns = [c.replace("_", " ") for c in shown.columns]

            self._df_view_shown = shown
            self._set_table(self._df_view_shown)
        except Exception:
            import traceback
            print("⚠️ HierarchyCompareTab._apply_filter failed:")
            traceback.print_exc()
            self._set_table(pd.DataFrame())

    def _set_table(self, df: pd.DataFrame | None):
        try:
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                df = pd.DataFrame()
            model = ColorPandasModel(df)
            self.table.setModel(model)
            self._sizer.defer_equalize()
        except Exception:
            import traceback
            print("⚠️ HierarchyCompareTab._set_table failed:")
            traceback.print_exc()
            self.table.setModel(None)

    def _auto_fit_columns(self, initial: bool = False):
        """Qt auto-fit; we still re-equalize to fill after initial render if needed."""
        try:
            self.table.resizeColumnsToContents()
            if initial:
                hdr = self.table.horizontalHeader()
                for i in range(hdr.count()):
                    width = hdr.sectionSize(i)
                    if width < 80:  # minimal comfortable width
                        hdr.resizeSection(i, 120)
            # Keep equal-fill look after auto-fit
            self._sizer.defer_equalize()
        except Exception:
            # never crash the UI for sizing
            pass