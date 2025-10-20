# src/core/tab_policy.py
from dataclasses import dataclass

@dataclass
class InputsReady:
    p1_tse: bool
    p1_hier: bool
    r1: bool

def tabs_to_enable(inputs: InputsReady) -> dict[str, bool]:
    """
    Returns a mapping of tab keys -> enabled?
    Keys you can reference in MainWindow: 'TSE_SUMMARY','TSE_TOTALS','TSE_ANNUAL',
                                          'HIER_COMPARE','HIER_HEALTH','AE_OVERVIEW','AE_ANNUAL'
    """
    enable = {
        "TSE_SUMMARY": inputs.p1_tse and inputs.r1,
        "TSE_TOTALS":  inputs.p1_tse and inputs.r1,
        "TSE_ANNUAL":  inputs.p1_tse and inputs.r1,
        "HIER_COMPARE": inputs.p1_hier and inputs.r1,
        "HIER_HEALTH":  inputs.p1_hier and inputs.r1,
        "AE_OVERVIEW": False,  # wire later if needed
        "AE_ANNUAL":   False,
    }
    return enable