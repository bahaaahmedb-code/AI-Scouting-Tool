"""Similarity search for similar, cheaper players (notebook cells 35, 39, 45).

Changes agreed in the plan:
* D2: the price filter uses OUT-OF-FOLD estimates (target and candidates), not the listed value.
* D4: shared strengths = features where both players are above their position average (z > 0),
      ranked by the smaller of the two z-scores.
NEW: relaxation suggestions when a search returns no (or few) candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from .constants import RADAR, SIM_FEATURES


def position_zscores(d: pd.DataFrame) -> pd.DataFrame:
    """Each statistic converted to a z-score within the player's position."""
    return d.groupby("position")[SIM_FEATURES].transform(lambda s: (s - s.mean()) / s.std()).fillna(0)


def similarity_matrix(Z: pd.DataFrame) -> np.ndarray:
    return cosine_similarity(Z.to_numpy())


def radar_percentiles(d: pd.DataFrame) -> pd.DataFrame:
    return d.groupby("position")[RADAR].rank(pct=True) * 100


def shared_strengths(z_a: np.ndarray, z_b: np.ndarray, k: int = 3) -> list[str]:
    both = np.minimum(z_a, z_b)
    order = np.argsort(-both)
    return [SIM_FEATURES[j] for j in order[:k] if both[j] > 0]


@dataclass
class ScoutQuery:
    target: int
    same_position: bool = True
    position: str | None = None          # explicit position filter (overrides same_position)
    max_pct: float = 60.0                # % of the target's out-of-fold estimate
    max_age: int | None = None
    min_age: int | None = None
    max_eur: float | None = None         # absolute cap (chatbot: "under 30 million")
    min_eur: float | None = None
    n: int = 10
    exclude: list[int] = field(default_factory=list)


def _mask(d: pd.DataFrame, q: ScoutQuery, value_col: str, max_pct, max_age, pos_mode) -> np.ndarray:
    t = d.loc[q.target]
    m = np.ones(len(d), dtype=bool)
    m[q.target] = False
    for e in q.exclude:
        m[e] = False
    if pos_mode == "explicit":
        m &= (d["position"] == q.position).to_numpy()
    elif pos_mode == "same":
        m &= (d["position"] == t["position"]).to_numpy()
    if max_pct is not None:
        m &= (d[value_col] <= max_pct / 100 * t[value_col]).to_numpy()
    if q.max_eur is not None:
        m &= (d[value_col] <= q.max_eur).to_numpy()
    if q.min_eur is not None:
        m &= (d[value_col] >= q.min_eur).to_numpy()
    if max_age is not None:
        m &= (d["age"] <= max_age).to_numpy()
    if q.min_age is not None:
        m &= (d["age"] >= q.min_age).to_numpy()
    return m


def _pos_mode(q: ScoutQuery) -> str:
    if q.position:
        return "explicit"
    return "same" if q.same_position else "any"


def scout(d: pd.DataFrame, Z: pd.DataFrame, S: np.ndarray, q: ScoutQuery, value_col: str = "oof_value_eur") -> dict:
    pos_mode = _pos_mode(q)
    m = _mask(d, q, value_col, q.max_pct, q.max_age, pos_mode)
    idx = np.flatnonzero(m)
    sims = S[q.target, idx]
    order = idx[np.argsort(-sims, kind="stable")][: q.n]
    zt = Z.iloc[q.target].to_numpy()
    tv = float(d.at[q.target, value_col])
    rows = []
    for rank, c in enumerate(order, 1):
        v = float(d.at[c, value_col])
        rows.append({
            "rank": rank, "id": int(c), "similarity": float(S[q.target, c]),
            "value_eur": v, "pct_of_target": v / tv * 100,
            "shared_strengths": shared_strengths(zt, Z.iloc[c].to_numpy()),
        })
    return {"n_passed": int(m.sum()), "results": rows, "pos_mode": pos_mode,
            "suggestions": relax_suggestions(d, q, value_col, int(m.sum())) if len(rows) < min(q.n, 3) else []}


def relax_suggestions(d: pd.DataFrame, q: ScoutQuery, value_col: str, n_now: int) -> list[dict]:
    """For each filter, the smallest relaxation that adds candidates, e.g. 'Raising the limit to 70% adds 4 candidates.'"""
    out = []
    pos_mode = _pos_mode(q)
    if q.max_pct is not None:
        for pct in range(int(q.max_pct) + 10, 201, 10):
            n = int(_mask(d, q, value_col, pct, q.max_age, pos_mode).sum())
            if n > n_now:
                out.append({"filter": "max_pct", "value": pct, "adds": n - n_now,
                            "text": f"Raising the price limit to {pct}% adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
                break
    if q.max_age is not None:
        for age in range(q.max_age + 1, 41):
            n = int(_mask(d, q, value_col, q.max_pct, age, pos_mode).sum())
            if n > n_now:
                out.append({"filter": "max_age", "value": age, "adds": n - n_now,
                            "text": f"Raising the age limit to {age} adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
                break
    if pos_mode != "any":
        n = int(_mask(d, q, value_col, q.max_pct, q.max_age, "any").sum())
        if n > n_now:
            out.append({"filter": "position", "value": "any", "adds": n - n_now,
                        "text": f"Allowing any position adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
    if q.max_eur is not None:
        n = int(_mask(d, ScoutQuery(**{**q.__dict__, "max_eur": None}), value_col, q.max_pct, q.max_age, pos_mode).sum())
        if n > n_now:
            out.append({"filter": "max_eur", "value": None, "adds": n - n_now,
                        "text": f"Removing the euro cap adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
    return out
