import pandas as pd
import numpy as np
from typing import Optional, List
from datetime import datetime
import os


class R1Loader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.fixed_columns = [
            'VERSION_NAME', 'OBJECTIVE_ID', 'OBJECTIVE_NAME',
            'EQUITY_SHARE', 'PRODUCT_STREAM', 'PRODUCT',
            'UNCERTAINTY', 'VALUATION', 'CUT_OFF', 'APPROVAL',
            'PROJECT_NAME', 'PROJECT_ID', 'UNIQUE_FIELD_NAME',
            'TECHNICAL_SUB_ENTITY_NAME', 'TECHNICAL_SUB_ENTITY_ID', 
            'TECHNICAL_ENTITY_NAME', 'TECHNICAL_ENTITY_ID',
            'AOO_LOB_RS1_P1_HIERARCHY_ALIGNMENT',
            'PMASTER_NAME', 'PMASTER_ID',
            'RESOURCE_VOLUME_CLASS', 'RESOURCE_VOLUME_SUB_CLASS',
            'ECONOMIC_CUT_OFF', 'TECHNICAL_CUT_OFF_DATE', 
            'LICENCE_CUT_OFF_DATE', 'AE_CAPEX_EXPEX_STATUS', 'UNITS'
        ]
        self.df = None
        self.production_columns: List[str] = []

    def load_data(self) -> pd.DataFrame:
        print(f"📂 Loading data from: {self.file_path}")
        df = pd.read_csv(self.file_path)
        
        # 2) Diagnostics for the columns that threw DtypeWarning by index
        mixed_idx = [61, 62, 63, 64, 65, 66, 68, 70, 81, 87, 93, 108, 111, 112]
        mixed_idx = [i for i in mixed_idx if i < len(df.columns)]
        mixed_cols = [df.columns[i] for i in mixed_idx]

        if mixed_cols:
            print("🔎 Columns with mixed types (by index):", mixed_idx)
            print("🔎 Column names:", mixed_cols)
            print("\n🔎 Inferred dtypes for these columns:")


        self.production_columns = [
            col for col in df.columns if col.startswith("CURRENT_YEAR")
        ]
        self.production_columns.sort(key=self._sort_production_columns)
        base_year = datetime.now().year
        rename_map = {col: str(base_year + i) for i, col in enumerate(self.production_columns)}
        df = df.rename(columns=rename_map)
        all_columns = self.fixed_columns + list(rename_map.values())
        all_columns = [col for col in all_columns if col in df.columns]
        df['TECHNICAL_SUB_ENTITY_ID'] = (
            df['TECHNICAL_SUB_ENTITY_ID']
            .astype(str).str.strip()
            .str.replace(r'\.0$', '', regex=True)
            .replace({'nan': pd.NA})
        )
        self.df = df[all_columns].copy()
        print(f"✅ Loaded {len(self.df)} rows and {len(all_columns)} columns.")
        return self.df

    @staticmethod
    def _sort_production_columns(col: str) -> int:
        """Helper to sort production columns logically (CURRENT_YEAR, CURRENT_YEAR_1, etc.)."""
        if col == "CURRENT_YEAR":
            return 0
        try:
            return int(col.split("_")[-1])
        except ValueError:
            return float("inf")
        
    def create_project_hierarchy(self) -> pd.DataFrame:
        """
        Create a project hierarchy DataFrame with unique OBJECTIVE_IDs.
        """
        if self.df is None:
            raise ValueError("Data not loaded. Run load_data() first.")

        hierarchy_cols = [
            'VERSION_NAME', 'OBJECTIVE_ID', 'OBJECTIVE_NAME',
            'PROJECT_NAME', 'PROJECT_ID', 'UNIQUE_FIELD_NAME',
            'TECHNICAL_SUB_ENTITY_NAME', 'TECHNICAL_SUB_ENTITY_ID',
            'TECHNICAL_ENTITY_NAME', 'TECHNICAL_ENTITY_ID',
            'AOO_LOB_RS1_P1_HIERARCHY_ALIGNMENT',
            'PMASTER_NAME', 'PMASTER_ID',
        ]

        existing_cols = [col for col in hierarchy_cols if col in self.df.columns]
        self.df_project_hierarchy = (
            self.df[existing_cols]
            .drop_duplicates(subset=["TECHNICAL_SUB_ENTITY_ID"])
            .reset_index(drop=True)
        )

        print(f"🧱 Created project hierarchy DataFrame with {len(self.df_project_hierarchy)} unique OBJECTIVE_IDs.")
        return self.df_project_hierarchy
    
    def create_production_dataframe(self) -> pd.DataFrame:
        """
        Create a DataFrame with unique combinations of production attributes,
        plus all yearly production columns.
        """
        if self.df is None:
            raise ValueError("Data not loaded. Run load_data() first.")

        group_cols = [
            'TECHNICAL_SUB_ENTITY_ID', 'TECHNICAL_SUB_ENTITY_NAME', 'EQUITY_SHARE', 'PRODUCT_STREAM', 'PRODUCT',
            'UNCERTAINTY', 'VALUATION', 'CUT_OFF', 'APPROVAL'
        ]

        # Filter columns that exist in the loaded DataFrame
        group_cols = [col for col in group_cols if col in self.df.columns]
        year_cols = [col for col in self.df.columns if col.isdigit()]  # production years

        # Include units
        cols_to_keep = group_cols + ['UNITS'] + year_cols
        existing_cols = [col for col in cols_to_keep if col in self.df.columns]
        
        df_temp = self.df[existing_cols].copy()
        df_temp[year_cols] = df_temp[year_cols].fillna(0)
        # Aggregate by unique combination (sum production)
        df_grouped = (
            df_temp
            .groupby(group_cols + ['UNITS'], dropna=False)[year_cols]
            .sum()
            .reset_index()
        )

        self.df_production = df_grouped
        print(f"⚙️ Created production DataFrame with {len(df_grouped)} unique combinations.")
        return self.df_production
        

    def create_hierarchy_dataframe(self) -> pd.DataFrame:
        """Alias to create_project_hierarchy() for external callers."""
        return self.create_project_hierarchy()

    def load_hierarchy(self) -> pd.DataFrame:
        """Compatibility alias (returns the project hierarchy DF)."""
        if getattr(self, "df_project_hierarchy", None) is None:
            if getattr(self, "df", None) is None:
                raise ValueError("Data not loaded. Run load_data() first.")
            self.create_project_hierarchy()
        return self.df_project_hierarchy


if __name__ == "__main__":
    file_path = r"C:\Users\Bartlomiej.Sarwa\OneDrive - Shell\Desktop\Data\Visualizer 08102025 023302.csv"
    loader = R1Loader(file_path)
    df = loader.load_data()
    print(df.head())
    df_hierarchy = loader.create_project_hierarchy()
    df_production = loader.create_production_dataframe()
    print(df_hierarchy.head())
    print("\n--- Production Data ---")
    print(df_production.head())
    df_production.to_csv(r"debug_outputs\testr1.csv")

