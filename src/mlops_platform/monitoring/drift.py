"""CP13 reproducible, aggregate-only population-stability-index diagnostics.

Uses reference-only binning; unobserved categories are included as separate
buckets. Drift is descriptive and does not prove model performance degradation.
"""
from __future__ import annotations
import math
from typing import Iterable
import numpy as np
import pandas as pd


def population_stability_index(reference: Iterable, current: Iterable, *, bins: int = 10,
                               categorical: bool = False, epsilon: float = 1e-6) -> float:
    """PSI with stable epsilon smoothing, fixed reference bins and missing bucket.

    Numerical PSI uses quantile bins determined from the reference set; if
    there are no distinct cutpoints, falls back to one nonmissing bucket.
    """
    ref = pd.Series(list(reference))
    cur = pd.Series(list(current))
    if len(ref) == 0 or len(cur) == 0 or not 2 <= bins <= 100:
        raise ValueError("Both samples must be non-empty; bins must be 2..100")
    if categorical:
        a = ref.astype("string").fillna("<MISSING>")
        b = cur.astype("string").fillna("<MISSING>")
    else:
        a = pd.to_numeric(ref, errors="coerce").replace([np.inf, -np.inf], np.nan)
        b = pd.to_numeric(cur, errors="coerce").replace([np.inf, -np.inf], np.nan)
        valid_ref = a.dropna()
        if len(valid_ref):
            cuts = np.unique(np.quantile(valid_ref.to_numpy(), np.linspace(0, 1, bins + 1)[1:-1]))
            cuts = cuts[np.isfinite(cuts)]
        else:
            cuts = np.array([], dtype=float)
        a = pd.Series(np.searchsorted(cuts, a, side="right"), index=a.index).astype("string")
        b = pd.Series(np.searchsorted(cuts, b, side="right"), index=b.index).astype("string")
        a[ref.isna() | pd.to_numeric(ref, errors="coerce").isna()] = "<MISSING>"
        b[cur.isna() | pd.to_numeric(cur, errors="coerce").isna()] = "<MISSING>"
    categories = sorted(set(a.tolist()) | set(b.tolist()))
    ra = a.value_counts(dropna=False).reindex(categories, fill_value=0).to_numpy(dtype=float)
    ca = b.value_counts(dropna=False).reindex(categories, fill_value=0).to_numpy(dtype=float)
    # Add epsilon as pseudocount to keep probabilities finite and normalized.
    ra = (ra + epsilon) / (ra.sum() + epsilon * len(ra))
    ca = (ca + epsilon) / (ca.sum() + epsilon * len(ca))
    result = float(np.sum((ca - ra) * np.log(ca / ra)))
    if not math.isfinite(result) or result < -1e-10:
        raise ValueError("PSI numerical instability")
    return max(0.0, result)


def drift_report(reference: pd.DataFrame, current: pd.DataFrame,
                 numeric: list[str], categorical: list[str],
                 alert_threshold: float = 0.2, minimum_rows: int = 500) -> dict:
    columns = numeric + categorical
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("Features must be unique and non-empty")
    if any(name not in reference.columns or name not in current.columns for name in columns):
        raise ValueError("Input feature missing from one of the datasets")
    if minimum_rows < 1 or alert_threshold <= 0:
        raise ValueError("Invalid monitoring policy")
    nref, ncur = len(reference), len(current)
    if min(nref, ncur) == 0:
        raise ValueError("Empty monitoring dataset")
    features = {}
    for name in columns:
        psi = population_stability_index(reference[name], current[name], categorical=name in categorical)
        features[name] = {"psi": round(psi, 6), "alert": psi > alert_threshold,
                          "reference_missing_pct": round(float(reference[name].isna().mean()) * 100, 3),
                          "current_missing_pct": round(float(current[name].isna().mean()) * 100, 3)}
    complete = min(nref, ncur) >= minimum_rows
    return {"format": "project12_cp13_drift_v1", "reference_rows": nref, "current_rows": ncur,
            "minimum_rows": minimum_rows, "psi_alert_threshold": alert_threshold,
            "status": "INCONCLUSIVE" if not complete else ("ALERT" if any(x["alert"] for x in features.values()) else "MONITORED"),
            "features": features,
            "note": "Descriptive shift only. Do not infer downstream model performance or approve release automatically."}
