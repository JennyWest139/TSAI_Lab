"""ARMA-/GARCH-Ordungswahl (AIC oder Nutzerauswahl)."""

from __future__ import annotations

import itertools

from tslab.services.models_arma import fit_arma
from tslab.services.models_garch import fit_garch

DEFAULT_ARMA_CANDIDATES: tuple[tuple[int, int], ...] = tuple(
    (p, q)
    for p in range(4)
    for q in range(4)
    if p + q > 0
)

DEFAULT_GARCH_CANDIDATES: tuple[tuple[int, int], ...] = tuple(
    (p, q)
    for p in range(4)
    for q in range(4)
    if p + q > 0
)


def parse_order_list(raw: object) -> list[tuple[int, int]]:
    """'1,1' oder ['1,1', '2,1'] -> [(1,1), (2,1)]."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if "," in text:
            p, q = text.split(",", 1)
            return [(int(p.strip()), int(q.strip()))]
        return []
    out: list[tuple[int, int]] = []
    for item in raw if isinstance(raw, list) else [raw]:
        text = str(item).strip()
        if not text or "," not in text:
            continue
        p, q = text.split(",", 1)
        out.append((int(p.strip()), int(q.strip())))
    return out


def select_arma_order_by_aic(
    y,
    *,
    candidates: list[tuple[int, int]] | None = None,
    default: tuple[int, int] = (1, 1),
) -> tuple[int, int]:
    best_order = default
    best_aic = float("inf")
    for p, q in candidates or DEFAULT_ARMA_CANDIDATES:
        try:
            res, _ = fit_arma(y, (p, q))
            aic = float(res.aic)
            if aic < best_aic:
                best_aic = aic
                best_order = (p, q)
        except Exception:
            continue
    return best_order


def select_garch_order_by_aic(
    y,
    mode_config,
    *,
    candidates: list[tuple[int, int]] | None = None,
    default: tuple[int, int] = (1, 1),
) -> tuple[int, int]:
    best_order = default
    best_aic = float("inf")
    for p, q in candidates or DEFAULT_GARCH_CANDIDATES:
        try:
            fit = fit_garch(y, mode_config, garch_p=p, garch_q=q)
            aic = float(fit.aic)
            if aic < best_aic:
                best_aic = aic
                best_order = (p, q)
        except Exception:
            continue
    return best_order


def resolve_orders(
    *,
    order_mode: str,
    y,
    mode_config,
    arma_user: list[tuple[int, int]] | None = None,
    garch_user: list[tuple[int, int]] | None = None,
    default_arma: tuple[int, int] = (1, 1),
    default_garch: tuple[int, int] = (1, 1),
) -> tuple[tuple[int, int], tuple[int, int]]:
    mode = (order_mode or "auto").strip().lower()
    if mode == "user":
        arma = arma_user[0] if arma_user else default_arma
        garch = garch_user[0] if garch_user else default_garch
        return arma, garch
    return (
        select_arma_order_by_aic(y, default=default_arma),
        select_garch_order_by_aic(y, mode_config, default=default_garch),
    )


def order_table_rows(max_p: int = 3, max_q: int = 3) -> list[dict]:
    rows = []
    for p, q in itertools.product(range(max_p + 1), range(max_q + 1)):
        if p + q == 0:
            continue
        rows.append({"p": p, "q": q, "label": f"({p},{q})"})
    return rows
