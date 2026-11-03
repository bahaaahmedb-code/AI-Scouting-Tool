"""FastAPI backend. Loads the precomputed bundle once; every endpoint answers from it.

    uvicorn app.api:app --port 8000          (from the backend folder)
"""
# NOTE: no `from __future__ import annotations` here - with slowapi's rate-limit wrappers it leaves
# annotations like `Position | None` unresolved and every request using them fails with a 500.
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .chatbot import ChatEngine
from .chatbot import llm
from .config import BACKEND_DIR, PROJECT_DIR, load_settings
from .constants import NUM_FEATURES, SIM_FEATURES, TOOLTIPS, pretty
from .chatbot.glossary import GLOSSARY
from .evaluation import EvalStore, sus_score
from .similarity import ScoutQuery
from .store import Store

settings = load_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
STATE: dict = {}

Position = Literal["D", "M", "F"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.time()
    store = Store.load(settings.artifacts_path)
    STATE["store"] = store
    STATE["chat"] = ChatEngine(store)
    STATE["eval"] = EvalStore(settings.log_path, settings.eval_logging)
    STATE["loaded_s"] = round(time.time() - t0, 2)
    yield


app = FastAPI(title="Moneyball EPL API", version="1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])


@app.exception_handler(RateLimitExceeded)
async def _rate_limited(request: Request, exc: RateLimitExceeded):
    return JSONResponse({"detail": "Too many requests. Please wait a moment and try again."}, status_code=429)


def S() -> Store:
    return STATE["store"]


def _player(i: int) -> int:
    if not 0 <= i < S().n:
        raise HTTPException(404, "Player not found in the sample.")
    return i


# ------------------------------------------------------------------ core
@app.get("/api/health")
def health():
    return {"ok": True, "players": S().n, "loaded_seconds": STATE.get("loaded_s")}


@app.get("/api/meta")
@limiter.limit(settings.rate_limit)
def meta(request: Request):
    m = S().meta()
    m["feedback_url"] = settings.feedback_url
    m["llm_rephrase"] = settings.llm_rephrase
    m["gemini_configured"] = llm.has_gemini_key()
    m["gemini_model"] = settings.gemini_model
    return m


@app.get("/api/players")
@limiter.limit(settings.rate_limit)
def players(request: Request, q: str = Query("", max_length=60), club: str | None = Query(None, max_length=60),
            position: Position | None = None, limit: int = Query(20, ge=1, le=500)):
    return S().search(q, club, position, limit)


@app.get("/api/players/{pid}")
@limiter.limit(settings.rate_limit)
def player(request: Request, pid: int):
    return S().profile(_player(pid))


@app.get("/api/players/{pid}/shap")
@limiter.limit(settings.rate_limit)
def player_shap(request: Request, pid: int, merged: bool = True, max_display: int = Query(12, ge=3, le=40)):
    return S().waterfall(_player(pid), merged=merged, max_display=max_display)


@app.get("/api/explain/global")
@limiter.limit(settings.rate_limit)
def explain_global(request: Request, position: Position | None = None):
    return S().global_importance(position)


@app.get("/api/explain/dependence/{feature}")
@limiter.limit(settings.rate_limit)
def explain_dependence(request: Request, feature: str):
    try:
        return S().dependence(feature)
    except KeyError:
        raise HTTPException(404, "Unknown feature.")


class ScoutBody(BaseModel):
    target: int = Field(ge=0)
    position_mode: Literal["same", "any", "D", "M", "F"] = "same"
    max_pct: float | None = Field(60, ge=5, le=500)
    max_age: int | None = Field(None, ge=16, le=45)
    min_age: int | None = Field(None, ge=16, le=45)
    n: int = Field(10, ge=1, le=50)


@app.get("/api/scout")
@limiter.limit(settings.rate_limit)
def scout(request: Request, target: int = Query(..., ge=0),
          position_mode: Literal["same", "any", "D", "M", "F"] = "same",
          max_pct: float = Query(60, ge=5, le=500),
          max_age: int | None = Query(None, ge=16, le=45),
          min_age: int | None = Query(None, ge=16, le=45),
          n: int = Query(10, ge=1, le=50)):
    _player(target)
    q = ScoutQuery(target=target, same_position=position_mode == "same",
                   position=position_mode if position_mode in ("D", "M", "F") else None,
                   max_pct=max_pct, max_age=max_age, min_age=min_age, n=n)
    return S().scout(q)


def _ids(ids: str, lo=1, hi=4) -> list[int]:
    try:
        out = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "ids must be comma-separated numbers.")
    if not lo <= len(out) <= hi or len(set(out)) != len(out):
        raise HTTPException(422, f"Choose between {lo} and {hi} different players.")
    return [_player(i) for i in out]


@app.get("/api/compare")
@limiter.limit(settings.rate_limit)
def compare(request: Request, ids: str = Query(..., max_length=60)):
    return S().compare(_ids(ids, 2, 4))


@app.get("/api/radar")
@limiter.limit(settings.rate_limit)
def radar(request: Request, ids: str = Query(..., max_length=60)):
    return S().radar(_ids(ids, 1, 4))


@app.get("/api/rankings")
@limiter.limit(settings.rate_limit)
def rankings(request: Request, by: str = Query("estimated_value", max_length=40), position: Position | None = None,
             club: str | None = Query(None, max_length=60), min_age: int | None = Query(None, ge=15, le=45),
             max_age: int | None = Query(None, ge=15, le=45), min_minutes: int | None = Query(None, ge=0, le=4000),
             n: int = Query(10, ge=1, le=100), ascending: bool | None = None):
    try:
        return S().rankings(by=by, position=position, club=club, min_age=min_age, max_age=max_age,
                            min_minutes=min_minutes, n=n, ascending=ascending)
    except KeyError:
        raise HTTPException(422, "Unknown ranking.")


class WhatIfBody(BaseModel):
    player: int = Field(ge=0)
    feature: str = Field(max_length=40)
    value: float = Field(ge=0, le=10000)


@app.post("/api/whatif")
@limiter.limit(settings.rate_limit)
def whatif(request: Request, body: WhatIfBody):
    try:
        return S().whatif(_player(body.player), body.feature, body.value)
    except KeyError:
        raise HTTPException(422, "This feature cannot be changed.")


@app.get("/api/glossary")
def glossary():
    return {"terms": [{"key": k, "title": t, "text": x} for k, (t, x) in GLOSSARY.items()],
            "features": [{"key": f, "label": pretty(f), "tooltip": TOOLTIPS.get(f, "")} for f in NUM_FEATURES]}


# ------------------------------------------------------------------ chat
class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(None, max_length=64)


class GeminiKeyBody(BaseModel):
    api_key: str | None = Field(None, max_length=256)
    enabled: bool | None = None


def _persist_env_var(key: str, value: str) -> None:
    env_path = BACKEND_DIR / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            if value:
                out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(ln)
    if not replaced and value:
        out.append(f"{key}={value}")
    env_path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")


@app.get("/api/chat/gemini-status")
def gemini_status():
    return {
        "configured": llm.has_gemini_key(),
        "masked_key": llm.masked_gemini_key(),
        "enabled": bool(settings.llm_rephrase),
        "model": settings.gemini_model,
        "free_key_url": "https://aistudio.google.com/apikey",
    }


@app.post("/api/chat/gemini-key")
@limiter.limit("15/minute")
def set_gemini_key(request: Request, body: GeminiKeyBody):
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "API key configuration is only allowed from localhost.")
    if body.api_key is not None:
        cleaned = body.api_key.strip()
        if not cleaned:
            os.environ.pop("GEMINI_API_KEY", None)
            _persist_env_var("GEMINI_API_KEY", "")
        else:
            ok, msg, verified_model = llm.verify_gemini_key(cleaned, settings.gemini_model)
            if not ok:
                raise HTTPException(400, msg)
            os.environ["GEMINI_API_KEY"] = cleaned
            _persist_env_var("GEMINI_API_KEY", cleaned)
            settings.llm_rephrase = True
            if verified_model:
                settings.gemini_model = verified_model
    if body.enabled is not None:
        settings.llm_rephrase = bool(body.enabled)
    return gemini_status()


@app.post("/api/chat")
@limiter.limit(settings.chat_rate_limit)
def chat(request: Request, body: ChatBody):
    reply = STATE["chat"].answer(body.message, body.session_id)
    rephrased = False
    llm_model_used = None
    use_gemini = settings.llm_rephrase and (llm.has_gemini_key() or bool(os.environ.get("ANTHROPIC_API_KEY")))

    if use_gemini and not reply["understood"] and llm.has_gemini_key():
        ctx = reply.get("context") or {}
        ctx_summary = ""
        if ctx.get("target"):
            ctx_summary += f"Active player: {ctx['target'].get('name')} ({ctx['target'].get('club')}). "
        if ctx.get("shortlist"):
            ctx_summary += f"Shortlist size: {len(ctx['shortlist'])}."
        rewritten = llm.rewrite_query(body.message, ctx_summary, model=settings.gemini_model)
        if rewritten and rewritten.lower() != body.message.strip().lower():
            retry = STATE["chat"].answer(rewritten, reply["session_id"])
            if retry["understood"]:
                reply = retry
                reply["rewritten_query"] = rewritten

    if use_gemini and not reply["understood"] and llm.has_gemini_key():
        from .chatbot.facts import check_numbers
        g_text, g_facts, g_model = llm.answer_grounded(
            body.message, S(), context_dict=reply.get("context"), model=settings.gemini_model
        )
        if g_text:
            reply["text"] = g_text
            reply["understood"] = True
            reply["intent"] = "explanation"
            reply["subintent"] = "gemini_grounded"
            reply["numbers"] = check_numbers(g_text, g_facts)
            rephrased = True
            llm_model_used = g_model
    elif use_gemini and reply["understood"] and reply.get("subintent") not in ("reset", "export"):
        from .chatbot.facts import Facts, check_numbers
        F = Facts()
        F.allow(reply["text"], reply.get("details") or "")
        if reply.get("table"):
            for r_row in reply["table"].get("rows", []):
                for k, v in r_row.items():
                    if not str(k).startswith("_"):
                        F.allow(v)
        new_text, used_m = llm.rephrase(
            body.message, reply["text"], F, table=reply.get("table"), model=settings.gemini_model
        )
        if new_text:
            reply["text"] = new_text
            table_blob = " ".join(
                str(v)
                for r_row in (reply.get("table") or {}).get("rows", [])
                for k, v in r_row.items()
                if not str(k).startswith("_")
            )
            reply["numbers"] = check_numbers(
                new_text + "\n" + (reply.get("details") or "") + "\n" + table_blob, F
            )
            rephrased = True
            llm_model_used = used_m

    reply["rephrased"] = rephrased
    reply["llm_model"] = llm_model_used
    STATE["eval"].log_chat(reply["session_id"], body.message, reply, rephrased)
    return reply


# ------------------------------------------------------------------ evaluation (access code)
def require_code(x_access_code: str | None = Header(None)):
    if not x_access_code or x_access_code != settings.eval_access_code:
        raise HTTPException(401, "Access code required.")
    return True


@app.post("/api/eval/login")
@limiter.limit("10/minute")
def eval_login(request: Request, ok: bool = Depends(require_code)):
    return {"ok": True}


class RatingItem(BaseModel):
    candidate_id: int = Field(ge=0)
    rank: int = Field(ge=1, le=50)
    similarity: float
    rating: int = Field(ge=1, le=5)


class RatingBody(BaseModel):
    evaluator: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    target_id: int = Field(ge=0)
    items: list[RatingItem] = Field(min_length=1, max_length=10)
    comparable_players: str = Field("", max_length=300)
    comment: str = Field("", max_length=1000)


@app.post("/api/eval/ratings")
def eval_ratings(body: RatingBody, ok: bool = Depends(require_code)):
    st = S()
    _player(body.target_id)
    for it in body.items:
        _player(it.candidate_id)
        STATE["eval"].insert("ratings", {"evaluator": body.evaluator, "target_id": body.target_id, "target_name": st.d.at[body.target_id, "player_name"],
                                         "candidate_id": it.candidate_id, "candidate_name": st.d.at[it.candidate_id, "player_name"],
                                         "rank": it.rank, "similarity": it.similarity, "rating": it.rating,
                                         "comparable_players": body.comparable_players, "comment": body.comment})
    return {"saved": len(body.items)}


class TaskBody(BaseModel):
    participant: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    task: str = Field(min_length=1, max_length=80)
    success: bool
    seconds: float = Field(ge=0, le=36000)
    notes: str = Field("", max_length=1000)


@app.post("/api/eval/tasks")
def eval_tasks(body: TaskBody, ok: bool = Depends(require_code)):
    STATE["eval"].insert("tasks", {**body.model_dump(), "success": int(body.success)})
    return {"saved": True}


class SusBody(BaseModel):
    participant: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    answers: list[int] = Field(min_length=10, max_length=10)


@app.post("/api/eval/sus")
def eval_sus(body: SusBody, ok: bool = Depends(require_code)):
    try:
        score = sus_score(body.answers)
    except ValueError as e:
        raise HTTPException(422, str(e))
    STATE["eval"].insert("sus", {"participant": body.participant, "answers": ",".join(map(str, body.answers)), "score": score})
    return {"score": score}


@app.post("/api/eval/chat-tests")
def eval_chat_tests(ok: bool = Depends(require_code)):
    from .chat_tests import run_chat_tests
    run_id = uuid.uuid4().hex[:8]
    res = run_chat_tests(S())
    for r in res["rows"]:
        STATE["eval"].insert("chat_tests", {"run_id": run_id, **{k: r[k] for k in ("qid", "question", "group_name", "expected_intent", "got_intent",
                                                                                   "intent_ok", "numbers_total", "numbers_matched", "expected_ok", "answer")}})
    return {"run_id": run_id, **res}


@app.get("/api/eval/summary")
def eval_summary(ok: bool = Depends(require_code)):
    return STATE["eval"].summary()


@app.get("/api/eval/export/{table}")
def eval_export(table: Literal["chat_log", "ratings", "tasks", "sus", "chat_tests"], code: str = Query(..., max_length=80)):
    if code != settings.eval_access_code:
        raise HTTPException(401, "Access code required.")
    return PlainTextResponse(STATE["eval"].csv(table), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{table}.csv"'})


# ------------------------------------------------------------------ frontend (built SPA)
DIST = PROJECT_DIR / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
