# src/data/loadersanaplanhier.py

import pandas as pd

class LoaderAnaplanHier:
    """
    Anaplan DIS loader.
    TODO: implement schema & transformations.
    """
    def __init__(self, path: str):
        self.path = path

    def load(self) -> pd.DataFrame:
        p = self.path.lower()
        if p.endswith(".csv"):
            df = pd.read_csv(self.path)
        elif p.endswith((".xlsx", ".xls")):
            df = pd.read_excel(self.path, engine="openpyxl")
        else:
            raise ValueError("Unsupported Anaplan DIS format; expected CSV or Excel.")
        # TODO: clean/normalize columns
        return df