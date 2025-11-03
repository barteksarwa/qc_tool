# src/data/models/tse_compare.py
from __future__ import annotations
import pandas as pd
from typing import Optional, Iterable

# Loaders (paths-based convenience)
from src.data.bronze.bronze_p1_tse import LoaderP1TSE
from src.data.bronze.bronze_r1 import R1Loader


class TSEComparator:
    """
    Compare P1 vs R1 production at TSE granularity.
    Preferred usage: set_p1_df(df), set_r1_df(df), then compare().
    Convenience: from_paths(p1_path, r1_path)
    """
    MERGE_KEYS = [
        "TECHNICAL_SUB_ENTITY_ID",
        "EQUITY_SHARE",
        "PRODUCT_STREAM",
        "PRODUCT",
        "UNCERTAINTY",
        "VALUATION",
        "CUT_OFF",
    ]

    def __init__(self):
        self.df_p1: Optional[pd.DataFrame] = None
        self.df_r1: Optional[pd.DataFrame] = None

    # ---------- API: dataframes ----------
    def set_p1_df(self, df: pd.DataFrame) -> "TSEComparator":
        self.df_p1 = df.copy()
        # Ensure rename 'TSE ID' -> 'TECHNICAL_SUB_ENTITY_ID'
        if "TECHNICAL_SUB_ENTITY_ID" not in self.df_p1.columns and "TSE ID" in self.df_p1.columns:
            self.df_p1 = self.df_p1.rename(columns={"TSE ID": "TECHNICAL_SUB_ENTITY_ID"})
        return self

    def set_r1_df(self, df: pd.DataFrame) -> "TSEComparator":
        self.df_r1 = df.copy()
        return self

    # ---------- API: paths convenience ----------
    @classmethod
    def from_paths(cls, p1_path: str, r1_path: str) -> "TSEComparator":
        inst = cls()
        # P1 TSE
        p1_loader = LoaderP1TSE(p1_path)
        df_p1 = p1_loader.extract_production_data()
        # R1
        r1_loader = R1Loader(r1_path)
        r1_loader.load_data()
        df_r1 = r1_loader.create_production_dataframe()
        return inst.set_p1_df(df_p1).set_r1_df(df_r1)

    # ---------- core compare ----------
    def compare(self) -> pd.DataFrame:
        if self.df_p1 is None or self.df_r1 is None:
            raise RuntimeError("Set P1 and R1 dataframes first or use from_paths().")

        p1 = self.df_p1.copy()
        r1 = self.df_r1.copy()

        # --- Normalization helpers ---
        def norm_id(s: pd.Series) -> pd.Series:
            return (
                s.astype(str)
                .str.strip()
                .str.upper()
                .str.replace(r"\.0$", "", regex=True)
            )

        def norm_enum(col: pd.Series) -> pd.Series:
            # For enumerations (e.g., EQUITY_SHARE, PRODUCT_STREAM, PRODUCT, etc.)
            return col.astype(str).str.strip().str.upper()

        # --- Normalize IDs ---
        if "TECHNICAL_SUB_ENTITY_ID" in p1.columns:
            p1["TECHNICAL_SUB_ENTITY_ID"] = norm_id(p1["TECHNICAL_SUB_ENTITY_ID"])
        if "TECHNICAL_SUB_ENTITY_ID" in r1.columns:
            r1["TECHNICAL_SUB_ENTITY_ID"] = norm_id(r1["TECHNICAL_SUB_ENTITY_ID"])

        # --- Normalize enum-like keys (EXCLUDING name) ---
        enum_keys = [k for k in self.MERGE_KEYS if k not in ("TECHNICAL_SUB_ENTITY_ID", "TECHNICAL_SUB_ENTITY_NAME")]
        for k in enum_keys:
            if k in p1.columns:
                p1[k] = norm_enum(p1[k])
            if k in r1.columns:
                r1[k] = norm_enum(r1[k])

        # --- Year columns (numbers as strings) ---
        p1_years = [c for c in p1.columns if str(c).isdigit()]
        r1_years = [c for c in r1.columns if str(c).isdigit()]
        common_years = sorted(set(p1_years).intersection(r1_years))

        # --- Keys for grouping / merging (NO name here) ---
        base_keys = [k for k in self.MERGE_KEYS if k != "TECHNICAL_SUB_ENTITY_NAME"]
        p1_keys = [k for k in base_keys if k in p1.columns]
        r1_keys = [k for k in base_keys if k in r1.columns]

        # --- Aggregate (sum) by keys ---
        p1_agg = p1.groupby(p1_keys)[p1_years].sum().reset_index() if p1_years else p1[p1_keys].drop_duplicates()
        r1_agg = r1.groupby(r1_keys)[r1_years].sum().reset_index() if r1_years else r1[r1_keys].drop_duplicates()

        # --- Carry UNITS from R1 (first per group) ---
        if "UNITS" in r1.columns:
            r1_units = r1.groupby(r1_keys)["UNITS"].first().reset_index()
            r1_agg = pd.merge(r1_agg, r1_units, on=r1_keys, how="left")

        # --- Ensure merge columns exist on both sides ---
        for k in base_keys:
            if k not in p1_agg.columns:
                p1_agg[k] = pd.NA
            if k not in r1_agg.columns:
                r1_agg[k] = pd.NA

        # --- Outer merge on base keys (NO name in the join) ---
        merged = pd.merge(
            p1_agg, r1_agg,
            on=base_keys,
            how="outer",
            suffixes=("_P1", "_R1"),
            indicator=True
        )

        # --- Add per-year diffs ---
        for y in common_years:
            p1_col = f"{y}_P1"
            r1_col = f"{y}_R1"
            if p1_col in merged.columns and r1_col in merged.columns:
                merged[f"{y}_Diff"] = merged[p1_col].fillna(0) - merged[r1_col].fillna(0)

        # --- Re-attach TECHNICAL_SUB_ENTITY_NAME by ID (prefer P1, then R1) ---
        name_cols = ["TECHNICAL_SUB_ENTITY_ID", "TECHNICAL_SUB_ENTITY_NAME"]
        candidates = []

        if "TECHNICAL_SUB_ENTITY_NAME" in p1.columns:
            # Use original case for names; only normalize ID
            nm = p1[name_cols].dropna(subset=["TECHNICAL_SUB_ENTITY_ID"]).copy()
            nm["TECHNICAL_SUB_ENTITY_ID"] = norm_id(nm["TECHNICAL_SUB_ENTITY_ID"])
            candidates.append(nm.drop_duplicates())

        if "TECHNICAL_SUB_ENTITY_NAME" in r1.columns:
            nm = r1[name_cols].dropna(subset=["TECHNICAL_SUB_ENTITY_ID"]).copy()
            nm["TECHNICAL_SUB_ENTITY_ID"] = norm_id(nm["TECHNICAL_SUB_ENTITY_ID"])
            candidates.append(nm.drop_duplicates())

        if candidates:
            name_map = pd.concat(candidates, ignore_index=True)
            # prefer first occurrence (P1 first because we appended it first)
            name_map = name_map.drop_duplicates(subset=["TECHNICAL_SUB_ENTITY_ID"], keep="first")
            merged = merged.merge(name_map, on="TECHNICAL_SUB_ENTITY_ID", how="left")

        # --- Presence flags ---
        merged["Present_P1"] = merged["_merge"].apply(lambda m: "✅" if m in ("both", "left_only") else "❌")
        merged["Present_R1"] = merged["_merge"].apply(lambda m: "✅" if m in ("both", "right_only") else "❌")

        # --- Reorder: base keys + NAME, then years/diffs, then others, then flags ---
        first = base_keys.copy()
        if "TECHNICAL_SUB_ENTITY_NAME" in merged.columns:
            first.insert(1, "TECHNICAL_SUB_ENTITY_NAME")  # right after ID

        year_and_diffs = [c for c in merged.columns if any(str(y) == c or c.startswith(f"{y}_") for y in common_years)]
        flags = ["Present_P1", "Present_R1", "_merge"]
        others = [c for c in merged.columns if c not in set(first + year_and_diffs + flags)]

        out = merged.loc[:, first + year_and_diffs + others + flags]
        return out