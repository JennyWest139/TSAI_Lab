"""ARMA-Modelle (statsmodels) fuer TSA."""

from __future__ import annotations

import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

from tslab.services.models_ar import _with_monthly_freq
from tslab.services.stats_fit import suppress_optimizer_warnings


def fit_arma(
    y: pd.Series,
    order: tuple[int, int],
    *,
    method: str = "innovations_mle",
) -> tuple[object, pd.Series]:
    """ARMA(p,q) mit konstantem Term; Rueckgabe: Ergebnisobjekt, In-Sample-Fitted."""
    y = _with_monthly_freq(y)
    p, q = order
    model = ARIMA(y, order=(p, 0, q), trend="c")
    # innovations_mle: naher an R/arima; Default statespace landet oft in lokalem Minimum
    with suppress_optimizer_warnings():
        res = model.fit(method=method)
    fitted = pd.Series(res.fittedvalues, index=y.index, name="fitted")
    return res, fitted.dropna()
