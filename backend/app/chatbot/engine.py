"""Chatbot engine: intent routing, answers built only from computed outputs, session context.

Answer templates `valuation`, `explain_player`, `explain_compare`, `explain_player_feature`, `explain_feature`,
`explain_global`, `scout`, `pair` port notebook cell 44-45 (txt_player, txt_compare, txt_player_feature,
txt_feature, txt_global, txt_scout, txt_pair). Every number is formatted through `Facts`.
"""
from __future__ import annotations

import csv
import io
import re
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np

from ..constants import CAT_FEATURES, GROUPS, NUM_FEATURES, PERF_GROUPS, POS_NAME, RADAR, RADAR_LABELS, SIM_FEATURES, TOOLTIPS, pretty
from ..data import norm_name
from ..similarity import ScoutQuery
from . import nlu
from .facts import Facts, check_numbers
from .glossary import GLOSSARY, HOWTO

POS_PLURAL = {"D": "defenders", "M": "midfielders", "F": "forwards"}


@dataclass
class Session:
    target: int | None = None
    players: list[int] = field(default_factory=list)
    scout: dict | None = None
    shortlist: list[int] = field(default_factory=list)
    table: dict | None = None
    last_intent: str | None = None
    pending: dict | None = None
    touched: float = field(default_factory=time.time)


class Reply:
    def __init__(self, intent: str, facts: Facts):
        self.intent = intent
        self.F = facts
        self.text = ""
        self.details = ""
        self.table = None
        self.chart = None
        self.suggestions: list[str] = []
        self.actions: list[dict] = []
        self.context_note = None
        self.understood = True
        self.subintent = None

    def to_dict(self) -> dict:
        full = "\n\n".join(x for x in [self.text, self.details] if x)
        if self.table:
            full += "\n" + " ".join(" ".join(str(v) for k, v in r.items() if not k.startswith("_")) for r in self.table["rows"])
        chk = check_numbers(full, self.F)
        return {"intent": self.intent, "subintent": self.subintent, "text": self.text, "details": self.details or None,
                "table": self.table, "chart": self.chart, "suggestions": self.suggestions[:2], "actions": self.actions,
                "context_note": self.context_note, "understood": self.understood, "numbers": chk}


class ChatEngine:
    def __init__(self, store, max_sessions: int = 500):
        self.st = store
        self.d = store.d
        self.lex = nlu.Lexicon(
            self.d["player_name"].tolist(),
            self.d["team_name"].unique().tolist(),
            self.d["nation"].dropna().unique().tolist() if "nation" in self.d.columns else [],
        )
        self.sessions: OrderedDict[str, Session] = OrderedDict()
        self.max_sessions = max_sessions
        meta = store.b["settings"]
        self.always = {"90", "0", "1", str(meta["min_minutes"]), str(meta["kaggle_matchday"]), "2025", "26",
                       str(store.n), "5", "60"}

    # ------------------------------------------------------------------ helpers
    def session(self, sid: str | None) -> tuple[str, Session]:
        sid = sid if sid and re.fullmatch(r"[A-Za-z0-9_-]{6,64}", sid) else uuid.uuid4().hex
        s = self.sessions.pop(sid, None) or Session()
        s.touched = time.time()
        self.sessions[sid] = s
        while len(self.sessions) > self.max_sessions:
            self.sessions.popitem(last=False)
        return sid, s

    def syn(self) -> str:
        return " *Prototype value (synthetic target).*" if self.st.synthetic else ""

    def name(self, i) -> str:
        return self.d.at[i, "player_name"]

    def who(self, i, F: Facts) -> str:
        r = self.d.loc[i]
        return f"**{r['player_name']}** ({r['team_name']}, {POS_NAME[r['position']]}, age {F.int(r['age'])})"

    def est(self, i) -> float:
        return float(self.d.at[i, "estimated_value_eur"])

    def pos_pct_text(self, i, f, F: Facts) -> str:
        p = float(self.st.pct_in_pos.at[i, f])
        pos = POS_NAME[self.d.at[i, "position"]].lower()
        return f"the highest among {pos}s" if p >= 99.9 else f"higher than {F.int(p)}% of {pos}s"

    def profile_link(self, i) -> dict:
        return {"label": f"Open {self.name(i)}'s profile", "href": f"/players/{int(i)}"}

    # ------------------------------------------------------------------ entry point
    def answer(self, message: str, session_id: str | None = None) -> dict:
        sid, s = self.session(session_id)
        q = (message or "").strip()[:500]
        F = Facts(self.always)
        try:
            r = self.route(q, s, F)
        except Exception as e:   # never show a stack trace to the user
            r = Reply("error", F)
            r.understood = False
            r.text = "Sorry, something went wrong while computing that answer. Please try rephrasing the question."
            r.subintent = type(e).__name__
        s.last_intent = r.intent if r.intent not in ("clarify", "error") else s.last_intent
        out = r.to_dict()
        out["session_id"] = sid
        out["context"] = {"target": self.st.summary(s.target) if s.target is not None else None,
                          "shortlist": [int(x) for x in s.shortlist], "filters": s.scout}
        return out

    # ------------------------------------------------------------------ routing
    def route(self, q: str, s: Session, F: Facts) -> Reply:
        if not q:
            return self.clarify(F, "What would you like to know?")
        ql = q.lower()

        if re.search(r"^(?:reset|clear|new chat|start over|forget)\b", ql):
            s.target = None
            s.players.clear()
            s.scout = None
            s.shortlist.clear()
            s.table = None
            s.last_intent = None
            s.pending = None
            r = Reply("howto", F)
            r.subintent = "reset"
            r.text = "Context cleared. Ask about any player, valuation, scouting shortlist, comparison, or ranking."
            r.suggestions = [f"How much is {self.name(self._top())} worth?", "Who are the most undervalued midfielders?"]
            return r

        # resolve a pending clarification ("which Gabriel?")
        if s.pending and s.pending.get("type") == "ambiguous":
            ids = s.pending["ids"]
            pick = None
            o = nlu.find_ordinal(q) or (int(q) if q.isdigit() else None)
            if o and 1 <= o <= len(ids):
                pick = ids[o - 1]
            else:
                qn = norm_name(q)
                m = [i for i in ids if qn and qn in self.lex.keys[i]]
                pick = m[0] if len(m) == 1 else None
            if pick is not None:
                orig = s.pending["question"].replace(s.pending["token"], self.name(pick), 1) if s.pending["token"] in s.pending["question"] else self.name(pick)
                s.pending = None
                return self.route(orig if self.lex.find_players(orig)[0] else self.name(pick), s, F)
            s.pending = None

        players, amb = self.lex.find_players(q)
        if amb:
            tok, ids = amb
            s.pending = {"type": "ambiguous", "ids": ids[:6], "question": q, "token": next((w for w in re.findall(r"[\w'’]+", q) if norm_name(w) == tok), tok)}
            r = Reply("clarify", F)
            r.text = (f"I found several players called **{tok.title()}**: " +
                      ", ".join(f"{F.int(k)}. {self.name(i)} ({self.d.at[i, 'team_name']})" for k, i in enumerate(ids[:6], 1)) +
                      ". Which one do you mean?")
            r.suggestions = [self.name(i) for i in ids[:2]]
            return r

        kind = nlu.out_of_scope(q)
        if kind:
            return self.decline(kind, players, F)

        if nlu.GREET_RE.search(ql) and not players:
            return self.greet(ql, F)
        if nlu.HOWTO_RE.search(ql) and not players:
            return self.howto(ql, F)
        if nlu.EXPORT_RE.search(ql):
            return self.export(s, F)
        if nlu.SUMMARY_RE.search(ql):
            return self.summarise(s, F)

        feats = nlu.find_features(q)
        raw_stats = nlu.find_raw_stats(q)
        pos = nlu.find_position(q)
        club_mention = self.lex.find_club(q)
        nation = self.lex.find_nation(q)
        scout_p = nlu.parse_scout_params(q)
        has_budget_or_age = any([
            scout_p["min_eur"], scout_p["cap_eur"], scout_p["min_age"], scout_p["max_age"],
            scout_p["min_minutes"], scout_p["max_minutes"],
        ])
        if feats == ["position"] and pos:
            feats = []
        if feats == ["nation_group"] and nation and (nlu.RANK_RE.search(ql) or nlu.BUY_RE.search(ql) or pos):
            feats = []

        if not players and nlu.ABOUT_RE.search(ql) and not (nlu.DEFINE_RE.search(ql) and len(q.split()) <= 5):
            return self.about_project(q, F)
        if not players and nlu.CLUB_AGG_RE.search(ql):
            return self.club_summary(q, F)
        if not players and nlu.POS_AGG_RE.search(ql):
            return self.position_summary(F)
        if not players and nlu.SCATTER_RE.search(ql):
            return self.listed_vs_estimated(q, pos, s, F)
        if not players and nlu.MODEL_RE.search(ql):
            return self.model_overview(q, F)

        term = nlu.find_glossary_term(q)
        if (term and nlu.DEFINE_RE.search(ql) and not players and not pos and not club_mention
                and not nation and not has_budget_or_age and not nlu.RANK_RE.search(ql) and not nlu.BUY_RE.search(ql)):
            return self.glossary(term, F)

        # follow-ups that use the session context
        resolved_note = None
        if not players:
            o = nlu.find_ordinal(q)
            if o and s.shortlist and 1 <= o <= len(s.shortlist):
                players = [s.shortlist[o - 1]]
            elif re.search(r"\b(?:their|them|they|these players|the shortlist|the candidates|those players)\b", ql) and s.shortlist and nlu.WHY_RE.search(ql):
                return self.shortlist_drivers(s, F)
            elif nlu.PRONOUN_RE.search(ql) and (s.target is not None or s.players):
                players = [s.target if s.target is not None else s.players[0]]
            elif s.last_intent in ("scouting",) and s.scout and (nlu.FOLLOW_RE.search(ql) or self._has_scout_params(q)) \
                    and not nlu.RANK_RE.search(ql.replace("top ", "")) and not nlu.BUY_RE.search(ql):
                return self.scout_followup(q, s, F)
            else:
                imp_id, resolved_note = self._resolve_implicit_player(q, pos, F)
                if imp_id is not None:
                    players = [imp_id]

        if nlu.WHATIF_RE.search(ql) and players:
            wf_feat = feats[0] if feats else ("age" if re.search(r"\b(?:was|were|aged|turned)\s+\d{2}\b", ql) else None)
            if wf_feat:
                r = self.whatif(players[0], wf_feat, q, s, F)
                if resolved_note:
                    r.context_note = resolved_note
                return r

        if nlu.DATA_RE.search(ql) and not (players and (nlu.wants_scouting(q) or nlu.STATS_RE.search(ql) or nlu.STRENGTH_RE.search(ql))):
            return self.data_quality(q, players, pos, s, F)

        if len(players) >= 2:
            self._set_players(s, players)
            if nlu.RADAR_RE.search(ql):
                return self.player_radar(players[:4], F)
            if nlu.wants_scouting(q) or re.search(r"\bsimilar|\bsimilarity\b|\balike\b", ql):
                if len(players) == 2:
                    return self.pair(players[0], players[1], F)
            if nlu.DIFF_RE.search(ql) or (nlu.WHY_RE.search(ql) and len(players) == 2):
                return self.explain_compare(players[0], players[1], F)
            return self.compare(players[:4], F)

        if len(players) == 1:
            i = players[0]
            if nlu.PROJECTION_RE.search(ql):
                r = self.player_projection(i, F)
                if resolved_note:
                    r.context_note = resolved_note
                return r
            like_intent = bool(re.search(r"\blike\b(?!\s+(?:that|this|so|it|a|an|the)\b)", ql))
            if (nlu.wants_scouting(q) or like_intent) and not re.search(r"\bwhy\b|\bexplain\b", ql):
                r = self.scout(i, q, s, F)
                if resolved_note:
                    r.context_note = resolved_note
                return r
            self._set_players(s, players)
            if nlu.STRENGTH_RE.search(ql):
                r = self.player_strengths(i, F)
                if resolved_note:
                    r.context_note = resolved_note
                return r
            if nlu.RADAR_RE.search(ql):
                r = self.player_radar([i], F)
                if resolved_note:
                    r.context_note = resolved_note
                return r
            if (nlu.STATS_RE.search(ql) or raw_stats) and not nlu.WHY_RE.search(ql):
                r = self.player_stats(i, F, q=q, raw_stats=raw_stats)
                if resolved_note:
                    r.context_note = resolved_note
                return r
            if feats and not resolved_note:
                return self.explain_player_feature(i, feats[:3], F)
            if nlu.GROUP_RE.search(ql):
                return self.explain_player_groups(i, F)
            if nlu.WHY_RE.search(ql):
                r = self.explain_player(i, F)
                if resolved_note:
                    r.context_note = resolved_note
                return r
            r = self.valuation(i, F, q=q)
            if resolved_note:
                r.context_note = resolved_note
            return r

        # ---- no player in the question ----
        prof_feats, matched, vague = nlu.map_profile(q)
        looking = re.search(
            r"\bfind\b|\blooking for\b|\bneed\b|\bwant\b|\bsearch\b|\bwho (?:is|are|can)\b|\bany\b|\bsuggest\b|\brecommend\b|\bshow me\b|\bto buy\b|\bto sign\b",
            ql,
        )

        unknown = self.lex.unknown_names(q)
        if unknown and not nlu.RANK_RE.search(ql) and not nlu.BUY_RE.search(ql) and not prof_feats and not club_mention and not nation and not has_budget_or_age and (
                nlu.VALUE_RE.search(ql) or nlu.wants_scouting(q) or nlu.WHY_RE.search(ql) or nlu.COMPARE_RE.search(ql)
                or len(q.split()) <= 3):
            return self.outside_sample(unknown, F)

        if nlu.wants_scouting(q) and not prof_feats and not pos and not has_budget_or_age:
            r = self.clarify(F, "Which player should I find alternatives for?")
            r.suggestions = [f"Find cheaper alternatives to {self.name(self._top())}", f"Who can replace {self.name(self._top('F'))} under 40 million?"]
            return r
        if prof_feats and (looking or pos or has_budget_or_age) and not (nlu.RANK_RE.search(ql) and not looking and not has_budget_or_age):
            return self.profile_scout(q, prof_feats, matched, pos, s, F)
        if vague and looking and not has_budget_or_age and not nlu.BUY_RE.search(ql):
            a, b = nlu.VAGUE_WORDS[vague]
            r = self.clarify(F, f"By *{vague}*, do you mean {a} or {b}?")
            p = POS_PLURAL.get(pos, "players")
            r.suggestions = [f"Find young {p} who score goals", f"Find {p} who create chances"]
            return r

        words = set(norm_name(q).split())
        wants_rank = bool(
            nlu.RANK_RE.search(ql)
            or nlu.BUY_RE.search(ql)
            or has_budget_or_age
            or club_mention
            or nation
            or raw_stats
            or (re.search(r"\bwho\b|\bwhich\b", ql) and (feats or pos or "valuable" in ql))
        )
        if feats and not wants_rank:
            return self.explain_feature(feats[0], F) if len(feats) == 1 else self._join(feats[:3], F)
        if (words & nlu.GLOBAL_WORDS or re.search(r"\bwhat drives\b", ql)) and not has_budget_or_age and not nlu.BUY_RE.search(ql):
            if nlu.GROUP_RE.search(ql):
                return self.explain_groups(pos, F)
            return self.explain_global(pos, F)
        if nlu.GROUP_RE.search(ql) and re.search(r"\bmatter|\bimportant|\bmost\b", ql):
            return self.explain_groups(pos, F)
        if wants_rank:
            return self.ranking(q, feats, pos, s, F, raw_stats=raw_stats)
        if feats:
            return self.explain_feature(feats[0], F) if len(feats) == 1 else self._join(feats[:3], F)
        if term:
            return self.glossary(term, F)
        if re.search(r"^(?:hi|hello|hey|thanks|thank you)\b", ql):
            r = Reply("howto", F)
            r.text = "Hello! I answer questions about player values, SHAP breakdowns, scouting alternatives, comparisons, budget searches, and rankings across all tabs."
            r.suggestions = [f"How much is {self.name(self._top())} worth?", "What is the best attacker to buy between 35m and 55m?"]
            return r
        return self.clarify(F, "I'm not sure what you're asking. Could you rephrase it, for example in one of these ways?", examples=True)

    def _resolve_implicit_player(self, q: str, pos: str | None, F: Facts) -> tuple[int | None, str | None]:
        """Resolve singular superlative descriptions like 'the top scorer' or 'the highest-valued forward'."""
        ql = q.lower()
        sp = nlu.parse_scout_params(q)
        if nlu.BUY_RE.search(ql) or any([sp["min_eur"], sp["cap_eur"], sp["min_age"], sp["max_age"]]):
            return None, None
        singular_noun = r"(?:scorer|goalscorer|assister|player|forward|attacker|striker|winger|midfielder|defender|centre[- ]back|full[- ]back)"
        has_ref = re.search(rf"\b(?:the\s+)?(?:top|leading|highest[- ]valued|most valuable|best|cheapest|youngest|oldest)\s+{singular_noun}\b", ql)
        if not has_ref:
            return None, None
        wants_single = (
            nlu.wants_scouting(q)
            or nlu.WHATIF_RE.search(ql)
            or nlu.STRENGTH_RE.search(ql)
            or re.search(r"\b(?:value|valuation|worth|estimate|estimated|how much|explain|breakdown|why is|stats|profile|radar)\b", ql)
        )
        if not wants_single or re.search(rf"\b{singular_noun}s\b", has_ref.group(0)):
            return None, None
        club = self.lex.find_club(q)
        sub = self.d
        if pos:
            sub = sub[sub["position"] == pos]
        if club:
            sub = sub[sub["team_name"] == club]
        if sub.empty:
            return None, None
        ref_txt = has_ref.group(0)
        if re.search(r"scorer", ref_txt):
            pid = int(sub["goals"].idxmax())
            note = f"Resolved '{ref_txt}' → {self.name(pid)} ({int(self.d.at[pid, 'goals'])} goals)."
        elif re.search(r"assister", ref_txt):
            pid = int(sub["assists"].idxmax())
            note = f"Resolved '{ref_txt}' → {self.name(pid)} ({int(self.d.at[pid, 'assists'])} assists)."
        elif "cheapest" in ref_txt:
            pid = int(sub["estimated_value_eur"].idxmin())
            note = f"Resolved '{ref_txt}' → {self.name(pid)}."
        elif "youngest" in ref_txt:
            pid = int(sub["age"].idxmin())
            note = f"Resolved '{ref_txt}' → {self.name(pid)} (age {int(self.d.at[pid, 'age'])})."
        elif "oldest" in ref_txt:
            pid = int(sub["age"].idxmax())
            note = f"Resolved '{ref_txt}' → {self.name(pid)} (age {int(self.d.at[pid, 'age'])})."
        else:
            pid = int(sub["estimated_value_eur"].idxmax())
            note = f"Resolved '{ref_txt}' → {self.name(pid)}."
        return pid, note

    def _has_scout_params(self, q):
        p = nlu.parse_scout_params(q)
        return any([p["ratio"], p["cap_eur"], p["min_eur"], p["max_age"], p["min_age"], p["younger"], p["n_given"], p["any_price"], nlu.find_position(q)])

    def _set_players(self, s: Session, players):
        new_target = players[0]
        s.players = list(players)
        s.target = new_target

    def _top(self, pos=None):
        d = self.d if pos is None else self.d[self.d["position"] == pos]
        return d["estimated_value_eur"].idxmax()

    def _join(self, feats, F):
        parts = [self.explain_feature(f, F) for f in feats]
        r = parts[0]
        r.text = "\n\n---\n\n".join(p.text for p in parts)
        return r

    @staticmethod
    def _fmt_signed_eur(val: float, F: Facts) -> str:
        sign = "+" if val >= 0 else "-"
        return f"{sign}{F.eur(abs(val))}"

    # ------------------------------------------------------------------ 0. model, dashboard & about overviews
    def model_overview(self, q: str, F: Facts) -> Reply:
        r = Reply("explanation", F)
        r.subintent = "model"
        ql = q.lower()
        m = self.st.meta()
        err = m["error"]
        n_feats = len(m["num_features"]) + len(m["cat_features"])
        F.allow("2")

        if re.search(r"\bwhat features\b|\blist (?:all )?(?:the )?features\b|\b28 features\b", ql):
            F.allow("28")
            feat_rows = []
            for k, item in enumerate(m["features"], 1):
                feat_rows.append({
                    "num": F.int(k),
                    "label": item["label"],
                    "group": item["group"],
                    "desc": item["tooltip"],
                })
                F.allow(item["tooltip"])
                F.allow(item["label"])
            r.text = (
                f"**All {F.int(len(feat_rows))} model input features** ({F.int(len(m['num_features']))} numeric + "
                f"{F.int(len(m['cat_features']))} categorical), grouped as shown on the Player Profile and Dashboard tabs:"
            )
            r.table = {
                "columns": [
                    {"key": "num", "label": "#"},
                    {"key": "label", "label": "Feature"},
                    {"key": "group", "label": "Category"},
                    {"key": "desc", "label": "Meaning"},
                ],
                "rows": feat_rows,
                "csv_name": "model_features.csv",
            }
            r.actions = [{"label": "Open Dashboard", "href": "/dashboard"}]
            r.suggestions = ["What are the most important features?", "How does the model work?"]
            return r

        r.text = (
            f"**How the Moneyball EPL valuation model works**\n\n"
            f"- **Dataset:** **{F.int(m['n_players'])}** Premier League outfield players across **{F.int(len(m['clubs']))}** clubs "
            f"({F.raw(m['season'])}, up to matchday {F.int(m['kaggle_matchday'])}; min **{F.int(m['min_minutes'])}** minutes; "
            f"**{F.int(m['train_size'])}** train / **{F.int(m['test_size'])}** held-out test).\n"
            f"- **Features ({F.int(n_feats)}):** per-90 attacking, creative, defensive & discipline metrics, pass accuracy, "
            f"minutes & start share, age (plus age²), position, nationality group, and club strength.\n"
            f"- **Model (`{m['chosen_model']}`):** predicts log market value (best by CV: `{m['best_by_cv']}`) and converts back to pounds.{self.syn()}\n"
            f"- **Cross-validated accuracy ({F.int(5)}-fold CV):** R² = **{F.num(err['cv_r2'], 2)}**, log RMSE = **{F.num(err['cv_rmse_log'], 3)}**, "
            f"log MAE = **{F.num(err['cv_mae_log'], 3)}**, typical error (MAE) = **{F.eur(err['cv_mae_eur'])}**, "
            f"median absolute error = **{F.pct(err['cv_median_abs_pct'], signed=False)}**.\n"
            f"- **Explainability & Scouting:** **TreeSHAP** decomposes every estimate from the base value (**{F.eur(m['base_eur'])}**), "
            f"and **cosine similarity** on {F.int(len(m['sim_features']))} position-standardised features finds cheaper lookalikes."
        )
        cv_rows = []
        for row in m["cv_results"]:
            cv_rows.append({
                "model": row["model"] + (" ★" if row["model"] == m["chosen_model"] else ""),
                "r2": F.num(row["cv_r2_mean"], 3),
                "rmse_log": F.num(row["cv_rmse_log"], 3),
                "mae_log": F.num(row["cv_mae_log"], 3),
                "mae": F.eur(row["cv_mae_eur"]),
                "med_pct": F.pct(row["cv_median_abs_pct"], signed=False, nd=1),
            })
        r.table = {
            "columns": [
                {"key": "model", "label": "Model"},
                {"key": "r2", "label": "CV R²"},
                {"key": "rmse_log", "label": "CV RMSE (log)"},
                {"key": "mae_log", "label": "CV MAE (log)"},
                {"key": "mae", "label": "CV MAE (£)"},
                {"key": "med_pct", "label": "Median Error"},
            ],
            "rows": cv_rows,
            "csv_name": "model_comparison.csv",
        }
        r.actions = [{"label": "Open Dashboard", "href": "/dashboard"}]
        r.suggestions = ["List all 28 features", "What are the limitations of the model?"]
        return r

    def about_project(self, q: str, F: Facts) -> Reply:
        r = Reply("howto", F)
        r.subintent = "about"
        m = self.st.meta()
        r.text = (
            f"**About Moneyball EPL & Known Limitations**\n\n"
            f"Moneyball EPL is a BSc thesis prototype covering **{F.int(m['n_players'])}** Premier League outfield players across "
            f"**{F.int(len(m['clubs']))}** clubs ({F.raw(m['season'])}, min {F.int(m['min_minutes'])} mins).\n\n"
            f"- **Data & {F.int(3)}-step matching:** merges Kaggle match stats (xG, xA, key passes, tackles, cards) with FBref metadata "
            f"(age, nationality, position, minutes) via exact name+club, exact name, and same-club fuzzy matching (≥{F.num(0.70, 2)} similarity).\n"
            f"- **Synthetic target caveat:** training values in this prototype are synthetically generated from features plus Gaussian noise to validate "
            f"the ML + SHAP + scouting pipeline — they are illustrative research outputs, not commercial Transfermarkt valuations.\n"
            f"- **Single-season outfield scope:** covers {F.int(1)} EPL season only; goalkeepers, injuries, wages, contract expiry, and off-field fame are not in the model.\n"
            f"- **Similarity ≠ tactical fit:** cosine similarity ({F.int(0)}–{F.int(1)}) matches statistical profile shape within position, complementing human scouting judgment.\n"
            f"- **Evaluation Console:** study evaluators can log answer ratings, task timings, and {F.int(10)}-item SUS usability scores ({F.int(0)}–{F.int(100)}) on `/eval`."
        )
        r.actions = [{"label": "Open About page", "href": "/about"}, {"label": "Open Evaluation Console", "href": "/eval"}]
        r.suggestions = ["How does the model work?", "Which season does the data cover?"]
        return r

    def club_summary(self, q: str, F: Facts) -> Reply:
        r = Reply("ranking", F)
        r.subintent = "clubs"
        ql = q.lower()
        d = self.d
        by_strength = bool(re.search(r"team strength|strongest", ql))
        by_avg = bool(re.search(r"\baverage\b|\bmean\b", ql))
        clubs = []
        for cname, g in d.groupby("team_name"):
            top_i = int(g["estimated_value_eur"].idxmax())
            clubs.append({
                "club": cname,
                "n": len(g),
                "total_est": float(g["estimated_value_eur"].sum()),
                "avg_est": float(g["estimated_value_eur"].mean()),
                "total_mkt": float(g["market_value_eur"].sum()),
                "strength": float(g["team_strength"].iloc[0]),
                "top_player": f"{self.name(top_i)} ({F.eur(float(g.at[top_i, 'estimated_value_eur']))})",
            })
        sort_key = "strength" if by_strength else ("avg_est" if by_avg else "total_est")
        clubs.sort(key=lambda x: -x[sort_key])
        rows = []
        for idx, c in enumerate(clubs, 1):
            rows.append({
                "rank": F.int(idx),
                "club": c["club"],
                "players": F.int(c["n"]),
                "total_est": F.eur(c["total_est"]),
                "avg_est": F.eur(c["avg_est"]),
                "total_mkt": F.eur(c["total_mkt"]),
                "strength": F.num(c["strength"], 2),
                "top_player": c["top_player"],
            })
        lead = clubs[0]
        metric_desc = "team strength" if by_strength else ("average player estimate" if by_avg else "total estimated squad value")
        r.text = (
            f"**Premier League clubs ranked by {metric_desc}** ({F.int(len(clubs))} clubs, {F.int(self.st.n)} outfield players with ≥{F.int(self.st.b['settings']['min_minutes'])} mins).{self.syn()}\n\n"
            f"Leader: **{lead['club']}** — total estimate **{F.eur(lead['total_est'])}** (avg **{F.eur(lead['avg_est'])}**, team strength **{F.num(lead['strength'], 2)}**)."
        )
        r.table = {
            "columns": [
                {"key": "rank", "label": "#"},
                {"key": "club", "label": "Club"},
                {"key": "players", "label": "Players"},
                {"key": "total_est", "label": "Total Est."},
                {"key": "avg_est", "label": "Avg Est."},
                {"key": "total_mkt", "label": "Total Listed"},
                {"key": "strength", "label": "Team Strength"},
                {"key": "top_player", "label": "Highest-Valued Player"},
            ],
            "rows": rows,
            "csv_name": "club_valuations.csv",
        }
        r.actions = [{"label": "Browse Players by Club", "href": "/players"}]
        r.suggestions = [f"{lead['club']} squad", "Average value by position"]
        return r

    def position_summary(self, F: Facts) -> Reply:
        r = Reply("explanation", F)
        r.subintent = "positions"
        d = self.d
        rows = []
        for pcode in ("F", "M", "D"):
            g = d[d["position"] == pcode]
            if g.empty:
                continue
            top_i = int(g["estimated_value_eur"].idxmax())
            rows.append({
                "pos": POS_PLURAL[pcode].title(),
                "count": F.int(len(g)),
                "avg_est": F.eur(float(g["estimated_value_eur"].mean())),
                "med_est": F.eur(float(g["estimated_value_eur"].median())),
                "avg_mkt": F.eur(float(g["market_value_eur"].mean())),
                "avg_goals": F.num(float(g["goals"].mean()), 1),
                "top_player": f"{self.name(top_i)} ({F.eur(float(g.at[top_i, 'estimated_value_eur']))})",
            })
        r.text = (
            f"**Valuation & output breakdown by position** across all **{F.int(self.st.n)}** outfield players.{self.syn()}\n\n"
            f"Use this alongside the position filter chips on the **Dashboard**, **Players**, and **Rankings** tabs."
        )
        r.table = {
            "columns": [
                {"key": "pos", "label": "Position"},
                {"key": "count", "label": "Players"},
                {"key": "avg_est", "label": "Avg Estimate"},
                {"key": "med_est", "label": "Median Estimate"},
                {"key": "avg_mkt", "label": "Avg Listed"},
                {"key": "avg_goals", "label": "Avg Goals"},
                {"key": "top_player", "label": "Top Player"},
            ],
            "rows": rows,
            "csv_name": "position_summary.csv",
        }
        r.actions = [{"label": "Open Dashboard", "href": "/dashboard"}]
        r.suggestions = ["What drives valuations for defenders?", "What drives valuations for forwards?"]
        return r

    def listed_vs_estimated(self, q: str, pos: str | None, s: Session, F: Facts) -> Reply:
        r = Reply("explanation", F)
        r.subintent = "listed_vs_estimated"
        ql = q.lower()
        d = self.d.copy()
        if pos:
            d = d[d["position"] == pos]
        d["est_mkt_ratio"] = d["estimated_value_eur"] / d["market_value_eur"].clip(lower=1.0)
        above = int((d["estimated_value_eur"] > d["market_value_eur"]).sum())
        below = len(d) - above
        want_below = bool(re.search(r"below the (?:dashed )?line|overvalued", ql))
        ordered = d.sort_values("est_mkt_ratio", ascending=want_below).head(10)
        s.shortlist = [int(i) for i in ordered.index]
        rows = []
        for idx, (i, row) in enumerate(ordered.iterrows(), 1):
            gap_pct = (float(row["estimated_value_eur"]) / float(row["market_value_eur"]) - 1.0) * 100.0
            rows.append({
                "rank": F.int(idx),
                "name": row["player_name"],
                "club": row["team_name"],
                "pos": row["position"],
                "age": F.int(row["age"]),
                "est": F.eur(float(row["estimated_value_eur"])),
                "mkt": F.eur(float(row["market_value_eur"])),
                "gap": F.pct(gap_pct),
                "_id": int(i),
            })
        scope = POS_PLURAL[pos] if pos else "players"
        mode_lbl = "below the dashed line (Model Estimate < Listed Value)" if want_below else "above the dashed line (Model Estimate > Listed Value)"
        r.text = (
            f"**Listed vs Model-Estimated Value ({scope})** — from the Dashboard scatter plot.{self.syn()}\n\n"
            f"- Out of **{F.int(len(d))}** {scope}, **{F.int(above)}** sit **above** the dashed equality line (model values them higher than listed) "
            f"and **{F.int(below)}** sit **below** it.\n"
            f"- Showing the top **{F.int(len(rows))}** {mode_lbl}:"
        )
        r.table = {
            "columns": [
                {"key": "rank", "label": "#"},
                {"key": "name", "label": "Player"},
                {"key": "club", "label": "Club"},
                {"key": "pos", "label": "Pos"},
                {"key": "age", "label": "Age"},
                {"key": "est", "label": "Model Est."},
                {"key": "mkt", "label": "Listed Value"},
                {"key": "gap", "label": "Est vs Listed"},
            ],
            "rows": rows,
            "csv_name": "listed_vs_estimated.csv",
        }
        r.actions = [{"label": "Open Dashboard Scatter", "href": "/dashboard"}]
        r.suggestions = [f"Explain {rows[0]['name']}", "Players below the dashed line" if not want_below else "Players above the dashed line"] if rows else []
        return r

    # ------------------------------------------------------------------ 1. valuation, stats, strengths & radar
    def valuation(self, i, F, q: str = "") -> Reply:
        r = Reply("valuation", F)
        est = self.est(i)
        listed = float(self.d.at[i, "market_value_eur"])
        goals = float(self.d.at[i, "goals"])
        assists = float(self.d.at[i, "assists"])
        mins = float(self.d.at[i, "minutes"])
        lo, hi = self.st.error_band(est)
        err = self.st.error
        pos = self.d.at[i, "position"]
        avg = self.st.position_average(pos)
        drivers = self.st.top_drivers(i, 3)
        drv = ", ".join(f"{d_['label']} ({F.pct(d_['pct'])})" for d_ in drivers)
        diff = (est / avg - 1) * 100
        mkt_gap = (est / listed - 1) * 100 if listed > 0 else 0.0
        nat_code = str(self.d.at[i, "nation"])
        nat_label = nlu.NATION_LABELS.get(nat_code, nat_code)
        r.text = (f"{self.who(i, F)} · {nat_label}: the model estimates **{F.eur(est)}** "
                  f"(listed: {F.eur(listed)}, **{F.pct(mkt_gap)}** vs listed).{self.syn()}\n\n"
                  f"- **Season output:** **{F.int(goals)}** goals, **{F.int(assists)}** assists across **{F.int(mins)}** minutes.\n"
                  f"- **Confidence band:** typically within {F.eur(lo)} to {F.eur(hi)} (CV MAE {F.eur(err['cv_mae_eur'])}, RMSE {F.eur(err['cv_rmse_eur'])}).\n"
                  f"- **Biggest SHAP drivers** (what the model uses, not causes): {drv}.\n"
                  f"- **Compared with other {POS_PLURAL[pos]}:** {F.pct(diff)} vs the {POS_NAME[pos].lower()} average of {F.eur(avg)}.")
        r.details = self._player_breakdown(i, F)
        r.suggestions = [f"What are {self.name(i)}'s strengths and weaknesses?", f"Find cheaper alternatives to {self.name(i)}"]
        r.actions = [self.profile_link(i)]
        r.chart = {"type": "waterfall", "ids": [int(i)]}
        return r

    def player_stats(self, i, F: Facts, q: str = "", raw_stats: list[str] | None = None) -> Reply:
        r = Reply("valuation", F)
        r.subintent = "stats"
        ql = (q or "").lower()
        prof = self.st.profile(i)
        row = self.d.loc[i]
        nat_code = str(row["nation"])
        nat_label = nlu.NATION_LABELS.get(nat_code, nat_code)

        lead_line = f"Season profile for {self.who(i, F)} ({nat_label}):"
        if re.search(r"\bnationality\b|\bwhere is .* from\b", ql):
            lead_line = f"**{self.name(i)}** is from **{nat_label}** (`{nat_code}`, nationality group `{row['nation_group']}`)."
        elif re.search(r"\bhow old\b|\bwhat age\b", ql):
            lead_line = f"**{self.name(i)}** is **{F.int(row['age'])}** years old."
        elif raw_stats:
            bits = []
            for rk in raw_stats[:3]:
                col = self.st.RANK_BY.get(rk, rk)
                if col in row.index and row[col] is not None:
                    v = float(row[col])
                    val_str = F.num(v, 2) if rk == "rating" else F.int(v)
                    bits.append(f"**{self.st.rank_label(rk)}**: **{val_str}**")
            if bits:
                lead_line = f"For {self.who(i, F)} — " + ", ".join(bits) + "."

        # Check if user asked for a specific group from the Player Profile -> Statistics tab
        chosen_group = None
        for gname in GROUPS:
            if gname.lower().split()[0] in ql:
                chosen_group = gname
                break
        stats_source = [s_it for s_it in prof["stats"] if s_it["group"] == chosen_group] if chosen_group else prof["key_stats"]

        r.text = (
            f"{lead_line}\n\n"
            f"- **Totals:** **{F.int(row['goals'])}** goals (xG {F.num(row['xg_filled'], 1)}), "
            f"**{F.int(row['assists'])}** assists (xA {F.num(row['xa_filled'], 1)}), "
            f"**{F.int(row['appearances'])}** apps, **{F.int(row['minutes'])}** minutes ({F.fmt_feature('start_share', row['start_share'])} started).\n"
            f"- **Valuation:** model estimate **{F.eur(prof['estimated_value_eur'])}** (listed {F.eur(prof['listed_value_eur'])}, "
            f"rank **#{F.int(prof['rank_in_position'])}** of {F.int(prof['n_in_position'])} {POS_PLURAL[row['position']]}).{self.syn()}"
        )
        stat_rows = []
        for st_item in stats_source:
            stat_rows.append({
                "stat": st_item["label"],
                "val": F.fmt_feature(st_item["key"], st_item["value"]),
                "pct": f"{F.int(st_item['pct_in_position'])}th",
                "avg": F.fmt_feature(st_item["key"], st_item["position_mean"]),
            })
        r.table = {
            "columns": [
                {"key": "stat", "label": f"Metric ({chosen_group})" if chosen_group else "Metric"},
                {"key": "val", "label": self.name(i)},
                {"key": "pct", "label": "Pos. Percentile"},
                {"key": "avg", "label": f"{POS_NAME[row['position']]} Avg"},
            ],
            "rows": stat_rows,
            "csv_name": f"{norm_name(self.name(i)).replace(' ', '_')}_stats.csv",
        }
        r.chart = {"type": "radar", "ids": [int(i)]}
        r.actions = [self.profile_link(i)]
        r.suggestions = [f"What are {self.name(i)}'s strengths and weaknesses?", f"Why is {self.name(i)} valued at that much?"]
        return r

    def player_strengths(self, i: int, F: Facts) -> Reply:
        r = Reply("valuation", F)
        r.subintent = "strengths"
        prof = self.st.profile(i)
        pos_lbl = POS_PLURAL[self.d.at[i, "position"]]
        stat_list = prof["stats"]
        strengths = sorted(
            [s_it for s_it in stat_list if s_it["pct_in_position"] is not None and s_it["pct_in_position"] >= 75 and s_it["key"] not in ("yellow_p90", "red_p90", "dispossessed_p90")],
            key=lambda x: -x["pct_in_position"],
        )[:6]
        weaknesses = sorted(
            [s_it for s_it in stat_list if s_it["pct_in_position"] is not None and s_it["pct_in_position"] <= 25 and s_it["key"] not in ("yellow_p90", "red_p90", "dispossessed_p90")],
            key=lambda x: x["pct_in_position"],
        )[:4]
        out = [f"**Strengths & Weaknesses for {self.who(i, F)}** (compared against {F.int(prof['n_in_position'])} {pos_lbl}):", ""]
        if strengths:
            out.append(f"**💪 Key Strengths (≥{F.int(75)}th percentile):**")
            for s_it in strengths:
                out.append(f"- **{s_it['label']}**: {F.fmt_feature(s_it['key'], s_it['value'])} (**{F.int(s_it['pct_in_position'])}th** percentile)")
            out.append("")
        else:
            out += [f"- No individual metric sits at or above the {F.int(75)}th percentile among {pos_lbl}.", ""]
        if weaknesses:
            out.append(f"**⚠️ Areas to Improve (≤{F.int(25)}th percentile):**")
            for w_it in weaknesses:
                out.append(f"- **{w_it['label']}**: {F.fmt_feature(w_it['key'], w_it['value'])} (**{F.int(w_it['pct_in_position'])}th** percentile)")
            out.append("")
        drivers = ", ".join(f"{d_['label']} ({F.pct(d_['pct'])})" for d_ in prof["top_drivers"])
        out.append(f"**Top {F.int(len(prof['top_drivers']))} SHAP value drivers:** {drivers} → model estimate **{F.eur(prof['estimated_value_eur'])}**.{self.syn()}")
        r.text = "\n".join(out)
        r.chart = {"type": "radar", "ids": [int(i)]}
        r.actions = [self.profile_link(i), {"label": f"Scout alternatives for {self.name(i)}", "href": f"/scout?target={int(i)}"}]
        r.suggestions = [f"Show {self.name(i)}'s stats", f"Find cheaper alternatives to {self.name(i)}"]
        return r

    def player_radar(self, ids: list[int], F: Facts) -> Reply:
        r = Reply("comparison" if len(ids) > 1 else "valuation", F)
        r.subintent = "radar"
        rad = self.st.radar(ids)
        cols = [{"key": "metric", "label": "Radar Metric"}]
        for idx, p in enumerate(rad["players"]):
            cols.append({"key": f"pct_{idx}", "label": f"{p['name']} (Pct)"})
            cols.append({"key": f"raw_{idx}", "label": f"{p['name']} (Actual)"})
        rows = []
        for ax_idx, (fk, label) in enumerate(zip(RADAR, RADAR_LABELS)):
            F.allow(label)
            row_d = {"metric": label}
            for p_idx, p in enumerate(rad["players"]):
                row_d[f"pct_{p_idx}"] = f"{F.int(p['percentiles'][ax_idx])}th"
                row_d[f"raw_{p_idx}"] = F.fmt_feature(fk, p["raw"][ax_idx])
            rows.append(row_d)
        names_txt = ", ".join(f"**{p['name']}** ({POS_NAME[p['position']]})" for p in rad["players"])
        r.text = (
            f"**Position Percentile Radar & Actual Stats** for {names_txt}.\n\n"
            f"Each percentile compares the player against peers in his own position ({F.int(100)} = highest in position), matching the Dashboard radar panel."
        )
        r.table = {"columns": cols, "rows": rows, "csv_name": "radar_comparison.csv"}
        r.chart = {"type": "radar", "ids": [int(x) for x in ids]}
        r.actions = [{"label": "Open Dashboard Radar", "href": "/dashboard"}]
        r.suggestions = [f"Why is {rad['players'][0]['name']} valued higher than {rad['players'][1]['name']}?"] if len(ids) == 2 else [f"Explain {rad['players'][0]['name']}"]
        return r

    def _player_breakdown(self, i, F) -> str:
        """notebook txt_player + exact waterfall £ steps"""
        c = self.st.shap_feat.iloc[i]
        wf = self.st.waterfall(i, max_display=28)
        eur_by_feat = {row["feature"]: row["eur"] for row in wf["rows"]}
        nm = self.name(i)
        est, listed = self.est(i), float(self.d.at[i, "market_value_eur"])
        base = self.st.b["base_eur"]

        def line(f):
            extra = f", {self.pos_pct_text(i, f, F)}" if f in NUM_FEATURES else ""
            eur_step = f" ({self._fmt_signed_eur(eur_by_feat[f], F)})" if f in eur_by_feat else ""
            return f"- **{pretty(f)}** = {F.fmt_feature(f, self.st.raw_value(i, f))}{extra} → **{F.pct(self._pc(c[f]))}**{eur_step} on value"

        ups = c[c > 0.02].sort_values(ascending=False).head(3)
        downs = c[c < -0.02].sort_values().head(2)
        rest = c.sum() - ups.sum() - downs.sum()
        out = [f"The model estimates **{F.eur(est)}** (listed value: {F.eur(listed)}). Starting from the base player value of "
               f"**{F.eur(base)}**, the model values {nm} at **{F.times(est / base)}** the average player.", ""]
        if len(ups):
            out += ["**What pushes the estimate up:**"] + [line(f) for f in ups.index] + [""]
        if len(downs):
            out += ["**What pulls it down:**"] + [line(f) for f in downs.index] + [""]
        out.append(f"All the other features together: **{F.pct(self._pc(rest))}**. (Percentages act in log space; the Waterfall £ steps add up exactly from {F.eur(base)} to {F.eur(est)}.)")
        ratio = est / listed
        if ratio < 0.8:
            out.append("\nThe model estimates **less** than the listed value: it sees this player as possibly overvalued, or the listed value contains things the model cannot see (fame, contract, injuries).")
        elif ratio > 1.25:
            out.append("\nThe model estimates **more** than the listed value: it sees this player as possibly undervalued, or the listed value contains things the model cannot see.")
        else:
            out.append("\nThe model's estimate is **close** to the listed value.")
        if i in self.st.train_idx:
            out.append("\n*(This player was in the training data, so the model has already seen his listed value.)*")
        return "\n".join(out)

    @staticmethod
    def _pc(c):
        return (np.exp(c) - 1) * 100

    # ------------------------------------------------------------------ 2. explanation
    def explain_player(self, i, F) -> Reply:
        r = Reply("explanation", F)
        r.subintent = "player"
        c = self.st.shap_feat.iloc[i]
        wf = self.st.waterfall(i, max_display=28)
        eur_by_feat = {row["feature"]: row["eur"] for row in wf["rows"]}
        ups = c[c > 0.02].sort_values(ascending=False).head(2)
        downs = c[c < -0.02].sort_values().head(1)
        bits = []
        if len(ups):
            bits.append("pushed **up** mainly by " + " and ".join(
                f"{pretty(f)} ({F.pct(self._pc(c[f]))}, {self._fmt_signed_eur(eur_by_feat.get(f, 0.0), F)})" for f in ups.index
            ))
        if len(downs):
            bits.append("pulled **down** most by " + " and ".join(
                f"{pretty(f)} ({F.pct(self._pc(c[f]))}, {self._fmt_signed_eur(eur_by_feat.get(f, 0.0), F)})" for f in downs.index
            ))
        r.text = (f"{self.who(i, F)} is estimated at **{F.eur(self.est(i))}**.{self.syn()} Starting from the base player "
                  f"({F.eur(self.st.b['base_eur'])}), the estimate is " + "; ".join(bits or ["close to the average on every feature"]) +
                  ".\n\n*SHAP values show what the model uses, and the Waterfall £ impacts sum step-by-step from the base value to the final estimate.*")
        r.details = self._player_breakdown(i, F)
        r.chart = {"type": "waterfall", "ids": [int(i)]}
        r.actions = [self.profile_link(i)]
        r.suggestions = [f"What are {self.name(i)}'s strengths and weaknesses?", f"Find cheaper alternatives to {self.name(i)}"]
        return r

    def explain_player_groups(self, i, F) -> Reply:
        r = Reply("explanation", F)
        r.subintent = "player_groups"
        wf = self.st.waterfall(i)
        lines = [f"- **{g['group']}**: {F.pct(g['pct'])}" for g in wf["groups"] if abs(g["pct"]) >= 0.5]
        r.text = (f"Feature groups for {self.who(i, F)} (estimate {F.eur(self.est(i))}).{self.syn()} Each line is the group's combined push on the estimate:\n\n"
                  + "\n".join(lines[:8]) + "\n\n*This shows what the model uses, not what causes value.*")
        r.chart = {"type": "waterfall", "ids": [int(i)]}
        r.suggestions = [f"Why is {self.name(i)} valued at that much?"]
        return r

    def explain_compare(self, a, b, F) -> Reply:
        """notebook txt_compare"""
        r = Reply("explanation", F)
        r.subintent = "compare"
        sf = self.st.shap_feat
        ea, eb = self.est(a), self.est(b)
        hi, lo = (a, b) if ea >= eb else (b, a)
        Hn, Ln = self.name(hi), self.name(lo)
        delta = sf.iloc[hi] - sf.iloc[lo]
        out = [f"The model estimates **{Hn}** at **{F.eur(max(ea, eb))}** and **{Ln}** at **{F.eur(min(ea, eb))}** "
               f"({F.times(max(ea, eb) / min(ea, eb))}).{self.syn()} The biggest reasons:", ""]
        for f in delta[delta > 0.02].sort_values(ascending=False).head(3).index:
            out.append(f"- **{pretty(f)}**: {Hn} {F.fmt_feature(f, self.st.raw_value(hi, f))} vs {Ln} {F.fmt_feature(f, self.st.raw_value(lo, f))} → **{F.pct(self._pc(delta[f]))}** for {Hn}")
        against = delta[delta < -0.02].sort_values().head(2).index
        if len(against):
            out += ["", f"Features that work in favour of **{Ln}**:"]
            for f in against:
                out.append(f"- **{pretty(f)}**: {Ln} {F.fmt_feature(f, self.st.raw_value(lo, f))} vs {Hn} {F.fmt_feature(f, self.st.raw_value(hi, f))} → **{F.pct(self._pc(-delta[f]))}** for {Ln}")
        out.append("\n*Based on SHAP contributions: what the model uses, not what causes value.*")
        r.text = "\n".join(out)
        r.chart = {"type": "radar", "ids": [int(hi), int(lo)]}
        r.suggestions = [f"Compare {Hn} and {Ln}", f"How similar are {Hn} and {Ln}?"]
        return r

    def explain_player_feature(self, i, feats, F) -> Reply:
        """notebook txt_player_feature"""
        r = Reply("explanation", F)
        r.subintent = "player_feature"
        c = self.st.shap_feat.iloc[i]
        nm = self.name(i)
        order = c.abs().sort_values(ascending=False).index.tolist()
        parts = []
        for f in feats:
            if f not in c.index:
                continue
            parts.append("\n".join([
                f"**{pretty(f)}** for **{nm}**:", "",
                f"- Value: **{F.fmt_feature(f, self.st.raw_value(i, f))}**" + (f" ({self.pos_pct_text(i, f, F)})" if f in NUM_FEATURES else ""),
                f"- Effect on the estimate: **{F.pct(self._pc(c[f]))}** compared with an average player",
                f"- This is the **#{F.int(order.index(f) + 1)}** biggest driver (out of {F.int(len(order))}) for {nm}'s estimated value of {F.eur(self.est(i))}.{self.syn()}"]))
        r.text = "\n\n---\n\n".join(parts) + "\n\n*SHAP shows what the model uses, not what causes value.*"
        r.chart = {"type": "waterfall", "ids": [int(i)]}
        r.suggestions = [f"How does {pretty(feats[0]).replace(' /90', '')} affect value?", f"Why is {nm} valued at that much?"]
        return r

    def explain_feature(self, f, F) -> Reply:
        """notebook txt_feature"""
        r = Reply("explanation", F)
        r.subintent = "feature"
        s = self.st.feature_summary(f)
        out = [f"**{pretty(f)}**", "",
               f"- Importance: **#{F.int(s['rank'])}** out of {F.int(s['n_features'])} features. On average it moves a player's estimated value by about **{F.pm(s['typical_pct'])}**."]
        if s["perf_rank"]:
            out.append(f"- Among the {F.int(s['n_perf'])} performance indicators it is **#{F.int(s['perf_rank'])}**.")
        if s["typical_pct"] < 2:
            out.append("- It has **almost no effect** on the model's estimates (less than ±2%), so there is no clear pattern to describe.")
            F.allow("2")
        elif "by_category" in s:
            out.append("- Average effect: " + ", ".join(f"{c['category']} **{F.pct(c['pct'])}**" for c in s["by_category"]) + ".")
        else:
            if f == "age":
                txt = f"- In the model, value is highest around **age {F.int(s['age_peak'])}** ({F.pct(s['age_peak_pct'])} vs an average player)"
                if s.get("young_pct") is not None:
                    txt += f"; players aged {F.int(21)} or younger get {F.pct(s['young_pct'])}"
                if s.get("old_pct") is not None:
                    txt += f"; players aged {F.int(31)} or older get {F.pct(s['old_pct'])}"
                out.append(txt + ".")
            else:
                out.append({"up": "- Direction: generally **higher values → higher estimated value**.",
                            "down": "- Direction: generally **higher values → lower estimated value**.",
                            "mixed": "- Direction: **not a simple 'more is better'** (see the dependence plot on the Dashboard)."}[s["direction"]])
                out.append(f"- Players in the **top {F.int(25)}%** on this stat get on average **{F.pct(s['top25_pct'])}** (vs an average player); "
                           f"players in the **bottom {F.int(25)}%** get **{F.pct(s['bottom25_pct'])}**.")
            out.append(f"- It matters most for **{s['most_pos'].lower()}s** ({F.pm(s['most_pos_pct'])}) and least for **{s['least_pos'].lower()}s** ({F.pm(s['least_pos_pct'])}).")
        out.append("\n*SHAP shows what the model uses, not what causes a high real-world value. Correlated features (e.g. goals, xG, shots) share credit.*")
        r.text = "\n".join(out)
        if f not in ("position", "nation_group"):
            r.chart = {"type": "dependence", "feature": f}
        r.actions = [{"label": "Open Dashboard", "href": "/dashboard"}]
        r.suggestions = ["What are the most important features?", f"Top 5 players by {pretty(f).replace(' /90', '')}" if f in NUM_FEATURES else "What drives value for forwards?"]
        return r

    def explain_global(self, pos, F) -> Reply:
        """notebook txt_global"""
        r = Reply("explanation", F)
        r.subintent = "global"
        g = self.st.global_importance(pos)
        who = "all players" if pos is None else POS_PLURAL[pos]
        out = [f"**Most important features for {who}** (typical effect on estimated value):", ""]
        out += [f"{k}. **{x['label']}** ({F.pm(x['pct'])})" for k, x in enumerate(g["merged"][:5], 1)]
        perf = [x for x in g["merged"] if x["group"] in PERF_GROUPS][:5]
        out += ["", f"**Top performance indicators for {who}:**", ""]
        out += [f"{k}. **{x['label']}** ({F.pm(x['pct'])})" for k, x in enumerate(perf, 1)]
        out.append("\n*These show what the model uses, not what causes value.*")
        r.text = "\n".join(out)
        r.actions = [{"label": "Open Dashboard", "href": "/dashboard"}]
        r.suggestions = ["How does age affect the value?", "What drives value for defenders?" if pos != "D" else "What drives value for forwards?"]
        return r

    def explain_groups(self, pos, F) -> Reply:
        r = Reply("explanation", F)
        r.subintent = "groups"
        g = self.st.global_importance(pos)
        who = "all players" if pos is None else POS_PLURAL[pos]
        out = [f"**Feature groups that matter most for {who}** (sum of typical effects, in log points converted to ±%):", ""]
        out += [f"{k}. **{x['group']}** ({F.pm(x['pct'])})" for k, x in enumerate(g["groups"][:8], 1)]
        out.append("\n*Groups add up related features (e.g. goals, xG and shots = attacking output). What the model uses, not causes.*")
        r.text = "\n".join(out)
        r.actions = [{"label": "Open Dashboard", "href": "/dashboard"}]
        r.suggestions = ["What are the most important features for midfielders?"]
        return r

    # ------------------------------------------------------------------ 3. scouting
    def _scout_query(self, i, p: dict, pos_override=None) -> tuple[ScoutQuery, list[str], bool]:
        tage = int(self.d.at[i, "age"])
        default_cap = not p.get("ratio") and not p.get("cap_eur") and not p.get("any_price")
        max_pct = 60.0 if default_cap else (p["ratio"] * 100 if p.get("ratio") else None)
        max_age = p.get("max_age") or (tage - 1 if p.get("younger") else None)
        q = ScoutQuery(target=int(i), same_position=pos_override is None, position=pos_override, max_pct=max_pct,
                       max_age=max_age, min_age=p.get("min_age"), max_eur=p.get("cap_eur"), min_eur=p.get("min_eur"),
                       n=p.get("n", 5))
        return q, [], default_cap

    def scout(self, i, text, s: Session, F, params: dict | None = None) -> Reply:
        p = params or nlu.parse_scout_params(text)
        pos_word = nlu.find_position(text) if params is None else p.get("position")
        pos_override = pos_word if pos_word and pos_word != self.d.at[i, "position"] else None
        p["position"] = pos_override
        q, _, default_cap = self._scout_query(i, p, pos_override)
        res = self.st.scout(q)
        r = Reply("scouting", F)
        r.subintent = "similar"
        if s.target is not None and s.target != i:
            r.context_note = f"Switching to {self.name(i)} as the target."
        s.target, s.players, s.scout = int(i), [int(i)], {**p, "target": int(i)}
        s.shortlist = [row["id"] for row in res["results"]]

        tv = res["target_value_eur"]
        filters = [f"same position ({POS_NAME[self.d.at[i, 'position']]})" if not pos_override else f"position: {POS_NAME[pos_override]}"]
        if q.max_pct is not None:
            filters.append(f"estimated value up to {F.int(q.max_pct)}% of the target's ({F.eur(res['max_value_eur'])})" + (" (default)" if default_cap else ""))
        if q.max_eur:
            filters.append(f"estimated value up to {F.eur(q.max_eur)}")
        if q.min_eur:
            filters.append(f"estimated value at least {F.eur(q.min_eur)}")
        if q.max_age:
            filters.append(f"age {F.int(q.max_age)} or younger")
        if q.min_age:
            filters.append(f"age {F.int(q.min_age)} or older")
        stand = ", ".join(x["label"] for x in res["target"]["standouts"])
        head = (f"**Players like {self.name(i)}** ({self.d.at[i, 'team_name']}, age {F.int(self.d.at[i, 'age'])}, "
                f"out-of-fold estimate {F.eur(tv)}).{self.syn()}\n\nFilters: " + "; ".join(filters) +
                f". **{F.int(res['n_passed'])}** players passed the filters.")
        if not res["results"]:
            sug = " ".join(x["text"] for x in res["suggestions"][:2]) or "Try a higher price limit or remove the age limit."
            for x in res["suggestions"]:
                F.allow(x["text"])
            r.text = head + f"\n\nNo candidates match these filters. {sug}"
            r.suggestions = [self._relax_phrase(x) for x in res["suggestions"][:2]] or [f"Find alternatives to {self.name(i)} at any price"]
            return r
        r.table = self._scout_table(res["results"], F)
        top = res["results"][0]
        r.text = (head + f"\n\nTop match: **{top['name']}** ({top['club']}, age {F.int(top['age'])}), similarity {F.num(top['similarity'])}, "
                  f"estimated {F.eur(top['value_eur'])} ({F.int(top['pct_of_target'])}% of the target).\n\n"
                  "*Similarity runs from 0 to 1 (1 = same profile shape), using per-90 stats compared within each position. "
                  "Prices are out-of-fold estimates: each player valued by a model that did not see him.*")
        if res["suggestions"]:
            for x in res["suggestions"]:
                F.allow(x["text"])
            r.text += "\n\n" + " ".join(x["text"] for x in res["suggestions"][:2])
        r.chart = {"type": "radar", "ids": [int(i), int(top["id"])]}
        r.actions = [{"label": "Open in Scout page", "href": f"/scout?target={int(i)}&max_pct={int(q.max_pct or 100)}" + (f"&max_age={q.max_age}" if q.max_age else "")},
                     self.profile_link(top["id"])]
        r.suggestions = [f"Why is {top['name']} valued at that much?", "Now limit it to under 24" if not q.max_age else "Summarise the shortlist"]
        return r

    def _relax_phrase(self, x):
        return {"max_pct": f"Raise the limit to {x['value']}%", "max_age": f"Only under {x['value']}",
                "position": "Allow any position", "max_eur": "At any price"}[x["filter"]]

    def _scout_table(self, rows, F) -> dict:
        t = {"columns": [{"key": k, "label": l} for k, l in [("rank", "#"), ("name", "Player"), ("club", "Club"), ("age", "Age"),
                                                            ("similarity", "Similarity"), ("value", "Est. value"), ("pct", "% of target"),
                                                            ("shared", "Shared strengths")]],
             "rows": [{"rank": F.int(x["rank"]), "name": x["name"], "club": x["club"], "age": F.int(x["age"]),
                       "similarity": F.num(x["similarity"]), "value": F.eur(x["value_eur"]), "pct": F.pct(x["pct_of_target"], signed=False),
                       "shared": ", ".join(x["shared_labels"]) or "-", "_id": x["id"]} for x in rows],
             "csv_name": "shortlist.csv"}
        return t

    def scout_followup(self, q, s: Session, F) -> Reply:
        p_new = nlu.parse_scout_params(q)
        p = dict(s.scout)
        ql = q.lower()
        for k in ("ratio", "cap_eur", "min_eur", "max_age", "min_age"):
            if p_new.get(k) is not None:
                p[k] = p_new[k]
        if p_new["younger"]:
            p["younger"] = True
        if p_new["n_given"]:
            p["n"] = p_new["n"]
        if p_new["any_price"]:
            p.update(ratio=None, cap_eur=None, any_price=True)
        if re.search(r"\bany age\b|\bno age limit\b|\bremove the age", ql):
            p.update(max_age=None, younger=False, min_age=None)
        if re.search(r"\bany position\b|\ball positions\b", ql):
            p["position"] = None
        pos = nlu.find_position(q)
        if pos:
            p["position"] = pos
        r = self.scout(s.scout["target"], "", s, F, params=p)
        r.context_note = "Re-running the last search with the new filter."
        return r

    def pair(self, a, b, F) -> Reply:
        """notebook txt_pair"""
        r = Reply("comparison", F)
        r.subintent = "similarity"
        pr = self.st.pair(a, b)
        na, nb = self.name(a), self.name(b)
        if not pr["same_position"]:
            r.text = (f"**{na}** is a {POS_NAME[self.d.at[a, 'position']].lower()} and **{nb}** is a {POS_NAME[self.d.at[b, 'position']].lower()}. "
                      "Similarity is only calculated between players of the **same position** (every stat is compared with the player's own position), "
                      "so I can't compare them directly.")
            r.suggestions = [f"Compare {na} and {nb}"]
            return r
        shared = ", ".join(pr["shared"]) or "nothing in particular"
        r.text = (f"**{na}** and **{nb}** have a similarity of **{F.num(pr['similarity'])}** (0 = nothing in common, 1 = identical profile shape).\n\n"
                  f"- Among the {F.int(pr['n_candidates'])} other {POS_PLURAL[self.d.at[a, 'position']]}, {nb} is the **#{F.int(pr['rank'])}** most similar player to {na}.\n"
                  f"- Both are above their position average in: {shared}.\n"
                  f"- Estimated values: {na} {F.eur(self.est(a))}, {nb} {F.eur(self.est(b))}.{self.syn()}")
        r.chart = {"type": "radar", "ids": [int(a), int(b)]}
        r.suggestions = [f"Why is {na} valued higher than {nb}?" if self.est(a) >= self.est(b) else f"Why is {nb} valued higher than {na}?"]
        return r

    def profile_scout(self, q, feats, matched, pos, s: Session, F) -> Reply:
        p = nlu.parse_scout_params(q)
        nation = self.lex.find_nation(q)
        club = self.lex.find_club(q)
        d = self.d
        pcol = "market_value_eur" if p["price_basis"] == "listed" else "oof_value_eur"
        plbl = "listed value" if p["price_basis"] == "listed" else "estimated value"
        m = np.ones(len(d), dtype=bool)
        if pos:
            m &= (d["position"] == pos).to_numpy()
        if club:
            m &= (d["team_name"] == club).to_numpy()
        if nation:
            m &= (d["nation"] == nation).to_numpy()
        if p["max_age"]:
            m &= (d["age"] <= p["max_age"]).to_numpy()
        if p["min_age"]:
            m &= (d["age"] >= p["min_age"]).to_numpy()
        if p["min_minutes"]:
            m &= (d["minutes"] >= p["min_minutes"]).to_numpy()
        if p["max_minutes"]:
            m &= (d["minutes"] <= p["max_minutes"]).to_numpy()
        if p["min_eur"]:
            m &= (d[pcol] >= p["min_eur"]).to_numpy()
        if p["cap_eur"]:
            m &= (d[pcol] <= p["cap_eur"]).to_numpy()
        score = self.st.Z[feats].mean(axis=1).to_numpy()
        idx = np.flatnonzero(m)
        order = idx[np.argsort(-score[idx])][: p["n"]]
        r = Reply("scouting", F)
        r.subintent = "profile"
        flt = [f"position: {POS_NAME[pos]}" if pos else "any position"]
        if club:
            flt.append(club)
        if nation:
            flt.append(nlu.NATION_LABELS.get(nation, nation))
        if p["min_age"] and p["max_age"] and p["min_age"] == p["max_age"]:
            flt.append(f"age {F.int(p['min_age'])}")
        else:
            if p["min_age"] and p["max_age"]:
                flt.append(f"age {F.int(p['min_age'])}–{F.int(p['max_age'])}")
            elif p["max_age"]:
                flt.append(f"age {F.int(p['max_age'])} or younger" + (" (*young* = 23 or younger)" if re.search(r"\byoung", q.lower()) and not re.search(r"\d", q) else ""))
                F.allow("23")
            elif p["min_age"]:
                flt.append(f"age {F.int(p['min_age'])} or older")
        if p["min_eur"] and p["cap_eur"]:
            flt.append(f"{plbl} {F.eur(p['min_eur'])} to {F.eur(p['cap_eur'])}")
        elif p["cap_eur"]:
            flt.append(f"{plbl} up to {F.eur(p['cap_eur'])}")
        elif p["min_eur"]:
            flt.append(f"{plbl} at least {F.eur(p['min_eur'])}")
        if p["min_minutes"]:
            flt.append(f"at least {F.int(p['min_minutes'])} mins")
        feat_txt = ", ".join(pretty(f) for f in feats)
        r.text = (f"I read *{', '.join(matched)}* as these features: **{feat_txt}**. Players are ranked by their average z-score on them "
                  f"(how far above their position average they are). Filters: {'; '.join(flt)}. **{F.int(m.sum())}** players passed.{self.syn()}")
        if not len(order):
            r.text += "\n\nNo players match. Try widening the age or budget range."
            return r
        s.shortlist = [int(x) for x in order]
        s.scout = None
        r.table = {"columns": [{"key": k, "label": l} for k, l in [("rank", "#"), ("name", "Player"), ("club", "Club"), ("age", "Age"),
                                                                  ("score", "Profile score"), ("value", "Est. value"), ("listed", "Listed value")]] +
                              [{"key": f, "label": pretty(f)} for f in feats[:3]],
                   "rows": [{"rank": F.int(k), "name": self.name(i), "club": d.at[i, "team_name"], "age": F.int(d.at[i, "age"]),
                             "score": F.num(score[i]), "value": F.eur(d.at[i, "oof_value_eur"]), "listed": F.eur(d.at[i, "market_value_eur"]),
                             **{f: F.fmt_feature(f, float(d.at[i, f])) for f in feats[:3]}, "_id": int(i)} for k, i in enumerate(order, 1)],
                   "csv_name": "profile_shortlist.csv"}
        r.text += f"\n\nTop profile match: **{self.name(order[0])}** ({d.at[order[0], 'team_name']}, profile score {F.num(score[order[0]])})."
        r.suggestions = [f"Explain {self.name(order[0])}", "Summarise the shortlist"]
        return r

    def shortlist_drivers(self, s: Session, F) -> Reply:
        r = Reply("explanation", F)
        r.subintent = "shortlist_drivers"
        rows = []
        for i in s.shortlist[:10]:
            td = self.st.top_drivers(i, 3)
            rows.append({"name": self.name(i), "value": F.eur(self.est(i)),
                         "drivers": "; ".join(f"{x['label']} {F.pct(x['pct'])}" for x in td), "_id": int(i)})
        r.table = {"columns": [{"key": "name", "label": "Player"}, {"key": "value", "label": "Model estimate"},
                               {"key": "drivers", "label": "Top 3 SHAP drivers"}], "rows": rows, "csv_name": "shortlist_drivers.csv"}
        r.text = f"SHAP breakdown for the {F.int(len(rows))} players on the last shortlist (top three drivers each).{self.syn()} *What the model uses, not what causes value.*"
        r.suggestions = [f"Why is {rows[0]['name']} valued at that much?"] if rows else []
        return r

    # ------------------------------------------------------------------ 4. comparison
    def compare(self, ids, F) -> Reply:
        r = Reply("comparison", F)
        r.subintent = "table"
        c = self.st.compare(ids)
        cols = [{"key": "metric", "label": ""}] + [{"key": f"p{k}", "label": p["name"]} for k, p in enumerate(c["players"])]
        rows = []

        def add(label, fn):
            rows.append({"metric": label, **{f"p{k}": fn(p) for k, p in enumerate(c["players"])}})

        add("Club", lambda p: p["club"])
        add("Position", lambda p: p["position_name"])
        add("Age", lambda p: F.int(p["age"]))
        add("Minutes", lambda p: F.int(p["minutes"]))
        add("Goals", lambda p: F.int(p.get("goals") or 0))
        add("Assists", lambda p: F.int(p.get("assists") or 0))
        add("Model estimate", lambda p: F.eur(p["estimated_value_eur"]))
        add("Listed value", lambda p: F.eur(p["listed_value_eur"]))
        for f, lab in c["stat_labels"].items():
            add(lab, lambda p, f=f: F.fmt_feature(f, p["stats"][f]))
        add("Top driver", lambda p: f"{p['top_drivers'][0]['label']} ({F.pct(p['top_drivers'][0]['pct'])})")
        r.table = {"columns": cols, "rows": rows, "csv_name": "comparison.csv"}
        sims = []
        for x in c["similarities"]:
            if x["same_position"]:
                sims.append(f"{self.name(x['a'])}–{self.name(x['b'])} {F.num(x['similarity'])}")
        ranked = sorted(c["players"], key=lambda p: -p["estimated_value_eur"])
        r.text = (f"Comparing {F.int(len(ids))} players.{self.syn()} Highest estimate: **{ranked[0]['name']}** ({F.eur(ranked[0]['estimated_value_eur'])}); "
                  f"lowest: **{ranked[-1]['name']}** ({F.eur(ranked[-1]['estimated_value_eur'])}).")
        r.text += (" Similarity (same position only, 0–1): " + "; ".join(sims) + ".") if sims else " They play different positions, so similarity is not computed."
        r.chart = {"type": "radar", "ids": [int(x) for x in ids]}
        r.actions = [{"label": "Open in Compare page", "href": "/compare?ids=" + ",".join(str(int(x)) for x in ids)}]
        r.suggestions = [f"Why is {ranked[0]['name']} valued higher than {ranked[-1]['name']}?", f"Show radar for {ranked[0]['name']} and {ranked[-1]['name']}"]
        return r

    # ------------------------------------------------------------------ 5. ranking & budget recruitment
    def ranking(self, q, feats, pos, s: Session, F, raw_stats: list[str] | None = None) -> Reply:
        ql = q.lower()
        p = nlu.parse_scout_params(q)
        club = self.lex.find_club(q)
        nation = self.lex.find_nation(q)
        n = p["n"] if p["n_given"] else 10
        wants_p90 = bool(re.search(r"per\s*90|/90|\bp90\b", ql))
        is_buy = bool(nlu.BUY_RE.search(ql) or p["min_eur"] or p["cap_eur"])
        price_col = "market_value_eur" if p["price_basis"] == "listed" else "estimated_value_eur"
        price_lbl = "listed market value" if p["price_basis"] == "listed" else "model estimate"
        asc = True if re.search(r"\blowest\b|\bfewest\b|\bcheapest\b|\bleast\b", ql) else None

        if re.search(r"\bovervalued\b", ql):
            by, asc = ("undervalued", True) if "listed" in ql else ("value_vs_similar", False)
        elif re.search(r"undervalued|bargain|value for money|cheap for|good value", ql):
            by = "undervalued" if "listed" in ql else "value_vs_similar"
        elif re.search(r"\byoungest\b", ql):
            by, asc = "age", True
        elif re.search(r"\boldest\b", ql):
            by, asc = "age", False
        elif raw_stats:
            by = raw_stats[0]
        elif not wants_p90 and ("goals_p90" in feats or re.search(r"\b(?:top|leading) scorers?\b|\bgolden boot\b|\bmost goals\b|\bscored the most\b", ql)):
            by = "goals"
        elif not wants_p90 and ("assists_p90" in feats or re.search(r"\bmost assists\b|\btop assisters?\b", ql)):
            by = "assists"
        elif not wants_p90 and "xg_p90" in feats and re.search(r"\bmost\b|\bhighest\b|\btop\b", ql):
            by = "xg_filled"
        elif not wants_p90 and "xa_p90" in feats and re.search(r"\bmost\b|\bhighest\b|\btop\b", ql):
            by = "xa_filled"
        elif p["price_basis"] == "listed" and not is_buy and re.search(r"\bvalue|valuable|expensive|cheapest\b", ql):
            by = "listed_value"
        elif feats and feats[0] in NUM_FEATURES:
            by = feats[0]
        else:
            by = "estimated_value"

        if by == "estimated_value" and asc is None and re.search(r"\bcheapest\b", ql):
            asc = True
        res = self.st.rankings(
            by=by, position=pos, club=club, nation=nation,
            min_age=p["min_age"], max_age=p["max_age"],
            min_minutes=p["min_minutes"], max_minutes=p["max_minutes"],
            min_eur=p["min_eur"], max_eur=p["cap_eur"], price_col=price_col,
            n=n, ascending=asc,
        )
        r = Reply("ranking", F)
        flt = []
        if pos:
            flt.append(POS_PLURAL[pos])
        if club:
            flt.append(club)
        if nation:
            flt.append(nlu.NATION_LABELS.get(nation, nation))
        if p["min_age"] and p["max_age"] and p["min_age"] == p["max_age"]:
            flt.append(f"age {F.int(p['min_age'])}")
        else:
            if p["min_age"] and p["max_age"]:
                flt.append(f"age {F.int(p['min_age'])}–{F.int(p['max_age'])}")
            elif p["max_age"]:
                flt.append(f"age {F.int(p['max_age'])} or younger")
            elif p["min_age"]:
                flt.append(f"age {F.int(p['min_age'])} or older")
        if p["min_eur"] and p["cap_eur"]:
            flt.append(f"{price_lbl} {F.eur(p['min_eur'])} to {F.eur(p['cap_eur'])}")
        elif p["cap_eur"]:
            flt.append(f"{price_lbl} up to {F.eur(p['cap_eur'])}")
        elif p["min_eur"]:
            flt.append(f"{price_lbl} at least {F.eur(p['min_eur'])}")
        if p["min_minutes"]:
            flt.append(f"at least {F.int(p['min_minutes'])} minutes")
        if p["max_minutes"]:
            flt.append(f"at most {F.int(p['max_minutes'])} minutes")

        money = by in ("estimated_value", "listed_value", "oof_value")
        int_cols = {
            "minutes", "goals", "assists", "age", "goal_contributions", "appearances", "matches_started",
            "penalty_goals", "headed_goals", "big_chances_created", "big_chances_missed", "key_passes",
            "total_shots", "shots_on_target", "successful_dribbles", "tackles_total", "tackles_won_total",
            "interceptions_total", "clearances_total", "ball_recoveries_total", "aerial_won_total",
            "touches_total", "yellow_cards", "red_cards", "clean_sheets", "totw", "fouls",
            "was_fouled_total", "offsides", "woodwork",
        }
        is_int_col = by in int_cols
        fmt = (lambda v: F.eur(v)) if money else (lambda v: F.int(v)) if is_int_col else (lambda v: F.num(v, 2))
        if by == "pass_accuracy":
            fmt = lambda v: F.fmt_feature("pass_accuracy", v)

        if is_buy and money:
            r.subintent = "budget_buy"
            r.table = {
                "columns": [
                    {"key": "rank", "label": "#"},
                    {"key": "name", "label": "Player"},
                    {"key": "club", "label": "Club"},
                    {"key": "pos", "label": "Pos"},
                    {"key": "age", "label": "Age"},
                    {"key": "goals", "label": "G"},
                    {"key": "assists", "label": "A"},
                    {"key": "est", "label": "Model Est."},
                    {"key": "listed", "label": "Listed Value"},
                    {"key": "gap", "label": "Est vs Listed"},
                ],
                "rows": [
                    {
                        "rank": F.int(x["rank"]),
                        "name": x["name"],
                        "club": x["club"],
                        "pos": x["position"],
                        "age": F.int(x["age"]),
                        "goals": F.int(x["goals"] or 0),
                        "assists": F.int(x["assists"] or 0),
                        "est": F.eur(x["estimated_value_eur"]),
                        "listed": F.eur(x["listed_value_eur"]),
                        "gap": F.pct((x["estimated_value_eur"] / x["listed_value_eur"] - 1.0) * 100.0 if x["listed_value_eur"] else 0.0),
                        "_id": x["id"],
                    }
                    for x in res["rows"]
                ],
                "csv_name": "budget_targets.csv",
            }
        else:
            r.table = {"columns": [{"key": "rank", "label": "#"}, {"key": "name", "label": "Player"}, {"key": "club", "label": "Club"},
                                   {"key": "pos", "label": "Pos"}, {"key": "age", "label": "Age"}, {"key": "metric", "label": res["label"]}]
                       + ([] if money else [{"key": "value", "label": "Model estimate"}]),
                       "rows": [{"rank": F.int(x["rank"]), "name": x["name"], "club": x["club"], "pos": x["position"], "age": F.int(x["age"]),
                                 "metric": fmt(x["metric"]), **({} if money else {"value": F.eur(x["estimated_value_eur"])}), "_id": x["id"]}
                                for x in res["rows"]], "csv_name": "ranking.csv"}

        direction = "lowest" if res["ascending"] else "highest"
        r.text = (f"**Top {F.int(len(res['rows']))} by {res['label']}** ({direction} first)" + (f" — {', '.join(flt)}" if flt else "") +
                  f". **{F.int(res['pool_size'])}** of {F.int(res['n_players'])} outfield players matched "
                  f"(min {F.int(res['min_minutes_rule'])} minutes)." + (self.syn() if money or by in ("value_vs_similar", "undervalued") else ""))

        if res["rows"]:
            s.shortlist = [int(x["id"]) for x in res["rows"]]
            s.scout = None
            lead = res["rows"][0]
            if is_buy and money:
                lead_gap = (lead["estimated_value_eur"] / lead["listed_value_eur"] - 1.0) * 100.0 if lead["listed_value_eur"] else 0.0
                r.text += (
                    f"\n\n- **Highest model-valued target in range:** **{lead['name']}** ({lead['club']}, age {F.int(lead['age'])}) — "
                    f"estimated at **{F.eur(lead['estimated_value_eur'])}** (listed {F.eur(lead['listed_value_eur'])}, {F.pct(lead_gap)}; "
                    f"{F.int(lead['goals'] or 0)} goals, {F.int(lead['assists'] or 0)} assists)."
                )
                bargains = [x for x in res["rows"] if x["listed_value_eur"] and x["estimated_value_eur"] > x["listed_value_eur"] * 1.1]
                if bargains:
                    best_b = max(bargains, key=lambda x: x["estimated_value_eur"] / x["listed_value_eur"])
                    if best_b["id"] != lead["id"]:
                        b_gap = (best_b["estimated_value_eur"] / best_b["listed_value_eur"] - 1.0) * 100.0
                        r.text += (
                            f"\n- **Best value-for-money vs listed price:** **{best_b['name']}** ({best_b['club']}, age {F.int(best_b['age'])}) — "
                            f"estimated at **{F.eur(best_b['estimated_value_eur'])}** vs listed **{F.eur(best_b['listed_value_eur'])}** (**{F.pct(b_gap)}**; "
                            f"{F.int(best_b['goals'] or 0)} goals, {F.int(best_b['assists'] or 0)} assists)."
                        )
            else:
                r.text += f"\n\nLeader: **{lead['name']}** ({lead['club']}) — **{fmt(lead['metric'])}**."

        # Cross-check listed market value when user gave a budget range without specifying 'listed'
        alt_suggestion = None
        if (p["min_eur"] or p["cap_eur"]) and p["price_basis"] == "estimated":
            alt_res = self.st.rankings(
                by="estimated_value", position=pos, club=club, nation=nation,
                min_age=p["min_age"], max_age=p["max_age"],
                min_minutes=p["min_minutes"], max_minutes=p["max_minutes"],
                min_eur=p["min_eur"], max_eur=p["cap_eur"], price_col="market_value_eur", n=5,
            )
            shown_ids = {x["id"] for x in res["rows"]}
            extra_mkt = [x for x in alt_res["rows"] if x["id"] not in shown_ids]
            if extra_mkt:
                names_mkt = ", ".join(
                    f"**{x['name']}** (listed {F.eur(x['listed_value_eur'])}, est. {F.eur(x['estimated_value_eur'])})"
                    for x in extra_mkt[:3]
                )
                r.text += f"\n- **Note on listed market values:** filtering by *listed* price instead also includes {names_mkt}."
                pos_w = POS_PLURAL.get(pos, "players")
                if p["min_eur"] and p["cap_eur"]:
                    lo_m, hi_m = int(round(p["min_eur"] / 1e6)), int(round(p["cap_eur"] / 1e6))
                    alt_suggestion = f"Best {pos_w} with listed value {lo_m}m to {hi_m}m"
                elif p["cap_eur"]:
                    hi_m = int(round(p["cap_eur"] / 1e6))
                    alt_suggestion = f"Best {pos_w} with listed value under {hi_m}m"

        if by == "value_vs_similar":
            r.text += " *Ratio = player's estimate ÷ median estimate of his 5 most similar peers (below 1 = cheaper than statistical peers).*"
        if not res["rows"]:
            r.table = None
            r.text += "\n\nNo players match these exact filters. Try widening the price or age range."

        rank_by_link = by if by in ("estimated_value", "goals", "assists", "xg_filled", "xa_filled", "minutes", "pass_accuracy", "tackles_won_p90", "dribbles_p90") else "estimated_value"
        r.actions = [{"label": "Open the Rankings page", "href": f"/rankings?by={rank_by_link}" + (f"&position={pos}" if pos else "")}]
        if res["rows"]:
            r.suggestions = [
                f"Explain {res['rows'][0]['name']}",
                alt_suggestion or f"Find cheaper alternatives to {res['rows'][0]['name']}",
            ]
        elif alt_suggestion:
            r.suggestions = [alt_suggestion]
        return r

    # ------------------------------------------------------------------ 6. data and quality
    def data_quality(self, q, players, pos, s: Session, F) -> Reply:
        ql = q.lower()
        r = Reply("data_quality", F)
        meta = self.st.b
        st = meta["settings"]
        if players:
            i = players[0]
            self._set_players(s, players)
            pv = self.st.provenance(i)
            step = {"name+club": "same name and club", "name": "same name (different club spelling or a mid-season move)",
                    "fuzzy": f"a close spelling at the same club (similarity of at least {F.num(0.70)})"}.get(pv["match_step"], "unknown")
            lines = [f"**{self.name(i)}** appears in **both** source files: the Kaggle file (statistics such as xG, xA, key passes, tackles and cards, "
                     f"up to matchday {F.int(st['kaggle_matchday'])}) and the FBref file (age, nationality, position, minutes). "
                     f"The two were matched by {step}."]
            if pv["kaggle_name"] and pv["fbref_name"] and pv["kaggle_name"] != pv["fbref_name"]:
                lines.append(f"The Kaggle file spells the name *{pv['kaggle_name']}*; the site uses the FBref spelling.")
            if pv["xg_filled"]:
                lines.append("xG for this player was blank in the Kaggle file, so it was estimated from his shots using the average xG per shot for his position.")
            else:
                lines.append("His xG is taken directly from the Kaggle file (not filled).")
            if pv["xa_filled"]:
                lines.append("xA was blank and was estimated from key passes using the league-wide average xA per key pass.")
            lines.append("He was in the model's training part." if pv["in_training"] else "He was in the held-back test part (the final model did not train on him).")
            r.text = " ".join(lines)
            r.subintent = "provenance"
            r.actions = [self.profile_link(i)]
            return r

        for nm in self.lex.unknown_names(q):
            ex = self.st.find_excluded(nm)
            if ex:
                return self._excluded_reply(ex, F, r)

        counts = meta["counts"]
        fi = meta["feat_info"]
        if re.search(r"how many", ql):
            p = nlu.parse_scout_params(q)
            club = self.lex.find_club(q)
            nation = self.lex.find_nation(q)
            price_col = "market_value_eur" if p["price_basis"] == "listed" else "estimated_value_eur"
            res = self.st.rankings(
                by="estimated_value", position=pos, club=club, nation=nation,
                min_age=p["min_age"], max_age=p["max_age"],
                min_minutes=p["min_minutes"], max_minutes=p["max_minutes"],
                min_eur=p["min_eur"], max_eur=p["cap_eur"], price_col=price_col, n=1,
            )
            flt = [x for x in [
                POS_PLURAL.get(pos), club, nlu.NATION_LABELS.get(nation, nation) if nation else None,
                f"age {F.int(p['min_age'])}–{F.int(p['max_age'])}" if p["min_age"] and p["max_age"] and p["min_age"] != p["max_age"] else
                (f"age {F.int(p['max_age'])} or younger" if p["max_age"] else (f"age {F.int(p['min_age'])} or older" if p["min_age"] else None)),
                f"{F.eur(p['min_eur'])} to {F.eur(p['cap_eur'])}" if p["min_eur"] and p["cap_eur"] else
                (f"up to {F.eur(p['cap_eur'])}" if p["cap_eur"] else (f"at least {F.eur(p['min_eur'])}" if p["min_eur"] else None)),
                f"at least {F.int(p['min_minutes'])} minutes" if p["min_minutes"] else None,
            ] if x]
            r.subintent = "count"
            r.text = (f"**{F.int(res['pool_size'])}** players match" + (f" ({', '.join(flt)})" if flt else "") +
                      f", out of {F.int(self.st.n)} outfield players with at least {F.int(st['min_minutes'])} minutes.")
            return r
        if re.search(r"fill|missing|blank", ql):
            r.subintent = "filled"
            r.text = (f"Blank xG values are filled from shots × the average xG per shot for the player's position; blank xA from key passes × the "
                      f"league-wide average xA per key pass. In the current sample **{F.int(fi['blank_xg'])}** player(s) had blank xG and "
                      f"**{F.int(fi['blank_xa'])}** had blank xA after the filters. Players not found in the FBref file have no age, so they are excluded.")
            return r
        if re.search(r"exclud|goalkeep|not in the sample|left out|why .* not", ql):
            r.subintent = "exclusions"
            r.text = (f"Players are excluded if they are goalkeepers, played fewer than {F.int(st['min_minutes'])} minutes, or could not be matched "
                      f"between the two files (no age). Of {F.int(counts['all'])} players in the Kaggle file, {F.int(counts['outfield'])} are outfield players, "
                      f"{F.int(counts['min_minutes'])} have enough minutes, and {F.int(counts['with_age'])} are matched with an age.")
            return r
        r.subintent = "coverage"
        bp = self.d["position"].value_counts()
        r.text = (f"The data covers the **{F.raw(st['season'])}** Premier League season, up to matchday **{F.int(st['kaggle_matchday'])}** for the Kaggle file. "
                  f"Sources: the Kaggle file ({F.int(counts['kaggle_rows'])} players, {F.int(counts['kaggle_cols'])} columns: xG, xA, key passes, tackles, cards…) "
                  f"and the FBref file ({F.int(counts['fbref_rows'])} rows: age, nationality, position, minutes). After the filters the sample has "
                  f"**{F.int(self.st.n)}** outfield players: {F.int(bp.get('M', 0))} midfielders, {F.int(bp.get('D', 0))} defenders, {F.int(bp.get('F', 0))} forwards.")
        if meta.get("is_sample_data"):
            r.text += " *Note: this deployment runs on the fictional development sample, not the real files.*"
        return r

    def _excluded_reply(self, ex, F, r) -> Reply:
        e = ex[0]
        r.subintent = "excluded"
        why = {"goalkeeper": "he is a goalkeeper (the model covers outfield players only)"}.get(e["reason"], e["reason"])
        if e["reason"].startswith("fewer"):
            why = f"he played {F.int(e['minutes'])} minutes, below the minimum"
            F.allow(self.st.b["settings"]["min_minutes"])
        elif e["reason"].startswith("no match"):
            why = "he could not be matched in the FBref file, so his age and nationality are unavailable"
        r.text = (f"**{e['name']}** ({e['club']}) is in the Kaggle file but not in the model's sample, because {why}. "
                  f"So I can't value or explain him. I can find similar players in the sample if you name one.")
        return r

    def outside_sample(self, names, F) -> Reply:
        for nm in names:
            ex = self.st.find_excluded(nm)
            if ex:
                return self._excluded_reply(ex, F, Reply("data_quality", F))
        r = Reply("out_of_scope", F)
        r.subintent = "outside_sample"
        r.text = (f"I can't find **{names[0]}** among the {F.int(self.st.n)} outfield players in the sample (Premier League {F.raw(self.st.b['settings']['season'])}, "
                  f"at least {F.int(self.st.b['settings']['min_minutes'])} minutes), so I can't value him. Check the spelling, or search the Players page.")
        r.actions = [{"label": "Search players", "href": "/players"}]
        r.suggestions = [f"How much is {self.name(self._top())} worth?"]
        return r

    # ------------------------------------------------------------------ 7/8. glossary, how-to
    def glossary(self, term, F) -> Reply:
        r = Reply("glossary", F)
        title, body = GLOSSARY[term]
        F.allow(body)          # numbers in a definition are illustrative constants, not player data
        r.text = f"**{title}**: {body}"
        r.subintent = term
        r.suggestions = {"shap": ["How do I read a waterfall chart?"], "cosine similarity": ["How do I run a scouting search?"],
                         "out of fold": ["What is the value filter?"]}.get(term, ["What are the most important features?"])
        return r

    def greet(self, ql: str, F) -> Reply:
        from . import llm
        r = Reply("howto", F)
        r.subintent = "identity"
        if re.search(r"^\s*(?:thanks+|thank\s+y+o+u+|thx)\b", ql):
            r.text = "You're welcome! Ask me about any Premier League player, budget transfer range, SHAP breakdown, scouting shortlist, or model metric whenever you're ready."
            r.suggestions = ["What is the best attacker to buy in the range of 35 million to 55 million?", "Which club has the highest squad value?"]
            return r
        m = self.st.meta()
        F.allow("3.8", "100")
        gem_line = (
            f"✨ **Gemini LLM status:** Connected (`{llm._resolve_models()[0]}`, key `{llm.masked_gemini_key()}`) — natural-language rewriting & phrasing are active with **100%** numeric fact-checking."
            if llm.has_gemini_key()
            else "🔑 **Gemini LLM status:** Ready — click **🔑 Connect Free Gemini API** at the top right of this chat and paste a free key from https://aistudio.google.com/apikey (no credit card needed) to enable `gemini-3.8-flash`!"
        )
        r.text = (
            f"👋 I'm the **Moneyball EPL AI Scouting & Valuation Assistant**!\n\n"
            f"- **Grounded data:** **{F.int(m['n_players'])}** Premier League outfield players across **{F.int(len(m['clubs']))}** clubs "
            f"({F.raw(m['season'])}, up to matchday {F.int(m['kaggle_matchday'])}; min {F.int(m['min_minutes'])} mins).\n"
            f"- **Capabilities:** Player valuations, **TreeSHAP** waterfall explanations, strengths & weaknesses, budget transfer searches, "
            f"cheaper lookalike scouting, radar comparisons, what-if simulations, and model CV accuracy.\n"
            f"- {gem_line}"
        )
        r.suggestions = [
            "What is the best attacker to buy in the range of 35 million to 55 million?",
            "How does the model work?",
        ]
        return r

    def howto(self, ql, F) -> Reply:
        r = Reply("howto", F)
        topic = ("dashboard" if re.search(r"dashboard|dependence|scatter", ql) else
                 "waterfall" if re.search(r"waterfall|read .*chart|shap", ql) else
                 "export" if re.search(r"export|csv|download|shortlist", ql) else
                 "scout" if re.search(r"scout|alternativ|replace|cheaper|similar", ql) else
                 "compare" if "compar" in ql else
                 "rankings" if re.search(r"rank|top|list", ql) else
                 "explain" if re.search(r"explain|why|valued", ql) else
                 "search" if re.search(r"search|find a player|profile", ql) else None)
        if topic is None:
            F.allow("35", "55")
            r.subintent = "capabilities"
            r.text = ("I can answer anything across all Moneyball EPL tabs: **player valuations & confidence bands**, **SHAP waterfall & feature drivers**, "
                      "**strengths & weaknesses**, **budget & profile scouting** (e.g. *best attacker to buy in the range of 35m to 55m*), "
                      "**side-by-side & radar comparisons**, **club & position summaries**, **what-if scenarios**, **model CV accuracy**, and **dataset/caveat details**.")
            r.suggestions = ["What is the best attacker to buy in the range of 35 million to 55 million?", "How does the model work?"]
            return r
        title, steps, href = HOWTO[topic]
        F.allow(" ".join(steps))
        r.subintent = topic
        r.text = f"**{title}**\n\n" + "\n".join(f"{k}. {x}" for k, x in enumerate(steps, 1))
        r.actions = [{"label": "Open the page", "href": href}]
        r.suggestions = ["Open the page for me" if False else "What is cosine similarity?" if topic == "scout" else "What is SHAP?"]
        return r

    # ------------------------------------------------------------------ limits, clarify
    def decline(self, kind, players, F) -> Reply:
        r = Reply("out_of_scope", F)
        r.subintent = kind
        uses = "the model only uses league statistics per 90 minutes, pass accuracy, playing time, age, position, nationality group and team strength"
        msg = {
            "fee": f"I can't predict transfer fees or what a club will pay; {uses}. I can give the model's estimated value instead.",
            "sign": f"I can't predict whether a player will sign or move; {uses}. I can find similar players instead.",
            "injury": f"Injury and fitness data are not in the model; {uses}.",
            "contract": f"Contract length, wages and agents are not in the model; {uses}.",
            "reputation": f"Reputation and off-field factors are not in the model; {uses}.",
            "future": f"I can't forecast future performance or potential; {uses}, from the current season only.",
            "goalkeeper": "Goalkeepers are excluded from the sample, because their statistics are completely different from outfield players'.",
        }[kind]
        r.text = msg
        if players:
            r.suggestions = [f"How much is {self.name(players[0])} worth?", f"Find cheaper alternatives to {self.name(players[0])}"]
        else:
            r.suggestions = ["What are the most important features?", f"How much is {self.name(self._top())} worth?"]
        return r

    def clarify(self, F, question, examples=False) -> Reply:
        r = Reply("clarify", F)
        r.understood = False
        top, fw = self.name(self._top()), self.name(self._top("F"))
        r.text = question
        if examples:
            r.text += f"\n\n- *How much is {top} worth?*\n- *Find cheaper alternatives to {fw} under {F.int(24)}*\n- *What drives value for defenders?*"
        r.suggestions = [f"How much is {top} worth?", f"Find cheaper alternatives to {fw}"]
        return r

    # ------------------------------------------------------------------ summaries, export, what-if
    def summarise(self, s: Session, F) -> Reply:
        r = Reply("scouting", F)
        r.subintent = "summary"
        if not s.shortlist:
            r.understood = False
            r.text = "There is no shortlist yet. Run a scouting search first, for example *Find cheaper alternatives to " + self.name(self._top("F")) + "*."
            return r
        ids = s.shortlist
        vals = self.d.loc[ids, "oof_value_eur"]
        ages = self.d.loc[ids, "age"]
        sents = []
        if s.scout and s.scout.get("target") is not None:
            t = s.scout["target"]
            sims = [float(self.st.S[t, i]) for i in ids]
            sents.append(f"The shortlist has {F.int(len(ids))} players similar to {self.name(t)} (out-of-fold estimate {F.eur(self.d.at[t, 'oof_value_eur'])}).")
            sents.append(f"Similarity ranges from {F.num(min(sims))} to {F.num(max(sims))}; the closest match is {self.name(ids[0])}.")
        else:
            sents.append(f"The shortlist has {F.int(len(ids))} players; the top-ranked is {self.name(ids[0])}.")
        sents.append(f"Estimated values range from {F.eur(vals.min())} to {F.eur(vals.max())}, with a median of {F.eur(vals.median())}.{self.syn()}")
        sents.append(f"Ages range from {F.int(ages.min())} to {F.int(ages.max())}; the youngest is {self.name(ages.idxmin())}.")
        cheapest = vals.idxmin()
        sents.append(f"The cheapest option is {self.name(cheapest)} ({self.d.at[cheapest, 'team_name']}) at {F.eur(vals.min())}.")
        r.text = " ".join(sents)
        r.suggestions = ["Export the shortlist", f"Why is {self.name(ids[0])} valued at that much?"]
        return r

    def export(self, s: Session, F) -> Reply:
        r = Reply("scouting", F)
        r.subintent = "export"
        if not s.shortlist:
            r.understood = False
            r.text = "There is nothing to export yet. Run a scouting search or a ranking first."
            return r
        rows = []
        for k, i in enumerate(s.shortlist, 1):
            row = {"rank": F.int(k), "name": self.name(i), "club": self.d.at[i, "team_name"], "position": self.d.at[i, "position"],
                   "age": F.int(self.d.at[i, "age"]), "minutes": F.int(self.d.at[i, "minutes"]),
                   "est_value": F.eur(self.d.at[i, "oof_value_eur"]), "_id": int(i)}
            if s.scout and s.scout.get("target") is not None:
                row["similarity"] = F.num(self.st.S[s.scout["target"], i])
            rows.append(row)
        cols = [{"key": k, "label": k.replace("_", " ").title()} for k in rows[0] if not k.startswith("_")]
        r.table = {"columns": cols, "rows": rows, "csv_name": "shortlist.csv", "export": True}
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=[c["key"] for c in cols], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
        r.table["csv"] = buf.getvalue()
        r.text = f"Here is the current shortlist ({F.int(len(rows))} players). Use **Download CSV** or **Copy** below.{self.syn()}"
        return r

    def whatif(self, i, f, q, s: Session, F) -> Reply:
        r = Reply("whatif", F)
        ql = q.lower()
        has_p90 = bool(re.search(r"(?:per|/)\s*90\b|\bp90\b", ql))
        q_clean = re.sub(r"(?:per|/)\s*90\b|\bp90\b", " ", ql)
        nums = [float(x) for x in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", q_clean)]
        if f not in NUM_FEATURES or f == "age_sq" or not nums:
            r.understood = False
            r.text = f"Tell me the new value, for example *What if {self.name(i)} scored 20 goals?* or *What if {self.name(i)} had 0.5 xG per 90?*"
            return r
        raw_input = nums[-1]
        F.allow(q)
        mins = float(self.d.at[i, "minutes"])
        season_note = ""
        is_delta = bool(re.search(r"\b(?:more|extra|additional|fewer|less)\b|\b(?:increased|decreased)\s+by\b", q_clean))

        if f in ("goals_p90", "np_goals_p90", "assists_p90") and not has_p90 and (raw_input >= 2 or is_delta):
            col_total = "assists" if f == "assists_p90" else "goals"
            old_total = float(self.d.at[i, col_total])
            if is_delta:
                sign = -1.0 if re.search(r"\b(?:fewer|less|decreased)\b", q_clean) else 1.0
                target_total = max(0.0, old_total + sign * raw_input)
            else:
                target_total = raw_input
            val = target_total * 90.0 / mins
            season_note = (f" ({F.int(target_total)} season {col_total} across {F.int(mins)} minutes, "
                           f"vs {F.int(old_total)} actual)")
        else:
            old_v = float(self.d.at[i, f])
            if is_delta:
                sign = -1.0 if re.search(r"\b(?:fewer|less|decreased|younger)\b", q_clean) else 1.0
                val = max(0.0, old_v + sign * raw_input)
            else:
                val = raw_input

        w = self.st.whatif(i, f, val)
        r.text = (f"**Hypothetical profile, not a real player.** If **{self.name(i)}** had {pretty(f)} = **{F.fmt_feature(f, val)}**"
                  f"{season_note} (actual: {F.fmt_feature(f, w['old_value'])}), the model's estimate would move from {F.eur(w['before_eur'])} to "
                  f"**{F.eur(w['after_eur'])}** (**{F.pct(w['change_pct'])}**).{self.syn()}")
        r.actions = [self.profile_link(i)]
        r.suggestions = [f"Why is {self.name(i)} valued at that much?", f"Find cheaper alternatives to {self.name(i)}"]
        return r

    def player_projection(self, i: int, F: Facts) -> Reply:
        r = Reply("projection", F)
        proj = self.st.projection(i)
        if not proj:
            r.text = f"No multi-season aging projection is available for **{self.name(i)}**."
            return r
        c = proj["contract"]
        fut = proj["future"]
        y1, y2, y3 = fut[0], fut[1], fut[2]
        F.allow("100", "2022", "2023", "2024", "2025", "2026", "2027", "2028", "2029",
                "22", "23", "24", "25", "26", "27", "28", "29", "3",
                proj["peak_age_window"], c["recommended_years"], c["contract_structure"])
        hist_str = ", ".join(
            f"**{F.raw(h['season'])}** ({h['club']}, {F.int(h['minutes'])} mins, Role Index **{F.num(h['role_index'], 1)}/100**)"
            for h in proj["history"]
        )
        r.text = (
            f"### 📈 Multi-Season Aging & Contract Advisory: {self.who(i, F)}\n\n"
            f"- **Trajectory Status:** **{proj['trajectory_label']}** *(Confidence: {proj['confidence']})*\n"
            f"- **Current 2025-26 Baseline (Age {F.int(proj['current_age'])}):** Role Performance Index **{F.num(proj['current_role_index'], 1)}/100** | Fair Value **{F.eur(proj['current_value_eur'])}**\n"
            f"- **Historical Track Record:** {hist_str if hist_str else '2025-26 Premier League season only'}\n\n"
            f"#### 🔮 3-Year Forward Projection\n"
            f"- **{y1['season']} (Age {F.int(y1['age'])}):** Role Index **{F.num(y1['role_index'], 1)}/100** ({F.pct(y1['perf_change_pts'], signed=True, nd=1)} pts) → Est. Value **{F.eur(y1['estimated_value_eur'])}** ({F.pct(y1['value_change_pct'])})\n"
            f"- **{y2['season']} (Age {F.int(y2['age'])}):** Role Index **{F.num(y2['role_index'], 1)}/100** ({F.pct(y2['perf_change_pts'], signed=True, nd=1)} pts) → Est. Value **{F.eur(y2['estimated_value_eur'])}** ({F.pct(y2['value_change_pct'])})\n"
            f"- **{y3['season']} (Age {F.int(y3['age'])}):** Role Index **{F.num(y3['role_index'], 1)}/100** ({F.pct(y3['perf_change_pts'], signed=True, nd=1)} pts) → Est. Value **{F.eur(y3['estimated_value_eur'])}** ({F.pct(y3['value_change_pct'])})\n\n"
            f"#### 📝 Contract Recommendation: **{c['recommended_years']}** ({c['verdict']})\n"
            f"- **Structure:** {c['contract_structure']}\n"
            f"- **Risk Level:** {c['risk_level']}\n"
            f"- **Scouting Rationale:** {F.raw(c['rationale'])}"
        )
        r.actions = [self.profile_link(i)]
        r.suggestions = [
            f"Find younger alternatives to {self.name(i)}",
            f"Why is {self.name(i)} valued at that much?",
        ]
        return r
