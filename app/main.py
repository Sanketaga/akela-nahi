"""Akela Nahi web server: the elder's app (/elder), the family page (/family) and the API.

Run:  .venv\\Scripts\\python -m uvicorn app.main:app --port 8000
"""
import asyncio
import json
import logging
import re
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, conversation, db, demo_history, gnani, scheduler, trends

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("akela")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    task = asyncio.create_task(scheduler.run_forever())
    log.info("Akela Nahi started. Gnani: %s", config.status())
    yield
    task.cancel()


app = FastAPI(title="Akela Nahi", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")

_basic = HTTPBasic(auto_error=False)


def require_login(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    """Password-protect everything when DASHBOARD_PASSWORD is set (username: family)."""
    if not config.DASHBOARD_PASSWORD:
        return
    ok = creds is not None and secrets.compare_digest(creds.username, "family") and secrets.compare_digest(
        creds.password, config.DASHBOARD_PASSWORD)
    if not ok:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})


AUTH = [Depends(require_login)]


# ---------------------------------------------------------------- pages

@app.get("/")
def home():
    return RedirectResponse("/family")


@app.get("/family", dependencies=AUTH)
def family_page():
    return FileResponse(config.STATIC_DIR / "family.html")


@app.get("/elder", dependencies=AUTH)
def elder_page():
    return FileResponse(config.STATIC_DIR / "elder.html")


@app.get("/audio/{name}", dependencies=AUTH)
def audio(name: str):
    if not re.fullmatch(r"(tts|vc)_[0-9a-f]{32}\.wav", name):
        raise HTTPException(404)
    path = config.AUDIO_DIR / name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/wav")


# ---------------------------------------------------------------- elders

class ElderIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    family_label: str = Field(min_length=1, max_length=40)
    language: str = "hi-IN"
    voice: str = config.GNANI_DEFAULT_VOICE
    call_time: str = "08:30"
    family_name: str = Field(min_length=1, max_length=60)
    family_relation: str = "son"
    family_language: str = "en-IN"
    medicines: str = Field(default="", max_length=300)
    share_transcript: bool = False
    use_family_voice: bool = False
    active: bool = True


def _validate(e: ElderIn) -> None:
    if e.language not in config.LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    if e.family_language not in config.FAMILY_LANGUAGES:
        raise HTTPException(400, "Family updates are available in English or Hindi")
    if e.voice not in config.TIMBRE_V3_VOICES:
        raise HTTPException(400, "Unknown Timbre v3 voice")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", e.call_time):
        raise HTTPException(400, "call_time must be HH:MM")


def _public(e: dict) -> dict:
    e = dict(e)
    e["has_family_voice"] = bool(e.pop("family_voice_embedding", None))
    return e


def _values(e: ElderIn) -> list:
    d = e.model_dump()
    return [int(d[c]) if isinstance(d[c], bool) else d[c] for c in db.ELDER_FIELDS]


def _elder_or_404(elder_id: int) -> dict:
    e = db.get_elder(elder_id)
    if not e:
        raise HTTPException(404)
    return e


@app.get("/api/status", dependencies=AUTH)
def api_status():
    return {**config.status(), "languages": config.LANGUAGES, "family_languages": config.FAMILY_LANGUAGES,
            "voices": config.TIMBRE_V3_VOICES}


@app.get("/api/elders", dependencies=AUTH)
def list_elders():
    return [_public(e) for e in db.all_("SELECT * FROM elders ORDER BY id")]


@app.post("/api/elders", dependencies=AUTH)
def create_elder(e: ElderIn):
    _validate(e)
    cols = db.ELDER_FIELDS
    new_id = db.execute(f"INSERT INTO elders({','.join(cols)}, created_at) VALUES({','.join('?' * len(cols))}, ?)",
                        *_values(e), db.now_iso())
    return _public(db.get_elder(new_id))


@app.put("/api/elders/{elder_id}", dependencies=AUTH)
def update_elder(elder_id: int, e: ElderIn):
    _elder_or_404(elder_id)
    _validate(e)
    db.execute(f"UPDATE elders SET {','.join(c + '=?' for c in db.ELDER_FIELDS)} WHERE id=?", *_values(e), elder_id)
    return _public(db.get_elder(elder_id))


@app.post("/api/elders/{elder_id}/family-voice", dependencies=AUTH)
async def family_voice(elder_id: int, audio: UploadFile = File(...)):
    """10-20 s of the son/daughter speaking (with their consent) -> Gnani voice clone embedding."""
    _elder_or_404(elder_id)
    data = await audio.read()
    if len(data) > 10_000_000:
        raise HTTPException(400, "Audio too large")
    try:
        emb = await asyncio.to_thread(gnani.create_voice_embedding, data, "voice.wav")
    except gnani.GnaniError as e:
        raise HTTPException(502, str(e))
    db.execute("UPDATE elders SET family_voice_embedding=?, use_family_voice=1 WHERE id=?", json.dumps(emb), elder_id)
    return {"ok": True}


@app.delete("/api/elders/{elder_id}/family-voice", dependencies=AUTH)
def delete_family_voice(elder_id: int):
    db.execute("UPDATE elders SET family_voice_embedding=NULL, use_family_voice=0 WHERE id=?", elder_id)
    return {"ok": True}


@app.get("/api/elders/{elder_id}/overview", dependencies=AUTH)
def overview(elder_id: int):
    elder = _elder_or_404(elder_id)
    calls = db.all_("SELECT id, kind, status, level, summary_json, started_at, ended_at FROM calls "
                    "WHERE elder_id=? ORDER BY id DESC LIMIT 30", elder_id)
    for c in calls:
        c.pop("summary_json", None)
        if c.get("summary") and not elder["share_transcript"]:
            c["summary"].pop("answers", None)
    return {
        "elder": _public(elder),
        "calls": calls,
        "alerts": db.all_("SELECT * FROM alerts WHERE elder_id=? ORDER BY id DESC LIMIT 20", elder_id),
        "questions": db.all_("SELECT * FROM questions WHERE elder_id=? ORDER BY id DESC LIMIT 10", elder_id),
        "updates": db.all_("SELECT * FROM updates WHERE elder_id=? ORDER BY id DESC LIMIT 30", elder_id),
    }


@app.get("/api/elders/{elder_id}/trends", dependencies=AUTH)
def health_trends(elder_id: int, refresh: bool = False):
    """14-day timeline, the numbers, and the AI-written trend report for the family."""
    elder = _elder_or_404(elder_id)
    return trends.report(elder, refresh=refresh)


@app.post("/api/elders/{elder_id}/sample-history", dependencies=AUTH)
def sample_history(elder_id: int):
    """Adds two weeks of synthetic check-ins so the trend view can be tried immediately."""
    _elder_or_404(elder_id)
    if db.one("SELECT id FROM calls WHERE elder_id=? AND kind='checkin' AND status='completed' LIMIT 1", elder_id):
        raise HTTPException(400, "This parent already has real check-ins")
    return {"added": demo_history.seed(elder_id)}


@app.get("/report/{elder_id}", dependencies=AUTH)
def doctor_report(elder_id: int):
    """A printable one-page summary the family can take to the doctor."""
    from fastapi.responses import HTMLResponse
    from html import escape
    elder = _elder_or_404(elder_id)
    t = trends.report(elder)
    rows = t["timeline"]
    sym = {True: "✓", False: "✗", None: "–"}

    def cell(r, key):
        if r["status"] == "missed":
            return "<td class=m>missed</td>"
        if r["status"] == "none":
            return "<td></td>"
        v = r[key]
        if key == "medicines_taken":
            return f"<td class={'bad' if v is False else ''}>{sym[v]}</td>"
        if key == "pain":
            return f"<td class={'bad' if v else ''}>{escape(', '.join(v)) or '–'}</td>"
        bad = v in ("poor", "low", "lonely")
        return f"<td class={'bad' if bad else ''}>{escape(v or '–')}</td>"

    head = "".join(f"<th>{r['date'][5:]}</th>" for r in rows)
    body = "".join(
        f"<tr><th>{label}</th>{''.join(cell(r, key) for r in rows)}</tr>"
        for label, key in (("Medicines", "medicines_taken"), ("Sleep", "sleep"), ("Food", "food"),
                           ("Pain", "pain"), ("Mood", "mood")))
    rep = t["report"]
    trends_html = "".join(f"<li><b>{escape(x['title'])}</b> ({x['direction']}): {escape(x['detail'])}</li>"
                          for x in rep["trends"]) or "<li>No pattern to report.</li>"
    html = f"""<!doctype html><html><head><meta charset=utf-8><title>Akela Nahi report: {escape(elder['family_label'])}</title>
<style>body{{font:14px/1.45 system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#1f1a15}}
h1{{font-size:22px;margin:0}}table{{border-collapse:collapse;width:100%;margin:14px 0;font-size:12px}}
td,th{{border:1px solid #ddd;padding:4px;text-align:center}}th{{background:#f6f2ea}}.bad{{color:#a52a1e;font-weight:600}}
.m{{color:#999}}.note{{background:#f6f2ea;padding:12px;border-radius:8px}}.muted{{color:#777;font-size:12px}}
@media print{{button{{display:none}}}}</style></head><body>
<button onclick="print()" style="float:right">Print</button>
<h1>{escape(elder['family_label'])}: last {len(rows)} days of check-ins</h1>
<p class=muted>Medicines on file: {escape(elder.get('medicines') or 'none listed')} · generated {t['generated_at'][:16].replace('T', ' ')} · {escape(t['engine_label'])}</p>
<div class=note><b>Summary for the doctor.</b> {escape(rep['doctor_note'])}</div>
<table><tr><th></th>{head}</tr>{body}</table>
<h3>Trends</h3><ul>{trends_html}</ul>
<p class=muted>Answers are what the parent said in short daily voice check-ins (Akela Nahi). This is not a medical record or a diagnosis.</p>
</body></html>"""
    return HTMLResponse(html)


@app.get("/api/calls/{call_id}", dependencies=AUTH)
def call_detail(call_id: int):
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404)
    elder = db.get_elder(call["elder_id"])
    for k in ("summary_json", "plan_json", "answers_json", "plan", "answers"):
        call.pop(k, None)
    # The family sees the elder's exact words only if the elder agreed (message calls are always shared).
    shared = bool(elder["share_transcript"]) or call["kind"] == "relay"
    call["turns"] = db.call_turns(call_id) if shared else None
    if call.get("summary") and not shared:
        call["summary"].pop("answers", None)
    return call


class FamilyMessage(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    ask_only: bool = False


@app.post("/api/elders/{elder_id}/family-message", dependencies=AUTH)
def family_message(elder_id: int, m: FamilyMessage):
    return {"result": conversation.handle_family_message(_elder_or_404(elder_id), m.text, m.ask_only)}


@app.post("/api/elders/{elder_id}/call", dependencies=AUTH)
def ring_now(elder_id: int):
    _elder_or_404(elder_id)
    return {"call_id": conversation.create_call(elder_id, "checkin")}


# ---------------------------------------------------------------- the elder's app

@app.get("/api/elders/{elder_id}/incoming", dependencies=AUTH)
def incoming(elder_id: int):
    c = db.one("SELECT id, kind FROM calls WHERE elder_id=? AND status='ringing' ORDER BY id LIMIT 1", elder_id)
    return {"call": c}


@app.post("/api/calls/{call_id}/answer", dependencies=AUTH)
def answer(call_id: int):
    call = db.get_call(call_id)
    if not call or call["status"] != "ringing":
        raise HTTPException(409, "This call is not ringing")
    return conversation.open_call(call_id)


@app.post("/api/calls/{call_id}/decline", dependencies=AUTH)
def decline(call_id: int):
    conversation.mark_no_answer(call_id)
    return {"ok": True}


@app.post("/api/calls/{call_id}/turn", dependencies=AUTH)
def turn(call_id: int, audio: UploadFile | None = File(None), text: str | None = Form(None)):
    """The elder answered: recorded audio (-> Gnani Prisma) or typed text (demo mode)."""
    call = db.get_call(call_id)
    if not call or call["status"] != "in_progress":
        raise HTTPException(409, "This call is not active")
    heard = (text or "").strip()[:500]
    if audio is not None:
        data = audio.file.read()
        if len(data) > 5_000_000:
            raise HTTPException(400, "Audio too large")
        if not config.gnani_enabled():
            raise HTTPException(400, "Speech needs GNANI_API_KEY. In demo mode, type the answer.")
        elder = db.get_elder(call["elder_id"])
        last_agent = next((t["text"] for t in reversed(db.call_turns(call_id)) if t["role"] == "agent"), "")
        try:
            heard = gnani.transcribe(data, "answer.wav", elder, previous_text=last_agent)
        except gnani.GnaniError as e:
            log.error("Prisma STT failed: %s", e)
            heard = ""
    result = conversation.elder_says(call_id, heard) if heard else conversation.unclear_audio(call_id)
    return {"heard": heard, **result}


@app.post("/api/calls/{call_id}/hangup", dependencies=AUTH)
def hangup(call_id: int):
    conversation.finish_call(call_id)
    return {"ok": True}


@app.post("/api/elders/{elder_id}/sos", dependencies=AUTH)
def sos(elder_id: int):
    _elder_or_404(elder_id)
    return conversation.sos(elder_id)
