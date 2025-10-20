# src/core/publish.py
import pandas as pd

def publish_tse(win, df: pd.DataFrame | None):
    if df is None: return
    win.tab_summary.set_data(df)
    win.tab_totals.set_data(df)
    win.tab_forecast.set_data(df)

def publish_hierarchy(win, hc_model, df: pd.DataFrame | None):
    if hc_model is None or df is None: return
    # Compare tab
    if hasattr(win.tab_hier_compare, "set_model"):
        win.tab_hier_compare.set_model(hc_model, df_compare=df)
    elif hasattr(win.tab_hier_compare, "set_data"):
        win.tab_hier_compare.set_data(df)
    # Health tab
    if hasattr(win.tab_hier_health, "set_model"):
        win.tab_hier_health.set_model(hc_model, df_compare=df)
    elif hasattr(win.tab_hier_health, "set_data"):
        win.tab_hier_health.set_data(df)