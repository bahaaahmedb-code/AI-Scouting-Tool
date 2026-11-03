"""Generate a FICTIONAL development sample with the same column names and layout as the two real sources.

    python scripts/make_sample_data.py          (run with the backend virtual environment)

* Players are invented (random first/last names). Club names are the 2025-26 Premier League clubs.
* The file layout mirrors the real files, including their quirks, so the real pipeline code is exercised:
  - Kaggle CSV: latin-1 encoding (letters like 'ć' become '?'), 'Brighton &amp; Hove Albion', blank xG/xA
  - FBref XLSX: junk rows above the 'Rk' header, short club names ('Manchester Utd'), nation as 'eng ENG',
    duplicated rows for players who changed club, a few name spellings that need fuzzy matching
Do NOT treat any number in this sample as real football data.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample"
SEED = 7

CLUBS_KAGGLE = ["Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton & Hove Albion", "Burnley", "Chelsea",
                "Crystal Palace", "Everton", "Fulham", "Leeds United", "Liverpool", "Manchester City",
                "Manchester United", "Newcastle United", "Nottingham Forest", "Sunderland", "Tottenham Hotspur",
                "West Ham United", "Wolverhampton"]
TO_FBREF = {"Manchester United": "Manchester Utd", "Newcastle United": "Newcastle", "Nottingham Forest": "Nottingham",
            "Tottenham Hotspur": "Tottenham", "West Ham United": "West Ham", "Wolverhampton": "Wolves",
            "Brighton & Hove Albion": "Brighton"}
FIRST = ["Adam", "Ben", "Callum", "Dario", "Eli", "Felix", "Gonçalo", "Hugo", "Ivan", "Jonas", "Kai", "Luka", "Mateo",
         "Nico", "Oscar", "Pablo", "Rúben", "Sami", "Tomás", "Umar", "Viktor", "Wout", "Yerson", "Zeki", "Aaron",
         "Bruno", "Cédric", "Dejan", "Emil", "Franco", "Goran", "Henrik", "Iker", "Jamal", "Kevin", "Leon", "Marko",
         "Noah", "Ollie", "Pedro", "Rafael", "Stefan", "Theo", "Valentin", "William", "Youssef", "Žan", "Ömer"]
LAST = ["Andersson", "Barker", "Costa", "Dalić", "Evans", "Fernández", "Grbić", "Hughes", "Ilić", "Jensen", "Kovač",
        "Lambert", "Moreau", "Novak", "Okafor", "Pérez", "Quinn", "Rossi", "Šimić", "Taylor", "Udoh", "Vidal",
        "Walsh", "Xhaka-Lee", "Yilmaz", "Zielinski", "Ashworth", "Bennett", "Carvalho", "Dubois", "Eriksen", "Foden-Hart",
        "García", "Holm", "Ibáñez", "Jović", "Keller", "Lindqvist", "Mendes", "Nkosi", "Oliveira", "Petrović", "Ramos",
        "Sørensen", "Turner", "Uzun", "Varga", "Whitfield", "Young", "Zapata", "Ødegård-Ruiz", "Bayındır"]
NATIONS = (["ENG"] * 34 + ["FRA"] * 8 + ["NED"] * 6 + ["BRA"] * 6 + ["ESP"] * 6 + ["POR"] * 5 +
           ["GER", "BEL", "ARG", "NOR", "DEN", "SCO", "IRL", "CRO", "SRB", "USA", "GHA", "NGA", "SEN", "JPN", "SWE",
            "URU", "COL", "MAR", "CIV", "POL", "SUI", "AUT", "WAL", "KOR"])
CLUB_STRENGTH = dict(zip(CLUBS_KAGGLE, np.linspace(0.35, -0.35, len(CLUBS_KAGGLE))[np.random.default_rng(1).permutation(len(CLUBS_KAGGLE))]))
POS_FBREF = {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}

# per-90 means (D, M, F) for the main counting stats
P90 = {
    "goals":             (0.04, 0.12, 0.38), "assists":          (0.05, 0.12, 0.17),
    "totalShots":        (0.55, 1.20, 2.60), "keyPasses":        (0.45, 1.20, 1.30),
    "bigChancesCreated": (0.07, 0.20, 0.25), "successfulDribbles": (0.35, 0.90, 1.40),
    "wasFouled":         (0.60, 1.20, 1.50), "tackles":          (2.10, 2.20, 1.00),
    "interceptions":     (1.10, 0.90, 0.35), "clearances":       (4.00, 1.00, 0.45),
    "ballRecovery":      (4.50, 5.00, 2.60), "aerialDuelsWon":   (2.60, 0.90, 1.50),
    "dispossessed":      (0.40, 1.00, 1.60), "touches":          (62.0, 60.0, 38.0),
    "yellowCards":       (0.17, 0.19, 0.12), "redCards":         (0.010, 0.008, 0.006),
}
POS_I = {"D": 0, "M": 1, "F": 2, "G": 0}


def strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def make_players(rng) -> pd.DataFrame:
    rows, used = [], set()
    for club in CLUBS_KAGGLE:
        n = int(rng.integers(24, 29))
        positions = ["G"] * 3 + list(rng.choice(["D", "M", "F"], size=n - 3, p=[0.38, 0.42, 0.20]))
        for pos in positions:
            while True:
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                if name not in used:
                    used.add(name)
                    break
            rows.append({"player_name": name, "team_name": club, "position": pos})
    return pd.DataFrame(rows)


def make_kaggle(players: pd.DataFrame, rng) -> pd.DataFrame:
    k = players.copy()
    n = len(k)
    k["appearances"] = rng.integers(1, 32, n)
    share = np.clip(rng.beta(2.2, 1.6, n), 0.02, 1)
    k["minutesPlayed"] = np.clip((k["appearances"] * 90 * share).round().astype(int), 1, 2790)
    k["matchesStarted"] = np.minimum(k["appearances"], (k["appearances"] * np.clip(share + rng.normal(0, 0.1, n), 0, 1)).round()).astype(int)
    talent = rng.normal(0, 1, n)
    strength = k["team_name"].map(CLUB_STRENGTH).to_numpy()
    n90 = k["minutesPlayed"] / 90
    for col, means in P90.items():
        mu = np.array([means[POS_I[p]] for p in k["position"]]) * np.exp(0.25 * talent + 0.6 * strength)
        k[col] = rng.poisson(np.maximum(mu * n90 * rng.lognormal(0, 0.25, n), 0))
    k.loc[k["position"] == "G", ["goals", "totalShots", "keyPasses", "assists"]] = 0
    k["shotsOnTarget"] = rng.binomial(k["totalShots"], 0.35)
    k["goals"] = np.minimum(k["goals"], k["shotsOnTarget"])
    k["penaltyGoals"] = rng.binomial(k["goals"], 0.12)
    k["tacklesWon"] = rng.binomial(k["tackles"], 0.62)
    k["expectedGoals"] = (k["totalShots"] * rng.uniform(0.07, 0.14, n) + k["goals"] * 0.25).round(4)
    k["expectedAssists"] = (k["keyPasses"] * rng.uniform(0.07, 0.12, n) + k["assists"] * 0.2).round(4)
    k["accuratePassesPercentage"] = np.clip(rng.normal(np.where(k["position"] == "F", 74, 83), 5, n) + 6 * strength, 55, 95).round(2)
    k["rating"] = np.clip(6.7 + 0.25 * talent + 0.5 * strength + rng.normal(0, 0.15, n), 5.8, 8.2).round(2)
    # about 15% blank xG (as in the real file), a few of them with enough minutes; xA blank for 2 players
    blank = rng.random(n) < 0.15
    blank &= ~(k["minutesPlayed"] >= 900) | (rng.random(n) < 0.08)
    k.loc[blank, "expectedGoals"] = np.nan
    k.loc[k.sample(2, random_state=SEED).index, "expectedAssists"] = np.nan
    # filler columns so the file has the real width (99 columns)
    extra = 99 - len(k.columns)
    for j in range(extra):
        k[f"extra_stat_{j + 1}"] = rng.integers(0, 50, n)
    k["team_name"] = k["team_name"].str.replace("&", "&amp;", regex=False)   # the real file has HTML entities
    return k


def make_fbref(players: pd.DataFrame, kaggle: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    unmatched = set(rng.choice(len(players), 5, replace=False))       # players missing from FBref
    fuzzy = set(rng.choice(len(players), 14, replace=False)) - unmatched
    for i, p in players.iterrows():
        if i in unmatched:
            continue
        name = p["player_name"]
        if i in fuzzy:   # different spelling that needs the fuzzy step (same club)
            first, last = name.split(" ", 1)
            name = f"{first[:-1] if len(first) > 4 else first + 'o'} {last}"
        age = int(np.clip(rng.normal(26, 4), 17, 37))
        nation = rng.choice(NATIONS)
        pos = POS_FBREF[p["position"]]
        if pos == "MF" and rng.random() < 0.2:
            pos = "MFFW"
        squad = TO_FBREF.get(p["team_name"], p["team_name"])
        mins = int(kaggle.at[i, "minutesPlayed"])
        rows.append([name, f"{nation.lower()[:2]} {nation}", pos, squad, age, 2025 - age, mins])
        if rng.random() < 0.03:   # moved clubs mid-season: a second row with fewer minutes
            other = TO_FBREF.get(c := rng.choice(CLUBS_KAGGLE), c)
            rows.append([name, f"{nation.lower()[:2]} {nation}", pos, other, age, 2025 - age, int(mins * 0.2)])
    while len(rows) < 551:        # youth players only in FBref
        age = int(rng.integers(16, 20))
        club = rng.choice(CLUBS_KAGGLE)
        rows.append([f"{rng.choice(FIRST)} {rng.choice(LAST)}-Junior", "eng ENG", rng.choice(["DF", "MF", "FW"]),
                     TO_FBREF.get(club, club), age, 2025 - age, int(rng.integers(1, 200))])
    fb = pd.DataFrame(rows[:551], columns=["Player", "Nation", "Pos", "Squad", "Age", "Born", "Min"])
    return fb


def write_fbref_xlsx(fb: pd.DataFrame, path: Path, rng):
    header = ["Rk", "Player", "Nation", "Pos", "Squad", "Age", "Born", "MP", "Starts", "Min", "90s", "Gls", "Ast"]
    body = []
    for r, row in enumerate(fb.itertuples(index=False), 1):
        mp = max(1, row.Min // 70)
        body.append([r, row.Player, row.Nation, row.Pos, row.Squad, row.Age, row.Born, mp, max(0, mp - 3), row.Min,
                     round(row.Min / 90, 1), int(rng.integers(0, 10)), int(rng.integers(0, 8))])
        if r % 25 == 0:           # FBref repeats the header inside the table
            body.append(header[:1] + ["Player"] + [None] * (len(header) - 2))
    junk = [["Standard Stats 2025-2026 Premier League (FICTIONAL SAMPLE)"] + [None] * (len(header) - 1),
            [None] * len(header), [None, None, None, None, None, None, None, "Playing Time", None, None, None, "Performance", None]]
    pd.DataFrame(junk + [header] + body).to_excel(path, header=False, index=False)


def main():
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    players = make_players(rng)
    kaggle = make_kaggle(players, rng)
    fbref = make_fbref(players, kaggle, rng)
    kaggle.to_csv(OUT / "premier_league_complete_stats_until31thGameDayOnSeason2025-26.csv", index=False,
                  encoding="latin-1", errors="replace")       # 'ć' -> '?', like the real file
    write_fbref_xlsx(fbref, OUT / "PL_25-26_Season.xlsx", rng)
    (OUT / "README.md").write_text(
        "# Fictional sample data\n\nGenerated by `scripts/make_sample_data.py`. Players are invented. Same column names "
        "and layout as the real Kaggle and FBref files, so the pipeline can be developed and tested without them.\n"
        "**No number in these files is real football data.** Put the real files in `data/raw/` and set `DATA_DIR=data/raw`.\n",
        encoding="utf-8")
    print(f"Kaggle sample: {kaggle.shape}, FBref sample: {fbref.shape} -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
