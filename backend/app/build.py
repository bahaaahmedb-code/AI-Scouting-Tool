"""Build step: run the full notebook pipeline once and save everything the API needs.

    python -m app.build            (from the backend folder)

Writes artifacts/bundle.joblib. The live site only loads this file; it never retrains.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from .config import load_settings
from .constants import NUM_FEATURES, PERF_GROUPS, group_of
from .data import load_and_prepare
from .features import attach_target, build_features
from .model import compute_shap, oof_estimates, train_and_compare
from .similarity import position_zscores, radar_percentiles, similarity_matrix

BUNDLE_VERSION = 1


def _file_hash(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def build(settings=None, verbose: bool = True) -> dict:
    s = settings or load_settings()
    t0 = time.time()
    log = print if verbose else (lambda *a, **k: None)

    sample, excluded, counts, fuzzy_log, kaggle_cols = load_and_prepare(
        s.data_path, s.kaggle_file, s.fbref_file, s.min_minutes)
    log(f"All players {counts['all']} -> outfield {counts['outfield']} -> >= {s.min_minutes} min "
        f"{counts['min_minutes']} -> with age {counts['with_age']}")

    d, feat_info = build_features(sample)
    log(f"blank xG before: {feat_info['blank_xg']} | blank xA before: {feat_info['blank_xa']}")
    d, target_info = attach_target(d, s)
    log("Target:", s.target_label)

    tr = train_and_compare(d, s)
    results = tr["results"]
    log(results[["cv_r2_mean", "cv_rmse_log", "test_r2_log", "test_mae_eur"]].round(3).to_string())
    log(f"Best model by cross-validated RMSE: {tr['best_by_cv']} | model used: {tr['chosen']} (setting model={s.model})")

    pipe = tr["pipes"][tr["chosen"]]
    sh = compute_shap(pipe, tr["X"], tr["X_train"])
    log(f"check: max |base + sum(SHAP) - model prediction| = {sh['gap']:.6f}")

    d["estimated_value_eur"] = np.exp(sh["pred_log"])                         # model estimate (= base + SHAP sum)
    d["oof_value_eur"] = oof_estimates(pipe, tr["X"], tr["y"], tr["kf"])      # out-of-fold estimate (scouting)
    d["value_gap_ratio"] = d["oof_value_eur"] / d["market_value_eur"]
    d["in_training"] = d.index.isin(tr["X_train"].index)

    Z = position_zscores(d)
    S = similarity_matrix(Z)
    pct_in_pos = d.groupby("position")[NUM_FEATURES].rank(pct=True) * 100
    radar_pct = radar_percentiles(d)

    # value relative to the 5 most similar same-position players (for rankings)
    rel = np.empty(len(d))
    for i in range(len(d)):
        same = np.flatnonzero((d["position"] == d.at[i, "position"]).to_numpy() & (np.arange(len(d)) != i))
        top = same[np.argsort(-S[i, same])[:5]]
        rel[i] = d.at[i, "oof_value_eur"] / float(np.median(d.loc[top, "oof_value_eur"]))
    d["value_vs_similar"] = rel

    shap_feat = sh["shap_feat"]
    imp_feat = shap_feat.abs().mean().sort_values(ascending=False)
    mean_abs = pd.Series(np.abs(sh["values"]).mean(axis=0), index=sh["names"])

    data_files = {"kaggle": s.kaggle_file, "fbref": s.fbref_file}
    hashes = {}
    for k, f in data_files.items():
        try:
            hashes[k] = _file_hash(s.data_path / f)
        except OSError:
            hashes[k] = None

    keep_excl = [c for c in ["player_name", "kaggle_name", "team_name", "position", "minutesPlayed", "in_fbref",
                             "match_step", "exclusion_reason"] if c in excluded.columns]
    bundle = {
        "version": BUNDLE_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {k: getattr(s, k) for k in ["data_dir", "kaggle_file", "fbref_file", "season", "kaggle_matchday",
                                                 "target_source", "market_value_csv", "min_minutes", "random_state",
                                                 "test_size", "cv_folds", "model"]},
        "target_is_synthetic": s.target_is_synthetic,
        "target_label": s.target_label,
        "data_hashes": hashes,
        "is_sample_data": "sample" in str(s.data_dir).replace("\\", "/").split("/"),
        "counts": counts, "feat_info": feat_info, "target_info": target_info,
        "fuzzy_log": fuzzy_log, "kaggle_columns": kaggle_cols,
        "players": d, "excluded": excluded[keep_excl].copy(),
        "train_idx": list(map(int, tr["X_train"].index)), "test_idx": list(map(int, tr["X_test"].index)),
        "results": results, "best_by_cv": tr["best_by_cv"], "chosen_model": tr["chosen"],
        "pipeline": pipe,
        "shap": {"names": sh["names"], "values": sh["values"], "base": sh["base"], "gap": sh["gap"],
                 "raw_data": sh["raw_data"]},
        "shap_feat": shap_feat, "imp_feat": imp_feat, "mean_abs": mean_abs,
        "perf_feats": [f for f in imp_feat.index if group_of(f) in PERF_GROUPS],
        "Z": Z, "S": S, "pct_in_pos": pct_in_pos, "radar_pct": radar_pct,
        "base_eur": float(np.exp(sh["base"].mean())),
        "build_seconds": round(time.time() - t0, 1),
    }
    out = s.artifacts_path
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out / "bundle.joblib", compress=3)
    summary = {k: bundle[k] for k in ["version", "built_at", "settings", "target_is_synthetic", "counts",
                                      "chosen_model", "best_by_cv", "data_hashes", "build_seconds"]}
    summary["cv_results"] = json.loads(results.round(4).to_json(orient="index"))
    summary["shap_gap"] = sh["gap"]
    (out / "build_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    log(f"Saved {out / 'bundle.joblib'} in {bundle['build_seconds']}s")
    return bundle


if __name__ == "__main__":
    try:
        build()
    except FileNotFoundError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
