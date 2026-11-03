"""Models, cross-validation, SHAP and out-of-fold estimates (notebook cells 15, 20, 35, 42).

Additions (marked NEW):
* `model` setting (auto | xgboost | rf | linear) picks the model used for estimates and SHAP.
  The notebook always explains XGBoost; `auto` follows the "lowest CV RMSE" rule.
* Cross-validated MAE / RMSE in euros (from the same 5-fold CV on the training part), for the
  "typical error range" shown next to every estimate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from .constants import CAT_FEATURES, NUM_FEATURES, feat_of

MODEL_KEYS = {"linear": "Linear Regression (baseline)", "rf": "Random Forest", "xgboost": "XGBoost"}


def make_pre() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), NUM_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
    ])


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
    seed = settings.random_state
    X = d[NUM_FEATURES + CAT_FEATURES]
    y = d["log_value"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=settings.test_size, random_state=seed, stratify=d["position"])

    pipes = {name: Pipeline([("pre", make_pre()), ("model", m)]) for name, m in make_models(seed).items()}
    kf = KFold(n_splits=settings.cv_folds, shuffle=True, random_state=seed)
    rows = []
    for name, pipe in pipes.items():
        cv = cross_validate(pipe, X_train, y_train, cv=kf, scoring=("r2", "neg_root_mean_squared_error"))
        # NEW: CV predictions on the training part (same folds) -> errors in euros and MAE (log)
        cvp = cross_val_predict(pipe, X_train, y_train, cv=kf)
        pipe.fit(X_train, y_train)
        pred = pipe.predict(X_test)
        eur_true, eur_pred = np.exp(y_test), np.exp(pred)
        rows.append({
            "model": name,
            "cv_r2_mean": cv["test_r2"].mean(), "cv_r2_std": cv["test_r2"].std(),
            "cv_rmse_log": -cv["test_neg_root_mean_squared_error"].mean(),
            "cv_mae_log": mean_absolute_error(y_train, cvp),                                   # NEW
            "cv_mae_eur": mean_absolute_error(np.exp(y_train), np.exp(cvp)),                   # NEW
            "cv_rmse_eur": float(np.sqrt(mean_squared_error(np.exp(y_train), np.exp(cvp)))),   # NEW
            "cv_median_abs_pct": float(np.median(np.abs(np.exp(cvp) - np.exp(y_train)) / np.exp(y_train)) * 100),  # NEW
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


def compute_shap(pipe: Pipeline, X: pd.DataFrame, X_train: pd.DataFrame):
    """SHAP values for every player (the explainer works on the pre-processed numbers), notebook cell 20."""
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

    # raw (un-scaled) feature values, so charts show real units
    cat_data = _dense(pre.named_transformers_["cat"].transform(X[CAT_FEATURES]))
    raw_data = np.hstack([X[NUM_FEATURES].to_numpy(dtype=float), cat_data])

    # notebook cell 42: merged per-feature contributions (age+age_sq, one-hot columns)
    shap_feat = pd.DataFrame(values, columns=names).T.groupby(feat_of, sort=False).sum().T
    _diff = float(np.abs(shap_feat.sum(axis=1) - values.sum(axis=1)).max())
    if _diff > 1e-4:
        import warnings
        warnings.warn(f"SHAP merge sanity check: max diff = {_diff:.6f} (tolerated)")
    return {"names": names, "values": values, "base": base, "pred_log": pred, "gap": gap,
            "raw_data": raw_data, "shap_feat": shap_feat}


def oof_estimates(pipe: Pipeline, X: pd.DataFrame, y: pd.Series, kf: KFold) -> np.ndarray:
    """notebook cell 35: each player predicted by a model that did not see him."""
    return np.exp(cross_val_predict(pipe, X, y, cv=kf)).astype("float64")
