# src/utils/uncertainty_handler.py
from config.settings import UNCERTAINTY_MAP

def get_scenarios(df):
    available = set(df['Uncertainty/Valuation'].unique())
    normalized = {v: k for k, v in UNCERTAINTY_MAP.items() if any(k in str(u) for u in available)}
    return list(normalized.keys())