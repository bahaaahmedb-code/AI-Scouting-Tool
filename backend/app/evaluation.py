"""Evaluation logging (thesis E3, E4, E6). SQLite file in logs/. No personal data is stored.

Tables: chat_log, ratings, tasks, sus, chat_tests.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_log (id INTEGER PRIMARY KEY, ts TEXT, session TEXT, question TEXT, intent TEXT, subintent TEXT,
    understood INTEGER, numbers_total INTEGER, numbers_matched INTEGER, unmatched TEXT, answer TEXT, rephrased INTEGER);
CREATE TABLE IF NOT EXISTS ratings (id INTEGER PRIMARY KEY, ts TEXT, evaluator TEXT, target_id INTEGER, target_name TEXT,
    candidate_id INTEGER, candidate_name TEXT, rank INTEGER, similarity REAL, rating INTEGER, comparable_players TEXT, comment TEXT);
CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, ts TEXT, participant TEXT, task TEXT, success INTEGER, seconds REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS sus (id INTEGER PRIMARY KEY, ts TEXT, participant TEXT, answers TEXT, score REAL);
CREATE TABLE IF NOT EXISTS chat_tests (id INTEGER PRIMARY KEY, ts TEXT, run_id TEXT, qid TEXT, question TEXT, group_name TEXT,
    expected_intent TEXT, got_intent TEXT, intent_ok INTEGER, numbers_total INTEGER, numbers_matched INTEGER, expected_ok INTEGER, answer TEXT);
"""
TABLES = {"chat_log", "ratings", "tasks", "sus", "chat_tests"}


def sus_score(answers: list[int]) -> float:
    """System Usability Scale: 10 items on 1-5. Odd items: score-1; even items: 5-score; sum x 2.5."""
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("SUS needs 10 answers between 1 and 5")
    return sum((a - 1) if k % 2 == 0 else (5 - a) for k, a in enumerate(answers)) * 2.5


class EvalStore:
    def __init__(self, log_dir: Path, enabled: bool = True):
        self.enabled = enabled
        self.lock = threading.Lock()
        self.path = Path(log_dir) / "moneyball_eval.sqlite"
        if enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._conn() as c:
                c.executescript(SCHEMA)

    def _conn(self):
        return sqlite3.connect(self.path)

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def insert(self, table: str, row: dict):
        if not self.enabled or table not in TABLES:
            return
        row = {"ts": self.now(), **row}
        cols = ", ".join(row)
        qs = ", ".join("?" for _ in row)
        with self.lock, self._conn() as c:
            c.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", list(row.values()))

    def log_chat(self, session, question, reply: dict, rephrased=False):
        n = reply.get("numbers", {})
        self.insert("chat_log", {"session": session, "question": question, "intent": reply.get("intent"),
                                 "subintent": reply.get("subintent"), "understood": int(bool(reply.get("understood"))),
                                 "numbers_total": n.get("total", 0), "numbers_matched": n.get("matched", 0),
                                 "unmatched": json.dumps(n.get("unmatched", [])), "answer": reply.get("text", ""),
                                 "rephrased": int(rephrased)})

    def rows(self, table: str) -> list[dict]:
        if not self.enabled or table not in TABLES:
            return []
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY id")]

    def csv(self, table: str) -> str:
        rows = self.rows(table)
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        return buf.getvalue()

    def summary(self) -> dict:
        out = {}
        chat = self.rows("chat_log")
        if chat:
            tot = sum(r["numbers_total"] for r in chat)
            out["chat"] = {"questions": len(chat), "understood_share": sum(r["understood"] for r in chat) / len(chat),
                           "numbers_total": tot, "numbers_matched_share": (sum(r["numbers_matched"] for r in chat) / tot) if tot else None}
        tasks = self.rows("tasks")
        if tasks:
            out["tasks"] = {"n": len(tasks), "success_rate": sum(r["success"] for r in tasks) / len(tasks),
                            "mean_seconds": sum(r["seconds"] or 0 for r in tasks) / len(tasks)}
        sus = self.rows("sus")
        if sus:
            out["sus"] = {"n": len(sus), "mean": sum(r["score"] for r in sus) / len(sus)}
        ratings = self.rows("ratings")
        if ratings:
            out["ratings"] = {"n": len(ratings), "mean": sum(r["rating"] for r in ratings) / len(ratings)}
        tests = self.rows("chat_tests")
        if tests:
            last = tests[-1]["run_id"]
            t = [r for r in tests if r["run_id"] == last]
            tot = sum(r["numbers_total"] for r in t)
            out["chat_tests"] = {"run_id": last, "n": len(t), "intent_accuracy": sum(r["intent_ok"] for r in t) / len(t),
                                 "expected_ok": sum(r["expected_ok"] for r in t) / len(t),
                                 "numbers_matched_share": (sum(r["numbers_matched"] for r in t) / tot) if tot else None}
        return out
