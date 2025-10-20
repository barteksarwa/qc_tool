
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView
from PySide6.QtCore import Qt
import pandas as pd

from .common.ui_table_utils import ColorPandasModel, EqualFillSizer


class HierarchyHealthTab(QWidget):
    """
    Simple AE-level view across sources (P1, R1, Anaplan):
      Columns:
        - Activity Entity in P1
        - Activity Entity in R1
        - Activity Entity in Anaplan
        - Comparison (Same)
      Rules:
        - We build a union of all AE names observed across available sources.
        - Display is the first original-cased value seen for that normalized AE per source.
        - "Comparison (Same)" is ✅ iff at least two sources are present and all present
          normalized AE values are identical; else ❌.
    """

    # canonical column names used by the comparison output
    AE_P1 = "ACTIVITY_ENTITY_NAME_P1"
    AE_R1 = "ACTIVITY_ENTITY_NAME_R1"

    # accept either *_AN or *_ANAPLAN for Anaplan source
    AE_AN_CANDIDATES = ("ACTIVITY_ENTITY_NAME_AN", "ACTIVITY_ENTITY_NAME_ANAPLAN")

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)

        title = QLabel("Hierarchy Health — Activity Entity (P1 / R1 / Anaplan)")
        title.setObjectName("HierarchyHealthTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(title)

        info = QLabel(
            "Shows Activity Entity names across sources (P1, R1, and Anaplan if present). "
            "“Comparison (Same)” is ✅ only when all present sources agree (case/trim-insensitive)."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = QTableView()
        root.addWidget(self.table)

        # Equalize columns and fill width on init and on resize
        self._sizer = EqualFillSizer(self.table, min_col_width=120, reapply_on_resize=True)

        self.reset_view()
        self._df_view = pd.DataFrame()

    # ---- Public API ----
    def set_model(self, hc, df_compare=None):
        """
        Accept the hierarchy comparison output (hc.df_out) and render the AE-level health view.
        """
        try:
            df = df_compare if isinstance(df_compare, pd.DataFrame) else getattr(hc, "df_out", None)
            if df is None or df.empty:
                self.reset_view()
                return

            out = self._build_ae_view(df)
            self._set_table(out)

        except Exception:
            import traceback
            print("⚠️ HierarchyHealthTab.set_model failed:")
            traceback.print_exc()
            self.reset_view()

    def reset_view(self):
        empty = pd.DataFrame(
            {
                "Activity Entity in P1": [],
                "Activity Entity in R1": [],
                "Activity Entity in Anaplan": [],
                "Comparison (Same)": [],
            }
        )
        self._set_table(empty)

    # ---- Internals ----
    def _set_table(self, df: pd.DataFrame):
        try:
            model = ColorPandasModel(df)
            self.table.setModel(model)
            self._df_view = df
            self._sizer.defer_equalize()
        except Exception:
            import traceback
            print("⚠️ _set_table failed:")
            traceback.print_exc()
            self.table.setModel(None)

    @staticmethod
    def _norm_series(s: pd.Series) -> pd.Series:
        return s.astype(str).str.strip().str.lower().replace({"nan": pd.NA, "": pd.NA})

    @staticmethod
    def _first_display_of_key(df: pd.DataFrame, col: str, key_norm: str) -> str:
        """
        Find the first original-cased value in df[col] whose normalized value equals key_norm.
        Returns "" if not found or column missing.
        """
        if col not in df.columns:
            return ""
        s = HierarchyHealthTab._norm_series(df[col])
        idx = s == key_norm
        if not idx.any():
            return ""
        raw = df.loc[idx, col].dropna()
        return "" if raw.empty else str(raw.iloc[0]).strip()

    def _resolve_anaplan_col(self, df: pd.DataFrame) -> str | None:
        for c in self.AE_AN_CANDIDATES:
            if c in df.columns:
                return c
        return None

    def _build_ae_view(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build a union of normalized AE keys across available sources.
        For each key, show the original-cased value per source and compute Same.
        """
        # Detect available sources
        has_p1 = self.AE_P1 in df.columns
        has_r1 = self.AE_R1 in df.columns
        ae_an = self._resolve_anaplan_col(df)
        has_an = ae_an is not None

        # Collect normalized AE keys from all present sources
        keys = set()
        if has_p1:
            keys |= set(self._norm_series(df[self.AE_P1]).dropna().unique().tolist())
        if has_r1:
            keys |= set(self._norm_series(df[self.AE_R1]).dropna().unique().tolist())
        if has_an:
            keys |= set(self._norm_series(df[ae_an]).dropna().unique().tolist())

        rows = []
        for k in sorted(keys):
            p1_disp = self._first_display_of_key(df, self.AE_P1, k) if has_p1 else ""
            r1_disp = self._first_display_of_key(df, self.AE_R1, k) if has_r1 else ""
            an_disp = self._first_display_of_key(df, ae_an, k) if has_an else ""

            # Compute sameness across present sources
            present = [x for x in [p1_disp, r1_disp, an_disp] if x]
            norms = {self._normalize_text(x) for x in present}
            same = "✅" if len(present) >= 2 and len(norms) == 1 else "❌"

            rows.append(
                {
                    "Activity Entity in P1": p1_disp,
                    "Activity Entity in R1": r1_disp,
                    "Activity Entity in Anaplan": an_disp,
                    "Comparison (Same)": same,
                }
            )

        # Keep a stable column order even if Anaplan is absent
        out = pd.DataFrame(rows, columns=[
            "Activity Entity in P1",
            "Activity Entity in R1",
            "Activity Entity in Anaplan",
            "Comparison (Same)",
        ])
        if not has_an and "Activity Entity in Anaplan" in out.columns:
            # Keep the column but leave it blank; it helps the UI stay consistent
            pass
        return out

    @staticmethod
    def _normalize_text(v: str) -> str:
        return "" if v is None else str(v).strip().lower()
