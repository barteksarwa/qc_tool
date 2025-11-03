import pandas as pd
import re
from io import StringIO
from pathlib import Path
from typing import Tuple

# ---------- CONFIG ----------
ITEM_TO_META = {
    "Production Oil": ("OIL", 100, "AFS"),
    "Production Gas": ("GAS", 100, "AFS"),
    "Sales Gas":      ("GAS", 100, "AFS"),   # computed
    "Fuel Gas":       ("GAS", 100, "CIO"),
    "Flare Gas":      ("GAS", 100, "F&L"),
    "Injection Gas":  ("GAS", 100, "INJ"),
    "Imported / Exported Gas": ("GAS", 100, "IMP"),
}

BASE_ITEM_REGEX = r"^(Production Oil|Production Gas|Fuel Gas|Flare Gas|Injection Gas|Imported / Exported Gas)"
def _file_tags_to_flags(file_path: str | Path) -> tuple[str, str]:
    """
    Derive (UNCERTAINTY, VALUATION) from file name:
      * contains 'SEC' -> ('Low', 'YAP')
      * contains 'MID' -> ('Best', 'PR')
      * otherwise blank strings (or choose a default)
    """
    name = Path(file_path).name.upper()
    if "SEC" in name:
        return "Low", "YAP"
    if "MID" in name:
        return "Best", "PR"
    if "LOW" in name:
        return "Low", "PR"
    if "HIGH" in name:
        return "High", "PR"
    return "", ""

def load_bronze(file_path: str | Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      bronze_wide: wide bronze table with years as columns
      bronze_long: long bronze table with Year/Value
    """
    # --- 1) Load CSV robustly (strip leading whitespace/BOM) ---
    p = Path(file_path)
    with open(p, "r", encoding="utf-8") as f:
        raw = f.read().lstrip()
    df = pd.read_csv(StringIO(raw))
    df.columns = [c.strip() for c in df.columns]

    # --- 2) Identify all year columns dynamically (YYYY) ---
    year_cols = sorted([c for c in df.columns if re.fullmatch(r"\d{4}", str(c))], key=int)

    # --- 3) Filter valid TSE rows ---
    if df["TSE ID"].dtype != "object":
        df["TSE ID"] = df["TSE ID"].astype("string")
    df["TSE Name"] = df["TSE Name"].astype("string")
    df = df.loc[df["TSE Name"].notna() & df["TSE ID"].notna()].copy()

    # --- 4) Normalize "Item 1" to base item ---
    df["BASE_ITEM"] = df["Item 1"].astype(str).str.extract(BASE_ITEM_REGEX)
    df = df.loc[df["BASE_ITEM"].notna()].copy()

    # --- 5) Long form for aggregation ---
    id_cols = ["Units", "TSE ID", "TSE Name", "BASE_ITEM"]
    long_df = df[id_cols + year_cols].melt(id_vars=id_cols, var_name="Year", value_name="Value")
    long_df["Value"] = pd.to_numeric(long_df["Value"], errors="coerce").fillna(0.0)

    # --- 6) Aggregate and compute Sales Gas ---
    grp_cols = ["TSE ID", "TSE Name", "Units", "Year", "BASE_ITEM"]
    agg = long_df.groupby(grp_cols, as_index=False)["Value"].sum()

    pivot = agg.pivot_table(
        index=["TSE ID", "TSE Name", "Units", "Year"],
        columns="BASE_ITEM",
        values="Value",
        aggfunc="sum",
        fill_value=0.0,
    )

    for c in ["Production Gas", "Fuel Gas", "Flare Gas", "Injection Gas", "Imported / Exported Gas"]:
        if c not in pivot.columns:
            pivot[c] = 0.0

    pivot["Sales Gas"] = (
        pivot["Production Gas"]
        - pivot["Fuel Gas"]
        - pivot["Flare Gas"]
        - pivot["Injection Gas"]
        - pivot["Imported / Exported Gas"]
    )

    # Back to long including Sales Gas
    pivot = pivot.reset_index()
    value_cols = [c for c in pivot.columns if c not in ["TSE ID", "TSE Name", "Units", "Year"]]
    long_sales = pivot.melt(
        id_vars=["TSE ID", "TSE Name", "Units", "Year"],
        value_vars=value_cols,
        var_name="BASE_ITEM",
        value_name="Value",
    )

    # Keep items we publish
    publish_items = [
        "Production Oil",
        "Production Gas",
        "Fuel Gas",
        "Flare Gas",
        "Injection Gas",
        "Imported / Exported Gas",
        "Sales Gas",
    ]
    long_sales = long_sales[long_sales["BASE_ITEM"].isin(publish_items)].copy()

    # --- 7) Map PRODUCT / EQUITY_SHARE / PRODUCT_STREAM ---
    meta = long_sales["BASE_ITEM"].map(ITEM_TO_META)
    long_sales["PRODUCT"] = meta.apply(lambda x: x[0] if isinstance(x, tuple) else None)
    long_sales["EQUITY_SHARE"] = meta.apply(lambda x: x[1] if isinstance(x, tuple) else None)
    long_sales["PRODUCT_STREAM"] = meta.apply(lambda x: x[2] if isinstance(x, tuple) else None)

    # --- 8) Drop rows where PRODUCT_STREAM is INJ or IMP ---
    long_sales = long_sales[~long_sales["PRODUCT_STREAM"].isin(["INJ", "IMP"])].copy()

    # --- 9) Add UNCERTAINTY and VALUATION based on file name ---
    uncertainty, valuation = _file_tags_to_flags(file_path)
    long_sales["UNCERTAINTY"] = uncertainty
    long_sales["VALUATION"] = valuation

    # --- 10) Produce bronze WIDE (years as columns) ---
    bronze_wide = long_sales.pivot_table(
        index=[
            "TSE ID",
            "TSE Name",
            "Units",
            "BASE_ITEM",
            "PRODUCT",
            "EQUITY_SHARE",
            "PRODUCT_STREAM",
            "UNCERTAINTY",
            "VALUATION",
        ],
        columns="Year",
        values="Value",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()

    bronze_wide = bronze_wide[
        [
            "TSE ID",
            "TSE Name",
            "Units",
            "PRODUCT",
            "EQUITY_SHARE",
            "PRODUCT_STREAM",
            "BASE_ITEM",
            "UNCERTAINTY",
            "VALUATION",
        ] + year_cols
    ]

    # --- 11) Bronze LONG (optional) ---
    bronze_long = long_sales[
        [
            "TSE ID",
            "TSE Name",
            "Units",
            "PRODUCT",
            "EQUITY_SHARE",
            "PRODUCT_STREAM",
            "BASE_ITEM",
            "Year",
            "Value",
            "UNCERTAINTY",
            "VALUATION",
        ]
    ].copy()

    return bronze_wide, bronze_long


if __name__ == "__main__":
    path = r"C:\Users\Bartlomiej.Sarwa\OneDrive - Shell\Desktop\Brazil\ARPR25\Input sheets to Anaplan\Tupi\SDF_Production_TE_TSE_2025_ARPR_SEC_Tupi_v1+v2 - emptied.csv"
    bronze_wide, bronze_long = load_bronze(path)

    print("Bronze (wide) sample:")
    print(bronze_wide.head(10))

    print("\nBronze (long) sample:")
    print(bronze_long.head(10))