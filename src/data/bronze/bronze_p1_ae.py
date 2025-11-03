# src/data/load_p1_ae.py
from __future__ import annotations

import pandas as pd
from typing import Optional
from pathlib import Path
import re


class LoaderP1AE:
    """
    Loader for the P1 Activity Entity (AE) Excel ("AE forecast report for Linear WF QC tool ...").

    What it does (aligned with LoaderP1TSE preprocessing):
      • Reads the first sheet (or a given sheet).
      • Splits 'Uncertainty/Valuation' into two columns: UNCERTAINTY, VALUATION (same logic as TSE).
      • Extracts YearOnly as a 4-digit year from 'Year' (works for '2025 01' and '2028').
      • Renames and type-coerces the AE-level metrics you requested.
      • Keeps Status (from 'Capex Expex Status').

    Selected metrics (columns → canonical names & units):
      I   '01. BOE AfS - GES - rate'               → BOE_GES_AFS_RATE_D        (daily rate)
      J   '02. Cond AfS - SWIS - rate'             → COND_SWIS_AFS_RATE_D      (daily rate)
      K   '02. NGL AfS - SWIS - rate'              → NGL_SWIS_AFS_RATE_D       (daily rate)
      L   '02. Oil AfS - SWIS - rate'              → OIL_SWIS_AFS_RATE_D       (daily rate)
      M   '03. Cond AfS - GES - rate'              → COND_GES_AFS_RATE_D       (daily rate)
      N   '03. NGL AfS - GES - rate'               → NGL_GES_AFS_RATE_D        (daily rate)
      O   '03. Oil AfS - GES - rate'               → OIL_GES_AFS_RATE_D        (daily rate)
      P   '04. Gas AfS - SWIS - yr volume'         → GAS_SWIS_AFS_VOL_Y        (annual volume)
      Q   '05. Gas AfS - GES - yr volume'          → GAS_GES_AFS_VOL_Y         (annual volume)
      R   '06. Gas CiO - SWIS (or GES) - yr volume'→ GAS_CIO_VOL_Y             (annual volume)

    Notes:
      - We avoid ratio fields (08–13.*) on purpose.
      - Names above match the headers visible in the sample sheet you provided.
    """

    # Raw headers we expect in the AE forecast report (see uploaded workbook)
    COL_PE_NAME = "PE name"
    COL_AE_NAME = "AE name"
    COL_AE_ID = "AE ID"
    COL_STATUS = "Capex Expex Status"
    COL_UV = "Uncertainty/Valuation"
    COL_YEAR = "Year"

    # Production columns to pick (header → canonical)
    PROD_MAP = {
        "01. BOE AfS - GES - rate": "BOE_GES_AFS_RATE_D",
        "02. Cond AfS - SWIS - rate": "COND_SWIS_AFS_RATE_D",
        "02. NGL AfS - SWIS - rate": "NGL_SWIS_AFS_RATE_D",
        "02. Oil AfS - SWIS - rate": "OIL_SWIS_AFS_RATE_D",
        "03. Cond AfS - GES - rate": "COND_GES_AFS_RATE_D",
        "03. NGL AfS - GES - rate": "NGL_GES_AFS_RATE_D",
        "03. Oil AfS - GES - rate": "OIL_GES_AFS_RATE_D",
        "04. Gas AfS - SWIS - yr volume": "GAS_SWIS_AFS_VOL_Y",
        "05. Gas AfS - GES - yr volume": "GAS_GES_AFS_VOL_Y",
        "06. Gas CiO - SWIS (or GES) - yr volume": "GAS_CIO_VOL_Y",
    }

    def __init__(self, path: str, sheet_name: Optional[str | int] = 0):
        self.path = str(path)
        self.sheet_name = sheet_name
        self.df_p1_ae: Optional[pd.DataFrame] = None

    # ----- internal helpers -----
    @staticmethod
    def _split_uncertainty_valuation(series: pd.Series) -> pd.DataFrame:
        """
        Mirror the splitting logic from LoaderP1TSE: handle 'Low', 'High', 'SEC', and 'X Y' forms.
        """
        def split_value(value):
            if pd.isna(value):
                return pd.Series(["", ""])
            s = str(value).strip()
            if s == "Low":
                return pd.Series(["Low", "PR"])
            elif s == "High":
                return pd.Series(["High", "PR"])
            elif s == "SEC":
                return pd.Series(["Low", "YAP"])
            elif " " in s:
                a, b = s.split(" ", 1)
                return pd.Series([a, b])
            else:
                return pd.Series([s, ""])

        out = series.apply(split_value)
        out.columns = ["UNCERTAINTY", "VALUATION"]
        return out

    @staticmethod
    def _year_only(series: pd.Series) -> pd.Series:
        """
        Extract a 4-digit year from values like '2025 01' OR '2028'.
        (Different from TSE's '(YYYY)' pattern; this matches the AE file.)
        """
        return series.astype(str).str.extract(r"(\d{4})")[0]

    @staticmethod
    def _to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    # ----- public API -----
    def load(self) -> pd.DataFrame:
        """
        Load the AE forecast Excel and return a cleaned DataFrame named df_p1_ae.
        """
        # Read the sheet
        df = pd.read_excel(self.path, sheet_name=self.sheet_name, engine="openpyxl")

        # Split Uncertainty/Valuation like in TSE
        if self.COL_UV in df.columns:
            uv = self._split_uncertainty_valuation(df[self.COL_UV])
            df = pd.concat([df.drop(columns=[self.COL_UV]), uv], axis=1)

        # YearOnly using a regex that fits '2025 01' / '2028'
        if self.COL_YEAR in df.columns:
            df["YearOnly"] = self._year_only(df[self.COL_YEAR])

        # Pick identity/descriptor columns (keep if present)
        id_cols = [c for c in [self.COL_PE_NAME, self.COL_AE_NAME, self.COL_AE_ID, self.COL_STATUS,
                               self.COL_YEAR, "YearOnly", "UNCERTAINTY", "VALUATION"]
                   if c in df.columns]

        # Build the production selection using header → canonical mapping
        prod_existing = {k: v for k, v in self.PROD_MAP.items() if k in df.columns}
        prod_cols_raw = list(prod_existing.keys())

        # Subset + rename
        keep_cols = id_cols + prod_cols_raw
        df = df.loc[:, keep_cols].copy()
        df = df.rename(columns=prod_existing)

        # Coerce numeric on metric columns
        metric_cols = list(prod_existing.values())
        df = self._to_numeric(df, metric_cols)

        # Rename ID columns to canonical uppercase (optional, consistent with TSE style)
        rename_ids = {
            self.COL_PE_NAME: "PE_NAME",
            self.COL_AE_NAME: "ACTIVITY_ENTITY_NAME",
            self.COL_AE_ID: "ACTIVITY_ENTITY_ID",
            self.COL_STATUS: "STATUS",
            self.COL_YEAR: "YEAR",
        }
        df = df.rename(columns={k: v for k, v in rename_ids.items() if k in df.columns})

        # Final ordering: IDs, status, UV fields, year fields, then metrics
        ordered = [c for c in ["PE_NAME", "ACTIVITY_ENTITY_NAME", "ACTIVITY_ENTITY_ID",
                               "STATUS", "UNCERTAINTY", "VALUATION", "YEAR", "YearOnly"]
                   if c in df.columns] + metric_cols
        df = df.loc[:, ordered]

        self.df_p1_ae = df
        return self.df_p1_ae


# ----- CLI test -----
if __name__ == "__main__":
    # Minimal CLI to exercise the loader on your local file path
    PATH = r"C:\Users\Bartlomiej.Sarwa\OneDrive - Shell\Desktop\Data\AE forecast report for Linear WF QC tool_20251008153353.XLSX"
    try:
        loader = LoaderP1AE(PATH, sheet_name=0)
        df = loader.load()
        print(f"✅ Loaded AE forecast: {len(df)} rows x {len(df.columns)} cols")
        print("• Columns:", list(df.columns))
        with pd.option_context("display.max_columns", 0, "display.width", 180):
            print("\n🔎 Head(10):")
            print(df.head(10))
    except Exception as e:
        import traceback
        print("❌ Failed to load P1 AE:", e)
        traceback.print_exc()