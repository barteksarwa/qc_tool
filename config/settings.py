# config/settings.py
import calendar


DAYS_IN_YEAR = {year: 366 if calendar.isleap(year) else 365 for year in range(2025, 2101)}


UNCERTAINTY_MAP = {
    'SEC': 'Low YAP',
    'Low': 'Low PR',
    'Best PR': 'Best PR',
    'High': 'High PR'
}

# Product mapping: Normalize XLSX to CSV
PRODUCT_MAP = {
    'OIL': 'OIL',
    'COND': 'COND',
    'NGL': 'NGL',
    'GAS': 'GAS',
    'Oil': 'OIL',
    'Cond': 'COND'
}

# Stream mapping if needed
STREAM_MAP = {
    'AFS': 'AFS',
    'CIO': 'CIO',
    'SWIS': 'SWIS',
    'F&L': 'F&L'
}

REQUIRED_COLS_CSV = ['OBJECTIVE_NAME', 'UNCERTAINTY', 'PRODUCT']
REQUIRED_COLS_XLSX = ['TSE name', 'Uncertainty/Valuation', 'Year']