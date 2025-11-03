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
        

        if 'TSE ID' in df.columns and 'TECHNICAL_SUB_ENTITY_ID' not in df.columns:
            df['TECHNICAL_SUB_ENTITY_ID'] = (
                df['TSE ID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            )

        # Normalize Name (try common header spellings)
        possible_name_cols = ['TSE name', 'TSE Name', 'TSE NAME',
                            'TECHNICAL SUB ENTITY NAME', 'TECHNICAL_SUB_ENTITY_NAME']
        name_col_found = next((c for c in possible_name_cols if c in df.columns), None)
        df['TECHNICAL_SUB_ENTITY_NAME'] = (
            df[name_col_found].astype(str).str.strip() if name_col_found else pd.NA
        )


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
                elif value_str == 'SEC':
                    return pd.Series(['Low', 'YAP'])
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
        Build annualized P1 production at TSE level and KEEP:
        - TECHNICAL_SUB_ENTITY_ID
        - TECHNICAL_SUB_ENTITY_NAME
        so the UI can display TSE Name reliably.

        Steps:
        1) Identify production columns (01. .. 22.)
        2) Melt wide -> long with ID + NAME kept in id_vars
        3) Aggregate to annual (average if multiple months, else keep as-is)
        4) Pivot years to columns
        5) Parse Production_Metric into PRODUCT / STREAM / EQUITY / CUT_OFF / TYPE
        6) Multiply by days in year
        7) Return tidy dataframe with ID + NAME + attributes + years
        """
        if self.df_transposed is None:
            self.load_p1tse()

        df = self.df_transposed.copy()

        # Ensure normalized TECHNICAL_SUB_ENTITY_ID exists (fallback from 'TSE ID')
        if 'TECHNICAL_SUB_ENTITY_ID' not in df.columns and 'TSE ID' in df.columns:
            df['TECHNICAL_SUB_ENTITY_ID'] = (
                df['TSE ID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            )

        # --- Identify production columns (e.g. '01. Cond ...' to '22. Gas ...') ---
        production_columns = []
        for i in range(1, 23):
            pattern = f"^{i:02d}\\."
            matching_cols = [col for col in df.columns if re.match(pattern, str(col))]
            production_columns.extend(matching_cols)

        if not production_columns:
            print("❌ No production columns found matching the pattern '01.' to '22.'")
            return pd.DataFrame()

        # --- Metadata columns to carry through ---
        # Keep both normalized ID and the original TSE ID (handy for debugging)
        metadata_cols = [
            'TECHNICAL_SUB_ENTITY_ID',
            'TECHNICAL_SUB_ENTITY_NAME',
            'TSE ID',
            'UNCERTAINTY',
            'VALUATION',
            'Year'
        ]
        missing_metadata = [c for c in metadata_cols if c not in df.columns]
        if missing_metadata:
            print(f"⚠️  Warning: Missing metadata columns: {missing_metadata}")
        metadata_cols = [c for c in metadata_cols if c in df.columns]

        # --- Melt to long ---
        df_melted = pd.melt(
            df,
            id_vars=metadata_cols,
            value_vars=production_columns,
            var_name='Production_Metric',
            value_name='Value'
        )

        # Remove ratio rows and cast to numeric
        df_melted = df_melted[~df_melted['Production_Metric'].str.contains('ratio', case=False, na=False)]
        df_melted['Value'] = pd.to_numeric(df_melted['Value'], errors='coerce')

        # --- Extract 4-digit year from 'Year' ---
        df_melted['YearOnly'] = df_melted['Year'].astype(str).str.extract(r'(\d{4})')[0]

        # --- Aggregate to annual (month-aware averaging) ---
        group_keys = [c for c in [
            'TECHNICAL_SUB_ENTITY_ID',
            'TECHNICAL_SUB_ENTITY_NAME',
            'TSE ID',
            'UNCERTAINTY',
            'VALUATION',
            'Production_Metric',
            'YearOnly'
        ] if c in df_melted.columns]

        counts = (
            df_melted
            .groupby(group_keys)
            .size()
            .reset_index(name='MonthCount')
        )

        df_annual = (
            df_melted
            .groupby(group_keys, as_index=False)
            .agg({'Value': 'sum'})
            .merge(counts, on=group_keys, how='left')
        )

        df_annual['Value'] = df_annual.apply(
            lambda r: r['Value'] / r['MonthCount'] if r['MonthCount'] and r['MonthCount'] > 1 else r['Value'],
            axis=1
        )

        # --- Pivot years to columns (keep ID + NAME in index) ---
        index_cols = [c for c in [
            'TECHNICAL_SUB_ENTITY_ID',
            'TECHNICAL_SUB_ENTITY_NAME',
            'TSE ID',
            'UNCERTAINTY',
            'VALUATION',
            'Production_Metric'
        ] if c in df_annual.columns]

        df_pivoted = (
            df_annual
            .pivot_table(index=index_cols, columns='YearOnly', values='Value')
            .reset_index()
        )

        # --- Parse Production_Metric into structured fields ---
        metric_components = df_pivoted['Production_Metric'].apply(self._parse_production_metric)
        df_pivoted['PRODUCT']        = metric_components.apply(lambda x: x.get('PRODUCT', ''))
        df_pivoted['EQUITY_SHARE']   = metric_components.apply(lambda x: x.get('EQUITY_SHARE', ''))
        df_pivoted['PRODUCT_STREAM'] = metric_components.apply(lambda x: x.get('PRODUCT_STREAM', ''))
        df_pivoted['CUT_OFF']        = metric_components.apply(lambda x: x.get('CUT_OFF', ''))
        df_pivoted['TYPE']           = metric_components.apply(lambda x: x.get('TYPE', ''))

        # --- Multiply by number of days in year ---
        def get_days_in_year(year):
            try:
                y = int(year)
                return 366 if ((y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)) else 365
            except (ValueError, TypeError):
                print(f"Warning: Invalid year '{year}', using 365 days as default")
                return 365

        # Strictly treat only 4-digit columns as year columns
        year_columns = [c for c in df_pivoted.columns if str(c).isdigit()]
        for y in year_columns:
            df_pivoted[y] = df_pivoted[y] * get_days_in_year(y)

        # --- Final tidy selection ---
        final_columns = [
            'TECHNICAL_SUB_ENTITY_ID', 'TECHNICAL_SUB_ENTITY_NAME',
            *(['TSE ID'] if 'TSE ID' in df_pivoted.columns else []),
            'UNCERTAINTY', 'VALUATION',
            'PRODUCT', 'EQUITY_SHARE', 'PRODUCT_STREAM', 'CUT_OFF', 'TYPE'
        ] + year_columns

        df_final = df_pivoted[[c for c in final_columns if c in df_pivoted.columns]].copy()
        print(df_final.head())
        self.df_production = df_final
        return self.df_production



if __name__ == "__main__":
    file_path = r"C:\Users\Bartlomiej.Sarwa\OneDrive - Shell\Desktop\Data\TSE MERO.XLSX"
    loader = LoaderP1TSE(file_path)
    df_transposed = loader.load_p1tse()

    print("\n--- Transposed Production Preview ---")
    print(df_transposed.head())

    df_production = loader.extract_production_data()
    print("\n--- Production Data Preview ---")
    print(df_production.head(10))
    df_production.to_csv(r"debug_outputs\testp1.csv")