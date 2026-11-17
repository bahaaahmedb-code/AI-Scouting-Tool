"""Models, cross-validation, SHAP and out-of-fold estimates (notebook cells 15, 20, 35, 42).

Additions (marked NEW):
* `model` setting (auto | xgboost | rf | linear) picks the model used for estimates and SHAP.
  The notebook always explains XGBoost; `auto` follows the "lowest CV RMSE" rule.
* Cross-validated MAE / RMSE in euros (from the same 5-fold CV on the training part), for the
  "typical error range" shown next to every estimate.
* Dedicated Goalkeeper (`G`) sub-pipeline (`train_goalkeepers`) so outfield models (`D`, `M`, `F`)
  retain their exact 276-player training/test split and accuracy while goalkeepers are modelled
  and explained using shot-stopping and command-of-area metrics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, LeaveOneOut, cross_val_predict, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from .constants import CAT_FEATURES, GK_NUM_FEATURES, NUM_FEATURES, feat_of

MODEL_KEYS = {"linear": "Linear Regression (baseline)", "rf": "Random Forest", "xgboost": "XGBoost"}


def make_pre(num_cols=None, cat_cols=None) -> ColumnTransformer:
    nc = num_cols if num_cols is not None else NUM_FEATURES
    cc = cat_cols if cat_cols is not None else CAT_FEATURES
    steps = [("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), nc)]
    if cc:
        steps.append(("cat", OneHotEncoder(handle_unknown="ignore"), cc))
    return ColumnTransformer(steps)


def make_models(seed: int) -> dict:
    return {
        "Linear Regression (baseline)": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=seed, n_jobs=-1),
        "XGBoost": XGBRegressor(n_estimators=500, learning_rate=0.03, max_depth=3, subsample=0.8,
                                colsample_bytree=0.8, reg_lambda=2.0, random_state=seed, n_jobs=-1),
    }


def _dense(a):
    return a.toarray() if hasattr(a, "toarray") else np.asarray(a)


def train_and_compare(d: pd.DataFrame, settings):
    """Train and compare models on the 276 outfield players (`D`, `M`, `F`) so outfield CV/test metrics remain identical."""
    seed = settings.random_state
    outfield = d[d["position"] != "G"]
    X = outfield[NUM_FEATURES + CAT_FEATURES]
    y = outfield["log_value"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=settings.test_size, random_state=seed, stratify=outfield["position"])

    pipes = {name: Pipeline([("pre", make_pre()), ("model", m)]) for name, m in make_models(seed).items()}
    kf = KFold(n_splits=settings.cv_folds, shuffle=True, random_state=seed)
    rows = []
    for name, pipe in pipes.items():
        cv = cross_validate(pipe, X_train, y_train, cv=kf, scoring=("r2", "neg_root_mean_squared_error"))
        cvp = cross_val_predict(pipe, X_train, y_train, cv=kf)
        pipe.fit(X_train, y_train)
        pred = pipe.predict(X_test)
        eur_true, eur_pred = np.exp(y_test), np.exp(pred)
        rows.append({
            "model": name,
            "cv_r2_mean": cv["test_r2"].mean(), "cv_r2_std": cv["test_r2"].std(),
            "cv_rmse_log": -cv["test_neg_root_mean_squared_error"].mean(),
            "cv_mae_log": mean_absolute_error(y_train, cvp),
            "cv_mae_eur": mean_absolute_error(np.exp(y_train), np.exp(cvp)),
            "cv_rmse_eur": float(np.sqrt(mean_squared_error(np.exp(y_train), np.exp(cvp)))),
            "cv_median_abs_pct": float(np.median(np.abs(np.exp(cvp) - np.exp(y_train)) / np.exp(y_train)) * 100),
            "test_r2_log": r2_score(y_test, pred),
            "test_mae_log": mean_absolute_error(y_test, pred),
            "test_rmse_log": float(np.sqrt(mean_squared_error(y_test, pred))),
            "test_mae_eur": mean_absolute_error(eur_true, eur_pred),
            "test_median_abs_pct": float(np.median(np.abs(eur_pred - eur_true) / eur_true) * 100),
        })
    results = pd.DataFrame(rows).set_index("model")
    best_by_cv = results["cv_rmse_log"].idxmin()
    chosen = best_by_cv if settings.model == "auto" else MODEL_KEYS[settings.model]
    return {
        "X": X, "y": y, "X_train": X_train, "X_test": X_test, "y_train": y_train, "y_test": y_test,
        "pipes": pipes, "kf": kf, "results": results, "best_by_cv": best_by_cv, "chosen": chosen,
    }


def train_goalkeepers(d: pd.DataFrame, settings):
    """Train a dedicated Goalkeeper valuation & SHAP pipeline on `position == 'G'` using goalkeeper metrics."""
    gks = d[d["position"] == "G"]
    if gks.empty:
        return None
    seed = settings.random_state
    X_gk = gks[GK_NUM_FEATURES]
    y_gk = gks["log_value"]

    # Regularized additive XGBoost (depth-1 trees) tuned for the 23-goalkeeper Premier League sample
    gk_pipe = Pipeline([
        ("pre", make_pre(GK_NUM_FEATURES, [])),
        ("model", XGBRegressor(
            n_estimators=250, learning_rate=0.04, max_depth=1, min_child_weight=1,
            subsample=0.9, colsample_bytree=0.8, reg_lambda=1.5, random_state=seed, n_jobs=-1
        )),
    ])
    n_splits = min(5, len(gks))
    kf_gk = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    oof_log = cross_val_predict(gk_pipe, X_gk, y_gk, cv=kf_gk)
    gk_pipe.fit(X_gk, y_gk)

    pre, model = gk_pipe.named_steps["pre"], gk_pipe.named_steps["model"]
    names = [n.split("__", 1)[1] for n in pre.get_feature_names_out()]
    X_t = _dense(pre.transform(X_gk))
    sv = shap.TreeExplainer(model)(X_t)
    values, base = np.asarray(sv.values), np.asarray(sv.base_values).reshape(-1)
    pred_log = model.predict(X_t)
    shap_feat = pd.DataFrame(values, columns=names, index=gks.index).T.groupby(feat_of, sort=False).sum().T

    return {
        "pipe": gk_pipe,
        "index": gks.index,
        "pred_log": pd.Series(pred_log, index=gks.index),
        "oof_eur": pd.Series(np.exp(oof_log), index=gks.index),
        "shap_feat": shap_feat,
        "base": pd.Series(base, index=gks.index),
        "cv_r2": float(r2_score(y_gk, oof_log)),
        "cv_rmse_log": float(np.sqrt(mean_squared_error(y_gk, oof_log))),
    }


def compute_shap(pipe: Pipeline, X: pd.DataFrame, X_train: pd.DataFrame):
    """SHAP values for every outfield player (notebook cell 20)."""
    pre, model = pipe.named_steps["pre"], pipe.named_steps["model"]
    names = [n.split("__", 1)[1] for n in pre.get_feature_names_out()]
    X_all_t = _dense(pre.transform(X))
    if isinstance(model, LinearRegression):
        background = _dense(pre.transform(X_train))
        explainer = shap.LinearExplainer(model, background)
        values = np.asarray(explainer.shap_values(X_all_t))
        base = np.full(len(X), float(np.ravel(explainer.expected_value)[0]))
    else:
        sv = shap.TreeExplainer(model)(X_all_t)
        values, base = np.asarray(sv.values), np.asarray(sv.base_values).reshape(-1)
    pred = model.predict(X_all_t)
    gap = float(np.abs(base + values.sum(axis=1) - pred).max())

    cat_data = _dense(pre.named_transformers_["cat"].transform(X[CAT_FEATURES]))
    raw_data = np.hstack([X[NUM_FEATURES].to_numpy(dtype=float), cat_data])

    shap_feat = pd.DataFrame(values, columns=names, index=X.index).T.groupby(feat_of, sort=False).sum().T
    _diff = float(np.abs(shap_feat.sum(axis=1) - values.sum(axis=1)).max())
    if _diff > 1e-4:
        import warnings
        warnings.warn(f"SHAP merge sanity check: max diff = {_diff:.6f} (tolerated)")
    return {"names": names, "values": values, "base": base, "pred_log": pred, "gap": gap,
            "raw_data": raw_data, "shap_feat": shap_feat}


def oof_estimates(pipe: Pipeline, X: pd.DataFrame, y: pd.Series, kf: KFold) -> np.ndarray:
    """notebook cell 35: each player predicted by a model that did not see him."""
    return np.exp(cross_val_predict(pipe, X, y, cv=kf))
