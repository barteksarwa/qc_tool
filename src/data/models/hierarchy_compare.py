# src/data/models_hierarchy.py
"""
Hierarchy comparison between P1 and R1 focused on AE/TE by **names** (not IDs).

• Merge key = TECHNICAL_SUB_ENTITY_ID (TSE ID).
• Activity Entity (AE):
    - P1: ACTIVITY_ENTITY_NAME
    - R1: PMASTER_NAME  → mapped into ACTIVITY_ENTITY_NAME
• Technical Entity (TE):
    - P1: TECHNICAL_ENTITY_NAME
    - R1: PROJECT_NAME  → mapped into TECHNICAL_ENTITY_NAME
• Class-based API to match your project style.
• Bottom: explicit test block with your file paths (no CLI needed).
"""

from __future__ import annotations
from typing import Tuple, Optional
import pandas as pd


# ------------------------ normalization helpers ------------------------ #
def _norm_id(s: pd.Series) -> pd.Series:
    """Normalize IDs to robust mergeable strings (strip, remove .0, upper, NA)."""
    return (
        s.astype(str)
         .str.strip()
         .str.replace(r"\.0$", "", regex=True)
         .str.upper()
         .replace({"NAN": pd.NA})
    )

def _norm_name(s: pd.Series) -> pd.Series:
    """Normalize names for comparison (trim, lower, treat ''/nan as NA)."""
    return (
        s.astype(str)
         .str.strip()
         .replace({"nan": pd.NA, "": pd.NA})
         .str.lower()
    )

def _ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = pd.NA
    return out


# ------------------------ file loading helpers ------------------------ #
def load_p1_hierarchy_from_file(path: str, sheet_name: str | int | None = 0) -> pd.DataFrame:
    """
    Load P1 AE–TE–TSE hierarchy using your LoaderP1Hierarchy.
    Force a single sheet (default first) to avoid pandas dict return.
    """
    try:
        from src.data.bronze.bronze_p1_hier import LoaderP1Hierarchy  # preferred
    except Exception:
        from src.data.bronze.bronze_p1_hier import LoaderP1Hierarchy            # fallback

    sheet = 0 if sheet_name in (None, "", "None") else sheet_name
    loader = LoaderP1Hierarchy(path, sheet_name=sheet)
    df = loader.load()
    if isinstance(df, dict):
        df = next(iter(df.values()))
    return df


def _derive_r1_hierarchy_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fallback: derive R1 hierarchy directly from the raw R1 df (after load_data()).
    Maps PMASTER/PROJECT names into canonical AE/TE names.
    """
    df = df.copy()

    # Normalize TSE key
    if "TECHNICAL_SUB_ENTITY_ID" not in df.columns:
        for alt in ("TSE ID", "TSE_ID", "TSE"):
            if alt in df.columns:
                df = df.rename(columns={alt: "TECHNICAL_SUB_ENTITY_ID"})
                break

    # Canonical AE/TE NAMEs for R1
    if "ACTIVITY_ENTITY_NAME" not in df.columns:
        if "PMASTER_NAME" in df.columns:
            df["ACTIVITY_ENTITY_NAME"] = df["PMASTER_NAME"]
        else:
            df["ACTIVITY_ENTITY_NAME"] = pd.NA

    if "TECHNICAL_ENTITY_NAME" not in df.columns:
        if "PROJECT_NAME" in df.columns:
            df["TECHNICAL_ENTITY_NAME"] = df["PROJECT_NAME"]
        else:
            df["TECHNICAL_ENTITY_NAME"] = pd.NA

    keep = [
        "TECHNICAL_SUB_ENTITY_ID",
        "TECHNICAL_SUB_ENTITY_NAME",
        "ACTIVITY_ENTITY_NAME",     # ← from PMASTER_NAME
        "TECHNICAL_ENTITY_NAME",    # ← from PROJECT_NAME
        "UNIQUE_FIELD_NAME",
        "PMASTER_NAME", "PROJECT_NAME",  # raw reference
        "OBJECTIVE_ID", "OBJECTIVE_NAME", "PROJECT_ID", "PMASTER_ID"
    ]
    existing = [c for c in keep if c in df.columns]
    if "TECHNICAL_SUB_ENTITY_ID" not in existing:
        raise KeyError("R1 data lacks a 'TECHNICAL_SUB_ENTITY_ID' compatible column.")

    out = df.loc[:, existing].copy()
    out["TECHNICAL_SUB_ENTITY_ID"] = _norm_id(out["TECHNICAL_SUB_ENTITY_ID"])
    out = out.drop_duplicates(subset=["TECHNICAL_SUB_ENTITY_ID"]).reset_index(drop=True)
    return out


def load_r1_hierarchy_from_file(path: str) -> Tuple[pd.DataFrame, str]:
    """
    Load R1 hierarchy via R1Loader. If no explicit hierarchy method exists,
    derive a hierarchy from r1.df. Returns (df, method_used).
    """
    try:
        from src.data.bronze.bronze_r1 import R1Loader  # prefer package import
    except Exception:
        from src.data.bronze.bronze_r1 import R1Loader
    except Exception as exc:
        raise ImportError("Could not import R1Loader (expected module 'loaders_r1').") from exc

    r1 = R1Loader(path)
    if hasattr(r1, "load_data"):
        r1.load_data()

    if hasattr(r1, "create_hierarchy_dataframe"):
        df = r1.create_hierarchy_dataframe(); method = "create_hierarchy_dataframe"
    elif hasattr(r1, "create_project_hierarchy"):
        df = r1.create_project_hierarchy();  method = "create_project_hierarchy"
    elif hasattr(r1, "load_hierarchy"):
        df = r1.load_hierarchy();            method = "load_hierarchy"
    elif hasattr(r1, "df") and isinstance(getattr(r1, "df"), pd.DataFrame):
        return _derive_r1_hierarchy_from_df(r1.df), "derived_from_df"
    else:
        raise AttributeError(
            "R1Loader does not expose a hierarchy method and no 'df' attribute was found. "
            "Expected 'create_hierarchy_dataframe()', 'create_project_hierarchy()', or 'load_hierarchy()'."
        )

    # Ensure canonical AE/TE name columns exist (mapping PMASTER/PROJECT)
    df = df.copy()
    if "ACTIVITY_ENTITY_NAME" not in df.columns and "PMASTER_NAME" in df.columns:
        df["ACTIVITY_ENTITY_NAME"] = df["PMASTER_NAME"]
    if "TECHNICAL_ENTITY_NAME" not in df.columns and "PROJECT_NAME" in df.columns:
        df["TECHNICAL_ENTITY_NAME"] = df["PROJECT_NAME"]

    # Normalize key & de-dup by TSE
    if "TECHNICAL_SUB_ENTITY_ID" not in df.columns:
        for alt in ("TSE ID", "TSE_ID", "TSE"):
            if alt in df.columns:
                df = df.rename(columns={alt: "TECHNICAL_SUB_ENTITY_ID"})
                break
    df["TECHNICAL_SUB_ENTITY_ID"] = _norm_id(df["TECHNICAL_SUB_ENTITY_ID"])
    df = df.drop_duplicates(subset=["TECHNICAL_SUB_ENTITY_ID"]).reset_index(drop=True)
    return df, method


# ------------------------ comparison class ------------------------ #
class HierarchyComparison:
    """
    Class-based P1 vs R1 hierarchy comparison (AE/TE by NAMES, not IDs).
    Typical use within your existing orchestrator:

        hc = HierarchyComparison()
        hc.set_p1(df_p1_hierarchy)             # or hc.load_p1_file(p1_path, sheet)
        hc.set_r1(df_r1_hierarchy)             # or hc.load_r1_file(r1_path)
        df_compare = hc.build()
        hc.save_csv("hierarchy_comparison_output.csv")

    You can keep _run_comparison() as your main orchestrator and simply
    create/use this class as one step among others.
    """

    def __init__(self) -> None:
        self.df_p1: Optional[pd.DataFrame] = None
        self.df_r1: Optional[pd.DataFrame] = None
        self.df_out: Optional[pd.DataFrame] = None

    # ---- loading / setting ---- #
    def load_p1_file(self, path: str, sheet_name: str | int | None = 0) -> "HierarchyComparison":
        self.df_p1 = load_p1_hierarchy_from_file(path, sheet_name=sheet_name)
        return self

    def load_r1_file(self, path: str) -> "HierarchyComparison":
        df_r1, method = load_r1_hierarchy_from_file(path)
        print(f"[HierarchyComparison] R1 hierarchy built using: {method}")
        self.df_r1 = df_r1
        return self

    def set_p1(self, df_p1: pd.DataFrame) -> "HierarchyComparison":
        self.df_p1 = df_p1.copy()
        return self

    def set_r1(self, df_r1: pd.DataFrame) -> "HierarchyComparison":
        self.df_r1 = df_r1.copy()
        return self

    # ---- preparation ---- #
    @staticmethod
    def _prepare_p1(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        need = [
            "TECHNICAL_SUB_ENTITY_ID",
            "TECHNICAL_SUB_ENTITY_NAME",
            "ACTIVITY_ENTITY_NAME",
            "TECHNICAL_ENTITY_NAME",
        ]
        out = _ensure_cols(out, need)
        out["TECHNICAL_SUB_ENTITY_ID"] = _norm_id(out["TECHNICAL_SUB_ENTITY_ID"])

        # normalized name shadows for comparison
        out["_AE_NAME_norm"] = _norm_name(out["ACTIVITY_ENTITY_NAME"])
        out["_TE_NAME_norm"] = _norm_name(out["TECHNICAL_ENTITY_NAME"])

        keep = need + ["_AE_NAME_norm", "_TE_NAME_norm"]
        return out.loc[:, keep].drop_duplicates().reset_index(drop=True)

    @staticmethod
    def _prepare_r1(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        # Map PMASTER/PROJECT → canonical AE/TE names if needed
        if "ACTIVITY_ENTITY_NAME" not in out.columns and "PMASTER_NAME" in out.columns:
            out["ACTIVITY_ENTITY_NAME"] = out["PMASTER_NAME"]
        if "TECHNICAL_ENTITY_NAME" not in out.columns and "PROJECT_NAME" in out.columns:
            out["TECHNICAL_ENTITY_NAME"] = out["PROJECT_NAME"]

        # Ensure TSE key
        if "TECHNICAL_SUB_ENTITY_ID" not in out.columns:
            for alt in ("TSE ID", "TSE_ID", "TSE"):
                if alt in out.columns:
                    out = out.rename(columns={alt: "TECHNICAL_SUB_ENTITY_ID"})
                    break

        out = _ensure_cols(
            out,
            [
                "TECHNICAL_SUB_ENTITY_ID",
                "TECHNICAL_SUB_ENTITY_NAME",
                "ACTIVITY_ENTITY_NAME",
                "TECHNICAL_ENTITY_NAME",
                "UNIQUE_FIELD_NAME",
                "PMASTER_NAME",
                "PROJECT_NAME",
            ],
        )
        out["TECHNICAL_SUB_ENTITY_ID"] = _norm_id(out["TECHNICAL_SUB_ENTITY_ID"])
        out["_AE_NAME_norm"] = _norm_name(out["ACTIVITY_ENTITY_NAME"])
        out["_TE_NAME_norm"] = _norm_name(out["TECHNICAL_ENTITY_NAME"])

        keep = [
            "TECHNICAL_SUB_ENTITY_ID",
            "TECHNICAL_SUB_ENTITY_NAME",
            "ACTIVITY_ENTITY_NAME",
            "TECHNICAL_ENTITY_NAME",
            "UNIQUE_FIELD_NAME",  # useful in R1
            "PMASTER_NAME",       # raw reference
            "PROJECT_NAME",       # raw reference
            "_AE_NAME_norm", "_TE_NAME_norm",
        ]
        existing = [c for c in keep if c in out.columns]
        return out.loc[:, existing].drop_duplicates().reset_index(drop=True)

    # ---- build ---- #
    def build(self) -> pd.DataFrame:
        if self.df_p1 is None or self.df_r1 is None:
            raise RuntimeError("Both P1 and R1 hierarchy DataFrames must be set before build().")

        key = "TECHNICAL_SUB_ENTITY_ID"
        p1 = self._prepare_p1(self.df_p1)
        r1 = self._prepare_r1(self.df_r1)

        merged = pd.merge(
            p1, r1, on=key, how="outer", suffixes=("_P1", "_R1"), indicator=True
        )

        # Presence flags
        merged["P1_Present"] = merged["_merge"].map(lambda m: "✅" if m in ("both", "left_only") else "❌")
        merged["R1_Present"] = merged["_merge"].map(lambda m: "✅" if m in ("both", "right_only") else "❌")

        # Name match flags (only meaningful if both present)
        merged["AE_Name_Match"] = (
            merged["_AE_NAME_norm_P1"].notna()
            & merged["_AE_NAME_norm_R1"].notna()
            & (merged["_AE_NAME_norm_P1"] == merged["_AE_NAME_norm_R1"])
        ).map({True: "✅", False: "❌"})

        merged["TE_Name_Match"] = (
            merged["_TE_NAME_norm_P1"].notna()
            & merged["_TE_NAME_norm_R1"].notna()
            & (merged["_TE_NAME_norm_P1"] == merged["_TE_NAME_norm_R1"])
        ).map({True: "✅", False: "❌"})

        first_cols = [
            key,
            "TECHNICAL_SUB_ENTITY_NAME_P1", "TECHNICAL_SUB_ENTITY_NAME_R1",
            "ACTIVITY_ENTITY_NAME_P1", "ACTIVITY_ENTITY_NAME_R1",
            "TECHNICAL_ENTITY_NAME_P1", "TECHNICAL_ENTITY_NAME_R1",
            "AE_Name_Match", "TE_Name_Match",
            "UNIQUE_FIELD_NAME",  # from R1 if present
            "P1_Present", "R1_Present",
        ]
        first_cols = [c for c in first_cols if c in merged.columns]
        other_cols = [c for c in merged.columns if c not in first_cols and c != "_merge"]

        out = merged.loc[:, first_cols + other_cols]
        self.df_out = out
        return out

    # ---- utility ---- #
    def save_csv(self, path: str, encoding: str = "utf-8-sig") -> None:
        if self.df_out is None:
            raise RuntimeError("Nothing to save; call build() first.")
        self.df_out.to_csv(path, index=False, encoding=encoding)

if __name__ == "__main__":
    """
    CLI to build and inspect the P1 vs R1 hierarchy comparison.

    Examples:
      # Use the defaults (your file paths below) and save CSVs
      python -m src.data.hierarchy_compare --save

      # Specify sheet by index or name for the P1 workbook
      python -m src.data.hierarchy_compare --p1 "C:\\path\\AE-TE-TSE hierarchy.xlsx" --p1-sheet 0 --r1 "C:\\path\\Vis OP Approved.csv" --save
    """
    import argparse
    from pathlib import Path
    import pandas as pd
    import sys

    # --- defaults (edit to your local files) ---
    DEFAULT_P1 = r"C:\Users\Bartlomiej.Sarwa\OneDrive - Shell\Desktop\Data\AE-TE-TSE hierarchy_20251012193030.XLSX"
    DEFAULT_R1 = r"C:\Users\Bartlomiej.Sarwa\OneDrive - Shell\Desktop\Data\Vis OP Approved.csv"

    parser = argparse.ArgumentParser(description="Build P1 vs R1 hierarchy comparison and print diagnostics.")
    parser.add_argument("--p1", default=DEFAULT_P1, help="P1 hierarchy Excel path (AE–TE–TSE).")
    parser.add_argument("--p1-sheet", default="0", help="Sheet index or name (default: 0).")
    parser.add_argument("--r1", default=DEFAULT_R1, help="R1 Visualizer CSV path.")
    parser.add_argument("--save", action="store_true", help="Save outputs to ./debug_outputs/")
    args = parser.parse_args()

    # Parse sheet into int/name
    try:
        p1_sheet = int(args.p1_sheet)
    except ValueError:
        p1_sheet = args.p1_sheet if args.p1_sheet not in ("", "None", "none") else 0

    # Existence checks
    p1_path = Path(args.p1)
    r1_path = Path(args.r1)
    if not p1_path.exists():
        print(f"❌ P1 file not found: {p1_path}"); sys.exit(1)
    if not r1_path.exists():
        print(f"❌ R1 file not found: {r1_path}"); sys.exit(1)

    print(f"📄 P1: {p1_path}")
    print(f"📄 R1: {r1_path}")

    try:
        # Build comparison using your class API:
        #   - load_p1_file(path, sheet_name)
        #   - load_r1_file(path)
        #   - build()
        # These methods and class exist in your module. [1](https://my.shell.com/personal/bartlomiej_sarwa_shell_com/Documents/Microsoft%20Copilot%20Chat%20Files/load_p1_hier.py)
        hc = HierarchyComparison()
        hc.load_p1_file(str(p1_path), sheet_name=p1_sheet)
        hc.load_r1_file(str(r1_path))
        df = hc.build()

        print(f"✅ Hierarchy compare built: {len(df)} rows x {len(df.columns)} cols")
        print("• Columns:", list(df.columns))
        with pd.option_context("display.max_columns", 0, "display.width", 200):
            print("\n🔎 Head(10):")
            print(df.head(10))

        if args.save:
            out_dir = Path("debug_outputs")
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            (out_dir / f"hierarchy_compare_{ts}.csv").write_text(
                df.to_csv(index=False, encoding="utf-8-sig"), encoding="utf-8-sig"
            )
            # Also save the normalized sources that hc holds
            if isinstance(hc.df_p1, pd.DataFrame):
                (out_dir / f"p1_hierarchy_loaded_{ts}.csv").write_text(
                    hc.df_p1.to_csv(index=False, encoding="utf-8-sig"), encoding="utf-8-sig"
                )
            if isinstance(hc.df_r1, pd.DataFrame):
                (out_dir / f"r1_hierarchy_loaded_{ts}.csv").write_text(
                    hc.df_r1.to_csv(index=False, encoding="utf-8-sig"), encoding="utf-8-sig"
                )
            print(f"📝 Saved CSV snapshots in {out_dir.resolve()}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Failed to build hierarchy compare: {e}")
        sys.exit(2)