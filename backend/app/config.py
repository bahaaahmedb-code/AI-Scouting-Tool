"""Configuration: config.yaml, overridden by environment variables (same key, upper case)."""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path

import yaml
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(PROJECT_DIR / ".env", override=False)
load_dotenv(BACKEND_DIR / ".env", override=False)


def _to_bool(v) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: str = "data/sample"
    kaggle_file: str = "premier_league_complete_stats_until31thGameDayOnSeason2025-26.csv"
    fbref_file: str = "PL_25-26_Season.xlsx"
    season: str = "2025-26"
    kaggle_matchday: int = 31
    target_source: str = "synthetic"
    market_value_csv: str | None = None
    min_minutes: int = 900
    random_state: int = 42
    test_size: float = 0.20
    cv_folds: int = 5
    model: str = "xgboost"
    artifacts_dir: str = "artifacts"
    log_dir: str = "logs"
    eval_logging: bool = True
    eval_access_code: str = "thesis2026"
    llm_rephrase: bool = True
    gemini_model: str = "gemini-3.5-flash-lite"
    rate_limit: str = "60/minute"
    chat_rate_limit: str = "20/minute"
    feedback_url: str = ""

    # ---- derived ----
    def path(self, p: str | None) -> Path | None:
        if p is None:
            return None
        q = Path(p)
        return q if q.is_absolute() else PROJECT_DIR / q

    @property
    def data_path(self) -> Path:
        return self.path(self.data_dir)

    @property
    def artifacts_path(self) -> Path:
        return self.path(self.artifacts_dir)

    @property
    def log_path(self) -> Path:
        if os.environ.get("VERCEL") and self.log_dir == "logs":
            return Path("/tmp/moneyball_logs")
        return self.path(self.log_dir)

    @property
    def target_is_synthetic(self) -> bool:
        return self.target_source != "csv" or not self.market_value_csv

    @property
    def target_label(self) -> str:
        return "market value (SYNTHETIC - NOT REAL)" if self.target_is_synthetic else "market value (Transfermarkt)"


def load_settings(config_file: str | Path | None = None, **overrides) -> Settings:
    cfg_path = Path(config_file or os.environ.get("MONEYBALL_CONFIG", BACKEND_DIR / "config.yaml"))
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    raw = raw or {}
    s = Settings()
    for f in fields(Settings):
        val = raw.get(f.name, getattr(s, f.name))
        env = os.environ.get(f.name.upper())
        if env is not None:
            val = None if env.lower() in {"", "none", "null"} else env
        if f.name in overrides:
            val = overrides[f.name]
        if val is not None:
            t = type(getattr(Settings(), f.name))
            if t is bool:
                val = _to_bool(val)
            elif t is int:
                val = int(val)
            elif t is float:
                val = float(val)
        setattr(s, f.name, val)
    if s.model not in {"auto", "xgboost", "rf", "linear"}:
        raise ValueError(f"model must be auto|xgboost|rf|linear, got {s.model!r}")
    return s
