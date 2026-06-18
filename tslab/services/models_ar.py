"""Einfache AR-Modelle (statsmodels) für Phase 0."""

from __future__ import annotations

import pandas as pd
from statsmodels.tsa.ar_model import AutoReg

from tslab.services.decomposition import pin_inferred_datetime_freq


def _with_monthly_freq(y: pd.Series) -> pd.Series:
    clean = y.dropna()
    if clean.index.freq is not None:
        return clean
    out = clean.copy()
    out.index = pin_inferred_datetime_freq(pd.DatetimeIndex(out.index))
    return out


def fit_ar(y: pd.Series, lags: int) -> tuple[object, pd.Series]:
    """AR(p) mit konstantem Term; Rückgabe: Ergebnisobjekt, In-Sample-Fitted."""
    y = _with_monthly_freq(y)
    model = AutoReg(y, lags=lags, trend="c", old_names=False)
    res = model.fit()
    fitted = pd.Series(res.fittedvalues, index=y.index[lags:], name="fitted")
    return res, fitted
