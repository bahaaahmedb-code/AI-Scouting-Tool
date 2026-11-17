"""Recency-weighted multi-season features for the main valuation model (Option B).

Each player's rate features are a weighted blend of up to three seasons:
    2025-26 -> 55 %,  2024-25 -> 30 %,  2023-24 -> 15 %
Weights are renormalised over the seasons a player actually has, so nobody is dropped
(a player with only 2025-26 data keeps 100 % of his current-season values).

Includes both outfield players (calibrated against `fbref_historical_2018_2025.csv`) and goalkeepers
(calibrated against `fbref_keepers_historical_2018_2025.csv`).
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from .aging import _find_historical_csv, _match_player_history
from .constants import GK_FEATURES, PER90_FEATURES

SEASON_WEIGHTS = {2026: 0.55, 2025: 0.30, 2024: 0.15}      # keyed by Season_End_Year
RATIO_FEATURES = list(PER90_FEATURES)
ADDITIVE_FEATURES = ["pass_accuracy"]
BLEND_FEATURES = RATIO_FEATURES + ADDITIVE_FEATURES + ["start_share"]

GK_RATIO_FEATURES = ["saves_p90", "goals_conceded_p90", "high_claims_p90", "long_balls_p90", "touches_p90", "ball_recovery_p90"]
GK_ADDITIVE_FEATURES = ["save_pct", "clean_sheet_pct", "pass_accuracy", "goals_prevented_p90"]
GK_BLEND_FEATURES = GK_RATIO_FEATURES + GK_ADDITIVE_FEATURES + ["start_share"]

MIN_PAIRS_PER_POSITION = 30


def load_history(data_path: Path) -> pd.DataFrame | None:
    p = _find_historical_csv(data_path)
    if p is None or not p.exists():
        return None
    return pd.read_csv(p, low_memory=False)


def load_gk_history(data_path: Path) -> pd.DataFrame | None:
    candidates = [
        data_path / "fbref_keepers_historical_2018_2025.csv",
        data_path.parent / "fbref_keepers_historical_2018_2025.csv",
        data_path.parent.parent / "fbref_keepers_historical_2018_2025.csv",
        data_path.parent.parent / "historical_datasets" / "fbref_keepers_2018_2025_merged.csv",
    ]
    for c in candidates:
        if c.exists():
            return pd.read_csv(c, low_memory=False)
    return None


def calibrate_history(d: pd.DataFrame, hist: pd.DataFrame, log=print) -> tuple[pd.DataFrame, dict]:
    """Rescale archive statistics to the 2025-26 (Kaggle) scale using outfield players present in both."""
    rows = []
    outfield = d[d["position"] != "G"]
    for i in outfield.index:
        ph = _match_player_history(d.loc[i], hist)
        ph = ph[(ph["Season_End_Year"] == 2025) & (ph["minutes"] >= 1200)]
        if ph.empty:
            continue
        h = ph.iloc[0]
        rows.append({"pos": d.at[i, "position"], **{f"cur_{f}": float(d.at[i, f]) for f in RATIO_FEATURES + ADDITIVE_FEATURES},
                     **{f"his_{f}": float(h[f]) for f in RATIO_FEATURES + ADDITIVE_FEATURES}})
    pairs = pd.DataFrame(rows)
    calib: dict = {"n_pairs": int(len(pairs)), "ratio": {}, "shift": {}}
    hist = hist.copy()

    def factor(sub: pd.DataFrame, f: str) -> float:
        c, h = sub[f"cur_{f}"].mean(), sub[f"his_{f}"].mean()
        return float(np.clip(c / h, 0.4, 2.5)) if h > 1e-6 and c > 1e-6 else 1.0

    for f in RATIO_FEATURES:
        glob = factor(pairs, f) if len(pairs) else 1.0
        per_pos = {}
        for pos in ("D", "M", "F"):
            sub = pairs[pairs["pos"] == pos] if len(pairs) else pairs
            per_pos[pos] = factor(sub, f) if len(sub) >= MIN_PAIRS_PER_POSITION else glob
        calib["ratio"][f] = per_pos
        hist[f] = hist[f] * hist["position"].map(per_pos).fillna(glob)
    for f in ADDITIVE_FEATURES:
        glob = float((pairs[f"cur_{f}"] - pairs[f"his_{f}"]).mean()) if len(pairs) else 0.0
        per_pos = {}
        for pos in ("D", "M", "F"):
            sub = pairs[pairs["pos"] == pos] if len(pairs) else pairs
            per_pos[pos] = float((sub[f"cur_{f}"] - sub[f"his_{f}"]).mean()) if len(sub) >= MIN_PAIRS_PER_POSITION else glob
        calib["shift"][f] = per_pos
        hist[f] = (hist[f] + hist["position"].map(per_pos).fillna(glob)).clip(40, 100)
    log(f"Calibrated archive to the 2025-26 scale using {calib['n_pairs']} players present in both sources")
    return hist, calib


def blend_multiseason(d: pd.DataFrame, hist_cal: pd.DataFrame, log=print, gk_hist: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    d = d.copy()
    all_blend_cols = list(dict.fromkeys(BLEND_FEATURES + GK_FEATURES))
    for f in all_blend_cols:
        if f in d.columns:
            d[f + "_cur"] = d[f]
    n_seasons = []
    for i in d.index:
        pos = d.at[i, "position"]
        if pos == "G":
            ph = _match_player_history(d.loc[i], gk_hist) if gk_hist is not None and not gk_hist.empty else pd.DataFrame()
            feat_list = [f for f in GK_BLEND_FEATURES if f in d.columns]
        else:
            ph = _match_player_history(d.loc[i], hist_cal)
            feat_list = BLEND_FEATURES

        seasons: dict[int, object] = {2026: d.loc[i]}
        if not ph.empty:
            for _, h in ph.iterrows():
                y = int(h["Season_End_Year"])
                if y in (2024, 2025) and float(h["minutes"]) >= 450:
                    seasons[y] = h
        wsum = sum(SEASON_WEIGHTS[y] for y in seasons)
        for f in feat_list:
            num, den = 0.0, 0.0
            for y, r in seasons.items():
                v = r[f] if (isinstance(r, pd.Series) and f in r.index) else (r.get(f, np.nan) if hasattr(r, "get") else np.nan)
                if v is None or pd.isna(v):
                    continue
                num += SEASON_WEIGHTS[y] * float(v)
                den += SEASON_WEIGHTS[y]
            if den > 0:
                d.at[i, f] = num / den
        d.at[i, "seasons_used"] = len(seasons)
        n_seasons.append(len(seasons))
        d.at[i, "weight_current"] = SEASON_WEIGHTS[2026] / wsum
    d["seasons_used"] = d["seasons_used"].astype(int)
    counts = {int(k): int(v) for k, v in pd.Series(n_seasons).value_counts().sort_index().items()}
    info = {"weights": {"2025-26": 0.55, "2024-25": 0.30, "2023-24": 0.15}, "players_by_seasons_used": counts,
            "blended_features": all_blend_cols, "not_blended": ["minutes", "age", "age_sq", "team_strength", "position", "nation_group"]}
    log(f"Recency-weighted features (55/30/15): players by seasons used = {counts}")
    return d, info
