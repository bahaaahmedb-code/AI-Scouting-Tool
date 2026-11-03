"""Runtime service: loads the build bundle once and answers every query from precomputed values.

All numbers that reach the website or the chatbot come from here.
"""
from __future__ import annotations

import math
from functools import cached_property
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .constants import (CAT_FEATURES, GROUPS, NUM_FEATURES, PER90_FEATURES, PERF_GROUPS, POS_NAME, RADAR,
                        RADAR_LABELS, SIM_FEATURES, TOOLTIPS, group_of, pretty)
from .data import norm_name
from .similarity import ScoutQuery, scout, shared_strengths

KEY_STATS = ["goals_p90", "xg_p90", "assists_p90", "xa_p90", "key_passes_p90", "dribbles_p90",
             "tackles_won_p90", "interceptions_p90", "aerial_won_p90", "pass_accuracy"]


def _f(x, nd=None):
    """JSON-safe float."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, nd) if nd is not None else x


def pct_change(c: float) -> float:
    """log points -> percent change in value"""
    return (math.exp(c) - 1) * 100


class Store:
    def __init__(self, bundle: dict):
        self.b = bundle
        self.d: pd.DataFrame = bundle["players"]
        self.shap = bundle["shap"]
        self.shap_feat: pd.DataFrame = bundle["shap_feat"]
        self.imp_feat: pd.Series = bundle["imp_feat"]
        self.Z: pd.DataFrame = bundle["Z"]
        self.S: np.ndarray = bundle["S"]
        self.pct_in_pos: pd.DataFrame = bundle["pct_in_pos"]
        self.radar_pct: pd.DataFrame = bundle["radar_pct"]
        self.results: pd.DataFrame = bundle["results"]
        self.chosen = bundle["chosen_model"]
        self.keys = self.d["player_name"].map(norm_name)
        self.train_idx = set(bundle["train_idx"])

    @classmethod
    def load(cls, artifacts_dir: Path) -> "Store":
        p = Path(artifacts_dir) / "bundle.joblib"
        if not p.exists():
            raise FileNotFoundError(f"{p} not found. Run the build step first: python -m app.build")
        return cls(joblib.load(p))

    # ------------------------------------------------------------------ basics
    @property
    def synthetic(self) -> bool:
        return bool(self.b["target_is_synthetic"])

    @property
    def n(self) -> int:
        return len(self.d)

    @cached_property
    def error(self) -> dict:
        r = self.results.loc[self.chosen]
        return {"cv_rmse_log": _f(r["cv_rmse_log"]), "cv_mae_log": _f(r["cv_mae_log"]),
                "cv_mae_eur": _f(r["cv_mae_eur"]), "cv_rmse_eur": _f(r["cv_rmse_eur"]),
                "cv_median_abs_pct": _f(r["cv_median_abs_pct"]), "cv_r2": _f(r["cv_r2_mean"])}

    def error_band(self, est: float) -> tuple[float, float]:
        """Typical range: estimate x/÷ exp(CV RMSE in log)."""
        k = math.exp(self.error["cv_rmse_log"])
        return est / k, est * k

    def meta(self) -> dict:
        d = self.d
        res = self.results.copy()
        return {
            "season": self.b["settings"]["season"], "kaggle_matchday": self.b["settings"]["kaggle_matchday"],
            "n_players": self.n, "by_position": {POS_NAME[k]: int(v) for k, v in d["position"].value_counts().items()},
            "clubs": sorted(d["team_name"].unique().tolist()), "min_minutes": self.b["settings"]["min_minutes"],
            "target_is_synthetic": self.synthetic, "target_label": self.b["target_label"],
            "is_sample_data": bool(self.b.get("is_sample_data")),
            "chosen_model": self.chosen, "best_by_cv": self.b["best_by_cv"], "model_setting": self.b["settings"]["model"],
            "cv_results": [{"model": m, **{k: _f(v, 4) for k, v in row.items()}} for m, row in res.iterrows()],
            "error": self.error, "counts": self.b["counts"], "feat_info": self.b["feat_info"],
            "train_size": len(self.b["train_idx"]), "test_size": len(self.b["test_idx"]),
            "shap_gap": _f(self.shap["gap"]), "base_eur": _f(self.b["base_eur"]), "built_at": self.b["built_at"],
            "num_features": NUM_FEATURES, "cat_features": CAT_FEATURES, "sim_features": SIM_FEATURES,
            "features": [{"key": f, "label": pretty(f), "group": group_of(f), "tooltip": TOOLTIPS.get(f, "")}
                         for f in NUM_FEATURES + CAT_FEATURES],
            "groups": GROUPS, "radar": [{"key": k, "label": l} for k, l in zip(RADAR, RADAR_LABELS)],
            "nation_groups": self.b["feat_info"]["top_nations"] + ["OTHER"],
        }

    # ------------------------------------------------------------------ players
    def summary(self, i: int) -> dict:
        r = self.d.loc[i]
        return {"id": int(i), "name": r["player_name"], "club": r["team_name"], "position": r["position"],
                "position_name": POS_NAME[r["position"]], "age": int(r["age"]), "minutes": int(r["minutes"]),
                "nation": r["nation"], "goals": _f(r.get("goals")), "assists": _f(r.get("assists")),
                "estimated_value_eur": _f(r["estimated_value_eur"]),
                "oof_value_eur": _f(r["oof_value_eur"]), "listed_value_eur": _f(r["market_value_eur"])}

    def search(self, q: str = "", club: str | None = None, position: str | None = None, limit: int = 20) -> list[dict]:
        d = self.d
        m = np.ones(len(d), dtype=bool)
        if club:
            m &= (d["team_name"] == club).to_numpy()
        if position:
            m &= (d["position"] == position).to_numpy()
        idx = np.flatnonzero(m)
        qn = norm_name(q)
        if qn:
            scored = []
            for i in idx:
                k = self.keys[i]
                if k.startswith(qn):
                    s = 0
                elif any(t.startswith(qn) for t in k.split()):
                    s = 1
                elif qn in k:
                    s = 2
                else:
                    continue
                scored.append((s, -d.at[i, "estimated_value_eur"], i))
            idx = [i for *_, i in sorted(scored)]
        else:
            idx = list(d.loc[idx].sort_values("estimated_value_eur", ascending=False).index)
        return [self.summary(i) for i in idx[:limit]]

    def position_average(self, pos: str) -> float:
        return float(self.d.loc[self.d["position"] == pos, "estimated_value_eur"].mean())

    def provenance(self, i: int) -> dict:
        r = self.d.loc[i]
        step = r.get("match_step")
        return {
            "in_kaggle": True, "in_fbref": bool(r.get("in_fbref", True)),
            "match_step": step, "kaggle_name": r.get("kaggle_name"), "fbref_name": r.get("fb_name"),
            "xg_filled": bool(r.get("xg_was_filled", False)), "xa_filled": bool(r.get("xa_was_filled", False)),
            "in_training": bool(i in self.train_idx),
        }

    def profile(self, i: int) -> dict:
        r = self.d.loc[i]
        est = float(r["estimated_value_eur"])
        lo, hi = self.error_band(est)
        pos_avg = self.position_average(r["position"])
        stats = []
        for f in NUM_FEATURES:
            if f == "age_sq":
                continue
            stats.append({"key": f, "label": pretty(f), "value": _f(r[f]), "group": group_of(f),
                          "pct_in_position": _f(self.pct_in_pos.at[i, f], 1), "tooltip": TOOLTIPS.get(f, ""),
                          "position_mean": _f(self.d.loc[self.d["position"] == r["position"], f].mean())})
        return {
            **self.summary(i), "born": _f(r.get("born")), "nation_group": r["nation_group"],
            "start_share": _f(r["start_share"]), "team_strength": _f(r["team_strength"]),
            "band_low_eur": lo, "band_high_eur": hi, "error": self.error,
            "position_avg_eur": pos_avg, "vs_position_avg_pct": (est / pos_avg - 1) * 100,
            "rank_in_position": int((self.d.loc[self.d["position"] == r["position"], "estimated_value_eur"] > est).sum()) + 1,
            "n_in_position": int((self.d["position"] == r["position"]).sum()),
            "key_stats": [s for s in stats if s["key"] in KEY_STATS], "stats": stats,
            "top_drivers": self.top_drivers(i, 3), "provenance": self.provenance(i),
        }

    # ------------------------------------------------------------------ SHAP
    def raw_value(self, i: int, f: str):
        if f == "position":
            return POS_NAME[self.d.at[i, "position"]]
        if f == "nation_group":
            return self.d.at[i, "nation_group"]
        return _f(self.d.at[i, f])

    def top_drivers(self, i: int, k: int = 3) -> list[dict]:
        c = self.shap_feat.iloc[i]
        order = c.abs().sort_values(ascending=False).index[:k]
        return [{"feature": f, "label": pretty(f), "contribution": _f(c[f]), "pct": _f(pct_change(c[f])),
                 "value": self.raw_value(i, f)} for f in order]

    def waterfall(self, i: int, merged: bool = True, max_display: int = 12) -> dict:
        base = float(self.shap["base"][i])
        if merged:
            c = self.shap_feat.iloc[i]
            items = [(f, float(c[f]), self.raw_value(i, f)) for f in c.index]
        else:
            vals = self.shap["values"][i]
            items = [(n, float(v), _f(self.shap["raw_data"][i, j])) for j, (n, v) in enumerate(zip(self.shap["names"], vals))]
        items.sort(key=lambda t: -abs(t[1]))
        shown, rest = items[:max_display], items[max_display:]
        pred = base + sum(v for _, v, _ in items)
        rows = [{"feature": f, "label": pretty(f), "contribution": v, "pct": pct_change(v), "value": raw,
                 "group": group_of(f), "tooltip": TOOLTIPS.get(f, "")} for f, v, raw in shown]
        if rest:
            rows.append({"feature": "_other", "label": f"{len(rest)} other features", "contribution": sum(v for _, v, _ in rest),
                         "pct": pct_change(sum(v for _, v, _ in rest)), "value": None, "group": "Other", "tooltip": ""})
        # SHAP is additive in log space, so the euro effect of one feature depends on what came before it.
        # Walk the rows in display order and take the change in exp(base + running sum): the euro steps
        # then add up exactly to (estimate - base).
        run = base
        for row in rows:
            nxt = run + row["contribution"]
            row["eur"] = math.exp(nxt) - math.exp(run)
            run = nxt
        model_pred = math.log(float(self.d.at[i, "estimated_value_eur"]))
        groups = {}
        for f, v, _ in items:
            groups[group_of(f)] = groups.get(group_of(f), 0.0) + v
        return {"player": self.summary(i), "base_log": base, "base_eur": math.exp(base), "prediction_log": pred,
                "prediction_eur": math.exp(pred), "check_gap": abs(pred - model_pred), "rows": rows,
                "groups": [{"group": g, "contribution": v, "pct": pct_change(v)} for g, v in sorted(groups.items(), key=lambda t: -abs(t[1]))],
                "in_training": bool(i in self.train_idx)}

    def global_importance(self, position: str | None = None) -> dict:
        mask = np.ones(self.n, dtype=bool) if not position else (self.d["position"] == position).to_numpy()
        vals = np.abs(self.shap["values"][mask]).mean(axis=0)
        per_col = pd.Series(vals, index=self.shap["names"]).sort_values(ascending=False)
        merged = self.shap_feat[mask].abs().mean().sort_values(ascending=False)
        grp = per_col.groupby(group_of).sum().sort_values(ascending=False)
        perf = [f for f in merged.index if group_of(f) in PERF_GROUPS]
        perf_total = float(merged[perf].sum()) or 1.0
        return {
            "position": position, "n": int(mask.sum()),
            "features": [{"feature": f, "label": pretty(f), "mean_abs": _f(v), "pct": _f(pct_change(v)), "group": group_of(f),
                          "tooltip": TOOLTIPS.get(f, "")} for f, v in per_col.items()],
            "merged": [{"feature": f, "label": pretty(f), "mean_abs": _f(v), "pct": _f(pct_change(v)), "group": group_of(f)} for f, v in merged.items()],
            "groups": [{"group": g, "mean_abs": _f(v), "pct": _f(pct_change(v)), "performance": g in PERF_GROUPS} for g, v in grp.items()],
            "performance_top10": [{"rank": k + 1, "feature": f, "label": pretty(f), "group": group_of(f), "mean_abs": _f(merged[f]),
                                   "pct": _f(pct_change(merged[f])), "share": _f(merged[f] / perf_total * 100)}
                                  for k, f in enumerate(perf[:10])],
        }

    def dependence(self, feature: str) -> dict:
        if feature not in self.shap_feat.columns:
            raise KeyError(feature)
        summary = self.feature_summary(feature)
        if feature in ("position", "nation_group"):
            return {"feature": feature, "label": pretty(feature), "tooltip": TOOLTIPS.get(feature, ""),
                    "categorical": True, "categories": summary.get("by_category", []), "points": [], "summary": summary}
        x = self.d[feature].to_numpy(dtype=float)
        y = self.shap_feat[feature].to_numpy()
        return {"feature": feature, "label": pretty(feature), "tooltip": TOOLTIPS.get(feature, ""),
                "categorical": False,
                "points": [{"id": int(i), "name": self.d.at[i, "player_name"], "position": self.d.at[i, "position"],
                            "x": _f(x[i]), "shap": _f(y[i]), "pct": _f(pct_change(y[i]))} for i in range(self.n)],
                "summary": summary}

    def feature_summary(self, f: str) -> dict:
        """Notebook txt_feature numbers, structured."""
        rank = list(self.imp_feat.index).index(f) + 1
        typ = pct_change(self.imp_feat[f])
        perf = self.b["perf_feats"]
        res = {"feature": f, "label": pretty(f), "rank": rank, "n_features": len(self.imp_feat), "typical_pct": typ,
               "perf_rank": perf.index(f) + 1 if f in perf else None, "n_perf": len(perf)}
        shp = self.shap_feat[f]
        if f == "position":
            m = shp.groupby(self.d["position"]).mean().sort_values(ascending=False)
            res["by_category"] = [{"category": POS_NAME[k], "pct": pct_change(v)} for k, v in m.items()]
        elif f == "nation_group":
            m = shp.groupby(self.d["nation_group"]).mean().sort_values(ascending=False)
            res["by_category"] = [{"category": k, "pct": pct_change(v)} for k, v in m.items()]
        else:
            vals = self.d[f].to_numpy(dtype=float)
            s = shp.to_numpy()
            if f == "age":
                by_age = pd.Series(s).groupby(np.round(vals)).agg(["mean", "size"])
                by_age = by_age[by_age["size"] >= 3]
                peak = by_age["mean"].idxmax()
                young, old = s[vals <= 21], s[vals >= 31]
                res["age_peak"] = float(peak)
                res["age_peak_pct"] = pct_change(by_age.loc[peak, "mean"])
                res["young_pct"] = pct_change(young.mean()) if len(young) >= 3 else None
                res["old_pct"] = pct_change(old.mean()) if len(old) >= 3 else None
            else:
                rho = spearmanr(vals, s)[0]
                res["rho"] = _f(rho)
                res["direction"] = "up" if rho > 0.5 else ("down" if rho < -0.5 else "mixed")
                q1, q3 = np.nanquantile(vals, [0.25, 0.75])
                res["top25_pct"] = pct_change(s[vals >= q3].mean())
                res["bottom25_pct"] = pct_change(s[vals <= q1].mean())
            pos_imp = shp.abs().groupby(self.d["position"]).mean().sort_values(ascending=False)
            res["most_pos"], res["most_pos_pct"] = POS_NAME[pos_imp.index[0]], pct_change(pos_imp.iloc[0])
            res["least_pos"], res["least_pos_pct"] = POS_NAME[pos_imp.index[-1]], pct_change(pos_imp.iloc[-1])
        return res

    # ------------------------------------------------------------------ scouting / similarity
    def scout(self, q: ScoutQuery) -> dict:
        res = scout(self.d, self.Z, self.S, q)
        t = q.target
        zt = self.Z.iloc[t]
        res["target"] = {**self.summary(t), "standouts": [{"feature": f, "label": pretty(f), "z": _f(zt[f])}
                                                         for f in zt.sort_values(ascending=False).index[:3]]}
        res["target_value_eur"] = float(self.d.at[t, "oof_value_eur"])
        res["max_value_eur"] = res["target_value_eur"] * q.max_pct / 100 if q.max_pct is not None else None
        res["query"] = {k: v for k, v in q.__dict__.items() if k != "exclude"}
        for row in res["results"]:
            row.update({k: v for k, v in self.summary(row["id"]).items() if k != "id"})
            row["shared_labels"] = [pretty(f) for f in row["shared_strengths"]]
        return res

    def similarity(self, a: int, b: int) -> float:
        return float(self.S[a, b])

    def pair(self, a: int, b: int) -> dict:
        same = self.d.at[a, "position"] == self.d.at[b, "position"]
        cand = np.flatnonzero((self.d["position"] == self.d.at[a, "position"]).to_numpy() & (np.arange(self.n) != a))
        rank = int((self.S[a, cand] > self.S[a, b]).sum()) + 1 if same else None
        return {"a": self.summary(a), "b": self.summary(b), "same_position": bool(same),
                "similarity": float(self.S[a, b]), "rank": rank, "n_candidates": int(len(cand)),
                "shared": [pretty(f) for f in shared_strengths(self.Z.iloc[a].to_numpy(), self.Z.iloc[b].to_numpy())]}

    def radar(self, ids: list[int]) -> dict:
        return {"axes": RADAR_LABELS, "keys": RADAR,
                "players": [{**self.summary(i), "percentiles": [_f(self.radar_pct.at[i, k], 1) for k in RADAR],
                             "raw": [_f(self.d.at[i, k]) for k in RADAR]} for i in ids],
                "note": "Percentile within the player's own position (100 = best in position)."}

    def compare(self, ids: list[int]) -> dict:
        players = []
        for i in ids:
            s = self.summary(i)
            s["stats"] = {f: _f(self.d.at[i, f]) for f in KEY_STATS}
            s["top_drivers"] = self.top_drivers(i, 3)
            players.append(s)
        sims = [{"a": int(a), "b": int(b), "similarity": float(self.S[a, b]),
                 "same_position": bool(self.d.at[a, "position"] == self.d.at[b, "position"])}
                for k, a in enumerate(ids) for b in ids[k + 1:]]
        return {"players": players, "similarities": sims,
                "stat_labels": {f: pretty(f) for f in KEY_STATS}, "radar": self.radar(ids)}

    # ------------------------------------------------------------------ rankings
    RANK_BY = {
        "estimated_value": "estimated_value_eur",
        "listed_value": "market_value_eur",
        "oof_value": "oof_value_eur",
        "value_vs_similar": "value_vs_similar",
        "undervalued": "value_gap_ratio",
        "goals": "goals",
        "assists": "assists",
        "goal_contributions": "goalsAssistsSum",
        "xg_filled": "xg_filled",
        "xa_filled": "xa_filled",
        "appearances": "appearances",
        "matches_started": "matchesStarted",
        "penalty_goals": "penaltyGoals",
        "headed_goals": "headedGoals",
        "big_chances_created": "bigChancesCreated",
        "big_chances_missed": "bigChancesMissed",
        "key_passes": "keyPasses",
        "total_shots": "totalShots",
        "shots_on_target": "shotsOnTarget",
        "successful_dribbles": "successfulDribbles",
        "tackles_total": "tackles",
        "tackles_won_total": "tacklesWon",
        "interceptions_total": "interceptions",
        "clearances_total": "clearances",
        "ball_recoveries_total": "ballRecovery",
        "aerial_won_total": "aerialDuelsWon",
        "touches_total": "touches",
        "yellow_cards": "yellowCards",
        "red_cards": "redCards",
        "clean_sheets": "cleanSheet",
        "rating": "rating",
        "totw": "totwAppearances",
        "fouls": "fouls",
        "was_fouled_total": "wasFouled",
        "offsides": "offsides",
        "woodwork": "hitWoodwork",
    }

    def rankings(self, by: str = "estimated_value", position: str | None = None, club: str | None = None,
                 min_age: int | None = None, max_age: int | None = None, min_minutes: int | None = None,
                 n: int = 10, ascending: bool | None = None, *,
                 max_minutes: int | None = None, min_eur: float | None = None, max_eur: float | None = None,
                 price_col: str = "estimated_value_eur", nation: str | None = None) -> dict:
        d = self.d
        col = self.RANK_BY.get(by, by)
        if col not in d.columns or (col not in self.RANK_BY.values() and col not in NUM_FEATURES):
            raise KeyError(by)
        m = np.ones(len(d), dtype=bool)
        if position:
            m &= (d["position"] == position).to_numpy()
        if club:
            m &= (d["team_name"] == club).to_numpy()
        if nation:
            m &= (d["nation"] == nation).to_numpy()
        if min_age is not None:
            m &= (d["age"] >= min_age).to_numpy()
        if max_age is not None:
            m &= (d["age"] <= max_age).to_numpy()
        if min_minutes is not None:
            m &= (d["minutes"] >= min_minutes).to_numpy()
        if max_minutes is not None:
            m &= (d["minutes"] <= max_minutes).to_numpy()
        pcol = price_col if price_col in d.columns else "estimated_value_eur"
        if min_eur is not None:
            m &= (d[pcol] >= min_eur).to_numpy()
        if max_eur is not None:
            m &= (d[pcol] <= max_eur).to_numpy()
        if ascending is None:
            ascending = by in ("value_vs_similar", "dispossessed_p90", "yellow_p90", "red_p90")
        sub = d[m].sort_values(col, ascending=ascending).head(n)
        rows = [{**self.summary(i), "metric": _f(sub.at[i, col]), "rank": k + 1} for k, i in enumerate(sub.index)]
        return {
            "by": by,
            "label": self.rank_label(by),
            "ascending": ascending,
            "pool_size": int(m.sum()),
            "min_minutes_rule": self.b["settings"]["min_minutes"],
            "n_players": self.n,
            "bounds": {
                "min_minutes": int(d["minutes"].min()),
                "max_minutes": int(d["minutes"].max()),
                "min_age": int(d["age"].min()),
                "max_age": int(d["age"].max()),
            },
            "rows": rows,
        }

    @staticmethod
    def rank_label(by: str) -> str:
        return {
            "estimated_value": "Model estimate",
            "listed_value": "Listed value",
            "oof_value": "Out-of-fold estimate",
            "value_vs_similar": "Estimate ÷ median estimate of 5 most similar players",
            "undervalued": "Out-of-fold estimate ÷ listed value",
            "goals": "Goals",
            "assists": "Assists",
            "goal_contributions": "Goals + Assists",
            "xg_filled": "Expected goals (xG)",
            "xa_filled": "Expected assists (xA)",
            "appearances": "Appearances",
            "matches_started": "Matches started",
            "penalty_goals": "Penalty goals",
            "headed_goals": "Headed goals",
            "big_chances_created": "Big chances created",
            "big_chances_missed": "Big chances missed",
            "key_passes": "Key passes",
            "total_shots": "Total shots",
            "shots_on_target": "Shots on target",
            "successful_dribbles": "Successful dribbles",
            "tackles_total": "Tackles",
            "tackles_won_total": "Tackles won",
            "interceptions_total": "Interceptions",
            "clearances_total": "Clearances",
            "ball_recoveries_total": "Ball recoveries",
            "aerial_won_total": "Aerial duels won",
            "touches_total": "Touches",
            "yellow_cards": "Yellow cards",
            "red_cards": "Red cards",
            "clean_sheets": "Clean sheets",
            "rating": "Average match rating",
            "totw": "Team of the Week appearances",
            "fouls": "Fouls committed",
            "was_fouled_total": "Times fouled",
            "offsides": "Offsides",
            "woodwork": "Hit woodwork",
        }.get(by, pretty(by))

    # ------------------------------------------------------------------ what-if
    def whatif(self, i: int, feature: str, value: float) -> dict:
        if feature not in NUM_FEATURES or feature == "age_sq":
            raise KeyError(feature)
        X = self.d.loc[[i], NUM_FEATURES + CAT_FEATURES].copy()
        before = float(self.d.at[i, "estimated_value_eur"])
        X[feature] = float(value)
        if feature == "age":
            X["age_sq"] = float(value) ** 2
        elif feature == "goals_p90":
            pen_p90 = max(0.0, float(self.d.at[i, "goals_p90"] - self.d.at[i, "np_goals_p90"]))
            X["np_goals_p90"] = max(0.0, float(value) - pen_p90)
        after = float(np.exp(self.b["pipeline"].predict(X)[0]))
        return {"player": self.summary(i), "feature": feature, "label": pretty(feature),
                "old_value": _f(self.d.at[i, feature]), "new_value": float(value),
                "before_eur": before, "after_eur": after, "change_pct": (after / before - 1) * 100,
                "note": "Model estimate for a hypothetical profile, not a real player."}

    # ------------------------------------------------------------------ data quality
    def find_excluded(self, q: str) -> list[dict]:
        ex = self.b["excluded"]
        qn = norm_name(q)
        if not qn:
            return []
        keys = ex["player_name"].map(norm_name)
        hits = ex[keys.str.contains(qn, regex=False) | keys.str.split().str[-1].eq(qn)]
        return [{"name": r["player_name"], "club": r["team_name"], "position": r["position"],
                 "minutes": int(r["minutesPlayed"]), "reason": r["exclusion_reason"]} for _, r in hits.head(5).iterrows()]
