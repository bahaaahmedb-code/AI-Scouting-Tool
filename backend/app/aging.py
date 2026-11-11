"""Multi-Season Aging Curve, Performance Trajectory & Contract-Length Recommendation Engine.

Strictly isolated from the 2025-26 valuation training pool:
- Learns position-specific aging deltas (D, M, F) across ages 18..37 using the 14,664 Big-5
  player-seasons (2017-18 to 2024-25) from `fbref_historical_2018_2025.csv`.
- Matches our 276 players (2025-26) to their historical 2022-23, 2023-24, and 2024-25 seasons
  (across Premier League + La Liga + Serie A + Bundesliga + Ligue 1).
- Projects each player's 2026-27 (Age +1), 2027-28 (Age +2), and 2028-29 (Age +3) per-90 stats,
  role performance index (0-100), and fair market valuation using the trained valuation pipeline.
- Produces an actionable Contract-Length & Transfer Advisory recommendation.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import math
import numpy as np
import pandas as pd

from .constants import CAT_FEATURES, NUM_FEATURES, PER90_FEATURES, POS_NAME, pretty
from .data import find_file, norm_name

# Sub-role weights so hybrid midfielders/wingers (like Salah/Palmer) or ball-playing CBs (like Saliba/Van Dijk)
# are evaluated on their true specialist profile rather than penalized for not doing a different role's tasks.
SUBROLE_PROFILES: dict[str, list[tuple[str, dict[str, float]]]] = {
    "F": [
        ("Goalscorer / Striker", {
            "np_goals_p90": 0.30, "xg_p90": 0.28, "shots_on_target_p90": 0.16,
            "xa_p90": 0.10, "assists_p90": 0.08, "touches_p90": 0.08,
        }),
        ("Wide Creator / Winger", {
            "np_goals_p90": 0.20, "xg_p90": 0.18, "xa_p90": 0.22,
            "key_passes_p90": 0.16, "dribbles_p90": 0.14, "assists_p90": 0.10,
        }),
    ],
    "M": [
        ("Attacking Midfielder / Inside Forward", {
            "np_goals_p90": 0.24, "xg_p90": 0.22, "xa_p90": 0.22,
            "key_passes_p90": 0.16, "assists_p90": 0.10, "dribbles_p90": 0.06,
        }),
        ("Playmaker / Box-to-Box Midfielder", {
            "key_passes_p90": 0.22, "xa_p90": 0.18, "touches_p90": 0.18,
            "pass_accuracy": 0.16, "ball_recovery_p90": 0.14, "tackles_won_p90": 0.12,
        }),
        ("Defensive / Holding Midfielder", {
            "ball_recovery_p90": 0.24, "interceptions_p90": 0.22, "tackles_won_p90": 0.20,
            "pass_accuracy": 0.18, "touches_p90": 0.16,
        }),
    ],
    "D": [
        ("Ball-Playing Center-Back", {
            "pass_accuracy": 0.26, "touches_p90": 0.20, "clearances_p90": 0.18,
            "aerial_won_p90": 0.18, "interceptions_p90": 0.10, "ball_recovery_p90": 0.08,
        }),
        ("Stopper / Aerial Defender", {
            "clearances_p90": 0.26, "aerial_won_p90": 0.26, "interceptions_p90": 0.20,
            "tackles_won_p90": 0.16, "pass_accuracy": 0.12,
        }),
        ("Full-Back / Wing-Back", {
            "tackles_won_p90": 0.22, "interceptions_p90": 0.18, "key_passes_p90": 0.18,
            "xa_p90": 0.16, "touches_p90": 0.14, "dribbles_p90": 0.12,
        }),
    ],
}

ROLE_HEADLINE_METRICS: dict[str, list[str]] = {
    "F": ["np_goals_p90", "xg_p90", "xa_p90", "shots_on_target_p90", "dribbles_p90", "minutes"],
    "M": ["key_passes_p90", "xa_p90", "np_goals_p90", "pass_accuracy", "ball_recovery_p90", "tackles_won_p90", "minutes"],
    "D": ["tackles_won_p90", "interceptions_p90", "clearances_p90", "aerial_won_p90", "pass_accuracy", "minutes"],
}

PEAK_AGE_RANGE: dict[str, tuple[int, int]] = {
    "F": (24, 28),
    "M": (25, 29),
    "D": (26, 30),
}


def _find_historical_csv(data_path: Path) -> Path | None:
    candidates = [
        data_path / "fbref_historical_2018_2025.csv",
        data_path.parent / "fbref_historical_2018_2025.csv",
        data_path.parent.parent / "fbref_historical_2018_2025.csv",
        data_path.parent.parent / "historical_datasets" / "fbref_big5_2018_2025_merged.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    return find_file(data_path, "fbref_historical_2018_2025.csv")


def _fit_position_aging_curves(hist: pd.DataFrame) -> dict:
    """Learn position-specific year-over-year aging multipliers/deltas across ages 17..39.

    Uses within-player consecutive season transitions where players played >= 900 minutes,
    blended with a smooth physiological aging prior to avoid sample-attrition survivorship bias.
    """
    h = hist.dropna(subset=["key", "position", "age", "Season_End_Year"]).copy()
    h = h[h["minutes"] >= 900].copy()
    h["age_int"] = h["age"].round().astype(int)
    h = h.sort_values(["key", "Born", "Season_End_Year", "minutes"], ascending=[True, True, True, False])
    h = h.drop_duplicates(["key", "Born", "Season_End_Year"])

    h_next = h.copy()
    h_next["Prev_Year"] = h_next["Season_End_Year"] - 1
    pairs = h.merge(
        h_next,
        left_on=["key", "Born", "Season_End_Year"],
        right_on=["key", "Born", "Prev_Year"],
        suffixes=("_t0", "_t1"),
    )

    stat_cols = PER90_FEATURES + ["pass_accuracy", "minutes", "start_share"]
    curves: dict[str, dict[int, dict[str, float]]] = {}

    for pos in ("D", "M", "F"):
        peak_lo, peak_hi = PEAK_AGE_RANGE[pos]
        pos_pairs = pairs[pairs["position_t0"] == pos]
        curves[pos] = {}
        for age in range(17, 40):
            sub = pos_pairs[pos_pairs["age_int_t0"].between(age - 1, age + 1)]
            n_emp = len(sub)
            emp_weight = min(0.45, n_emp / 140.0)

            if age < peak_lo:
                # Developing player (18..peak_lo-1): both per-90 output and playing time incline
                dev_boost = 0.045 * ((peak_lo - age) / max(1, peak_lo - 18))
                prior_rate_mult = 1.0 + dev_boost
                prior_min_mult = 1.0 + min(0.06, dev_boost * 1.2)
                prior_acc_delta = +0.30
            elif age <= peak_hi:
                # Prime plateau window (peak_lo..peak_hi): sustained peak output & minutes
                mid_peak = 0.5 * (peak_lo + peak_hi)
                prior_rate_mult = 1.012 if age <= mid_peak else 0.996
                prior_min_mult = 1.005 if age <= mid_peak else 0.995
                prior_acc_delta = +0.10
            else:
                # Post-peak aging curve (steeper for forwards, gentler for defenders)
                yrs_over = age - peak_hi
                decay_scale = {"F": 0.025, "M": 0.020, "D": 0.015}[pos]
                min_scale = {"F": 0.028, "M": 0.023, "D": 0.018}[pos]
                prior_rate_mult = max(0.80, 1.0 - decay_scale * (yrs_over ** 1.15))
                prior_min_mult = max(0.76, 1.0 - min_scale * (yrs_over ** 1.18))
                prior_acc_delta = -0.12 * max(0, yrs_over - 2)

            age_deltas: dict[str, float] = {}
            for col in stat_cols:
                c0, c1 = f"{col}_t0", f"{col}_t1"
                if col == "pass_accuracy":
                    emp_d = float((sub[c1] - sub[c0]).median()) if n_emp >= 10 else prior_acc_delta
                    emp_d = float(np.clip(emp_d, -1.5, 1.5))
                    age_deltas[col] = emp_weight * emp_d + (1.0 - emp_weight) * prior_acc_delta
                elif col in ("minutes", "start_share"):
                    # In prime or pre-peak years, do not let mid-season rotation noise drag minutes down
                    if age <= peak_hi:
                        age_deltas[col] = prior_min_mult
                    else:
                        if n_emp >= 10 and sub[c0].median() > 0:
                            emp_m = float(np.clip(sub[c1].median() / sub[c0].median(), 0.78, 1.02))
                        else:
                            emp_m = prior_min_mult
                        age_deltas[col] = min(prior_min_mult + 0.01, emp_weight * emp_m + (1.0 - emp_weight) * prior_min_mult)
                else:
                    if n_emp >= 10 and sub[c0].mean() > 1e-4:
                        emp_m = float(np.clip(sub[c1].mean() / sub[c0].mean(), 0.82, 1.15))
                    else:
                        emp_m = prior_rate_mult
                    if age <= peak_lo:
                        blended = max(1.005, emp_weight * emp_m + (1.0 - emp_weight) * prior_rate_mult)
                    elif age <= peak_hi:
                        blended = float(np.clip(emp_weight * emp_m + (1.0 - emp_weight) * prior_rate_mult, 0.985, 1.025))
                    else:
                        blended = min(prior_rate_mult + 0.015, emp_weight * emp_m + (1.0 - emp_weight) * prior_rate_mult)
                    age_deltas[col] = blended

            curves[pos][age] = age_deltas

    return {
        "curves": curves,
        "total_historical_rows": int(len(hist)),
        "pl_historical_rows": int((hist["Comp"] == "Premier League").sum()) if "Comp" in hist.columns else 0,
        "consecutive_pairs": int(len(pairs)),
    }


def _select_subrole(row_or_dict, pos: str, ref_df: pd.DataFrame) -> tuple[str, dict[str, float]]:
    """Pick the specialist sub-role profile that best fits a player's 2025-26 style."""
    profiles = SUBROLE_PROFILES.get(pos, SUBROLE_PROFILES["M"])
    pos_sub = ref_df[ref_df["position"] == pos]
    if pos_sub.empty:
        pos_sub = ref_df

    best_name = profiles[0][0]
    best_weights = profiles[0][1]
    best_score = -1.0

    for name, weights in profiles:
        s = _score_with_weights(row_or_dict, weights, pos_sub, full_season_minutes=2200.0)
        if s > best_score:
            best_score = s
            best_name = name
            best_weights = weights
    return best_name, best_weights


def _score_with_weights(row_or_dict, weights: dict[str, float], pos_sub: pd.DataFrame, full_season_minutes: float = 2400.0) -> float:
    total_w = 0.0
    acc = 0.0
    for feat, w in weights.items():
        val = row_or_dict.get(feat) if isinstance(row_or_dict, dict) else row_or_dict[feat]
        if val is None or (isinstance(val, float) and math.isnan(val)):
            continue
        arr = pos_sub[feat].dropna().to_numpy(dtype=float)
        if len(arr) == 0:
            continue
        pct = float(np.mean(arr <= float(val)) * 100.0)
        acc += w * pct
        total_w += w

    mins = float((row_or_dict.get("minutes") if isinstance(row_or_dict, dict) else row_or_dict["minutes"]) or 1800.0)
    avail_factor = float(np.clip(0.86 + 0.14 * min(1.0, mins / max(900.0, full_season_minutes)), 0.80, 1.02))
    raw_score = (acc / max(total_w, 1e-6)) * avail_factor
    return float(np.clip(round(raw_score, 1), 15.0, 99.0))


def _match_player_history(player_row: pd.Series, hist: pd.DataFrame) -> pd.DataFrame:
    """Find a 2025-26 player's historical seasons (2022-23, 2023-24, 2024-25) from the Big-5 archive."""
    key = norm_name(player_row["player_name"])
    kag_key = norm_name(player_row.get("kaggle_name", player_row["player_name"]))
    born = player_row.get("born")
    age_2526 = float(player_row["age"])

    cand = hist[(hist["key"] == key) | (hist["key"] == kag_key)].copy()
    if cand.empty:
        tokens = key.split()
        surname = tokens[-1] if tokens else ""
        if len(surname) >= 4:
            sub = hist[hist["key"].str.endswith(surname, na=False)].copy()
            if not sub.empty and pd.notna(born):
                sub = sub[sub["Born"].sub(float(born)).abs() <= 1]
            if not sub.empty:
                scores = sub["key"].map(lambda k: SequenceMatcher(None, key, k).ratio())
                best_k = sub.loc[scores.idxmax(), "key"]
                if scores.max() >= 0.68:
                    cand = sub[sub["key"] == best_k].copy()

    if not cand.empty and pd.notna(born):
        born_m = cand[cand["Born"].sub(float(born)).abs() <= 1]
        if not born_m.empty:
            cand = born_m
    elif not cand.empty:
        cand = cand[(cand["age"] - (age_2526 - (2026 - cand["Season_End_Year"]))).abs() <= 2.5]

    if cand.empty:
        return cand

    cand = cand.sort_values(["Season_End_Year", "minutes"], ascending=[True, False]).drop_duplicates("Season_End_Year")
    return cand[cand["Season_End_Year"].isin([2023, 2024, 2025])].reset_index(drop=True)


def _recommend_contract(age: int, pos: str, subrole: str, perf_now: float, perf_y2: float, perf_y3: float,
                        val_now: float, val_y3: float) -> dict:
    """Generate a data-driven contract length & structure recommendation based on age, position, and 3-year projection."""
    peak_lo, peak_hi = PEAK_AGE_RANGE.get(pos, (25, 29))
    perf_delta_2y = perf_y2 - perf_now
    perf_delta_3y = perf_y3 - perf_now
    val_retention_3y = (val_y3 / max(val_now, 1e5) - 1.0) * 100.0

    if age <= 23:
        years = "5 Years"
        min_yr, max_yr = 4, 5
        structure = "Long-term core asset deal (4–5 years + club 1-year extension option)"
        risk = "Low"
        verdict = "Acquire / Lock Down Long-Term"
        rationale = (
            f"At age {age}, this {subrole.lower()} is in the pre-peak development window "
            f"(peak years {peak_lo}–{peak_hi}). Both role performance ({perf_now:.0f} → {perf_y3:.0f}) and "
            f"projected valuation ({val_retention_3y:+.0f}% over 3 years) support a full 5-year commitment."
        )
    elif age <= peak_hi - 1:
        if perf_delta_3y >= -2.5:
            years = "4 Years"
            min_yr, max_yr = 4, 4
            structure = "Prime-window standard contract (4 years)"
            risk = "Low"
            verdict = "Sign for Full Prime Window"
        else:
            years = "3–4 Years"
            min_yr, max_yr = 3, 4
            structure = "Structured prime deal (3 years guaranteed + 1-year club option)"
            risk = "Low-Moderate"
            verdict = "Sign for Prime Years"
        rationale = (
            f"Entering/in the prime {POS_NAME[pos].lower()} window (ages {peak_lo}–{peak_hi}). "
            f"A {years.lower()} deal captures peak tactical output ({perf_now:.0f} → {perf_y2:.0f} in Year 2) "
            f"while protecting resale value before post-{peak_hi} depreciation begins."
        )
    elif age <= peak_hi + 1:
        if perf_delta_2y >= -3.5 and perf_now >= 65:
            years = "2–3 Years"
            min_yr, max_yr = 2, 3
            structure = "2-year guaranteed deal + 1-year appearances-based club option"
            risk = "Moderate"
            verdict = "Short-to-Medium Term Contender Signing"
        else:
            years = "2 Years"
            min_yr, max_yr = 1, 2
            structure = "2-year bridge contract with incentives tied to minutes played"
            risk = "Moderate"
            verdict = "Cautious 2-Year Deal"
        rationale = (
            f"At age {age}, the player is at the upper edge of the typical {POS_NAME[pos].lower()} peak ({peak_lo}–{peak_hi}). "
            f"Near-term output stays reliable ({perf_y2:.0f}/100 at age {age + 2}), but estimated market value shifts by "
            f"{val_retention_3y:+.0f}% by age {age + 3} — cap guaranteed commitment at {max_yr} years."
        )
    else:
        if perf_now >= 72 and perf_delta_2y >= -7.5:
            years = "1–2 Years"
            min_yr, max_yr = 1, 2
            structure = "1-to-2 year elite veteran contract (1+1 club option tied to starts & output)"
            risk = "Moderate (Low Resale, High Immediate Impact)"
            verdict = "High-Impact Short-Term Deal (1+1)"
            rationale = (
                f"Elite veteran {subrole.lower()} (current role index {perf_now:.0f}/100 at age {age}). "
                f"Based on his last 3 seasons, he is projected to remain an impactful contributor at age {age + 1}–{age + 2} "
                f"({perf_y2:.0f}/100 index), before physical aging accelerates at age {age + 3} ({perf_y3:.0f}/100, "
                f"{val_retention_3y:+.0f}% valuation change). A 1–2 year deal (or 1+1 option) captures his elite level without late-contract risk."
            )
        else:
            years = "1 Year"
            min_yr, max_yr = 1, 1
            structure = "1-year rolling veteran contract with appearance bonuses"
            risk = "High"
            verdict = "1-Year Rolling Deal Only"
            rationale = (
                f"At age {age}, the position aging curve projects a steady decline over the next 2–3 seasons "
                f"(role index {perf_now:.0f} → {perf_y2:.0f} at age {age + 2} → {perf_y3:.0f} at age {age + 3}). "
                f"Limit commitment to a 1-year rolling deal."
            )

    return {
        "recommended_years": years,
        "min_years": min_yr,
        "max_years": max_yr,
        "contract_structure": structure,
        "risk_level": risk,
        "verdict": verdict,
        "rationale": rationale,
        "val_retention_3y_pct": round(val_retention_3y, 1),
    }


def build_aging_projections(d: pd.DataFrame, pipe, data_path: Path, log=print) -> dict:
    """Build multi-season history + 3-year forward projections for all 276 players in `d`."""
    hist_csv = _find_historical_csv(data_path)
    if hist_csv is None or not hist_csv.exists():
        log("WARNING: fbref_historical_2018_2025.csv not found; building aging curves from parametric prior only.")
        hist = pd.DataFrame(columns=["key", "Player", "Squad", "Comp", "position", "Season_End_Year", "season", "age", "Born", "minutes"] + PER90_FEATURES + ["pass_accuracy", "start_share"])
    else:
        hist = pd.read_csv(hist_csv, low_memory=False)
        log(f"Loaded historical multi-season dataset ({len(hist)} player-seasons) from {hist_csv.name}")

    curve_meta = _fit_position_aging_curves(hist)
    curves = curve_meta["curves"]

    player_projections: dict[int, dict] = {}
    matched_2425 = 0
    matched_2324 = 0

    for i in range(len(d)):
        row = d.loc[i]
        pos = row["position"]
        pos_sub = d[d["position"] == pos]
        subrole_name, subrole_weights = _select_subrole(row, pos, d)

        age_now = int(round(float(row["age"])))
        est_now = float(row["estimated_value_eur"])
        # Because 2025-26 is through Matchday 31 (~81% of a 38-game season), benchmark full-season availability at 2000m for 2025-26
        perf_now = _score_with_weights(row, subrole_weights, pos_sub, full_season_minutes=2000.0)
        head_cols = ROLE_HEADLINE_METRICS.get(pos, ROLE_HEADLINE_METRICS["M"])

        # 1. Match historical seasons (2022-23, 2023-24, 2024-25)
        p_hist = _match_player_history(row, hist)
        if not p_hist.empty and (p_hist["Season_End_Year"] == 2025).any():
            matched_2425 += 1
        if not p_hist.empty and (p_hist["Season_End_Year"] == 2024).any():
            matched_2324 += 1

        history_seasons: list[dict] = []
        for _, hrow in p_hist.iterrows():
            h_perf = _score_with_weights(hrow, subrole_weights, pos_sub, full_season_minutes=2400.0)
            X_h = row[NUM_FEATURES + CAT_FEATURES].to_frame().T.copy()
            for col in PER90_FEATURES + ["pass_accuracy", "minutes", "start_share"]:
                if col in hrow and pd.notna(hrow[col]):
                    X_h[col] = float(hrow[col])
            # Scale 38-match historical minutes to 31-matchday equivalent so the 2025-26 model pipeline evaluates on the same minute scale
            X_h["minutes"] = float(np.clip(float(hrow["minutes"]) * (31.0 / 38.0), 450.0, 2790.0))
            h_age = float(hrow["age"]) if pd.notna(hrow["age"]) else float(age_now - (2026 - int(hrow["Season_End_Year"])))
            X_h["age"] = h_age
            X_h["age_sq"] = h_age ** 2
            h_val = float(np.exp(pipe.predict(X_h)[0]))

            history_seasons.append({
                "season": str(hrow["season"]),
                "season_end_year": int(hrow["Season_End_Year"]),
                "type": "historical",
                "club": str(hrow["Squad"]),
                "league": str(hrow.get("Comp", "Premier League")),
                "age": int(round(h_age)),
                "minutes": int(round(float(hrow["minutes"]))),
                "role_index": round(h_perf, 1),
                "estimated_value_eur": round(h_val, -4),
                "stats": {k: round(float(hrow[k]), 2) for k in head_cols if k != "minutes" and k in hrow and pd.notna(hrow[k])},
            })

        current_entry = {
            "season": "2025-26",
            "season_end_year": 2026,
            "type": "current",
            "club": str(row["team_name"]),
            "league": "Premier League",
            "age": age_now,
            "minutes": int(round(float(row["minutes"]))),
            "role_index": round(perf_now, 1),
            "estimated_value_eur": round(est_now, -4),
            "stats": {k: round(float(row[k]), 2) for k in head_cols if k != "minutes"},
        }

        all_past = history_seasons + [current_entry]
        n_seasons_used = len(all_past)
        if n_seasons_used >= 2:
            idx_vals = [x["role_index"] for x in all_past]
            yrs = [x["season_end_year"] for x in all_past]
            span = max(1, yrs[-1] - yrs[0])
            personal_idx_slope = (idx_vals[-1] - idx_vals[0]) / span
        else:
            personal_idx_slope = 0.0

        # Multi-season anchor: blend 70% current 2025-26 rate + 30% recent historical rate so 1 partial season doesn't distort projections
        sim_row = row[NUM_FEATURES + CAT_FEATURES].copy()
        if not p_hist.empty:
            recent_hist = p_hist.iloc[-1]
            for col in PER90_FEATURES + ["pass_accuracy"]:
                if col in recent_hist and pd.notna(recent_hist[col]):
                    sim_row[col] = 0.72 * float(row[col]) + 0.28 * float(recent_hist[col])

        # Feature-level personal annual multiplier
        personal_feat_mult: dict[str, float] = {}
        if not p_hist.empty:
            earliest = p_hist.iloc[0]
            span_f = max(1.0, 2026.0 - float(earliest["Season_End_Year"]))
            for col in PER90_FEATURES:
                v_now = float(sim_row[col])
                v_old = float(earliest[col]) if col in earliest and pd.notna(earliest[col]) else v_now
                if v_old > 0.05 and v_now > 0.05:
                    raw_ann = (v_now / v_old) ** (1.0 / span_f)
                    personal_feat_mult[col] = float(np.clip(raw_ann, 0.92, 1.08))
                else:
                    personal_feat_mult[col] = 1.0
        else:
            for col in PER90_FEATURES:
                personal_feat_mult[col] = 1.0

        base_personal_w = 0.30 if n_seasons_used >= 3 else (0.18 if n_seasons_used == 2 else 0.0)
        peak_lo, peak_hi = PEAK_AGE_RANGE[pos]

        # Recompute starting score & valuation of the multi-season anchor at current age so future deltas are smooth
        anchor_val_now = float(np.exp(pipe.predict(sim_row[NUM_FEATURES + CAT_FEATURES].to_frame().T)[0]))
        anchor_perf_now = _score_with_weights(sim_row, subrole_weights, pos_sub, full_season_minutes=2000.0)
        # Update current_entry role_index to reflect the player's true multi-season stabilized current level
        perf_now = round(0.75 * perf_now + 0.25 * anchor_perf_now, 1)
        current_entry["role_index"] = perf_now

        future_seasons: list[dict] = []
        for step in (1, 2, 3):
            target_age = age_now + step
            lookup_age = min(39, max(17, target_age - 1))
            pos_curve = curves[pos][lookup_age]
            w_pers = base_personal_w * (0.60 ** (step - 1))

            for col in PER90_FEATURES + ["pass_accuracy", "minutes", "start_share"]:
                c_delta = pos_curve[col]
                if col == "pass_accuracy":
                    sim_row[col] = float(np.clip(float(sim_row[col]) + c_delta, 55.0, 96.5))
                elif col in ("minutes", "start_share"):
                    if col == "minutes":
                        sim_row[col] = float(np.clip(float(sim_row[col]) * c_delta, 450.0, 2790.0))
                    else:
                        sim_row[col] = float(np.clip(float(sim_row[col]) * c_delta, 0.15, 1.0))
                else:
                    p_mult = personal_feat_mult.get(col, 1.0)
                    if target_age > peak_hi + 1 and p_mult > 1.0:
                        p_mult = 1.0 + (p_mult - 1.0) * 0.20
                    elif target_age <= peak_hi and p_mult < 0.98:
                        p_mult = max(0.98, p_mult)
                    blended_mult = (1.0 - w_pers) * c_delta + w_pers * p_mult
                    if col in ("dispossessed_p90", "yellow_p90", "red_p90"):
                        sim_row[col] = float(sim_row[col])
                    else:
                        sim_row[col] = max(0.0, float(sim_row[col]) * blended_mult)

            sim_row["age"] = float(target_age)
            sim_row["age_sq"] = float(target_age ** 2)

            X_fut = sim_row[NUM_FEATURES + CAT_FEATURES].to_frame().T
            raw_fut_val = float(np.exp(pipe.predict(X_fut)[0]))
            # Anchor the relative valuation ratio to the player's actual 2025-26 estimated_value_eur
            val_ratio = raw_fut_val / max(anchor_val_now, 1e5)
            fut_val = est_now * val_ratio

            fut_perf = _score_with_weights(sim_row, subrole_weights, pos_sub, full_season_minutes=2000.0)
            fut_year = 2026 + step
            # Project full 38-game season minutes for display
            disp_mins = int(round(min(3420.0, float(sim_row["minutes"]) * (38.0 / 31.0))))

            future_seasons.append({
                "season": f"{fut_year - 1}-{str(fut_year)[-2:]}",
                "season_end_year": fut_year,
                "type": "projected",
                "club": str(row["team_name"]),
                "league": "Premier League (Projected)",
                "age": target_age,
                "minutes": disp_mins,
                "role_index": round(fut_perf, 1),
                "estimated_value_eur": round(fut_val, -4),
                "value_change_pct": round((fut_val / max(est_now, 1e5) - 1.0) * 100.0, 1),
                "perf_change_pts": round(fut_perf - perf_now, 1),
                "stats": {k: round(float(sim_row[k]), 2) for k in head_cols if k != "minutes"},
            })

        perf_y1 = future_seasons[0]["role_index"]
        perf_y2 = future_seasons[1]["role_index"]
        perf_y3 = future_seasons[2]["role_index"]
        val_y1 = future_seasons[0]["estimated_value_eur"]
        val_y2 = future_seasons[1]["estimated_value_eur"]
        val_y3 = future_seasons[2]["estimated_value_eur"]

        delta_2y = perf_y2 - perf_now
        delta_3y = perf_y3 - perf_now
        if delta_2y >= 1.5 or (age_now < peak_lo and delta_3y >= 0.5):
            traj_code = "incline"
            traj_label = "Projected Incline (Ascending)"
            traj_badge = "green"
        elif delta_2y >= -2.2 and age_now <= peak_hi:
            traj_code = "plateau"
            traj_label = "Peak Plateau (Prime Window)"
            traj_badge = "blue"
        elif delta_2y >= -6.0:
            traj_code = "gradual_decline"
            traj_label = "Gradual Post-Peak Decline"
            traj_badge = "amber"
        else:
            traj_code = "steep_decline"
            traj_label = "Accelerated Aging Risk"
            traj_badge = "red"

        contract = _recommend_contract(
            age=age_now,
            pos=pos,
            subrole=subrole_name,
            perf_now=perf_now,
            perf_y2=perf_y2,
            perf_y3=perf_y3,
            val_now=est_now,
            val_y3=val_y3,
        )

        confidence = (
            "High (3+ Seasons Personal Track Record + Position Aging Curve)"
            if n_seasons_used >= 3
            else (
                "Medium-High (2 Seasons Personal Track Record + Position Aging Curve)"
                if n_seasons_used == 2
                else "Standard (2025-26 Baseline + Position Aging Curve)"
            )
        )

        player_projections[int(i)] = {
            "player_id": int(i),
            "name": str(row["player_name"]),
            "club": str(row["team_name"]),
            "position": pos,
            "position_name": POS_NAME[pos],
            "subrole": subrole_name,
            "current_age": age_now,
            "peak_age_window": f"{PEAK_AGE_RANGE[pos][0]}–{PEAK_AGE_RANGE[pos][1]}",
            "seasons_analyzed": n_seasons_used,
            "confidence": confidence,
            "personal_idx_slope_per_yr": round(float(personal_idx_slope), 2),
            "trajectory_code": traj_code,
            "trajectory_label": traj_label,
            "trajectory_badge": traj_badge,
            "current_role_index": round(perf_now, 1),
            "projected_role_index_y1": perf_y1,
            "projected_role_index_y2": perf_y2,
            "projected_role_index_y3": perf_y3,
            "current_value_eur": round(est_now, -4),
            "projected_value_y1_eur": val_y1,
            "projected_value_y2_eur": val_y2,
            "projected_value_y3_eur": val_y3,
            "headline_metrics": [{"key": k, "label": pretty(k)} for k in head_cols if k != "minutes"],
            "history": history_seasons,
            "current": current_entry,
            "future": future_seasons,
            "timeline": history_seasons + [current_entry] + future_seasons,
            "contract": contract,
        }

    log(f"Built aging & contract projections for {len(player_projections)} players "
        f"(matched 2024-25: {matched_2425}/{len(d)}, 2023-24: {matched_2324}/{len(d)})")

    return {
        "meta": {
            "total_historical_player_seasons": curve_meta["total_historical_rows"],
            "pl_historical_player_seasons": curve_meta["pl_historical_rows"],
            "consecutive_pairs_learned": curve_meta["consecutive_pairs"],
            "matched_2024_25": matched_2425,
            "matched_2023_24": matched_2324,
            "peak_windows": {k: f"{v[0]}–{v[1]}" for k, v in PEAK_AGE_RANGE.items()},
        },
        "players": player_projections,
    }
