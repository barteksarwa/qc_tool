# src/core/orchestrator.py
from __future__ import annotations
from typing import Optional, Tuple
import os
import pandas as pd

# loaders
from src.data.bronze.bronze_p1_tse import LoaderP1TSE
from src.data.bronze.bronze_p1_hier import LoaderP1Hierarchy
from src.data.bronze.bronze_r1 import R1Loader

# models
from src.data.models.tse_compare import TSEComparator
from src.data.models.hierarchy_compare import HierarchyComparison



class DataOrchestrator:
    """Owns file paths, cached DFs and derived builds. No Qt, easy to test."""

    def __init__(self) -> None:
        # paths
        self.p1_tse_path: Optional[str] = None
        self.p1_hier_path: Optional[str] = None
        self.p1_hier_sheet: Optional[str | int] = 0
        self.r1_path: Optional[str] = None

        # cached DFs
        self.df_p1_tse: Optional[pd.DataFrame] = None
        self.df_p1_hier: Optional[pd.DataFrame] = None
        self.df_r1_raw: Optional[pd.DataFrame] = None
        self.df_r1_hier: Optional[pd.DataFrame] = None

        # derived
        self.df_tse_compare: Optional[pd.DataFrame] = None
        self.df_hier_compare: Optional[pd.DataFrame] = None
        self.hc_model: Optional[HierarchyComparison] = None

    # ---------------- paths (clear caches if change) ----------------
    def set_p1_tse(self, path: Optional[str]) -> None:
        if path != self.p1_tse_path:
            self.p1_tse_path = path
            self.df_p1_tse = None
            self.df_tse_compare = None

    def set_p1_hierarchy(self, path: Optional[str], sheet: Optional[str | int] = 0) -> None:
        if path != self.p1_hier_path or sheet != self.p1_hier_sheet:
            self.p1_hier_path = path
            self.p1_hier_sheet = sheet
            self.df_p1_hier = None
            self.df_hier_compare = None
            self.hc_model = None

    def set_r1(self, path: Optional[str]) -> None:
        if path != self.r1_path:
            self.r1_path = path
            self.df_r1_raw = None
            self.df_r1_hier = None
            self.df_tse_compare = None
            self.df_hier_compare = None
            self.hc_model = None

    # ---------------- loads (no‑reload guard) ----------------
    def load_p1_tse(self) -> Optional[pd.DataFrame]:
        if self.df_p1_tse is not None or not self.p1_tse_path:
            return self.df_p1_tse
        loader = LoaderP1TSE(self.p1_tse_path)
        df = loader.extract_production_data()  # correct API for your loader
        self.df_p1_tse = df if isinstance(df, pd.DataFrame) else None
        rows = len(self.df_p1_tse) if isinstance(self.df_p1_tse, pd.DataFrame) else 0
        print(f"✅ P1 TSE loaded ({rows} rows): {os.path.basename(self.p1_tse_path)}")
        return self.df_p1_tse

    def load_p1_hierarchy(self) -> Optional[pd.DataFrame]:
        if self.df_p1_hier is not None or not self.p1_hier_path:
            return self.df_p1_hier
        sheet = 0 if self.p1_hier_sheet in (None, "", "None") else self.p1_hier_sheet
        loader = LoaderP1Hierarchy(self.p1_hier_path, sheet_name=sheet)
        df = loader.load()
        self.df_p1_hier = df if isinstance(df, pd.DataFrame) else None
        rows = len(self.df_p1_hier) if isinstance(self.df_p1_hier, pd.DataFrame) else 0
        print(f"✅ P1 Hierarchy loaded ({rows} rows): {os.path.basename(self.p1_hier_path)}")
        return self.df_p1_hier

    def load_r1(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        if self.df_r1_raw is not None and self.df_r1_hier is not None:
            return self.df_r1_raw, self.df_r1_hier
        if not self.r1_path:
            return None, None
        r1 = R1Loader(self.r1_path)
        self.df_r1_raw = r1.load_data()
        # hierarchy DF
        if hasattr(r1, "create_hierarchy_dataframe"):
            self.df_r1_hier = r1.create_hierarchy_dataframe()
        elif hasattr(r1, "create_project_hierarchy"):
            self.df_r1_hier = r1.create_project_hierarchy()
        elif hasattr(r1, "load_hierarchy"):
            self.df_r1_hier = r1.load_hierarchy()
        else:
            self.df_r1_hier = self.df_r1_raw
        print(f"✅ R1 raw loaded ({len(self.df_r1_raw) if self.df_r1_raw is not None else 0} rows)")
        print(f"🧱 R1 hierarchy cached ({len(self.df_r1_hier) if self.df_r1_hier is not None else 0} rows)")
        return self.df_r1_raw, self.df_r1_hier
    
        
    def _save_debug_df(self, df: pd.DataFrame | None, name: str) -> None:
        """Write a CSV snapshot into ./debug_outputs/ with a timestamp."""
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return
        from pathlib import Path
        out_dir = Path("debug_outputs")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"{name}_{ts}.csv"
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"📝 Debug saved: {path}")
        except Exception as e:
            print(f"⚠️ Could not write debug CSV {path}: {e}")


    # ---------------- derived builds (only when inputs are ready) ----------------
    def build_tse_compare(self) -> Optional[pd.DataFrame]:
        if self.df_tse_compare is not None:
            return self.df_tse_compare
        if not (self.p1_tse_path and self.r1_path):
            return None
        # Comparator reads from paths (consistent with your current models.py)
        comp = TSEComparator.from_paths(self.p1_tse_path, self.r1_path)
        self.df_tse_compare = comp.compare()
        print("📊 TSE comparison ready.")
        return self.df_tse_compare

    def build_hierarchy_compare(self):
        if self.df_hier_compare is not None and self.hc_model is not None:
            return self.hc_model, self.df_hier_compare
        if self.df_r1_hier is None or self.df_p1_hier is None:
            return None, None
        hc = HierarchyComparison()
        hc.set_p1(self.df_p1_hier)     # pass DFs directly (no re-read)
        hc.set_r1(self.df_r1_hier)
        self.df_hier_compare = hc.build()
        self.hc_model = hc
        print(f"✅ Hierarchy comparison ready ({len(self.df_hier_compare)} rows)")
        return hc, self.df_hier_compare