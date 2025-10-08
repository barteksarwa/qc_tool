import pandas as pd
from src.data.loaders_r1 import R1Loader
from src.data.loadersp1tse import LoaderP1TSE

class P1R1Comparator:
    def __init__(self, p1_path: str, r1_path: str):
        self.p1_path = p1_path
        self.r1_path = r1_path
        self.df_p1 = None
        self.df_r1 = None
        self.df_comparison = None

    def load_data(self):
        """Load and prepare both P1 and R1 datasets."""
        print("📥 Loading P1 data...")
        p1_loader = LoaderP1TSE(self.p1_path)
        self.df_p1 = p1_loader.extract_production_data().copy()
        self.df_p1.rename(columns={"TSE ID": "TECHNICAL_SUB_ENTITY_ID"}, inplace=True)

        print("📥 Loading R1 data...")
        r1_loader = R1Loader(self.r1_path)
        r1_loader.load_data()
        self.df_r1 = r1_loader.create_production_dataframe().copy()

        print("✅ Both datasets loaded successfully.")
        
        # Debug: Check the data before merging
        print(f"📊 P1 data shape: {self.df_p1.shape}")
        print(f"📊 R1 data shape: {self.df_r1.shape}")
        print(f"🔍 P1 CUT_OFF values: {self.df_p1['CUT_OFF'].unique()}")
        print(f"🔍 R1 CUT_OFF values: {self.df_r1['CUT_OFF'].unique()}")

    def compare(self) -> pd.DataFrame:
        if self.df_p1 is None or self.df_r1 is None:
            self.load_data()

        merge_keys = [
            'TECHNICAL_SUB_ENTITY_ID', 'EQUITY_SHARE', 'PRODUCT_STREAM',
            'PRODUCT', 'UNCERTAINTY', 'VALUATION'
        ]

        # Identify all year columns (numbers only)
        p1_years = [c for c in self.df_p1.columns if c.isdigit()]
        r1_years = [c for c in self.df_r1.columns if c.isdigit()]
        all_years = sorted(set(p1_years).intersection(r1_years))

        # --- ✅ Normalize data types
        for key in merge_keys:
            self.df_p1[key] = self.df_p1[key].astype(str).str.strip().str.upper()
            self.df_r1[key] = self.df_r1[key].astype(str).str.strip().str.upper()

        # --- ✅ Drop CUT_OFF from R1 and aggregate P1 by merge_keys
        df_p1_agg = self.df_p1.groupby(merge_keys)[p1_years].sum().reset_index()
        df_p1_agg['SOURCE'] = 'P1'

        df_r1_agg = self.df_r1.groupby(merge_keys)[r1_years].sum().reset_index()
        df_r1_agg['SOURCE'] = 'R1'

        # --- ✅ Merge properly
        df_merged = pd.merge(
            df_p1_agg,
            df_r1_agg,
            on=merge_keys,
            how='outer',
            suffixes=('_P1', '_R1'),
            indicator=True
        )

        print(f"🔍 Merge result breakdown:")
        print(f"   - Both: {len(df_merged[df_merged['_merge'] == 'both'])}")
        print(f"   - P1 only: {len(df_merged[df_merged['_merge'] == 'left_only'])}")
        print(f"   - R1 only: {len(df_merged[df_merged['_merge'] == 'right_only'])}")

        # Create comparison columns for each year
        comparison_data = []
        for year in all_years:
            col_p1 = f"{year}_P1"
            col_r1 = f"{year}_R1"
            
            # Fill NaN values with 0 for comparison
            p1_values = df_merged[col_p1].fillna(0)
            r1_values = df_merged[col_r1].fillna(0)
            
            # Calculate difference
            diff = p1_values - r1_values
            
            # Store the comparison
            comparison_data.extend([
                pd.Series(p1_values, name=col_p1),
                pd.Series(r1_values, name=col_r1),
                pd.Series(diff, name=f"{year}_Diff")
            ])

        # Combine all comparison data
        comparison_df = pd.concat(comparison_data, axis=1)
        
        # Combine merge keys with comparison data
        final_columns = merge_keys + ['_merge'] + list(comparison_df.columns)
        df_comparison = pd.concat([
            df_merged[merge_keys + ['_merge']].reset_index(drop=True),
            comparison_df.reset_index(drop=True)
        ], axis=1)

        self.df_comparison = df_comparison
        print(f"✅ Comparison DataFrame created with {len(df_comparison)} rows and {len(df_comparison.columns)} columns.")

        # Analysis of the comparison
        self._analyze_comparison(df_comparison, all_years)

        return self.df_comparison

    def _analyze_comparison(self, df_comparison: pd.DataFrame, all_years: list):
        """Analyze the comparison results."""
        print("\n" + "="*50)
        print("📊 COMPARISON ANALYSIS")
        print("="*50)
        
        # Check unique values for key columns
        print("🔍 Unique values in key columns:")
        for col in ['EQUITY_SHARE', 'PRODUCT_STREAM', 'PRODUCT', 'UNCERTAINTY', 'VALUATION']:
            if col in df_comparison.columns:
                print(f"   {col}: {df_comparison[col].unique()}")
        
        # Analyze differences
        total_differences = 0
        significant_differences = 0
        
        for year in all_years:
            diff_col = f"{year}_Diff"
            if diff_col in df_comparison.columns:
                non_zero = (df_comparison[diff_col] != 0).sum()
                large_diff = (abs(df_comparison[diff_col]) > 100).sum()  # threshold for "significant"
                total_differences += non_zero
                significant_differences += large_diff
                
                print(f"📅 {year}: {non_zero} non-zero differences, {large_diff} significant differences")
        
        print(f"📈 Total non-zero differences across all years: {total_differences}")
        print(f"⚠️  Significant differences (>100): {significant_differences}")
        
        # Show some examples of differences
        if significant_differences > 0:
            print("\n🔍 Examples of significant differences:")
            diff_examples = []
            for year in all_years[:3]:  # Show first 3 years
                diff_col = f"{year}_Diff"
                if diff_col in df_comparison.columns:
                    large_diffs = df_comparison[abs(df_comparison[diff_col]) > 100]
                    if len(large_diffs) > 0:
                        for _, row in large_diffs.head(2).iterrows():
                            diff_examples.append({
                                'TSE_ID': row['TECHNICAL_SUB_ENTITY_ID'],
                                'Year': year,
                                'P1_Value': row.get(f"{year}_P1", 0),
                                'R1_Value': row.get(f"{year}_R1", 0),
                                'Difference': row[diff_col]
                            })
            
            for example in diff_examples[:5]:  # Show up to 5 examples
                print(f"   TSE {example['TSE_ID']} - {example['Year']}: "
                      f"P1={example['P1_Value']:.2f}, R1={example['R1_Value']:.2f}, "
                      f"Diff={example['Difference']:.2f}")

    def get_matched_records(self) -> pd.DataFrame:
        """Get only records that exist in both P1 and R1."""
        if self.df_comparison is None:
            self.compare()
        return self.df_comparison[self.df_comparison['_merge'] == 'both'].copy()

    def get_p1_only_records(self) -> pd.DataFrame:
        """Get records that only exist in P1."""
        if self.df_comparison is None:
            self.compare()
        return self.df_comparison[self.df_comparison['_merge'] == 'left_only'].copy()

    def get_r1_only_records(self) -> pd.DataFrame:
        """Get records that only exist in R1."""
        if self.df_comparison is None:
            self.compare()
        return self.df_comparison[self.df_comparison['_merge'] == 'right_only'].copy()


if __name__ == "__main__":
    p1_path = r"C:\Users\Lenovo\Documents\python_projects\qc_tool\Empty P1.XLSX"
    r1_path = r"C:\Users\Lenovo\Documents\python_projects\qc_tool\Empty Visualizer (1).csv"

    comparator = P1R1Comparator(p1_path, r1_path)
    df_comparison = comparator.compare()
    
    # Save different types of comparisons
    df_comparison.to_csv(r"C:\Users\Lenovo\Documents\python_projects\qc_tool\debug_outputs\full_comparison.csv")
    comparator.get_matched_records().to_csv(r"C:\Users\Lenovo\Documents\python_projects\qc_tool\debug_outputs\matched_records.csv")
    comparator.get_p1_only_records().to_csv(r"C:\Users\Lenovo\Documents\python_projects\qc_tool\debug_outputs\p1_only_records.csv")
    comparator.get_r1_only_records().to_csv(r"C:\Users\Lenovo\Documents\python_projects\qc_tool\debug_outputs\r1_only_records.csv")
    
    print("\n--- Comparison Preview ---")
    print(df_comparison.head(10))