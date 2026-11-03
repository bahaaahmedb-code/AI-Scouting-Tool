"""Feature engineering (notebook cell 11) and the target (cell 13)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import norm_name


def fill_xg_xa(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fill blank xG / xA.

    Ported exactly: xG uses a ratio *per position* (xG per shot); xA uses ONE league-wide ratio (xA per key pass).
    """
    d = d.copy()
    xg_ratio = d.groupby("position").apply(
        lambda g: g["expectedGoals"].sum() / g.loc[g["expectedGoals"].notna(), "totalShots"].sum())
    xa_ratio = d["expectedAssists"].sum() / d.loc[d["expectedAssists"].notna(), "keyPasses"].sum()
    d["xg_was_filled"] = d["expectedGoals"].isna()            # NEW (provenance)
    d["xa_was_filled"] = d["expectedAssists"].isna()          # NEW (provenance)
    d["xg_filled"] = d["expectedGoals"].fillna(d["totalShots"] * d["position"].map(xg_ratio))
    d["xa_filled"] = d["expectedAssists"].fillna(d["keyPasses"] * xa_ratio)
    info = {"xg_ratio_by_position": {k: float(v) for k, v in xg_ratio.items()}, "xa_ratio": float(xa_ratio),
            "blank_xg": int(d["xg_was_filled"].sum()), "blank_xa": int(d["xa_was_filled"].sum())}
    return d, info


def per90(value, minutes):
    """value / (minutes / 90)"""
    return value / (minutes / 90)


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d, info = fill_xg_xa(df)
    n90 = d["minutesPlayed"] / 90
    per90_src = {
        "goals_p90": d["goals"], "np_goals_p90": d["goals"] - d["penaltyGoals"], "assists_p90": d["assists"],
        "xg_p90": d["xg_filled"], "xa_p90": d["xa_filled"],
        "shots_p90": d["totalShots"], "shots_on_target_p90": d["shotsOnTarget"],
        "key_passes_p90": d["keyPasses"], "big_chances_created_p90": d["bigChancesCreated"],
        "dribbles_p90": d["successfulDribbles"], "was_fouled_p90": d["wasFouled"],
        "tackles_p90": d["tackles"], "tackles_won_p90": d["tacklesWon"], "interceptions_p90": d["interceptions"],
        "clearances_p90": d["clearances"], "ball_recovery_p90": d["ballRecovery"], "aerial_won_p90": d["aerialDuelsWon"],
        "dispossessed_p90": d["dispossessed"], "touches_p90": d["touches"],
        "yellow_p90": d["yellowCards"], "red_p90": d["redCards"],
    }
    for k, v in per90_src.items():
        d[k] = v / n90

    d["pass_accuracy"] = d["accuratePassesPercentage"]
    d["start_share"] = d["matchesStarted"] / d["appearances"].clip(lower=1)
    d["minutes"] = d["minutesPlayed"]
    d["age_sq"] = d["age"] ** 2
    top_nations = d["nation"].value_counts().head(6).index
    d["nation_group"] = np.where(d["nation"].isin(top_nations), d["nation"], "OTHER")
    d["team_strength"] = d.groupby("team_name").apply(
        lambda g: np.average(g["rating"], weights=g["minutesPlayed"])).reindex(d["team_name"]).values
    info["top_nations"] = list(top_nations)
    return d, info


# ---------------------------------------------------------------- target (cell 13)
def zscore(s):
    return (s - s.mean()) / s.std()


def make_synthetic_values(d: pd.DataFrame, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    att = zscore(d["xg_p90"] + d["xa_p90"])
    dfn = zscore(d["tackles_won_p90"] + d["interceptions_p90"] + d["ball_recovery_p90"] + d["clearances_p90"])
    w_att = d["position"].map({"F": 0.70, "M": 0.40, "D": 0.10})
    w_def = d["position"].map({"F": 0.00, "M": 0.20, "D": 0.45})
    log_m = (2.3 + w_att * att + w_def * dfn + 0.30 * zscore(d["minutes"])
             - 0.025 * (d["age"] - 25.5) ** 2 + 0.45 * zscore(d["team_strength"])
             + rng.normal(0, 0.5, len(d)))
    return (np.exp(log_m).clip(0.5, 150) * 1e6).round(-5)     # in euros, between 0.5M and 150M


def attach_real_values(d: pd.DataFrame, csv_path) -> tuple[pd.DataFrame, int]:
    mv = pd.read_csv(csv_path)                                   # needs columns: player_name, market_value_eur
    missing_cols = {"player_name", "market_value_eur"} - set(mv.columns)
    if missing_cols:
        raise ValueError(f"{csv_path} must contain columns player_name, market_value_eur (missing: {missing_cols})")
    mv["key"] = mv["player_name"].map(norm_name)
    mv = mv.sort_values("market_value_eur", ascending=False).drop_duplicates("key")
    out = d.merge(mv[["key", "market_value_eur"]], on="key", how="left")
    n_missing = int(out["market_value_eur"].isna().sum())
    return out.dropna(subset=["market_value_eur"]).reset_index(drop=True), n_missing


def attach_target(d: pd.DataFrame, settings) -> tuple[pd.DataFrame, dict]:
    if settings.target_is_synthetic:
        d = d.copy()
        d["market_value_eur"] = make_synthetic_values(d, settings.random_state)
        info = {"synthetic": True, "dropped_without_value": 0}
    else:
        d, n_missing = attach_real_values(d, settings.path(settings.market_value_csv))
        info = {"synthetic": False, "dropped_without_value": n_missing}
    d["log_value"] = np.log(d["market_value_eur"])
    return d, info
