# src/data/loaderssdfp.py

import pandas as pd

class LoaderSDFP:
    """
    Standard Data Feeder - Production loader.
    TODO: implement schema & transformations.
    """
    def __init__(self, path: str):
        self.path = path

    def load(self) -> pd.DataFrame:
        if self.path.lower().endswith(".csv"):
            df = pd.read_csv(self.path)
        elif self.path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(self.path, engine="openpyxl")
        else:
            raise ValueError("Unsupported SDFP format; expected CSV or Excel.")
        # TODO: clean/normalize columns
        return df