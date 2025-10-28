# src/core/publish.py
import traceback

def publish_tse(win, df):
    if df is None:
        return
    try:
        win.tab_summary.set_data(df)
        win.tab_totals.set_data(df)
        win.tab_forecast.set_data(df)
    except Exception:
        print("⚠️ publish_tse failed:")
        traceback.print_exc()

def _try_publish_one(tab, hc_model, df) -> bool:
    """
    Try (in order):
      1) set_model(model, df_compare=df)
      2) set_model(model)
      3) set_data(df)
    Returns True if any call succeeded, False otherwise.
    """
    # 1) set_model(model, df_compare=df)
    try:
        if hasattr(tab, "set_model"):
            try:
                tab.set_model(hc_model, df_compare=df)
                return True
            except TypeError:
                # signature doesn't accept df_compare
                tab.set_model(hc_model)
                return True
    except Exception:
        print(f"⚠️ {tab.__class__.__name__}.set_model(...) failed:")
        traceback.print_exc()

    # 3) set_data(df)
    try:
        if hasattr(tab, "set_data") and df is not None:
            tab.set_data(df)
            return True
    except Exception:
        print(f"⚠️ {tab.__class__.__name__}.set_data(df) failed:")
        traceback.print_exc()

    return False

def publish_hierarchy(win, hc_model, df):
    """
    Push hierarchy compare into tabs without ever crashing the UI.
    """
    try:
        ok1 = _try_publish_one(win.tab_hier_compare, hc_model, df)
        ok2 = _try_publish_one(win.tab_hier_health,  hc_model, df)
        if not (ok1 or ok2):
            print("⚠️ No compatible publish method found on hierarchy tabs (set_model / set_data).")
    except Exception:
        print("⚠️ publish_hierarchy failed:")
        traceback.print_exc()