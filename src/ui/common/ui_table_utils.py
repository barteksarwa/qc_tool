# src/ui/common/ui_table_utils.py
from __future__ import annotations
from typing import Optional, Set, Callable
import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QEvent, QTimer, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableView, QHeaderView


# ---------- Formatting & normalization ----------
def norm_text(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


def norm_series_upper(s: pd.Series) -> pd.Series:
    return s.dropna().astype(str).str.strip().str.upper()


# ---------- Models ----------
class ColorPandasModel(QAbstractTableModel):
    """
    Simple model over a pandas DataFrame that centers text and colors ✅/❌ cells.
    """
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        value = "" if index.row() >= len(self._df) else str(self._df.iat[index.row(), index.column()])
        if role == Qt.DisplayRole:
            return value
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        if role == Qt.BackgroundRole and value in ["❌", "✅"]:
            # Red for mismatch (❌), green for aligned (✅)
            return QColor(255, 150, 150) if value == "❌" else QColor(204, 255, 229)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section]) if section < len(self._df.columns) else ""
            return str(section + 1)
        return None


class DynamicNumericModel(QAbstractTableModel):
    """
    Numeric-friendly model:
      - formats numeric columns for DisplayRole
      - exposes raw float in UserRole for correct sorting
      - optional background coloring via a predicate(col_name, value) -> QColor|None
    """
    def __init__(
        self,
        df: pd.DataFrame,
        numeric_cols: Optional[Set[str]] = None,
        bg_predicate: Optional[Callable[[str, float], Optional[QColor]]] = None,
        fmt: str = "{:,.2f}",
    ):
        super().__init__()
        self._df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        self._nums = set(numeric_cols) if numeric_cols else {
            c for c in self._df.columns if pd.api.types.is_numeric_dtype(self._df[c])
        }
        self._fmt = fmt
        self._bgp = bg_predicate

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section]) if section < len(self._df.columns) else ""
            return str(section + 1)
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = self._df.columns[index.column()]
        val = self._df.iat[index.row(), index.column()]
        is_num = col in self._nums

        if role == Qt.DisplayRole:
            if is_num:
                try:
                    return self._fmt.format(float(val))
                except Exception:
                    return ""
            return "" if pd.isna(val) else str(val)

        if role == Qt.UserRole and is_num:
            try:
                return float(val)
            except Exception:
                return 0.0

        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight if is_num else Qt.AlignLeft

        if role == Qt.BackgroundRole and self._bgp and is_num and pd.notna(val):
            try:
                return self._bgp(col, float(val))
            except Exception:
                return None

        return None


# ---------- Column sizing: equal & fill ----------

class EqualFillSizer(QObject):
    """
    Installs on a QTableView to keep columns equal and filling the viewport
    on init and after resizes (without blocking user's manual column drags).
    """
    def __init__(self, table: QTableView, min_col_width: int = 80, reapply_on_resize: bool = True):
        super().__init__(parent=table)  # parent to table so it is owned & cleaned up
        self.table = table
        self.min_col_width = int(min_col_width)
        self.reapply = bool(reapply_on_resize)
        self._defer = False

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.installEventFilter(self)  # now valid because we are a QObject

    # QObject event filter
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.table and self.reapply and event.type() == QEvent.Resize:
            self.defer_equalize()
        # return False to continue normal processing
        return False

    def defer_equalize(self):
        if self._defer:
            return
        self._defer = True
        QTimer.singleShot(0, self.equalize_and_fill)

    def equalize_and_fill(self):
        self._defer = False
        hdr = self.table.horizontalHeader()
        col_count = hdr.count()
        if col_count <= 0:
            return

        # Lock while sizing
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.Fixed)

        # Ensure geometry is up-to-date
        self.table.doItemsLayout()
        self.table.viewport().update()

        # Compute usable width
        viewport_w = self.table.viewport().width()

        # Deduct vertical header and vertical scrollbar widths if visible
        vh = self.table.verticalHeader()
        if vh and vh.isVisible():
            viewport_w -= vh.width()
        vsb = self.table.verticalScrollBar()
        if vsb and vsb.isVisible():
            viewport_w -= vsb.width()

        # Deduct inter-column grid gaps
        grid_gap = 1 if self.table.showGrid() else 0
        usable = viewport_w - max(0, col_count - 1) * grid_gap
        if usable <= 0:
            hdr.setSectionResizeMode(QHeaderView.Interactive)
            return

        base = max(self.min_col_width, usable // col_count)
        if base * col_count > usable:
            base = max(self.min_col_width, usable // col_count)
        total_base = base * col_count
        remainder = max(0, usable - total_base)

        for i in range(col_count):
            w = base + (1 if i < remainder else 0)
            hdr.resizeSection(i, w)

        # Return control to users
        hdr.setSectionResizeMode(QHeaderView.Interactive)


# ---------- Convenience: set a model and equalize ----------
def set_model_and_equalize(
    table: QTableView,
    model: QAbstractTableModel,
    *,
    min_col_width: int = 80,
    reapply_on_resize: bool = True,
) -> EqualFillSizer:
    """
    Set the provided model on the table and ensure columns are equal & filling.
    Returns the EqualFillSizer (keep a ref if you want explicit control).
    """
    table.setModel(model)
    sizer = EqualFillSizer(table, min_col_width=min_col_width, reapply_on_resize=reapply_on_resize)
    sizer.defer_equalize()  # perform after layout settles
    return sizer