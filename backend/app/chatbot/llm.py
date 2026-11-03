"""Gemini Free-Tier LLM integration (via official `google-genai` Interactions API).

Provides three strictly fact-grounded capabilities when `GEMINI_API_KEY` is configured:
1. `rewrite_query`   — Translates casual/slang/indirect user questions into canonical Moneyball EPL queries
                       using Gemini Structured Output when the deterministic NLU returns `understood=False`.
2. `rephrase`        — Polishes deterministic answers (with or without tables) into concise football-scout prose.
                       Rejected automatically unless `check_numbers` passes with zero unmatched numbers and all
                       player names in bold are preserved.
3. `answer_grounded` — Answers open-ended analytical questions strictly from a verified Store facts snapshot,
                       validated against `Facts` / `check_numbers`.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from .facts import Facts, check_numbers

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
FALLBACK_GEMINI_MODELS = ("gemini-3.1-flash-lite", "gemini-3.8-flash")
_EXECUTOR = ThreadPoolExecutor(max_workers=4)

REPHRASE_SYSTEM = (
    "You are the Moneyball EPL football analytics & scouting assistant (Premier League 2025-26, XGBoost + TreeSHAP). "
    "Rewrite the draft answer so it reads naturally, clearly, and insightfully for a football scout or analyst. "
    "STRICT FACTUAL RULES:\n"
    "1. Use ONLY the facts and numbers present in the Draft Answer and Table Preview.\n"
    "2. NEVER invent, change, round, or recalculate any number, price, percentage, age, or stat.\n"
    "3. Keep EVERY bold player name (**Name**) from the Draft Answer intact.\n"
    "4. If the Draft Answer mentions 'Prototype value (synthetic target)' or 'synthetic', keep that caveat.\n"
    "5. Keep Markdown formatting (**bold**, bullet points) concise (under 140 words). Do NOT output a Markdown table "
    "because the UI already renders the interactive table separately below your text.\n"
    "6. Remember SHAP describes what moves the model's estimate, not real-world causation."
)

REWRITE_SYSTEM = (
    "You translate casual, conversational, or indirect user questions for the Moneyball EPL Premier League (2025-26) "
    "analytics app into a single clean, direct query understood by the app's deterministic engine.\n"
    "Supported canonical query patterns:\n"
    "- Valuations: 'Value <Player>', 'What is <Player> strengths and weaknesses?', '<Player> stats', '<Player> attacking stats'\n"
    "- SHAP explanations: 'Explain <Player>', 'What drives valuations for <defenders/midfielders/attackers>?'\n"
    "- Budget & recruitment: 'Best <defender/midfielder/attacker> to buy in the range of <X>m to <Y>m', 'Best <pos> under <X>m', "
    "'Find creative midfielders between <X>m and <Y>m'\n"
    "- Scouting lookalikes: 'Scout <Player>', 'Find cheaper alternatives to <Player> under <age>'\n"
    "- Comparisons & radar: 'Compare <Player A> and <Player B>', 'Why is <Player A> valued higher than <Player B>?', "
    "'Show radar for <Player A> and <Player B>'\n"
    "- Leaderboards: 'Who is the top scorer?', 'Who has the most assists?', 'Who are the most undervalued midfielders?', "
    "'Which club has the highest squad value?', 'Rank clubs by team strength', 'Average value by position'\n"
    "- What-if: 'What if <Player> scored <N> goals?', 'What if <Player> was <age>?'\n"
    "- Model & methodology: 'How does the model work?', 'List all 28 features', 'Listed vs model-estimated value', "
    "'What are the limitations of the model?', 'What is <term>?'\n"
    "Use full standard player/club names if the user used a nickname (e.g. 'Starboy' -> 'Bukayo Saka', 'Cold Palmer' -> 'Cole Palmer', "
    "'Gunners' -> 'Arsenal', 'Spurs' -> 'Tottenham Hotspur', 'City' -> 'Manchester City', 'Pool'/'Reds' -> 'Liverpool').\n"
    "Set `in_scope` to false ONLY if the user asks about something completely unrelated to Premier League players, valuations, stats, or this model."
)

GROUNDED_QA_SYSTEM = (
    "You are the Moneyball EPL assistant. Answer the user's question concisely using ONLY the Verified Dataset Snapshot provided. "
    "STRICT RULES:\n"
    "1. Every single number you write MUST appear verbatim in the Verified Dataset Snapshot — never calculate new numbers or round differently.\n"
    "2. Never mention players or clubs not in the snapshot.\n"
    "3. Note that valuations are prototype synthetic values where relevant.\n"
    "4. Keep the answer clear, helpful, and under 140 words in Markdown."
)


class QueryRewrite(BaseModel):
    canonical_query: str = Field(description="Clean canonical Moneyball EPL query string.")
    in_scope: bool = Field(description="True if related to EPL players, stats, scouting, valuations, or the model.")


def get_gemini_key(override_key: str | None = None) -> str:
    return (override_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


def has_gemini_key() -> bool:
    return bool(get_gemini_key())


def masked_gemini_key() -> str | None:
    k = get_gemini_key()
    if not k:
        return None
    if len(k) <= 8:
        return "••••"
    return f"{k[:4]}…{k[-4:]}"


def _resolve_models(preferred: str | None = None) -> list[str]:
    m = (preferred or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
    # Automatically upgrade deprecated legacy model strings per current Gemini SDK rules
    if m.startswith(("gemini-2.5", "gemini-2.0", "gemini-1.5", "gemini-1.0")):
        m = DEFAULT_GEMINI_MODEL
    chain = [m]
    for fb in (DEFAULT_GEMINI_MODEL, *FALLBACK_GEMINI_MODELS):
        if fb not in chain:
            chain.append(fb)
    return chain


def _thinking_level_for(model_name: str) -> str:
    if "flash-lite" in model_name:
        return "minimal"
    return "low"


def _call_gemini(
    prompt: str,
    *,
    system_instruction: str,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 2048,
    response_schema: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> tuple[str | None, str | None]:
    """Call Gemini Interactions API (`client.interactions.create`) with low thinking latency and hard timeout."""
    key = get_gemini_key(api_key)
    if not key:
        return None, None
    try:
        from google import genai
    except Exception:
        return None, None

    def _invoke_once(candidate_model: str) -> str | None:
        client = genai.Client(api_key=key)
        kwargs: dict[str, Any] = {
            "input": prompt,
            "system_instruction": system_instruction,
            "generation_config": {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "thinking_level": _thinking_level_for(candidate_model),
            },
            "store": False,
            "timeout": timeout,
        }
        if response_schema is not None:
            kwargs["response_format"] = {
                "type": "text",
                "mime_type": "application/json",
                "schema": response_schema,
            }
        interaction = client.interactions.create(model=candidate_model, **kwargs)
        return (interaction.output_text or "").strip() or None

    for candidate_model in _resolve_models(model)[:2]:
        fut = _EXECUTOR.submit(_invoke_once, candidate_model)
        try:
            out = fut.result(timeout=min(timeout, 5.5))
            if out:
                return out, candidate_model
        except FuturesTimeoutError:
            continue
        except Exception as exc:
            err_s = str(exc).lower()
            if "api_key_invalid" in err_s or "api key not valid" in err_s or "permission_denied" in err_s:
                return None, None
            continue
    return None, None


def verify_gemini_key(api_key: str, model: str | None = None) -> tuple[bool, str, str | None]:
    """Ping Gemini with a tiny stateless interaction to verify a user-supplied free-tier key."""
    key = (api_key or "").strip()
    if not key:
        return False, "API key is empty.", None
    try:
        from google import genai
        last_err = "Unknown error"
        for candidate_model in _resolve_models(model):
            def _ping(m_name: str = candidate_model):
                client = genai.Client(api_key=key)
                return client.interactions.create(
                    model=m_name,
                    input="Reply with the single word OK.",
                    generation_config={
                        "max_output_tokens": 256,
                        "temperature": 0.0,
                        "thinking_level": _thinking_level_for(m_name),
                    },
                    store=False,
                    timeout=7.0,
                )
            try:
                inter = _EXECUTOR.submit(_ping).result(timeout=8.5)
                if inter and (inter.output_text or inter.status == "completed"):
                    return True, "Connected", candidate_model
            except FuturesTimeoutError:
                return False, "Gemini request timed out while verifying key. Please try again.", None
            except Exception as exc:
                last_err = str(exc)
                if "API_KEY_INVALID" in last_err or "api key not valid" in last_err.lower():
                    return False, "Invalid Gemini API key. Check your key from Google AI Studio.", None
                continue
        return False, f"Could not reach Gemini model: {last_err[:160]}", None
    except Exception as exc:
        return False, f"Gemini SDK error: {str(exc)[:160]}", None


def rewrite_query(
    question: str,
    context_summary: str = "",
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> str | None:
    """Translate an unparsed conversational query into a canonical Moneyball EPL query."""
    prompt = f"User message: {question}"
    if context_summary:
        prompt = f"Session context: {context_summary}\n{prompt}"
    raw, _ = _call_gemini(
        prompt,
        system_instruction=REWRITE_SYSTEM,
        api_key=api_key,
        model=model,
        temperature=0.0,
        max_output_tokens=1024,
        response_schema=QueryRewrite.model_json_schema(),
        timeout=6.5,
    )
    if not raw:
        return None
    try:
        parsed = QueryRewrite.model_validate_json(raw)
        if parsed.in_scope and parsed.canonical_query.strip():
            return parsed.canonical_query.strip()
    except Exception:
        return None
    return None


def _format_table_preview(table: dict | None, max_rows: int = 5) -> str:
    if not table or not table.get("rows") or not table.get("columns"):
        return ""
    cols = [c for c in table["columns"] if not str(c.get("key", "")).startswith("_")]
    header = " | ".join(c.get("label") or c["key"] for c in cols)
    lines = [header]
    for row in table["rows"][:max_rows]:
        lines.append(" | ".join(str(row.get(c["key"], "")) for c in cols))
    return "\n".join(lines)


def rephrase(
    question: str,
    draft: str,
    facts: Facts,
    *,
    table: dict | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Rephrase `draft` using Gemini (or Anthropic fallback), returning `(new_text, model_used)` if 100% grounded."""
    preview = _format_table_preview(table)
    user_prompt = f"User question: {question}\n\nDraft Answer:\n{draft}"
    if preview:
        user_prompt += f"\n\nTable Preview (shown below your text in the UI — do NOT repeat as a markdown table):\n{preview}"

    text, used_model = _call_gemini(
        user_prompt,
        system_instruction=REPHRASE_SYSTEM,
        api_key=api_key,
        model=model,
        temperature=0.2,
        max_output_tokens=2048,
        timeout=8.0,
    )

    # Optional Anthropic fallback if user only set ANTHROPIC_API_KEY
    if not text and not get_gemini_key(api_key) and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            anth_model = os.environ.get("LLM_MODEL", "claude-sonnet-4-5")
            msg = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]).messages.create(
                model=anth_model,
                max_tokens=500,
                system=REPHRASE_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text, used_model = msg.content[0].text.strip(), anth_model
        except Exception:
            text, used_model = None, None

    if not text:
        return None, None

    # Reject if Gemini emitted a markdown table header separator
    if re.search(r"^\s*\|?\s*:?-{3,}:?\s*\|", text, flags=re.M):
        return None, None

    # Strict numeric grounding check: every number must exist in `facts`
    if check_numbers(text, facts)["unmatched"]:
        return None, None

    # Preserve proper player names (e.g. **Bukayo Saka**) that appear in the original draft
    bold_entities = [
        b.strip() for b in re.findall(r"\*\*([^*]+)\*\*", draft)
        if 2 <= len(b.strip().split()) <= 3
        and not any(ch.isdigit() or ch in ":&/()—–-•%" for ch in b)
        and all(w[0].isupper() for w in b.strip().split() if w)
        and b.strip().lower() not in {"moneyball epl", "model estimate", "key strengths", "listed value"}
    ]
    for ent in bold_entities[:2]:
        if ent.lower() not in text.lower():
            return None, None

    return text, used_model


def answer_grounded(
    question: str,
    store,
    *,
    context_dict: dict | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str | None, Facts, str | None]:
    """Answer open-ended analytical questions strictly from a verified Store snapshot."""
    F = Facts()
    m = store.meta()
    err = m["error"]
    top_val = store.rankings("estimated_value", n=8)["rows"]
    top_barg = store.rankings("value_vs_similar", n=6)["rows"]
    top_goals = store.rankings("goals", n=5)["rows"]
    top_assists = store.rankings("assists", n=5)["rows"]

    lines = [
        f"Season: {F.raw(m['season'])}, Matchday: {F.int(m['kaggle_matchday'])}, Sample: {F.int(m['n_players'])} outfield players "
        f"across {F.int(len(m['clubs']))} clubs (minimum {F.int(m['min_minutes'])} minutes).",
        f"Primary Model: {m['chosen_model']} (5-fold CV R2={F.num(err['cv_r2'], 2)}, RMSE_log={F.num(err['cv_rmse_log'], 3)}, "
        f"MAE={F.eur(err['cv_mae_eur'])}, median abs error={F.pct(err['cv_median_abs_pct'], signed=False)}). "
        f"Base player estimate: {F.eur(m['base_eur'])}. Target source: synthetic prototype.",
        "Top Valued Players: " + "; ".join(
            f"{r['name']} ({r['club']}, {r['position']}, age {F.int(r['age'])}, est {F.eur(r['estimated_value_eur'])}, listed {F.eur(r['listed_value_eur'])})"
            for r in top_val
        ),
        "Top Value-for-Money Bargains (vs similar peers): " + "; ".join(
            f"{r['name']} ({r['club']}, {r['position']}, age {F.int(r['age'])}, est {F.eur(r['estimated_value_eur'])})"
            for r in top_barg
        ),
        "Top Scorers: " + "; ".join(f"{r['name']} ({r['club']}): {F.int(r['goals'])} goals" for r in top_goals),
        "Top Assisters: " + "; ".join(f"{r['name']} ({r['club']}): {F.int(r['assists'])} assists" for r in top_assists),
    ]
    if context_dict and context_dict.get("target"):
        tid = context_dict["target"].get("id")
        if tid is not None and 0 <= tid < store.n:
            s = store.summary(tid)
            lines.append(
                f"Active Player in Session: {s['name']} ({s['club']}, {s['position_name']}, age {F.int(s['age'])}, "
                f"minutes {F.int(s['minutes'])}, goals {F.int(s['goals'] or 0)}, assists {F.int(s['assists'] or 0)}, "
                f"est {F.eur(s['estimated_value_eur'])}, listed {F.eur(s['listed_value_eur'])})."
            )

    snapshot = "\n".join(lines)
    F.allow(snapshot)

    prompt = f"Verified Dataset Snapshot:\n{snapshot}\n\nUser Question: {question}"
    text, used_model = _call_gemini(
        prompt,
        system_instruction=GROUNDED_QA_SYSTEM,
        api_key=api_key,
        model=model,
        temperature=0.15,
        max_output_tokens=2048,
        timeout=8.0,
    )
    if not text:
        return None, F, None
    if check_numbers(text, F)["unmatched"]:
        return None, F, None
    return text, F, used_model
