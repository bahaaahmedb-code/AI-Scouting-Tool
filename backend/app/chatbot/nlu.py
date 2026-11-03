"""Understanding a question: players, features, filters and intent.

`find_players`, `find_features`, `wants_scouting` and `parse_scout_params` are ported from notebook
cells 43 and 45 (find_players now returns up to 4 players for comparisons). Intent detection is NEW.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re

from ..data import norm_name
from .glossary import GLOSSARY, GLOSSARY_ALIASES

# ------------------------------------------------------------------ notebook cell 43
STOP = {"what", "when", "where", "which", "while", "this", "that", "with", "have", "been", "from", "more", "than", "most", "much",
        "worth", "value", "valued", "high", "higher", "lower", "player", "model", "feature", "features", "team", "does", "will", "about",
        # NEW: common words that are also surnames in some samples
        "young", "best", "find", "show", "like", "under", "over", "only", "same", "city", "united", "data", "file", "files",
        "long", "short", "good", "hall", "cash", "rice", "burn", "cook", "hill", "wood"} - {"rice", "burn", "cash", "wood"}

FEATURE_WORDS = {
    "xg": "xg_p90", "expected goals": "xg_p90", "xa": "xa_p90", "expected assists": "xa_p90",
    "non penalty goals": "np_goals_p90", "np goals": "np_goals_p90",
    "top scorer": "goals_p90", "top scorers": "goals_p90", "leading scorer": "goals_p90", "leading scorers": "goals_p90",
    "goalscorer": "goals_p90", "goalscorers": "goals_p90", "goal scorer": "goals_p90", "goal scorers": "goals_p90",
    "scorer": "goals_p90", "scorers": "goals_p90", "goals": "goals_p90", "scored": "goals_p90",
    "assister": "assists_p90", "assisters": "assists_p90", "assists": "assists_p90",
    "shots on target": "shots_on_target_p90", "shots": "shots_p90", "key passes": "key_passes_p90",
    "big chances created": "big_chances_created_p90", "big chances": "big_chances_created_p90",
    "dribbles completed": "dribbles_p90", "dribbles": "dribbles_p90", "dribbling": "dribbles_p90", "fouled": "was_fouled_p90",
    "tackles won": "tackles_won_p90", "tackles": "tackles_p90", "tackling": "tackles_won_p90",
    "interceptions": "interceptions_p90", "clearances": "clearances_p90",
    "ball recoveries": "ball_recovery_p90", "recoveries": "ball_recovery_p90",
    "aerial duels": "aerial_won_p90", "aerial": "aerial_won_p90", "dispossessed": "dispossessed_p90", "touches": "touches_p90",
    "yellow cards": "yellow_p90", "yellow": "yellow_p90", "red cards": "red_p90", "red card": "red_p90",
    "pass completion": "pass_accuracy", "pass accuracy": "pass_accuracy", "passing": "pass_accuracy",
    "minutes played": "minutes", "minutes": "minutes", "playing time": "minutes",
    "age": "age", "years old": "age", "team strength": "team_strength", "team quality": "team_strength", "club strength": "team_strength",
    "position": "position", "nationality": "nation_group", "nation": "nation_group",
    # NEW
    "starts": "start_share", "share of matches started": "start_share", "headers": "aerial_won_p90",
}
_phrases = sorted(FEATURE_WORDS, key=len, reverse=True)

POS_WORDS = {"defender": "D", "defenders": "D", "midfielder": "M", "midfielders": "M", "forward": "F", "forwards": "F",
             "striker": "F", "strikers": "F", "attacker": "F", "attackers": "F", "winger": "F", "wingers": "F",
             "centre back": "D", "center back": "D", "centre backs": "D", "full back": "D", "fullback": "D", "cb": "D",
             "midfield": "M", "defence": "D", "defense": "D"}
GLOBAL_WORDS = {"important", "importance", "matter", "matters", "drivers", "driver", "factors", "influence", "influential",
                "contribute", "contributes", "drive", "drives"}
SCOUT_WORDS = {"alternative", "alternatives", "similar", "replace", "replacement", "replacements", "cheaper", "scout", "scouting",
               "substitute", "substitutes", "successor", "lookalike", "lookalikes", "comparable", "instead"}
SCOUT_PHRASES = (" players like ", " player like ", " someone like ", " anyone like ", " somebody like ")
NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
UNIT = r"(?:m\b|mn\b|mil\b|million|millions)"
NOT_MONEY = r"(?!\s*(?:%|percent|" + UNIT + r"))"

NATION_ALIASES = {
    "england": "ENG", "english": "ENG", "eng": "ENG",
    "brazil": "BRA", "brazilian": "BRA", "brazilians": "BRA", "bra": "BRA",
    "spain": "ESP", "spanish": "ESP", "esp": "ESP",
    "france": "FRA", "french": "FRA", "fra": "FRA",
    "portugal": "POR", "portuguese": "POR", "por": "POR",
    "netherlands": "NED", "dutch": "NED", "holland": "NED", "ned": "NED",
    "germany": "GER", "german": "GER", "germans": "GER", "ger": "GER",
    "argentina": "ARG", "argentinian": "ARG", "argentine": "ARG", "arg": "ARG",
    "belgium": "BEL", "belgian": "BEL", "bel": "BEL",
    "italy": "ITA", "italian": "ITA", "italians": "ITA", "ita": "ITA",
    "norway": "NOR", "norwegian": "NOR", "nor": "NOR",
    "sweden": "SWE", "swedish": "SWE", "swe": "SWE",
    "denmark": "DEN", "danish": "DEN", "den": "DEN",
    "croatia": "CRO", "croatian": "CRO", "cro": "CRO",
    "scotland": "SCO", "scottish": "SCO", "sco": "SCO",
    "wales": "WAL", "welsh": "WAL", "wal": "WAL",
    "ireland": "IRL", "irish": "IRL", "irl": "IRL",
    "northern ireland": "NIR", "northern irish": "NIR", "nir": "NIR",
    "ecuador": "ECU", "ecuadorian": "ECU", "ecu": "ECU",
    "colombia": "COL", "colombian": "COL", "col": "COL",
    "uruguay": "URU", "uruguayan": "URU", "uru": "URU",
    "japan": "JPN", "japanese": "JPN", "jpn": "JPN",
    "south korea": "KOR", "korean": "KOR", "kor": "KOR",
    "usa": "USA", "american": "USA", "united states": "USA",
    "ghana": "GHA", "ghanaian": "GHA", "gha": "GHA",
    "nigeria": "NGA", "nigerian": "NGA", "nga": "NGA",
    "senegal": "SEN", "senegalese": "SEN", "sen": "SEN",
    "ivory coast": "CIV", "ivorian": "CIV", "cote d ivoire": "CIV", "civ": "CIV",
    "cameroon": "CMR", "cameroonian": "CMR", "cmr": "CMR",
    "morocco": "MAR", "moroccan": "MAR", "mar": "MAR",
    "egypt": "EGY", "egyptian": "EGY", "egy": "EGY",
    "poland": "POL", "polish": "POL", "pol": "POL",
    "switzerland": "SUI", "swiss": "SUI", "sui": "SUI",
    "austria": "AUT", "austrian": "AUT", "aut": "AUT",
    "serbia": "SRB", "serbian": "SRB", "srb": "SRB",
    "hungary": "HUN", "hungarian": "HUN", "hun": "HUN",
    "slovenia": "SVN", "slovenian": "SVN", "svn": "SVN",
    "czechia": "CZE", "czech": "CZE", "cze": "CZE",
    "greece": "GRE", "greek": "GRE", "gre": "GRE",
    "turkey": "TUR", "turkish": "TUR", "tur": "TUR",
    "mexico": "MEX", "mexican": "MEX", "mex": "MEX",
    "paraguay": "PAR", "paraguayan": "PAR", "par": "PAR",
    "jamaica": "JAM", "jamaican": "JAM", "jam": "JAM",
    "burkina faso": "BFA", "bfa": "BFA",
}

NATION_LABELS = {
    "ENG": "England", "BRA": "Brazil", "ESP": "Spain", "FRA": "France", "POR": "Portugal",
    "NED": "Netherlands", "GER": "Germany", "ARG": "Argentina", "BEL": "Belgium", "ITA": "Italy",
    "NOR": "Norway", "SWE": "Sweden", "DEN": "Denmark", "CRO": "Croatia", "SCO": "Scotland",
    "WAL": "Wales", "IRL": "Ireland", "NIR": "Northern Ireland", "ECU": "Ecuador", "COL": "Colombia",
    "URU": "Uruguay", "JPN": "Japan", "KOR": "South Korea", "USA": "United States", "GHA": "Ghana",
    "NGA": "Nigeria", "SEN": "Senegal", "CIV": "Ivory Coast", "CMR": "Cameroon", "MAR": "Morocco",
    "EGY": "Egypt", "POL": "Poland", "SUI": "Switzerland", "AUT": "Austria", "SRB": "Serbia",
    "HUN": "Hungary", "SVN": "Slovenia", "CZE": "Czechia", "GRE": "Greece", "TUR": "Turkey",
    "MEX": "Mexico", "PAR": "Paraguay", "JAM": "Jamaica", "BFA": "Burkina Faso",
}

RAW_STAT_WORDS = {
    "goal contributions": "goal_contributions", "goal contribution": "goal_contributions",
    "goals and assists": "goal_contributions", "goals plus assists": "goal_contributions",
    "g a": "goal_contributions", "ga": "goal_contributions",
    "appearances": "appearances", "games played": "appearances", "matches played": "appearances",
    "matches started": "matches_started",
    "penalty goals": "penalty_goals", "penalties scored": "penalty_goals", "penalties": "penalty_goals",
    "headed goals": "headed_goals", "headers scored": "headed_goals",
    "big chances missed": "big_chances_missed", "missed chances": "big_chances_missed",
    "clean sheets": "clean_sheets", "clean sheet": "clean_sheets",
    "match rating": "rating", "average rating": "rating", "player rating": "rating", "rating": "rating",
    "team of the week": "totw", "totw": "totw",
    "fouls committed": "fouls", "fouls": "fouls",
    "offsides": "offsides", "offside": "offsides",
    "hit woodwork": "woodwork", "woodwork": "woodwork",
}
_raw_stat_phrases = sorted(RAW_STAT_WORDS, key=len, reverse=True)


def find_raw_stats(q: str) -> list[str]:
    qn = " " + norm_name(q.replace("g+a", "g a").replace("g/a", "g a")) + " "
    out = []
    for p in _raw_stat_phrases:
        tag = " " + p + " "
        if tag in qn:
            k = RAW_STAT_WORDS[p]
            if k not in out:
                out.append(k)
            qn = qn.replace(tag, " ")
    return out


class Lexicon:
    """Player-name lookup built from the sample."""

    def __init__(self, names, clubs, nations=None):
        self.keys = {i: norm_name(n) for i, n in enumerate(names)}
        self.names = list(names)
        self.nations = set(nations or [])
        self.club_keys = {norm_name(c): c for c in clubs}
        aliases = {"spurs": "Tottenham Hotspur", "man city": "Manchester City", "man utd": "Manchester United",
                   "man united": "Manchester United", "villa": "Aston Villa", "forest": "Nottingham Forest",
                   "wolves": "Wolverhampton", "brighton": "Brighton & Hove Albion", "palace": "Crystal Palace",
                   "newcastle": "Newcastle United", "west ham": "West Ham United", "leeds": "Leeds United",
                   "tottenham": "Tottenham Hotspur", "nottingham": "Nottingham Forest"}
        for a, c in aliases.items():
            if c in clubs:
                self.club_keys[a] = c
        self.vocab = set()
        for k in self.keys.values():
            self.vocab.update(k.split())

    # notebook find_players, extended to 4 players
    def find_players(self, q: str, limit: int = 4):
        _keys = self.keys
        qn = " " + norm_name(q) + " "
        full = [i for i, k in _keys.items() if k and " " + k + " " in qn]
        full = [i for i in full if not any(_keys[i] != _keys[j] and " " + _keys[i] + " " in " " + _keys[j] + " " for j in full)]
        covered = {t for i in full for t in _keys[i].split()}
        last = {}
        for i, k in _keys.items():
            tok = k.split()[-1] if k else ""
            if len(tok) >= 4 and tok not in STOP and tok not in covered and " " + tok + " " in qn:
                last.setdefault(tok, []).append(i)
        ambiguous = [(t, ids) for t, ids in last.items() if len(ids) > 1]
        if ambiguous:
            return [], ambiguous[0]
        hits = [(qn.index(" " + _keys[i] + " "), i) for i in full] + [(qn.index(" " + t + " "), ids[0]) for t, ids in last.items()]
        seen, out = set(), []
        for _, i in sorted(hits):
            if i not in seen:
                seen.add(i)
                out.append(i)
        if out:
            return out[:limit], None

        # First / middle name fallback (e.g. "Gabriel", "Bukayo", "Erling")
        other = {}
        for i, k in _keys.items():
            for tok in k.split()[:-1]:
                if len(tok) >= 4 and tok not in STOP and " " + tok + " " in qn:
                    other.setdefault(tok, []).append(i)
        amb_other = [(t, ids) for t, ids in other.items() if len(ids) > 1]
        if amb_other:
            return [], amb_other[0]
        if other:
            hits_o = [(qn.index(" " + t + " "), ids[0]) for t, ids in other.items()]
            return [i for _, i in sorted(hits_o)][:limit], None

        # Fuzzy fallback for minor spelling typos (e.g. "Haalland", "Sakka", "Gyokerez")
        q_tokens = [t for t in norm_name(q).split() if len(t) >= 4 and t not in STOP and t not in COMMON_QUERY_WORDS]
        fuzzy_hits = []
        for qt in q_tokens:
            best_score, best_ids = 0.0, []
            for i, k in _keys.items():
                surname = k.split()[-1] if k else ""
                if len(surname) < 4:
                    continue
                sc = SequenceMatcher(None, qt, surname).ratio()
                if sc >= 0.84:
                    if sc > best_score + 0.01:
                        best_score, best_ids = sc, [i]
                    elif abs(sc - best_score) <= 0.01:
                        best_ids.append(i)
            if len(best_ids) == 1 and best_ids[0] not in fuzzy_hits:
                fuzzy_hits.append(best_ids[0])
        return fuzzy_hits[:limit], None

    def find_club(self, q: str) -> str | None:
        qn = " " + norm_name(q) + " "
        for k in sorted(self.club_keys, key=len, reverse=True):
            if " " + k + " " in qn:
                return self.club_keys[k]
        return None

    def find_nation(self, q: str) -> str | None:
        qn = " " + norm_name(q) + " "
        for k in sorted(NATION_ALIASES, key=len, reverse=True):
            if " " + k + " " in qn:
                code = NATION_ALIASES[k]
                if not self.nations or code in self.nations:
                    return code
        return None

    def unknown_names(self, q: str) -> list[str]:
        """Capitalised words that look like a name but are not in the sample (for 'outside the sample' answers)."""
        known = COMMON_QUERY_WORDS | set(POS_WORDS) | set(self.vocab)
        for p in FEATURE_WORDS:
            known.update(p.split())
        for p in RAW_STAT_WORDS:
            known.update(p.split())
        for p in NATION_ALIASES:
            known.update(p.split())
        for p in GLOSSARY:
            known.update(p.split())
        for p in GLOSSARY_ALIASES:
            known.update(p.split())
        for c in self.club_keys:
            known.update(c.split())
        out = []
        q_stripped = q.lstrip()
        for m in re.finditer(r"\b[A-ZÀ-Ý][a-zà-ÿ'’]+(?:[- ][A-ZÀ-Ý][a-zà-ÿ'’]+)*", q_stripped):
            w = m.group(0)
            parts = [norm_name(p.replace("’s", "").replace("'s", "")) for p in re.split(r"[- ]", w)]
            if m.start() == 0 and len(parts) == 1 and len(q_stripped.split()) > 2 and not re.search(r"['’]s\b", w):
                continue
            if all(p and p not in known for p in parts) and len(w) >= 4:
                out.append(w.replace("’s", "").replace("'s", ""))
        return out


def find_features(q: str) -> list[str]:
    qn = " " + norm_name(q) + " "
    found = []
    for p in _phrases:
        for v in {p, p[:-1] if p.endswith("s") else p}:
            tag = " " + v + " "
            if tag in qn:
                if FEATURE_WORDS[p] not in found:
                    found.append(FEATURE_WORDS[p])
                qn = qn.replace(tag, " ")
                break
    return found


def find_position(q: str) -> str | None:
    qn = " " + norm_name(q) + " "
    for w in sorted(POS_WORDS, key=len, reverse=True):
        if " " + w + " " in qn:
            return POS_WORDS[w]
    return None


# ------------------------------------------------------------------ notebook cell 45
def wants_scouting(q: str) -> bool:
    qn = " " + norm_name(q) + " "
    return bool(set(qn.split()) & SCOUT_WORDS) or any(p in qn for p in SCOUT_PHRASES)


def parse_scout_params(q: str) -> dict:
    ql = q.lower().replace(",", "")
    p = dict(ratio=None, cap_eur=None, min_eur=None, max_age=None, min_age=None, younger=False, n=5, n_given=False,
             any_price=False, min_minutes=None, max_minutes=None,
             price_basis="listed" if re.search(r"\blisted\b|\bmarket value|\bmkt value|\btransfermarkt\b", ql) else "estimated")

    # 1. Explicit money ranges ("35 million to 55 million", "between £20m and £40m", "35-55m")
    rng_m = re.search(
        r"(?:between|from|in the range of|range(?: of)?|within)?\s*[£€$]?(\d+(?:\.\d+)?)\s*(?:" + UNIT + r")?\s*(?:to|and|-|–|—)\s*[£€$]?(\d+(?:\.\d+)?)\s*" + UNIT,
        ql,
    )
    if rng_m:
        a, b = float(rng_m.group(1)) * 1e6, float(rng_m.group(2)) * 1e6
        p["min_eur"], p["cap_eur"] = min(a, b), max(a, b)
        ql = ql[:rng_m.start()] + " " + ql[rng_m.end():]
    else:
        around_m = re.search(r"\b(?:around|about|roughly|approximately|near|~)\s*[£€$]?(\d+(?:\.\d+)?)\s*" + UNIT, ql)
        if around_m:
            v = float(around_m.group(1)) * 1e6
            p["min_eur"], p["cap_eur"] = v * 0.8, v * 1.2
            ql = ql[:around_m.start()] + " " + ql[around_m.end():]
        else:
            spans = []
            for m in re.finditer(r"[£€$]?(\d+(?:\.\d+)?)(\+)?\s*" + UNIT, ql):
                before = ql[max(0, m.start() - 20):m.start()]
                value = float(m.group(1)) * 1e6
                if m.group(2) == "+" or re.search(r"\b(?:over|above|more than|at least|minimum|min|greater than|from)\b|>", before):
                    p["min_eur"] = value
                else:
                    p["cap_eur"] = value
                spans.append((m.start(), m.end()))
            for st_idx, en_idx in reversed(spans):
                ql = ql[:st_idx] + " " + ql[en_idx:]

    # 2. Percentage of target value
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", ql)
    if m:
        p["ratio"] = float(m.group(1)) / 100
    elif re.search(r"\bhalf\b", ql):
        p["ratio"] = 0.5
    elif re.search(r"\b(?:a|one) third\b", ql):
        p["ratio"] = 1 / 3
    elif re.search(r"\bquarter\b", ql):
        p["ratio"] = 0.25

    # 3. Minutes bounds ("at least 1500 minutes", "under 1500 minutes")
    m_max_min = re.search(r"\b(?:under|fewer than|less than|below|max(?:imum)?)\s*(\d{3,4})\s*min(?:ute)?s?\b", ql)
    if m_max_min:
        p["max_minutes"] = int(m_max_min.group(1))
        ql = ql.replace(m_max_min.group(0), " ")
    m = re.search(r"(\d{3,4})\s*(?:\+\s*)?min(?:ute)?s?\b", ql)
    if m:
        p["min_minutes"] = int(m.group(1))
        ql = ql.replace(m.group(0), " ")

    # 4. Age ranges & bounds ("aged 20 to 24", "between 21 and 25", "under 23", "28+", "prime age")
    age_rng = (
        re.search(r"\b(?:aged?|between|from|in the (?:age )?range of|age range(?: of)?)\s*(\d{2})\s*(?:to|and|-|–|—)\s*(\d{2})\b" + NOT_MONEY, ql)
        or re.search(r"\b(\d{2})\s*(?:to|-|–|—)\s*(\d{2})\s*(?:years? old|yo|y/o|yrs?)\b", ql)
    )
    if age_rng:
        a1, a2 = int(age_rng.group(1)), int(age_rng.group(2))
        if 15 <= min(a1, a2) and max(a1, a2) <= 45:
            p["min_age"], p["max_age"] = min(a1, a2), max(a1, a2)

    m = (re.search(r"(?:younger than|under|below|up to|at most|no older than|max(?:imum)? age(?: of)?|aged? (?:under|below))\s*(\d{2})\b" + NOT_MONEY, ql)
         or re.search(r"\b(\d{2})\s*or younger\b", ql))
    if m and 15 <= int(m.group(1)) <= 45:
        p["max_age"] = int(m.group(1))
    m = re.search(r"\bu-?(\d{2})\b", ql)
    if m and p["max_age"] is None and 15 <= int(m.group(1)) <= 45:
        p["max_age"] = int(m.group(1))
    m = (re.search(r"(?:older than|over|above|at least|min(?:imum)? age(?: of)?|aged? (?:over|above))\s*(\d{2})\b" + NOT_MONEY, ql)
         or re.search(r"\b(\d{2})\s*(?:or older|\+)\b" + NOT_MONEY, ql))
    if m and 15 <= int(m.group(1)) <= 45:
        p["min_age"] = int(m.group(1))
    if p["min_age"] is None and p["max_age"] is None:
        m_ex = re.search(r"\b(?:aged|age)\s*(\d{2})\b|\b(\d{2})\s*(?:years? old|yo|y/o)\b", ql)
        if m_ex:
            exact_a = int(m_ex.group(1) or m_ex.group(2))
            if 15 <= exact_a <= 45:
                p["min_age"] = p["max_age"] = exact_a
        elif re.search(r"\bprime(?: age)?\b", ql):
            p["min_age"], p["max_age"] = 24, 28
        elif re.search(r"\bveterans?\b|\bexperienced\b", ql):
            p["min_age"] = 29

    if p["max_age"] is None:
        if re.search(r"\byoung(?:ster|sters)?\b|\bprospects?\b", ql):
            p["max_age"] = 23
        elif re.search(r"\byounger\b", ql):
            p["younger"] = True

    # 5. Count N
    m = (re.search(r"\b(?:top|best|first|list|show)\s+(\d{1,2})\b" + NOT_MONEY, ql)
         or re.search(r"\b(\d{1,2})\s+(?:\w+\s+)?(?:players|forwards|midfielders|defenders|attackers|strikers|alternatives|options|replacements|candidates|names)\b", ql))
    if m:
        p["n"] = max(1, min(25, int(m.group(1))))
        p["n_given"] = True
    else:
        for w, k in NUMW.items():
            if re.search(rf"\b{w}\s+(?:\w+\s+)?(?:players?|forwards?|midfielders?|defenders?|attackers?|strikers?|alternatives?|options?|replacements?|candidates?)\b|\b(?:top|best|first)\s+{w}\b", ql):
                p["n"] = k
                p["n_given"] = True
                break
    p["any_price"] = bool(re.search(r"any price|regardless of (?:the )?(?:price|cost|value)|any budget|no budget|whatever (?:the )?price|any cost|at any cost", ql))
    return p


# ------------------------------------------------------------------ NEW: profile descriptions
PROFILE_WORDS = {
    "creates chances": ["key_passes_p90", "xa_p90", "big_chances_created_p90"], "create chances": ["key_passes_p90", "xa_p90", "big_chances_created_p90"],
    "creative": ["key_passes_p90", "xa_p90", "big_chances_created_p90"], "chance creator": ["key_passes_p90", "xa_p90", "big_chances_created_p90"],
    "playmaker": ["key_passes_p90", "xa_p90", "touches_p90"], "creator": ["key_passes_p90", "xa_p90", "big_chances_created_p90"],
    "scores": ["np_goals_p90", "xg_p90"], "goalscorer": ["np_goals_p90", "xg_p90"], "goal scorer": ["np_goals_p90", "xg_p90"],
    "finisher": ["np_goals_p90", "xg_p90", "shots_on_target_p90"], "clinical": ["np_goals_p90", "shots_on_target_p90"],
    "scoring": ["np_goals_p90", "xg_p90"], "goal threat": ["xg_p90", "shots_p90"],
    "dribbler": ["dribbles_p90", "was_fouled_p90"], "dribbles": ["dribbles_p90"], "takes players on": ["dribbles_p90"], "beats players": ["dribbles_p90"],
    "wins headers": ["aerial_won_p90"], "good in the air": ["aerial_won_p90"], "aerial": ["aerial_won_p90"], "headers": ["aerial_won_p90"],
    "ball winner": ["tackles_won_p90", "ball_recovery_p90"], "wins the ball": ["tackles_won_p90", "ball_recovery_p90"],
    "tackler": ["tackles_won_p90"], "tackles": ["tackles_won_p90"], "wins tackles": ["tackles_won_p90"],
    "reads the game": ["interceptions_p90"], "intercepts": ["interceptions_p90"], "interceptions": ["interceptions_p90"],
    "defensive": ["tackles_won_p90", "interceptions_p90", "clearances_p90"], "defends well": ["tackles_won_p90", "interceptions_p90", "clearances_p90"],
    "passer": ["pass_accuracy", "touches_p90"], "good passer": ["pass_accuracy", "touches_p90"], "keeps the ball": ["pass_accuracy"],
    "accurate passing": ["pass_accuracy"], "on the ball": ["touches_p90", "pass_accuracy"], "involved": ["touches_p90"],
    "shoots a lot": ["shots_p90"], "shooter": ["shots_p90", "shots_on_target_p90"], "assists": ["assists_p90", "xa_p90"],
    "recovers the ball": ["ball_recovery_p90"], "presses": ["ball_recovery_p90", "tackles_p90"],
}
VAGUE_WORDS = {"attacking": ("scoring (xG, goals)", "creating (xA, key passes)"),
               "good": ("scoring", "creating chances"), "complete": ("attacking output", "defending"),
               "quality": ("scoring", "creating chances"), "talented": ("scoring", "creating chances"),
               "offensive": ("scoring (xG, goals)", "creating (xA, key passes)")}
_profile_phrases = sorted(PROFILE_WORDS, key=len, reverse=True)


def map_profile(q: str) -> tuple[list[str], list[str], str | None]:
    """Returns (features, phrases matched, vague word if the description is too vague)."""
    qn = " " + norm_name(q) + " "
    feats, matched = [], []
    for p in _profile_phrases:
        if " " + p + " " in qn:
            matched.append(p)
            qn = qn.replace(" " + p + " ", " ")
            for f in PROFILE_WORDS[p]:
                if f not in feats:
                    feats.append(f)
    vague = None
    if not feats:
        for w in VAGUE_WORDS:
            if f" {w} " in " " + norm_name(q) + " ":
                vague = w
                break
    return feats, matched, vague


def find_glossary_term(q: str) -> str | None:
    qn = " " + norm_name(q.replace("/90", " per 90").replace("-", " ")) + " "
    cands = {**{k: k for k in GLOSSARY}, **GLOSSARY_ALIASES}
    for t in sorted(cands, key=len, reverse=True):
        tn = norm_name(t)
        if tn and " " + tn + " " in qn:
            return cands[t]
    return None


# ------------------------------------------------------------------ NEW: intent detection
OUT_OF_SCOPE = [
    (r"\btransfer fee|\bfee\b|\bbid\b|\bwhat (?:will|would) .* pay|\bhow much (?:will|would|should) .* (?:pay|cost to buy)|release clause|\bbuyout", "fee"),
    (r"\bwill (?:he|they|\w+) (?:sign|join|move|leave)|\bsign for\b|\bgoing to sign|\btransfer rumou?r|\bjoin (?:us|our club)", "sign"),
    (r"\binjur|\bfitness\b|\bmedical\b", "injury"),
    (r"\bcontract|\bwages?\b|\bsalary|\bagent\b|\bexpir", "contract"),
    (r"\breputation|\bfamous|\bpopular|\bsocial media|\bfollowers|\bpersonality|\battitude|\boff[- ]field|\bcharacter\b", "reputation"),
    (r"\bnext season|\bin the future\b|\bwill (?:he|\w+) score|\bpredict (?:his|the) (?:goals|future)|\bfuture potential\b|\bpredict .* potential\b", "future"),
    (r"\bgoalkeeper|\bkeeper\b|\bgk\b", "goalkeeper"),
]
COMMON_QUERY_WORDS = {
    "i", "premier", "league", "shap", "xg", "xa", "xgboost", "fbref", "kaggle", "transfermarkt", "csv", "epl",
    "what", "why", "how", "who", "which", "show", "find", "compare", "list", "top", "give", "tell", "explain",
    "is", "are", "can", "could", "would", "the", "a", "an", "and", "or", "of", "in", "for", "to", "me", "my", "his", "their",
    "rank", "ranking", "rankings", "best", "worst", "better", "worse", "now", "only", "export", "summarise", "summarize",
    "define", "where", "when", "does", "do", "did", "estimate", "estimated", "value", "valued", "values", "valuation",
    "valuations", "worth", "price", "priced", "listed", "market", "please", "hi", "hello", "hey", "thanks", "thank", "ok",
    "rmse", "mae", "per", "u", "most", "least", "fewest", "highest", "lowest", "cheapest", "expensive", "undervalued",
    "overvalued", "bargain", "bargains", "young", "younger", "youngest", "old", "older", "oldest", "player", "players",
    "squad", "squads", "roster", "club", "clubs", "team", "teams", "season", "matchday", "stats", "statistics", "numbers", "profile",
    "model", "models", "accuracy", "accurate", "performance", "error", "errors", "methodology", "pipeline", "work", "works",
    "random", "forest", "linear", "regression", "dashboard", "scout", "scouting", "alternative", "alternatives",
    "replacement", "replacements", "similar", "similarity", "cheap", "cheaper", "good", "all", "every", "any", "reset", "clear",
    "buy", "buying", "sign", "signing", "recruit", "recruitment", "budget", "range", "between", "from", "around", "about",
    "million", "millions", "pound", "pounds", "strengths", "strength", "weakness", "weaknesses", "limitations", "limitation",
    "caveats", "radar", "waterfall", "dependence", "scatter", "nationality", "nation", "nations", "countries", "country",
    "england", "france", "spain", "brazil", "portugal", "netherlands", "germany", "argentina", "belgium", "italy",
}

GREET_RE = re.compile(
    r"^\s*(?:hi+|he+y+|he+l+o+|yo+|good (?:morning|afternoon|evening)|greetings|sup|what'?s up)\s*[!?.]*$|"
    r"\bwho+\s+are+\s+y+o+u+\b|\bwhat\s+are\s+y+o+u+\b|\bwhat'?s\s+your\s+name\b|"
    r"\bare\s+you\s+(?:an?\s+)?(?:ai|bot|chatbot|gemini|llm|gpt|claude|connected)\b|"
    r"\b(?:did|have)\s+you\s+connect(?:ed)?\s+(?:to\s+)?gemini\b|\bgemini\s+(?:api|status|connected)\b|"
    r"^\s*(?:thanks+|thank\s+y+o+u+|thx)\b"
)
HOWTO_RE = re.compile(r"\bhow (?:do|can|should) i\b|\bhow to\b|\bwhere (?:can|do) i\b|\bwhere (?:is|are) (?:the|this)\b|\bwhere do i find\b|"
                      r"\bopen the\b|\btake me to\b|\bhelp me (?:use|with)\b|\bi'?m stuck\b|\bgo to\b|\bwhat can you do\b|^help\b")
MODEL_RE = re.compile(r"\bhow does the model work\b|\bhow (?:is|are) (?:the )?model\b|\bhow (?:is|are) (?:player |market )?valu(?:es?|ed|ations?) "
                      r"(?:calculated|computed|predicted|estimated|modeled|modelled)\b|\bhow accurate\b|\bmodel accuracy\b|"
                      r"\bmodel performance\b|\bmodel error\b|\bmethodology\b|\bwhich model\b|\bcompare (?:the )?models\b|"
                      r"\br2\b|\br[- ]squared\b|\bxgboost vs\b|\btrain(?:ing)? (?:and|vs) test\b|\bbase value of the model\b|"
                      r"\bwhat features (?:does|are in) the model\b|\blist (?:all )?(?:the )?features\b|\b28 features\b")
ABOUT_RE = re.compile(r"\blimitations?\b|\bcaveats?\b|\bweaknesses of the (?:model|tool|system|app)\b|"
                      r"\babout this (?:tool|app|project|site|thesis|prototype)\b|\bwhat does this (?:tool|app|site|prototype) do\b|"
                      r"\bname[- ]matching\b|\bfuzzy matching\b|\bevaluation console\b|\bsus score\b|\bsynthetic (?:data|target)\b")
CLUB_AGG_RE = re.compile(r"\bsquad values?\b|\bclub values?\b|\bteam values?\b|\bmost valuable (?:clubs?|teams?|squads?)\b|"
                         r"\brank (?:the )?(?:clubs?|teams?)\b|\bwhich (?:club|team) has the (?:highest|most|lowest|best|strongest)\b|"
                         r"\bclubs? by team strength\b|\bstrongest (?:clubs?|teams?)\b|\blist (?:all )?(?:the )?clubs\b|\bhow many clubs\b")
POS_AGG_RE = re.compile(r"\baverage value by position\b|\bvalue by position\b|\bcompare (?:the )?positions\b|"
                        r"\bposition averages?\b|\bwhich position is (?:worth|valued) (?:the )?(?:most|highest|least)\b")
SCATTER_RE = re.compile(r"\blisted vs\.? (?:model[- ]?)?estimated\b|\bestimated vs\.? listed\b|"
                        r"\babove the (?:dashed )?line\b|\bbelow the (?:dashed )?line\b|\bbiggest gap between listed and estimated\b")
BUY_RE = re.compile(r"\bto buy\b|\bto sign\b|\bshould (?:i|we) (?:buy|sign)\b|\brecruit|\btransfer target|\bwithin (?:a |the )?budget\b|\bbudget of\b|\bin the range of\b")
STRENGTH_RE = re.compile(r"\bstrengths?\b|\bweakness(?:es)?\b|\bweak points?\b|\bstrong points?\b|\bareas? to improve\b|\bpros and cons\b|"
                         r"\bwhat is .* good at\b|\bwhat is .* bad at\b")
RADAR_RE = re.compile(r"\bradar\b|\bspider chart\b|\bpercentile comparison\b|\bpercentiles for\b")
STATS_RE = re.compile(r"\bstats\b|\bstatistics\b|\bstat line\b|\bseason output\b|\bhow many (?:goals|assists|minutes|appearances|starts|cards|yellow|red|clean sheets|penalties)\b|"
                      r"\bprofile\b|\bnationality\b|\bwhere is .* from\b|\bhow old is\b|\bwhat age is\b|\bwhich club does .* play\b")
DEFINE_RE = re.compile(r"\bwhat (?:is|are|does|'?s)\b|\bwhat is meant by\b|\bdefine\b|\bdefinition\b|\bmeaning of\b|\bmean\b|\bstand for\b|"
                       r"\bexplain (?:the term|what)\b|\bwhat do you mean\b")
DATA_RE = re.compile(r"\bsource|\bfiles?\b|\bfbref\b|\bkaggle\b|\bfilled\b|\bmissing\b|\bmatchday|\bgame ?day|"
                     r"\b(?:which|what) season\b|\bseason cover|"
                     r"\bcover(?:s|age)?\b|\bhow many players\b|\bhow many (?:defenders|midfielders|forwards|attackers)\b|\bexcluded|"
                     r"\bnot in (?:the )?(?:sample|data|list)|\bwhy (?:is|isn'?t) .* (?:not )?(?:in|included)|\bcolumns?\b|\bsample size\b|"
                     r"\bdata quality\b|\bwhere does the data\b|\bup to date\b|\bhow many .* (?:are there|return|match|pass)")
RANK_RE = re.compile(r"\btop\b|\bbest\b|\bhighest\b|\blowest\b|\bmost\b|\bfewest\b|\bleast\b|\brank|\blist\b|"
                     r"\bwho (?:has|have|scored)\b|\bwho (?:is|are) (?:the|our|most|best|top|highest|lowest|cheapest|youngest|oldest)\b|"
                     r"\bmost valuable\b|\bexpensive\b|\bcheapest\b|\bleaders?\b|\bundervalued\b|\bovervalued\b|\bbargains?\b|\bvalue for money\b|"
                     r"\byoungest\b|\boldest\b|\btop scorers?\b|\bleading scorers?\b|\bgolden boot\b")
WHY_RE = re.compile(r"\bwhy\b|\bexplain\b|\bbreakdown\b|\bbreak down\b|\bshap\b|\bdrivers?\b|\bwhat makes\b|\bwhat drives\b|\breasons?\b|\bwaterfall\b")
VALUE_RE = re.compile(r"\bworth\b|\bvalue\b|\bvalued\b|\bhow much\b|\bestimate|\bprice\b|\bcost\b|\bvaluation\b|\bconfident\b|\bconfidence\b")
COMPARE_RE = re.compile(r"\bcompare\b|\bcomparison\b|\bvs\.?\b|\bversus\b|\bside by side\b|\bagainst\b|\bhead to head\b")
DIFF_RE = re.compile(r"\bwhy\b.*\b(?:higher|more|lower|less|above|below|than|differ)|\bdifference\b|\bdiffer\b")
WHATIF_RE = re.compile(r"\bwhat if\b|\bwhat would happen if\b|\bif (?:he|she|\w+) (?:had|scored|got|made|played|was|were)\b|"
                       r"\b(?:increased|decreased|rose|dropped|went up|went down) to\b|\bhypothetical")
SUMMARY_RE = re.compile(r"\bsummar(?:y|ise|ize)\b|\bsum up\b|\bin a few sentences\b")
EXPORT_RE = re.compile(r"\bexport\b|\bdownload\b|\bcsv\b|\bcopy (?:the|this|it)\b|\bsave (?:the|this) (?:list|shortlist)\b")
GROUP_RE = re.compile(r"\bgroups?\b|\bcategor(?:y|ies)\b|\battacking output\b|\bcreativity\b|\bdefending\b|\bdiscipline\b")
FOLLOW_RE = re.compile(r"^(?:now|and|also|ok|okay|what about|how about|same|only|just|but|then|instead|make it|limit|raise|lower|change|switch|show (?:me )?more)\b")
PRONOUN_RE = re.compile(r"\b(?:he|him|his|they|them|their|this player|that player|the target)\b")
ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
           "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}


def find_ordinal(q: str) -> int | None:
    ql = q.lower()
    m = re.search(r"(?:#|number |no\.? ?)(\d{1,2})\b", ql)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|1st|2nd|3rd|4th|5th)\b(?: one| player| candidate| name| option)?", ql)
    if m and re.search(r"\b(?:one|player|candidate|name|option|on the list|in the list)\b|^the (?:first|second|third)", ql):
        return ORDINAL[m.group(1)]
    return None


def out_of_scope(q: str) -> str | None:
    ql = q.lower()
    for pat, kind in OUT_OF_SCOPE:
        if re.search(pat, ql):
            return kind
    return None
