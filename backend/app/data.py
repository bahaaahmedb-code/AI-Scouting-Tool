"""Load and merge the two 2025-26 source files, then filter the sample.

Faithful port of notebook cells 5, 7 and 9. Additions (marked NEW) only *record* provenance
(which matching step found a player, why a player was excluded) so the website can explain it.
"""
from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

from .constants import TEAM_MAP

FUZZY_THRESHOLD = 0.70
BIO_COLS = ["age", "born", "nation", "pos_fbref", "fb_name"]


def norm_name(s) -> str:
    """lowercase, strip accents, keep letters only. 'Gabriel Magalhães' -> 'gabriel magalhaes'"""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def find_file(data_dir: Path, name: str) -> Path | None:
    """Return the path of a data file. Also accepts renamed copies, e.g. 'PL_25-26_Season (1).xlsx'."""
    exact = data_dir / name
    if exact.exists():
        return exact
    stem, suffix = Path(name).stem, Path(name).suffix
    hits = sorted(data_dir.glob(f"{stem}*{suffix}"))
    return hits[0] if hits else None


def require_file(data_dir: Path, name: str) -> Path:
    p = find_file(data_dir, name)
    if p is None:
        found = sorted(x.name for x in data_dir.iterdir() if x.is_file())[:25] if data_dir.exists() else []
        raise FileNotFoundError(f"Could not find '{name}' in {data_dir.resolve()}. Files found here: {found}")
    return p


# ---------------------------------------------------------------- loading (cell 5)
def load_kaggle(path: Path) -> pd.DataFrame:
    kg = pd.read_csv(path, encoding="latin-1")
    kg["team_name"] = kg["team_name"].map(html.unescape)      # 'Brighton &amp; Hove Albion' -> 'Brighton & Hove Albion'
    return kg


def load_fbref(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None)
    hdr = raw.index[raw[0].astype(str).eq("Rk")][0]            # real header row
    fb = raw.iloc[hdr + 1:, [1, 2, 3, 4, 5, 6, 9]].copy()     # pick columns by position (names repeat in FBref)
    fb.columns = ["player", "nation_raw", "pos_fbref", "squad", "age", "born", "minutes_fbref"]
    fb = fb[fb["player"].notna() & (fb["player"] != "Player")]
    for c in ["age", "born", "minutes_fbref"]:
        fb[c] = pd.to_numeric(fb[c], errors="coerce")
    fb["nation"] = fb["nation_raw"].astype(str).str.split().str[-1]   # 'eng ENG' -> 'ENG'
    return fb.reset_index(drop=True)


# ---------------------------------------------------------------- merging (cell 7)
def merge_sources(kg: pd.DataFrame, fb: pd.DataFrame) -> tuple[pd.DataFrame, list[tuple]]:
    kg = kg.copy()
    fb = fb.copy()
    fb["team_std"] = fb["squad"].replace(TEAM_MAP)
    fb["key"] = fb["player"].map(norm_name)
    fb["fb_name"] = fb["player"]
    kg["key"] = kg["player_name"].map(norm_name)
    kg["kaggle_name"] = kg["player_name"]                       # NEW: keep the original Kaggle spelling

    # players with 2 clubs appear twice in FBref; keep the row with the most minutes for the fallback step
    fb_best = fb.sort_values("minutes_fbref", ascending=False).drop_duplicates("key")

    # step 1: name + club
    m1 = kg.merge(fb.drop_duplicates(["key", "team_std"])[["key", "team_std"] + BIO_COLS],
                  left_on=["key", "team_name"], right_on=["key", "team_std"], how="left")
    m1["match_step"] = np.where(m1["age"].notna(), "name+club", None)      # NEW
    # step 2: name only
    miss = m1["age"].isna()
    step2 = kg.loc[miss, ["key"]].merge(fb_best[["key"] + BIO_COLS], on="key", how="left")
    m1.loc[miss, BIO_COLS] = step2[BIO_COLS].values
    m1.loc[miss & m1["age"].notna(), "match_step"] = "name"                 # NEW
    # step 3: fuzzy, inside the same club
    fuzzy_log = []
    for i in m1.index[m1["age"].isna()]:
        cand = fb[fb["team_std"] == m1.at[i, "team_name"]]
        if cand.empty:
            continue
        scores = cand["key"].map(lambda k: SequenceMatcher(None, m1.at[i, "key"], k).ratio())
        j = scores.idxmax()
        if scores[j] >= FUZZY_THRESHOLD:
            m1.loc[i, BIO_COLS] = cand.loc[j, BIO_COLS].values
            m1.at[i, "match_step"] = "fuzzy"                                # NEW
            fuzzy_log.append((m1.at[i, "player_name"], cand.at[j, "player"], m1.at[i, "team_name"], round(float(scores[j]), 2)))

    df = m1.drop(columns=["team_std"])
    # use the clean FBref spelling for names (Kaggle has garbled ones like 'Benjamin eko')
    df["player_name"] = df["fb_name"].fillna(df["player_name"])
    df["key"] = df["player_name"].map(norm_name)
    df["in_fbref"] = df["age"].notna()                                      # NEW
    return df, fuzzy_log


# ---------------------------------------------------------------- filtering (cell 9)
def filter_sample(df: pd.DataFrame, min_minutes: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Returns (sample, excluded, counts). `excluded` is NEW: every dropped Kaggle player with the reason."""
    reason = pd.Series(None, index=df.index, dtype=object)
    reason[df["position"] == "G"] = "goalkeeper"
    reason[reason.isna() & (df["minutesPlayed"] < min_minutes)] = f"fewer than {min_minutes} minutes"
    reason[reason.isna() & df["age"].isna()] = "no match between the two sources (age unknown)"

    n0 = len(df)
    n1 = int((df["position"] != "G").sum())
    n2 = int(((df["position"] != "G") & (df["minutesPlayed"] >= min_minutes)).sum())
    sample = df[reason.isna()].reset_index(drop=True)
    excluded = df[reason.notna()].assign(exclusion_reason=reason[reason.notna()]).reset_index(drop=True)
    counts = {"all": n0, "outfield": n1, "min_minutes": n2, "with_age": len(sample)}
    return sample, excluded, counts


def load_and_prepare(data_dir: Path, kaggle_file: str, fbref_file: str, min_minutes: int):
    kg = load_kaggle(require_file(data_dir, kaggle_file))
    fb = load_fbref(require_file(data_dir, fbref_file))
    merged, fuzzy_log = merge_sources(kg, fb)
    sample, excluded, counts = filter_sample(merged, min_minutes)
    counts["kaggle_rows"], counts["kaggle_cols"] = kg.shape
    counts["fbref_rows"] = len(fb)
    counts["matched_with_age"] = int(merged["age"].notna().sum())
    return sample, excluded, counts, fuzzy_log, list(kg.columns)
