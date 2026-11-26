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

from .constants import (CAT_FEATURES, GK_FEATURES, GK_NUM_FEATURES, GK_RADAR, GK_RADAR_LABELS,
                        GK_SIM_FEATURES, GROUPS, NUM_FEATURES, PER90_FEATURES, PERF_GROUPS, POS_NAME,
                        RADAR, RADAR_LABELS, SIM_FEATURES, TOOLTIPS, group_of, pretty)
from .data import norm_name
from .similarity import ScoutQuery, scout, shared_strengths

KEY_STATS = ["goals_p90", "xg_p90", "assists_p90", "xa_p90", "key_passes_p90", "dribbles_p90",
             "tackles_won_p90", "interceptions_p90", "aerial_won_p90", "pass_accuracy"]

GK_KEY_STATS = ["goals_prevented_p90", "save_pct", "saves_p90", "clean_sheet_pct",
                "high_claims_p90", "long_balls_p90", "pass_accuracy", "touches_p90"]

ALL_NUM_FEATURES = list(dict.fromkeys(NUM_FEATURES + GK_NUM_FEATURES))
OUTFIELD_SHAP_COLS = [f for f in NUM_FEATURES if f != "age_sq"] + CAT_FEATURES
GK_SHAP_COLS = [f for f in GK_NUM_FEATURES if f != "age_sq"]


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
        self.aging_data = bundle.get("aging", {"meta": {}, "players": {}})

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
        aging_players = (self.b.get("aging") or {}).get("players") or {}
        aging_meta = (self.b.get("aging") or {}).get("meta") or {}
        age_buckets: dict[int, dict[str, list[float]]] = {}
        for pid_k, pr in aging_players.items():
            pos_c = pr.get("position")
            if pos_c not in ("G", "D", "M", "F"):
                continue
            for pt in (pr.get("history") or []) + [pr.get("current")] + (pr.get("future") or []):
                if not pt or pt.get("age") is None or pt.get("role_index") is None:
                    continue
                ag = int(pt["age"])
                if 18 <= ag <= 35:
                    age_buckets.setdefault(ag, {}).setdefault(pos_c, []).append(float(pt["role_index"]))
        aging_curves = []
        for ag in sorted(age_buckets):
            row_c: dict[str, float | int] = {"age": ag}
            for pos_c in ("G", "D", "M", "F"):
                vals = age_buckets[ag].get(pos_c) or []
                if len(vals) >= 2:
                    row_c[pos_c] = round(float(np.mean(vals)), 1)
            if len(row_c) > 1:
                aging_curves.append(row_c)

        pos_accuracy = []
        for pos_c in ("F", "M", "D", "G"):
            sub_p = d[d["position"] == pos_c]
            if len(sub_p) >= 2:
                yt = np.log(sub_p["market_value_eur"].to_numpy(dtype=float))
                yp = np.log(sub_p["oof_value_eur"].to_numpy(dtype=float))
                ss_tot = float(np.sum((yt - yt.mean()) ** 2)) or 1.0
                r2_p = 1.0 - float(np.sum((yt - yp) ** 2)) / ss_tot
                med_pct_p = float(np.median(np.abs(sub_p["oof_value_eur"] - sub_p["market_value_eur"]) / sub_p["market_value_eur"]) * 100.0)
                mae_m_p = float(np.mean(np.abs(sub_p["oof_value_eur"] - sub_p["market_value_eur"])) / 1e6)
                pos_accuracy.append({
                    "position": pos_c,
                    "label": POS_NAME[pos_c],
                    "n": int(len(sub_p)),
                    "r2": round(r2_p, 3),
                    "med_abs_pct": round(med_pct_p, 1),
                    "mae_m": round(mae_m_p, 2),
                })

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
            "num_features": NUM_FEATURES, "gk_num_features": GK_NUM_FEATURES,
            "cat_features": CAT_FEATURES, "sim_features": SIM_FEATURES,
            "features": [{"key": f, "label": pretty(f), "group": group_of(f), "tooltip": TOOLTIPS.get(f, "")}
                         for f in ALL_NUM_FEATURES + CAT_FEATURES],
            "groups": GROUPS, "radar": [{"key": k, "label": l} for k, l in zip(RADAR, RADAR_LABELS)],
            "gk_radar": [{"key": k, "label": l} for k, l in zip(GK_RADAR, GK_RADAR_LABELS)],
            "gk_model": {k: _f(v, 4) for k, v in (self.b.get("gk_model") or {}).items() if k in ("cv_r2", "cv_rmse_log")},
            "nation_groups": self.b["feat_info"]["top_nations"] + ["OTHER"],
            "aging_curves": aging_curves,
            "backtest_summary": aging_meta.get("backtest_summary"),
            "peak_windows": aging_meta.get("peak_windows"),
            "position_accuracy": pos_accuracy,
        }

    # ------------------------------------------------------------------ players
    def summary(self, i: int) -> dict:
        r = self.d.loc[i]
        return {"id": int(i), "name": r["player_name"], "club": r["team_name"], "position": r["position"],
                "position_name": POS_NAME[r["position"]], "age": int(r["age"]), "minutes": int(r["minutes"]),
                "nation": r["nation"], "goals": _f(r.get("goals")), "assists": _f(r.get("assists")),
                "clean_sheets": _f(r.get("cleanSheet")), "save_pct": _f(r.get("save_pct"), 1),
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
            q_toks = set(qn.split())
            scored = []
            for i in idx:
                k = self.keys[i]
                k_toks = set(k.split())
                if k == qn or q_toks <= k_toks:
                    s = 0
                elif k.startswith(qn):
                    s = 1
                elif any(t.startswith(qn) for t in k.split()):
                    s = 2
                elif qn in k:
                    s = 3
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
        is_gk = r["position"] == "G"
        est = float(r["estimated_value_eur"])
        lo, hi = self.error_band(est)
        pos_avg = self.position_average(r["position"])
        num_feats = GK_NUM_FEATURES if is_gk else NUM_FEATURES
        key_feats = GK_KEY_STATS if is_gk else KEY_STATS
        stats = []
        for f in num_feats:
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
            "key_stats": [s for s in stats if s["key"] in key_feats], "stats": stats,
            "top_drivers": self.top_drivers(i, 3), "provenance": self.provenance(i),
            "projection": self.projection(i),
            "seasons_used": int(r["seasons_used"]) if "seasons_used" in r.index else None,
        }

    def projection(self, i: int) -> dict | None:
        players_map = self.aging_data.get("players", {})
        return players_map.get(int(i)) or players_map.get(str(i))

    # ------------------------------------------------------------------ SHAP
    def raw_value(self, i: int, f: str):
        if f == "position":
            return POS_NAME[self.d.at[i, "position"]]
        if f == "nation_group":
            return self.d.at[i, "nation_group"]
        return _f(self.d.at[i, f])

    def _player_shap_cols(self, i: int) -> list[str]:
        if self.d.at[i, "position"] == "G":
            return [c for c in GK_SHAP_COLS if c in self.shap_feat.columns]
        return [c for c in OUTFIELD_SHAP_COLS if c in self.shap_feat.columns]

    def top_drivers(self, i: int, k: int = 3) -> list[dict]:
        cols = self._player_shap_cols(i)
        c = self.shap_feat.loc[i, cols]
        order = c.abs().sort_values(ascending=False).index[:k]
        return [{"feature": f, "label": pretty(f), "contribution": _f(c[f]), "pct": _f(pct_change(c[f])),
                 "value": self.raw_value(i, f)} for f in order]

    def waterfall(self, i: int, merged: bool = True, max_display: int = 12) -> dict:
        base = float(self.shap["base"][i])
        is_gk = self.d.at[i, "position"] == "G"
        if merged or is_gk:
            cols = self._player_shap_cols(i)
            c = self.shap_feat.loc[i, cols]
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
                "in_training": bool(i in self.train_idx or is_gk)}

    def global_importance(self, position: str | None = None) -> dict:
        if position == "G":
            mask = (self.d["position"] == "G").to_numpy()
            cols = [c for c in GK_SHAP_COLS if c in self.shap_feat.columns]
            merged = self.shap_feat.loc[mask, cols].abs().mean().sort_values(ascending=False)
            per_col = merged.copy()
        else:
            mask = (self.d["position"] != "G").to_numpy() if not position else (self.d["position"] == position).to_numpy()
            vals = np.abs(self.shap["values"][mask]).mean(axis=0)
            per_col = pd.Series(vals, index=self.shap["names"]).sort_values(ascending=False)
            cols = [c for c in OUTFIELD_SHAP_COLS if c in self.shap_feat.columns]
            merged = self.shap_feat.loc[mask, cols].abs().mean().sort_values(ascending=False)
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
        if feature in GK_FEATURES and feature not in NUM_FEATURES:
            idx = self.d.index[self.d["position"] == "G"]
        elif feature in NUM_FEATURES and feature not in GK_NUM_FEATURES:
            idx = self.d.index[self.d["position"] != "G"]
        else:
            idx = self.d.index
        x = self.d[feature].to_numpy(dtype=float)
        y = self.shap_feat[feature].to_numpy()
        return {"feature": feature, "label": pretty(feature), "tooltip": TOOLTIPS.get(feature, ""),
                "categorical": False,
                "points": [{"id": int(i), "name": self.d.at[i, "player_name"], "position": self.d.at[i, "position"],
                            "x": _f(x[i]), "shap": _f(y[i]), "pct": _f(pct_change(y[i]))} for i in idx],
                "summary": summary}

    def feature_summary(self, f: str) -> dict:
        """Notebook txt_feature numbers, structured."""
        if f in self.imp_feat.index:
            rank = list(self.imp_feat.index).index(f) + 1
            typ = pct_change(self.imp_feat[f])
        else:
            gk_mask = self.d["position"] == "G"
            gk_imp = self.shap_feat.loc[gk_mask, GK_SHAP_COLS].abs().mean().sort_values(ascending=False)
            rank = list(gk_imp.index).index(f) + 1 if f in gk_imp.index else 1
            typ = pct_change(float(gk_imp.get(f, 0.0)))
        perf = self.b["perf_feats"]
        res = {"feature": f, "label": pretty(f), "rank": rank, "n_features": len(self.imp_feat), "typical_pct": typ,
               "perf_rank": perf.index(f) + 1 if f in perf else None, "n_perf": len(perf)}
        if f in GK_FEATURES and f not in NUM_FEATURES:
            sub_mask = self.d["position"] == "G"
        elif f in NUM_FEATURES and f not in GK_NUM_FEATURES:
            sub_mask = self.d["position"] != "G"
        else:
            sub_mask = pd.Series(True, index=self.d.index)
        shp = self.shap_feat.loc[sub_mask, f]
        d_sub = self.d.loc[sub_mask]
        if f == "position":
            m = shp.groupby(d_sub["position"]).mean().sort_values(ascending=False)
            res["by_category"] = [{"category": POS_NAME[k], "pct": pct_change(v)} for k, v in m.items()]
        elif f == "nation_group":
            m = shp.groupby(d_sub["nation_group"]).mean().sort_values(ascending=False)
            res["by_category"] = [{"category": k, "pct": pct_change(v)} for k, v in m.items()]
        else:
            vals = d_sub[f].to_numpy(dtype=float)
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
            pos_imp = shp.abs().groupby(d_sub["position"]).mean().sort_values(ascending=False)
            res["most_pos"], res["most_pos_pct"] = POS_NAME[pos_imp.index[0]], pct_change(pos_imp.iloc[0])
            res["least_pos"], res["least_pos_pct"] = POS_NAME[pos_imp.index[-1]], pct_change(pos_imp.iloc[-1])
        return res

    # ------------------------------------------------------------------ scouting / similarity
    def scout(self, q: ScoutQuery) -> dict:
        S_mat = self.b.get("S_neural") if (getattr(q, "method", "neural") == "neural" and self.b.get("S_neural") is not None) else self.S
        res = scout(self.d, self.Z, S_mat, q)
        t = q.target
        zt = self.Z.iloc[t]
        t_pos = self.d.at[t, "position"]
        sim_cols = GK_SIM_FEATURES if t_pos == "G" else SIM_FEATURES
        zt_sub = zt[[c for c in sim_cols if c in zt.index]]
        res["target"] = {**self.summary(t), "standouts": [{"feature": f, "label": pretty(f), "z": _f(zt_sub[f])}
                                                         for f in zt_sub.sort_values(ascending=False).index[:3]]}
        res["target_value_eur"] = float(self.d.at[t, "oof_value_eur"])
        res["max_value_eur"] = res["target_value_eur"] * q.max_pct / 100 if q.max_pct is not None else None
        res["method"] = "neural" if (getattr(q, "method", "neural") == "neural" and self.b.get("S_neural") is not None) else "cosine"
        res["neural_meta"] = self.b.get("neural_meta")
        res["query"] = {k: v for k, v in q.__dict__.items() if k != "exclude"}
        for row in res["results"]:
            row.update({k: v for k, v in self.summary(row["id"]).items() if k != "id"})
            row["shared_labels"] = [pretty(f) for f in row["shared_strengths"]]
        return res

    def similarity(self, a: int, b: int) -> float:
        return float(self.S[a, b])

    def pair(self, a: int, b: int) -> dict:
        same = self.d.at[a, "position"] == self.d.at[b, "position"]
        pos_a = self.d.at[a, "position"]
        cand = np.flatnonzero((self.d["position"] == pos_a).to_numpy() & (np.arange(self.n) != a))
        rank = int((self.S[a, cand] > self.S[a, b]).sum()) + 1 if same else None
        return {"a": self.summary(a), "b": self.summary(b), "same_position": bool(same),
                "similarity": float(self.S[a, b]), "rank": rank, "n_candidates": int(len(cand)),
                "shared": [pretty(f) for f in shared_strengths(
                    self.Z.iloc[a].to_numpy(), self.Z.iloc[b].to_numpy(), k=3, pos=pos_a if same else None
                )]}

    def radar(self, ids: list[int]) -> dict:
        all_gk = bool(ids) and all(self.d.at[i, "position"] == "G" for i in ids)
        axes = GK_RADAR_LABELS if all_gk else RADAR_LABELS
        keys = GK_RADAR if all_gk else RADAR
        return {"axes": axes, "keys": keys,
                "players": [{**self.summary(i), "percentiles": [_f(self.radar_pct.at[i, k], 1) for k in keys],
                             "raw": [_f(self.d.at[i, k]) for k in keys]} for i in ids],
                "note": "Percentile within the player's own position (100 = best in position)."}

    def compare(self, ids: list[int]) -> dict:
        all_gk = bool(ids) and all(self.d.at[i, "position"] == "G" for i in ids)
        stat_keys = GK_KEY_STATS if all_gk else KEY_STATS
        players = []
        for i in ids:
            s = self.summary(i)
            s["stats"] = {f: _f(self.d.at[i, f]) for f in stat_keys}
            s["top_drivers"] = self.top_drivers(i, 3)
            players.append(s)
        sims = [{"a": int(a), "b": int(b), "similarity": float(self.S[a, b]),
                 "same_position": bool(self.d.at[a, "position"] == self.d.at[b, "position"])}
                for k, a in enumerate(ids) for b in ids[k + 1:]]
        return {"players": players, "similarities": sims,
                "stat_labels": {f: pretty(f) for f in stat_keys}, "radar": self.radar(ids)}

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
        "saves": "saves",
        "goals_prevented": "goalsPrevented",
        "high_claims": "highClaims",
        "goals_conceded": "goalsConceded",
        "rating": "rating",
        "totw": "totwAppearances",
        "fouls": "fouls",
        "was_fouled_total": "wasFouled",
        "offsides": "offsides",
        "woodwork": "hitWoodwork",
    }

    GK_ONLY_RANKINGS = set(GK_FEATURES) | {"saves", "goals_prevented", "high_claims", "goals_conceded"}

    def rankings(self, by: str = "estimated_value", position: str | None = None, club: str | None = None,
                 min_age: int | None = None, max_age: int | None = None, min_minutes: int | None = None,
                 n: int = 10, ascending: bool | None = None, *,
                 max_minutes: int | None = None, min_eur: float | None = None, max_eur: float | None = None,
                 price_col: str = "estimated_value_eur", nation: str | None = None) -> dict:
        d = self.d
        col = self.RANK_BY.get(by, by)
        if col not in d.columns or (col not in self.RANK_BY.values() and col not in ALL_NUM_FEATURES):
            raise KeyError(by)
        m = np.ones(len(d), dtype=bool)
        if position:
            m &= (d["position"] == position).to_numpy()
        elif by in self.GK_ONLY_RANKINGS or col in self.GK_ONLY_RANKINGS:
            m &= (d["position"] == "G").to_numpy()
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
            ascending = by in ("value_vs_similar", "dispossessed_p90", "yellow_p90", "red_p90", "goals_conceded_p90", "goals_conceded")
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
            "saves": "Total saves",
            "goals_prevented": "Goals prevented (PSxG +/-)",
            "high_claims": "High claims",
            "goals_conceded": "Goals conceded",
            "rating": "Average match rating",
            "totw": "Team of the Week appearances",
            "fouls": "Fouls committed",
            "was_fouled_total": "Times fouled",
            "offsides": "Offsides",
            "woodwork": "Hit woodwork",
        }.get(by, pretty(by))

    # ------------------------------------------------------------------ what-if & club audit
    def whatif(self, i: int, feature: str | None = None, value: float | None = None,
               changes: dict[str, float] | None = None) -> dict:
        pos = self.d.at[i, "position"]
        is_gk = pos == "G"
        valid_feats = GK_NUM_FEATURES if is_gk else NUM_FEATURES
        updates: dict[str, float] = {}
        if changes:
            for k, v in changes.items():
                if k not in valid_feats or k == "age_sq":
                    raise KeyError(k)
                updates[k] = float(v)
        elif feature is not None and value is not None:
            if feature not in valid_feats or feature == "age_sq":
                raise KeyError(feature)
            updates[feature] = float(value)
        else:
            raise KeyError("feature")

        before = float(self.d.at[i, "estimated_value_eur"])
        if is_gk:
            X = self.d.loc[[i], GK_NUM_FEATURES].copy()
            for f_k, f_v in updates.items():
                X[f_k] = f_v
                if f_k == "age":
                    X["age_sq"] = f_v ** 2
            after = float(np.exp(self.b["gk_model"]["pipeline"].predict(X)[0]))
        else:
            X = self.d.loc[[i], NUM_FEATURES + CAT_FEATURES].copy()
            for f_k, f_v in updates.items():
                X[f_k] = f_v
                if f_k == "age":
                    X["age_sq"] = f_v ** 2
                elif f_k == "goals_p90" and "np_goals_p90" not in updates:
                    pen_p90 = max(0.0, float(self.d.at[i, "goals_p90"] - self.d.at[i, "np_goals_p90"]))
                    X["np_goals_p90"] = max(0.0, f_v - pen_p90)
            after = float(np.exp(self.b["pipeline"].predict(X)[0]))

        pos_peers = self.d.loc[(self.d["position"] == pos) & (self.d.index != i), "estimated_value_eur"]
        rank_before = int((pos_peers > before).sum()) + 1
        rank_after = int((pos_peers > after).sum()) + 1
        first_feat = next(iter(updates))
        applied = [
            {"feature": f_k, "label": pretty(f_k), "old_value": _f(self.d.at[i, f_k]), "new_value": _f(f_v)}
            for f_k, f_v in updates.items()
        ]
        return {
            "player": self.summary(i),
            "feature": first_feat,
            "label": pretty(first_feat) if len(updates) == 1 else f"{len(updates)} modified attributes",
            "old_value": _f(self.d.at[i, first_feat]),
            "new_value": float(updates[first_feat]),
            "applied_changes": applied,
            "before_eur": before,
            "after_eur": after,
            "delta_eur": after - before,
            "change_pct": (after / before - 1) * 100,
            "rank_before": rank_before,
            "rank_after": rank_after,
            "n_in_position": int(len(pos_peers) + 1),
            "note": "Model estimate for a hypothetical profile, not a real player.",
        }

    def club_audit(self, club: str, max_pct: float = 90.0) -> dict:
        sub = self.d[self.d["team_name"] == club]
        if sub.empty:
            raise KeyError(club)

        # Compute position-relative Role Index benchmarks & Hopkins/Cohen effect-size margins
        # across all 299 EPL players (Hopkins, 2002; Cohen, 1988):
        #   - SWC (Smallest Worthwhile Change) = 0.2 * SD  (filters out trivial 1-3 pt noise)
        #   - Moderate significant margin      = 0.5..0.6 * SD (true competitive gap / decline)
        pos_bench: dict[str, dict[str, float]] = {}
        for pos_code in ("G", "D", "M", "F"):
            p_now_vals, p_y3_vals = [], []
            for idx_all in self.d.index[self.d["position"] == pos_code]:
                pr = self.projection(int(idx_all)) or {}
                rn = float(pr.get("current_role_index") or 60.0)
                fl = pr.get("future") or []
                r3 = float(fl[-1]["role_index"]) if fl else rn
                p_now_vals.append(rn)
                p_y3_vals.append(r3)
            y3_sd = float(np.std(p_y3_vals)) if len(p_y3_vals) > 1 else 12.0
            y3_med = float(np.percentile(p_y3_vals, 50)) if p_y3_vals else 62.0
            swc = round(0.20 * y3_sd, 1)       # Smallest Worthwhile Change (~2.5-3.5 pts)
            sig_gap = round(0.50 * y3_sd, 1)   # Significant below-median gap (~6.2-8.8 pts)
            sig_drop = round(0.60 * y3_sd, 1)  # Hopkins Moderate significant decline (~7.5-10.6 pts)
            pos_bench[pos_code] = {
                "now_med":  float(np.percentile(p_now_vals, 50)) if p_now_vals else 62.0,
                "y3_med":   y3_med,
                "y3_sd":    y3_sd,
                "swc":      swc,
                "sig_gap":  sig_gap,
                "sig_drop": sig_drop,
                "y3_weak":  y3_med - sig_gap,   # Significantly below positional median (-0.5 SD)
                "y3_p70":   float(np.percentile(p_y3_vals, 70)) if p_y3_vals else 72.0,
            }

        roster = []
        for i in sub.index:
            s = self.summary(int(i))
            proj = self.projection(int(i)) or {}
            contract = proj.get("contract") or {}
            r_idx = float(proj.get("current_role_index") or 60.0)
            fut_list = proj.get("future") or []
            r_idx_y3 = float(fut_list[-1]["role_index"]) if fut_list else r_idx
            perf_delta_3y = round(r_idx_y3 - r_idx, 1)
            subrole = proj.get("subrole") or POS_NAME[s["position"]]
            age_val = int(s["age"])
            pb = pos_bench[s["position"]]
            # Young developing = U23 improving by >= SWC (0.2 SD) AND reaching above significant-weakness floor
            is_developing = age_val <= 23 and perf_delta_3y >= pb["swc"] and r_idx < pb["now_med"] and r_idx_y3 >= pb["y3_weak"]
            if r_idx_y3 >= pb["y3_p70"]:
                pitch_status = "core"
            elif is_developing:
                pitch_status = "developing"
            elif r_idx >= pb["now_med"] and perf_delta_3y <= -pb["sig_drop"] and r_idx_y3 < pb["y3_med"] + pb["swc"]:
                pitch_status = "succession"
            elif r_idx_y3 < pb["y3_weak"]:
                pitch_status = "upgrade"
            else:
                pitch_status = "core"
            roster.append({
                **s,
                "role_index": _f(r_idx, 1),
                "role_index_y3": _f(r_idx_y3, 1),
                "perf_delta_3y": _f(perf_delta_3y, 1),
                "pitch_status": pitch_status,
                "subrole": subrole,
                "trajectory_label": proj.get("trajectory_label") or "Stable",
                "trajectory_badge": proj.get("trajectory_badge") or "blue",
                "recommended_years": contract.get("recommended_years") or "3 Years",
                "contract_verdict": contract.get("verdict") or "Standard Deal",
                "contract_risk": contract.get("risk_level") or "Low",
                "val_retention_3y_pct": _f(contract.get("val_retention_3y_pct"), 1),
                "att_score": float(self.d.at[i, "xg_p90"] + self.d.at[i, "xa_p90"] + self.d.at[i, "goals_p90"]),
            })

        # Sort helper: blend of Role Index and playing time
        def starter_key(p):
            return (p["role_index"] or 0.0) + 0.004 * (p["minutes"] or 0)

        gks = sorted([p for p in roster if p["position"] == "G"], key=starter_key, reverse=True)
        defs = sorted([p for p in roster if p["position"] == "D"], key=starter_key, reverse=True)
        mids = sorted([p for p in roster if p["position"] == "M"], key=starter_key, reverse=True)
        fwds = sorted([p for p in roster if p["position"] == "F"], key=starter_key, reverse=True)

        xi_gk = gks[:1]
        n_def_pick = min(4, max(3, len(defs))) if len(defs) >= 3 else len(defs)
        xi_def = defs[:n_def_pick]
        picked_ids = {p["id"] for p in xi_gk + xi_def}

        rem_outfield = sorted(
            [p for p in roster if p["position"] != "G" and p["id"] not in picked_ids],
            key=starter_key,
            reverse=True,
        )
        spots_left = max(0, 11 - len(xi_gk) - len(xi_def))
        chosen_mid_att = rem_outfield[:spots_left]
        picked_ids.update(p["id"] for p in chosen_mid_att)

        # Split chosen_mid_att into MID line and ATT line (target 3 ATT and 3-4 MID)
        pure_f = [p for p in chosen_mid_att if p["position"] == "F"]
        non_f = [p for p in chosen_mid_att if p["position"] != "F"]
        # Sort non_f by attacking orientation (Wingers / Attacking Midfielders first)
        non_f_att = sorted(
            non_f,
            key=lambda p: (1 if ("Winger" in p["subrole"] or "Attacking" in p["subrole"]) else 0, p["att_score"]),
            reverse=True,
        )
        n_att_target = min(3, max(1, len(pure_f) if len(pure_f) >= 2 else 3))
        need_wingers = max(0, n_att_target - len(pure_f))
        xi_att = pure_f + non_f_att[:need_wingers]
        att_ids = {p["id"] for p in xi_att}
        xi_mid = [p for p in chosen_mid_att if p["id"] not in att_ids]

        starters = xi_gk + xi_def + xi_mid + xi_att
        bench = sorted([p for p in roster if p["id"] not in picked_ids], key=starter_key, reverse=True)

        best_xi_est = sum(p["estimated_value_eur"] or 0.0 for p in starters)
        best_xi_mkt = sum(p["listed_value_eur"] or 0.0 for p in starters)
        total_est = sum(p["estimated_value_eur"] or 0.0 for p in roster)
        total_mkt = sum(p["listed_value_eur"] or 0.0 for p in roster)
        avg_age = float(np.mean([p["age"] for p in roster]))
        xi_avg_age = float(np.mean([p["age"] for p in starters])) if starters else avg_age
        xi_avg_role = float(np.mean([p["role_index"] for p in starters])) if starters else 65.0

        # ── 2025-26 Team Unit Diagnostics (Attack / Midfield / Defense vs 3Y Aging) ──
        # Computed BEFORE transfer suggestions so team-level unit weaknesses & internal
        # development verdicts directly guide which positions need external recruitment.
        club_unit_raw = {}
        for c_name, c_df in self.d.groupby("team_name"):
            gks_c = c_df[c_df["position"] == "G"]
            defs_c = c_df[c_df["position"] == "D"]
            mids_c = c_df[c_df["position"] == "M"]
            att_mids_c = c_df[c_df["position"].isin(["F", "M"])]
            goals_tot = float(c_df["goals"].sum())
            xg_tot = float((c_df["xg_p90"] * c_df["minutes"] / 90.0).sum())
            bc_p90 = float(att_mids_c["big_chances_created_p90"].mean()) if len(att_mids_c) else 0.0
            pass_acc = float(mids_c["pass_accuracy"].mean()) if len(mids_c) else float(c_df["pass_accuracy"].mean())
            kp_p90 = float(mids_c["key_passes_p90"].mean()) if len(mids_c) else float(c_df["key_passes_p90"].mean())
            rec_p90 = float(mids_c["ball_recovery_p90"].mean()) if len(mids_c) else float(c_df["ball_recovery_p90"].mean())
            gc_p90 = float(gks_c["goals_conceded_p90"].mean()) if len(gks_c) else 1.4
            cs_pct = float(gks_c["clean_sheet_pct"].mean()) if len(gks_c) else 25.0
            def_act = float(
                (defs_c["tackles_won_p90"] + defs_c["interceptions_p90"] + defs_c["clearances_p90"]).mean()
            ) if len(defs_c) else 5.0
            club_unit_raw[c_name] = {
                "goals": goals_tot, "xg": xg_tot, "bc_p90": bc_p90,
                "pass_acc": pass_acc, "kp_p90": kp_p90, "rec_p90": rec_p90,
                "gc_p90": gc_p90, "cs_pct": cs_pct, "def_act": def_act,
            }

        def _z(vals: dict[str, float], invert: bool = False) -> dict[str, float]:
            arr = np.array(list(vals.values()), dtype=float)
            mu, sd = float(arr.mean()), float(arr.std()) or 1.0
            return {k: ((-1.0 if invert else 1.0) * (v - mu) / sd) for k, v in vals.items()}

        z_goals = _z({k: v["goals"] for k, v in club_unit_raw.items()})
        z_xg = _z({k: v["xg"] for k, v in club_unit_raw.items()})
        z_bc = _z({k: v["bc_p90"] for k, v in club_unit_raw.items()})
        att_scores = {k: 0.45 * z_goals[k] + 0.40 * z_xg[k] + 0.15 * z_bc[k] for k in club_unit_raw}

        z_pass = _z({k: v["pass_acc"] for k, v in club_unit_raw.items()})
        z_kp = _z({k: v["kp_p90"] for k, v in club_unit_raw.items()})
        z_rec = _z({k: v["rec_p90"] for k, v in club_unit_raw.items()})
        mid_scores = {k: 0.40 * z_pass[k] + 0.40 * z_kp[k] + 0.20 * z_rec[k] for k in club_unit_raw}

        z_gc = _z({k: v["gc_p90"] for k, v in club_unit_raw.items()}, invert=True)
        z_cs = _z({k: v["cs_pct"] for k, v in club_unit_raw.items()})
        z_da = _z({k: v["def_act"] for k, v in club_unit_raw.items()})
        def_scores = {k: 0.55 * z_gc[k] + 0.35 * z_cs[k] + 0.10 * z_da[k] for k in club_unit_raw}

        def _rank_of(score_map: dict[str, float], target_club: str) -> int:
            ordered = sorted(score_map.items(), key=lambda kv: -kv[1])
            for idx_r, (cn, _) in enumerate(ordered, start=1):
                if cn == target_club:
                    return idx_r
            return 10

        cur_u = club_unit_raw[club]
        n_clubs_total = len(club_unit_raw)

        def _build_unit_diag(unit_key: str, title: str, rank: int, stat_line: str, unit_players: list[dict], recruit_noun: str) -> dict:
            u_age = float(np.mean([p["age"] for p in unit_players])) if unit_players else 25.0
            u_now = float(np.mean([p["role_index"] for p in unit_players])) if unit_players else 60.0
            u_y3 = float(np.mean([p["role_index_y3"] for p in unit_players])) if unit_players else u_now
            u_delta = round(u_y3 - u_now, 1)

            if rank <= 7:
                verdict = "Strong Unit"
                badge = "green"
                note = f"Top-{rank} Premier League {title.lower()} in 2025-26; maintain current core."
            elif rank <= 12:
                # Require a significant unit-level drop (>= 5.0 pts) for Aging Watch
                if u_delta <= -5.0:
                    verdict = "Aging Watch"
                    badge = "amber"
                    note = f"Mid-table {title.lower()} (#{rank}/{n_clubs_total}) projected to drop significantly ({u_delta:+.1f} pts over 3Y) — plan gradual succession."
                else:
                    verdict = "Solid Unit"
                    badge = "blue"
                    note = f"Mid-table {title.lower()} (#{rank}/{n_clubs_total}) with a stable 3-year trajectory ({u_delta:+.1f} pts)."
            else:
                # Bottom-8 EPL team unit -> require a worthwhile improvement (>= +3.0 pts, Hopkins SWC) to Hold & Develop
                if u_delta >= 3.0 and u_age <= 24.5:
                    verdict = "Weakness — Hold & Develop"
                    badge = "blue"
                    note = (
                        f"Bottom-8 EPL {title.lower()} (#{rank}/{n_clubs_total}) in 2025-26, but starters are young "
                        f"(avg {u_age:.1f}y) and projected to improve significantly ({u_delta:+.1f} pts over 3Y) — internal development recommended."
                    )
                else:
                    verdict = "Weakness — Recruit Needed"
                    badge = "red"
                    note = (
                        f"Bottom-8 EPL {title.lower()} (#{rank}/{n_clubs_total}) in 2025-26 and starters are not projected "
                        f"to improve significantly ({u_delta:+.1f} pts over 3Y) — prioritize signing a {recruit_noun}."
                    )
            return {
                "unit": unit_key,
                "title": title,
                "epl_rank": rank,
                "n_clubs": n_clubs_total,
                "stat_line": stat_line,
                "avg_age": _f(u_age, 1),
                "role_now": _f(u_now, 1),
                "role_y3": _f(u_y3, 1),
                "delta_3y": _f(u_delta, 1),
                "verdict": verdict,
                "badge": badge,
                "note": note,
            }

        team_diagnostics = [
            _build_unit_diag(
                "attack", "Attacking Unit", _rank_of(att_scores, club),
                f"{int(round(cur_u['goals']))} Goals · {cur_u['xg']:.1f} xG · {cur_u['bc_p90']:.2f} Big Chances/90",
                xi_att, "forward / winger",
            ),
            _build_unit_diag(
                "midfield", "Midfield Unit", _rank_of(mid_scores, club),
                f"{cur_u['pass_acc']:.1f}% Pass Acc · {cur_u['kp_p90']:.2f} Key Passes/90 · {cur_u['rec_p90']:.1f} Rec/90",
                xi_mid, "central midfielder",
            ),
            _build_unit_diag(
                "defense", "Defensive Unit", _rank_of(def_scores, club),
                f"{cur_u['gc_p90']:.2f} Conceded/90 · {cur_u['cs_pct']:.1f}% Clean Sheets",
                xi_gk + xi_def, "defender / goalkeeper",
            ),
        ]
        unit_by_key = {u["unit"]: u for u in team_diagnostics}
        starter_unit_map: dict[int, str] = {}
        for p in xi_gk + xi_def:
            starter_unit_map[p["id"]] = "defense"
        for p in xi_mid:
            starter_unit_map[p["id"]] = "midfield"
        for p in xi_att:
            starter_unit_map[p["id"]] = "attack"

        # Weakest starter per unit (used when a unit is flagged 'Weakness — Recruit Needed')
        # Only protect true league superstars (role_index_y3 >= 78); otherwise pick the weakest starter in the weak unit.
        weakest_in_unit: dict[str, int] = {}
        for u_key, u_group in (("attack", xi_att), ("midfield", xi_mid), ("defense", xi_gk + xi_def)):
            candidates_u = [
                p for p in u_group
                if (p.get("role_index_y3") or p["role_index"] or 60.0) < 78.0
            ] or u_group
            if candidates_u:
                weakest_in_unit[u_key] = min(
                    candidates_u,
                    key=lambda p: (p.get("role_index_y3") or p["role_index"] or 60.0),
                )["id"]

        # Identify genuine squad priorities combining position-relative 3Y benchmarks + 2025-26 Team Unit Diagnostics:
        # 1. Protect anyone in the top 30% of their position's 3Y projection (y3_p70), EXCEPT the weakest starter
        #    in a team unit explicitly flagged 'Weakness — Recruit Needed' (unless they are a >=78 superstar).
        # 2. Protect young improving starters in a 'Weakness — Hold & Develop' unit (no panic buy).
        # 3. Boost / surface starters in 'Weakness — Recruit Needed' and 'Aging Watch' units.
        # 4. Never force 3 cards if a club's Best XI and team units are all strong (0 to 3 priorities).
        vuln_candidates = []
        for p in starters:
            reasons = []
            urgency = 0.0
            category = None
            r_now = p["role_index"] or 65.0
            r_y3 = p["role_index_y3"] if p.get("role_index_y3") is not None else r_now
            d3 = p["perf_delta_3y"] if p.get("perf_delta_3y") is not None else 0.0
            age_val = int(p["age"])
            pb = pos_bench[p["position"]]
            pos_lbl = POS_NAME[p["position"]].lower()
            u_key = starter_unit_map.get(p["id"], "midfield")
            u_diag = unit_by_key.get(u_key)
            u_verdict = u_diag["verdict"] if u_diag else ""
            is_weak_unit_target = (u_verdict == "Weakness — Recruit Needed" and weakest_in_unit.get(u_key) == p["id"] and r_y3 < 78.0)

            # Elite 3-year outlook protection (top 30% of their position in 2028/29)
            if r_y3 >= pb["y3_p70"] and not is_weak_unit_target:
                continue

            # Hold & Develop protection: only if improvement is at least Hopkins SWC (0.2 SD)
            if u_verdict == "Weakness — Hold & Develop" and age_val <= 24 and d3 >= pb["swc"]:
                continue
            if age_val <= 23 and d3 >= pb["swc"] and r_y3 >= pb["y3_weak"] and not is_weak_unit_target:
                continue

            # Case A: Statistically significant 3Y decline (>= 0.6 SD, Hopkins Moderate) -> Succession Plan
            if r_now >= pb["now_med"] and d3 <= -pb["sig_drop"] and r_y3 < pb["y3_med"] + pb["swc"]:
                category = "Succession Plan"
                reasons.append(
                    f"Significant 3Y decline: {r_now:.0f} → {r_y3:.0f} ({d3:+.1f} pts, exceeds {pb['sig_drop']:.1f}-pt {pos_lbl} threshold)"
                )
                urgency += abs(min(0.0, d3)) * 2.0 + max(0.0, pb["y3_med"] + pb["swc"] - r_y3) * 1.8

            # Case B: Significantly below positional median (-0.5 SD) -> Performance Upgrade
            elif r_y3 < pb["y3_weak"]:
                category = "Performance Upgrade"
                if age_val <= 23 and d3 > 0.0:
                    reasons.append(
                        f"Projected 2028/29 Role Index {r_y3:.1f}/100 remains significantly below EPL {pos_lbl} median ({pb['y3_med']:.0f}; threshold {pb['y3_weak']:.0f})"
                    )
                else:
                    reasons.append(
                        f"Projected 2028/29 Role Index {r_y3:.1f}/100 (significantly below EPL {pos_lbl} median {pb['y3_med']:.0f}; cutoff {pb['y3_weak']:.0f})"
                    )
                    if d3 <= -pb["sig_drop"]:
                        reasons.append(f"Significant 3Y decline of {d3:+.1f} pts")
                urgency += (pb["y3_med"] - r_y3) * 2.2 + abs(min(0.0, d3)) * 1.5

            # Team-Unit Diagnostics integration:
            if u_verdict == "Weakness — Recruit Needed":
                if category:
                    urgency += 18.0
                    reasons.insert(
                        0,
                        f"Team {u_diag['title']} ranked #{u_diag['epl_rank']}/{u_diag['n_clubs']} in EPL ({u_diag['stat_line']}) — recruit needed",
                    )
                elif weakest_in_unit.get(u_key) == p["id"]:
                    category = "Team Unit Upgrade"
                    urgency += 24.0 + max(0.0, pb["y3_med"] - r_y3)
                    reasons.append(
                        f"Team {u_diag['title']} ranked #{u_diag['epl_rank']}/{u_diag['n_clubs']} in EPL ({u_diag['stat_line']})"
                    )
                    reasons.append(f"Lowest 3Y projected starter in unit ({r_now:.0f} → {r_y3:.0f}/100)")
            elif u_verdict == "Aging Watch" and d3 <= -pb["sig_drop"] and category:
                urgency += 8.0
                reasons.append(f"Team {u_diag['title']} on 3Y Aging Watch (#{u_diag['epl_rank']}/{u_diag['n_clubs']} EPL)")

            if urgency > 0.0 and category:
                vuln_candidates.append((urgency, category, reasons, p))

        vuln_candidates.sort(key=lambda t: -t[0])
        chosen_vulns = []
        seen_pos = set()
        for urg, category, reasons, p in vuln_candidates:
            if len(chosen_vulns) >= 3:
                break
            if p["position"] in seen_pos and len(vuln_candidates) > 3 and urg < 35:
                continue
            seen_pos.add(p["position"])
            chosen_vulns.append((urg, category, reasons, p))

        club_player_ids = [int(i) for i in sub.index]
        vulnerabilities = []
        for urg, category, reasons, p in chosen_vulns:
            pid = p["id"]
            starter_est = float(p["estimated_value_eur"] or 1e6)
            # Return the full sorted pool of external positive-fit younger replacements
            # so each starter card has its own responsive % of Starter Value budget slider.
            q = ScoutQuery(
                target=pid,
                same_position=True,
                max_pct=None,
                max_age=min(28, max(25, p["age"] - 1)) if p["age"] >= 28 else 27,
                n=40,
                exclude=club_player_ids,
            )
            pool = [r for r in self.scout(q)["results"] if (r.get("similarity") or 0.0) > 0.0]
            if len(pool) < 5:
                q_wide = ScoutQuery(
                    target=pid,
                    same_position=True,
                    max_pct=None,
                    max_age=30,
                    n=40,
                    exclude=club_player_ids,
                )
                pool = [r for r in self.scout(q_wide)["results"] if (r.get("similarity") or 0.0) > 0.0]

            enriched_pool = []
            for r_cand in pool[:25]:
                cid = r_cand["id"]
                c_proj = self.projection(cid) or {}
                c_cont = c_proj.get("contract") or {}
                c_est = float(self.d.at[cid, "estimated_value_eur"])
                c_mkt = float(self.d.at[cid, "market_value_eur"])
                enriched_pool.append({
                    "id": cid,
                    "name": r_cand["name"],
                    "club": r_cand["club"],
                    "position": r_cand["position"],
                    "age": r_cand["age"],
                    "similarity": _f(r_cand["similarity"], 3),
                    "estimated_value_eur": _f(c_est),
                    "listed_value_eur": _f(c_mkt),
                    "pct_of_starter": _f((c_est / max(starter_est, 1e5)) * 100.0, 1),
                    "savings_vs_starter_eur": _f(starter_est - c_est),
                    "role_index": _f(c_proj.get("current_role_index") or 65.0, 1),
                    "subrole": c_proj.get("subrole") or POS_NAME[r_cand["position"]],
                    "recommended_years": c_cont.get("recommended_years") or "4 Years",
                    "shared_labels": r_cand.get("shared_labels", [])[:2],
                })

            default_recs = [r for r in enriched_pool if r["pct_of_starter"] <= max_pct][:3]
            if not default_recs:
                default_recs = enriched_pool[:3]

            vulnerabilities.append({
                "starter": p,
                "category": category,
                "priority": "High" if urg >= 35 else ("Medium" if urg >= 18 else "Watchlist"),
                "reasons": reasons,
                "replacements": default_recs,
                "replacement_pool": enriched_pool,
            })

        formation_str = f"{len(xi_def)}-{len(xi_mid)}-{len(xi_att)}"
        return {
            "club": club,
            "formation": formation_str,
            "n_players": len(roster),
            "team_strength": _f(float(sub["team_strength"].iloc[0]), 2),
            "best_xi_est_eur": _f(best_xi_est),
            "best_xi_mkt_eur": _f(best_xi_mkt),
            "best_xi_gap_pct": _f((best_xi_est / best_xi_mkt - 1.0) * 100.0 if best_xi_mkt > 0 else 0.0, 1),
            "total_est_eur": _f(total_est),
            "total_mkt_eur": _f(total_mkt),
            "total_gap_pct": _f((total_est / total_mkt - 1.0) * 100.0 if total_mkt > 0 else 0.0, 1),
            "avg_age": _f(avg_age, 1),
            "best_xi_avg_age": _f(xi_avg_age, 1),
            "best_xi_avg_role_index": _f(xi_avg_role, 1),
            "team_diagnostics": team_diagnostics,
            "pitch": {
                "gk": xi_gk,
                "def": xi_def,
                "mid": xi_mid,
                "att": xi_att,
            },
            "starters": starters,
            "bench": bench,
            "vulnerabilities": vulnerabilities,
        }

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
