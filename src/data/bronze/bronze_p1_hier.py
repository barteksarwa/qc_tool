import pandas as pd

class LoaderP1Hierarchy:
    """
    Loader for P1 hierarchy (AE–TE–TSE) Excel files.
    Produces a normalized DataFrame with columns:
      ACTIVITY_ENTITY_NAME, ACTIVITY_ENTITY_ID,
      TECHNICAL_ENTITY_NAME, TECHNICAL_ENTITY_ID,
      TECHNICAL_SUB_ENTITY_NAME, TECHNICAL_SUB_ENTITY_ID  (merge key)
    """

    _COL_MAP = {
        # Activity Entity
        "activity entity": "ACTIVITY_ENTITY_NAME",
        "activity entity name": "ACTIVITY_ENTITY_NAME",
        "activity entity id": "ACTIVITY_ENTITY_ID",
        "ae id": "ACTIVITY_ENTITY_ID",
        "pmaster_id": "ACTIVITY_ENTITY_ID",

        # Technical Entity
        "technical entity": "TECHNICAL_ENTITY_NAME",
        "technical entity name": "TECHNICAL_ENTITY_NAME",
        "technical entity id": "TECHNICAL_ENTITY_ID",
        "te id": "TECHNICAL_ENTITY_ID",

        # Technical Sub-Entity
        "technical sub entity": "TECHNICAL_SUB_ENTITY_NAME",
        "technical sub-entity": "TECHNICAL_SUB_ENTITY_NAME",
        "technical_sub_entity": "TECHNICAL_SUB_ENTITY_NAME",
        "technical sub entity id": "TECHNICAL_SUB_ENTITY_ID",
        "technical sub-entity id": "TECHNICAL_SUB_ENTITY_ID",
        "tse id": "TECHNICAL_SUB_ENTITY_ID",

        # Optional (R1)
        "objective name (r1)": "R1_OBJECTIVE_NAME",
        "objective id (r1)": "R1_OBJECTIVE_ID",
    }

    # >>> NEW: labels we expect to see in a promoted header row
    _HEADER_CANDIDATES = {
        "activity entity", "activity entity id",
        "technical entity", "technical entity id",
        "technical sub entity", "technical sub entity id",
        "technical sub-entity", "technical sub-entity id",
        "technical_sub_entity", "technical_sub_entity id",
        "tse id",
    }
    # <<< NEW

    def __init__(self, path: str, sheet_name: str | int | None = 0):
        self.path = path
        self.sheet_name = sheet_name  # 0 = first sheet by default

    # >>> NEW
    @staticmethod
    def _maybe_promote_header_row(df: pd.DataFrame) -> pd.DataFrame:
        """
        Detects cases where the real headers are in the first data row(s)
        and promotes that row to the column headers.
        Heuristic:
          - many 'Unnamed' columns, OR
          - current headers don't contain any of our key labels,
        and a top row contains 3+ of the expected header labels.
        """
        if df.empty:
            return df

        cols = [str(c) for c in df.columns]
        unnamed_ratio = sum(c.lower().startswith("unnamed") for c in cols) / max(len(cols), 1)
        have_key_in_cols = any(
            any(lbl in c.strip().lower() for lbl in LoaderP1Hierarchy._HEADER_CANDIDATES)
            for c in cols
        )
        if have_key_in_cols and unnamed_ratio < 0.4:
            # Looks fine; nothing to promote
            return df

        # Scan first few rows for a plausible header record
        scan_n = min(8, len(df))
        best_row_idx = None
        best_score = -1
        for i in range(scan_n):
            row_vals = df.iloc[i].astype(str).str.strip().str.lower().tolist()
            score = sum(1 for v in row_vals if v in LoaderP1Hierarchy._HEADER_CANDIDATES)
            if score > best_score:
                best_score = score
                best_row_idx = i

        if best_row_idx is not None and best_score >= 3:
            # Promote this row to header
            new_cols = df.iloc[best_row_idx].astype(str).str.strip().tolist()
            df = df.iloc[best_row_idx + 1 :].copy()
            df.columns = new_cols
            df = df.reset_index(drop=True)
            # Trim any all-empty columns after reheader
            df = df.dropna(axis=1, how="all")
            return df

        # No good header row found; return as-is
        return df
    # <<< NEW

    def load(self) -> pd.DataFrame:
        # Use first sheet when sheet_name is None, empty, or the string "None"
        sheet = 0 if self.sheet_name in (None, "", "None") else self.sheet_name

        df = pd.read_excel(self.path, engine="openpyxl", sheet_name=sheet)

        # If someone passed sheet=None, pick the first from dict
        if isinstance(df, dict):
            df = next(iter(df.values()))

        # Drop completely empty columns/rows
        df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")

        # >>> NEW: try to promote real header row if needed
        df = self._maybe_promote_header_row(df)
        # <<< NEW

        # Normalize column names via _COL_MAP
        rename_map = {}
        for c in df.columns:
            key = str(c).strip().lower().replace("\n", " ")
            rename_map[c] = self._COL_MAP.get(key, None)

        mapped = {orig: new for orig, new in rename_map.items() if new}
        df = df.rename(columns=mapped)

        # Trim strings for key text columns
        for col in [
            "ACTIVITY_ENTITY_NAME",
            "TECHNICAL_ENTITY_NAME",
            "TECHNICAL_SUB_ENTITY_NAME",
        ]:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str).str.strip().replace({"nan": pd.NA})
                )

        # Ensure IDs are strings, trimmed, drop '.0'
        for col in [
            "ACTIVITY_ENTITY_ID",
            "TECHNICAL_ENTITY_ID",
            "TECHNICAL_SUB_ENTITY_ID",
            "R1_OBJECTIVE_ID",
        ]:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str)
                           .str.strip()
                           .str.replace(r"\.0$", "", regex=True)
                           .replace({"nan": pd.NA})
                )

        # Keep only rows that have at least a TSE or AE/TE data
        essential_cols = [
            "ACTIVITY_ENTITY_ID",
            "TECHNICAL_ENTITY_ID",
            "TECHNICAL_SUB_ENTITY_ID",
        ]
        if any(c in df.columns for c in essential_cols):
            df = df.dropna(subset=[c for c in essential_cols if c in df.columns], how="all")

        # Reorder preferred columns first
        prefer = [
            "ACTIVITY_ENTITY_NAME", "ACTIVITY_ENTITY_ID",
            "TECHNICAL_ENTITY_NAME", "TECHNICAL_ENTITY_ID",
            "TECHNICAL_SUB_ENTITY_NAME", "TECHNICAL_SUB_ENTITY_ID",
            "R1_OBJECTIVE_NAME", "R1_OBJECTIVE_ID",
        ]
        ordered = [c for c in prefer if c in df.columns] + [c for c in df.columns if c not in prefer]
        df = df.loc[:, ordered]

        return df