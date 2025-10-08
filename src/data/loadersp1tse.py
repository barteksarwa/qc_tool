import pandas as pd
import os
import re


class LoaderP1TSE:
    """
    Loader for P1 Technical Sub-Entity Excel files (transposed format).
    Columns A–H: Metadata
    Columns I–AP: Production data (transposed).
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.df_raw = None
        self.df_transposed = None

    def load_p1tse(self) -> pd.DataFrame:
        print(f"📂 Loading data from: {self.file_path}")
        df = pd.read_excel(self.file_path)
        if 'Uncertainty/Valuation' in df.columns:
            # FIX: Better handling of Uncertainty/Valuation splitting
            def split_uncertainty_valuation(value):
                if pd.isna(value):
                    return pd.Series(['', ''])
                value_str = str(value).strip()
                if value_str == 'Low':
                    return pd.Series(['Low', 'PR'])
                elif value_str == 'High':
                    return pd.Series(['High', 'PR'])
                elif ' ' in value_str:
                    parts = value_str.split(' ', 1)
                    return pd.Series([parts[0], parts[1]])
                else:
                    return pd.Series([value_str, ''])
            
            split_results = df['Uncertainty/Valuation'].apply(split_uncertainty_valuation)
            df[['UNCERTAINTY', 'VALUATION']] = split_results
            df.drop(columns=['Uncertainty/Valuation'], inplace=True)
            
            # Debug output to check the splitting
            print(f"🔍 UNCERTAINTY values after splitting: {df['UNCERTAINTY'].unique()}")
            print(f"🔍 VALUATION values after splitting: {df['VALUATION'].unique()}")
            
        df['YearOnly'] = df['Year'].astype(str).str.extract(r'(\d{4})')[0]
        self.df_transposed = df
        return self.df_transposed

    def _parse_production_metric(self, metric_string):
        """
        Parse production metric string into components:
        - Drop first 4 characters
        - Next word: PRODUCT
        - Next word after space: EQUITY_SHARE (capitalized)
        - Drop next 5 chars
        - Next expression until space: PRODUCT_STREAM
        - Next expression: CUT_OFF
        - Drop next 5 chars
        - Last expression: TYPE
        """
        try:
            # Remove first 4 characters
            remaining = metric_string[4:]
            
            # Split into components
            parts = remaining.split()
            
            # Extract components according to the pattern
            product = parts[0].upper() if len(parts) > 0 else ""
            product_stream = parts[1].upper() if len(parts) > 1 else ""
            
            # Join remaining parts and look for the pattern
            remaining_str = ' '.join(parts[2:]) if len(parts) > 2 else ""
            
            # More robust parsing using regex to handle the pattern
            pattern = r'^-\s+([^-]+?)\s+([^-]+?)\s+-\s+(.+)$'
            match = re.search(pattern, remaining_str)
            
            if match:
                equity_share = match.group(1).replace('%', '').strip()
                cut_off = match.group(2).replace('tr', 'Applied').replace('unt', 'Not Applied').strip()
                metric_type = match.group(3).strip()
            else:
                # Fallback: try simpler parsing
                stream_parts = remaining_str.split(' - ')
                if len(stream_parts) >= 3:
                    first_part = stream_parts[0].strip()
                    # Split first part to separate product_stream and cut_off
                    first_parts = first_part.split()
                    if len(first_parts) >= 2:
                        product_stream = first_parts[0]
                        cut_off = first_parts[1]
                    else:
                        product_stream = first_part
                        cut_off = ""
                    metric_type = stream_parts[2].strip()
                else:
                    product_stream = ""
                    cut_off = ""
                    metric_type = remaining_str
            
            return {
                'PRODUCT': product,
                'EQUITY_SHARE': equity_share,
                'PRODUCT_STREAM': product_stream,
                'CUT_OFF': cut_off,
                'TYPE': metric_type
            }
            
        except Exception as e:
            print(f"Warning: Could not parse metric string: {metric_string}. Error: {e}")
            return {
                'PRODUCT': "",
                'EQUITY_SHARE': "",
                'PRODUCT_STREAM': "",
                'CUT_OFF': "",
                'TYPE': ""
            }


    def extract_production_data(self) -> pd.DataFrame:
        """
        Extract production data with selected metadata and keep years as columns.
        Handles monthly → annual aggregation intelligently:
        - If multiple months exist → average over the available months
        - If only one record per year → use as-is (no division by 12)
        """
        if self.df_transposed is None:
            self.load_p1tse()
        
        # print("🔄 Extracting production data...")

        # --- Identify production columns (e.g. '01. Cond AfS...' to '22. Gas F&L...') ---
        production_columns = []
        for i in range(1, 23):
            pattern = f"^{i:02d}\\."
            matching_cols = [col for col in self.df_transposed.columns if re.match(pattern, str(col))]
            production_columns.extend(matching_cols)

        metadata_cols = ['TSE ID', 'UNCERTAINTY', 'VALUATION', 'Year']
        missing_metadata = [col for col in metadata_cols if col not in self.df_transposed.columns]
        if missing_metadata:
            print(f"⚠️  Warning: Missing metadata columns: {missing_metadata}")
            metadata_cols = [col for col in metadata_cols if col in self.df_transposed.columns]

        if not production_columns:
            print("❌ No production columns found matching the pattern '01.' to '22.'")
            return pd.DataFrame()

        # print(f"📊 Found {len(production_columns)} production columns")

        # --- Melt from wide to long format (one row per production metric per month) ---
        df_melted = pd.melt(
            self.df_transposed,
            id_vars=metadata_cols,
            value_vars=production_columns,
            var_name='Production_Metric',
            value_name='Value'
        )

        # Remove ratio columns and convert values to numeric
        df_melted = df_melted[~df_melted['Production_Metric'].str.contains('ratio', case=False, na=False)]
        df_melted['Value'] = pd.to_numeric(df_melted['Value'], errors='coerce')

        # print("Melted dataframe preview:")
        # print(df_melted.head(10))

        # --- Extract year number (e.g. '2025 01' → '2025') ---
        df_melted['YearOnly'] = df_melted['Year'].astype(str).str.extract(r'(\d{4})')[0]

        # --- COUNT how many entries (months) exist for each year per metric ---
        counts = (
            df_melted
            .groupby(['TSE ID', 'UNCERTAINTY', 'VALUATION', 'Production_Metric', 'YearOnly'])
            .size()
            .reset_index(name='MonthCount')
        )

        # --- AGGREGATE monthly values by summing ---
        df_annual = (
            df_melted
            .groupby(['TSE ID', 'UNCERTAINTY', 'VALUATION', 'Production_Metric', 'YearOnly'], as_index=False)
            .agg({'Value': 'sum'})
            .merge(counts, on=['TSE ID', 'UNCERTAINTY', 'VALUATION', 'Production_Metric', 'YearOnly'])
        )

        # --- NEW LOGIC: Adjust based on available months ---
        # If multiple months exist, average over those months
        # If only one record, keep value as-is
        df_annual['Value'] = df_annual.apply(
            lambda r: r['Value'] / r['MonthCount'] if r['MonthCount'] > 1 else r['Value'],
            axis=1
        )

        # --- Pivot to have years as columns ---
        df_pivoted = df_annual.pivot_table(
            index=['TSE ID', 'UNCERTAINTY', 'VALUATION', 'Production_Metric'],
            columns='YearOnly',
            values='Value'
        ).reset_index()

        # print("✅ Annualized pivoted dataframe preview:")
        # print(df_pivoted.head(10))
        # print("Numeric dtypes preview:")
        # print(df_pivoted.select_dtypes(include=['number']).dtypes.head())

        # # --- Parse Production_Metric into structured fields ---
        # print("🔍 Parsing Production_Metric column...")
        metric_components = df_pivoted['Production_Metric'].apply(self._parse_production_metric)

        df_pivoted['PRODUCT'] = metric_components.apply(lambda x: x['PRODUCT'])
        df_pivoted['EQUITY_SHARE'] = metric_components.apply(lambda x: x['EQUITY_SHARE'])
        df_pivoted['PRODUCT_STREAM'] = metric_components.apply(lambda x: x['PRODUCT_STREAM'])
        df_pivoted['CUT_OFF'] = metric_components.apply(lambda x: x['CUT_OFF'])
        df_pivoted['TYPE'] = metric_components.apply(lambda x: x['TYPE'])

                # --- Function to determine days in a year (handles leap years) ---
        def get_days_in_year(year):
            try:
                year_int = int(year)
                # Leap year: divisible by 4, but not by 100 unless also by 400
                if (year_int % 4 == 0 and year_int % 100 != 0) or (year_int % 400 == 0):
                    return 366
                return 365
            except (ValueError, TypeError):
                print(f"Warning: Invalid year '{year}', using 365 days as default")
                return 365

        # --- Reorder columns and apply correct days-in-year multiplier ---
        year_columns = [col for col in df_pivoted.columns if col not in 
                       ['TSE ID', 'UNCERTAINTY', 'VALUATION', 'Production_Metric', 
                        'PRODUCT', 'EQUITY_SHARE', 'PRODUCT_STREAM', 'CUT_OFF', 'TYPE']]
        for year_col in year_columns:
            days = get_days_in_year(year_col)
            df_pivoted[year_col] = df_pivoted[year_col] * days
            print(f"Applied {days} days for year {year_col}")
        
        final_columns = ['TSE ID', 'UNCERTAINTY', 'VALUATION', 
                        'PRODUCT', 'EQUITY_SHARE', 'PRODUCT_STREAM', 'CUT_OFF', 'TYPE'] + year_columns

        df_final = df_pivoted[final_columns]

        self.df_production = df_final
        # print(f"✅ Production data extracted: {len(df_final)} rows, {len(df_final.columns)} columns")

        return self.df_production



if __name__ == "__main__":
    file_path = r"C:\Users\Lenovo\Documents\python_projects\qc_tool\Empty P1.XLSX"
    loader = LoaderP1TSE(file_path)
    df_transposed = loader.load_p1tse()

    print("\n--- Transposed Production Preview ---")
    print(df_transposed.head())

    df_production = loader.extract_production_data()
    print("\n--- Production Data Preview ---")
    print(df_production.head(10))
    df_production.to_csv(r"C:\Users\Lenovo\Documents\python_projects\qc_tool\debug_outputs\testp1.csv")