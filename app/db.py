"""SQLite storage. Small, file-based, no server to run."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS elders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,              -- how the caller addresses them, e.g. "Sharma ji", "Amma"
    family_label TEXT NOT NULL,      -- how the family refers to them, e.g. "Papa"
    language TEXT NOT NULL DEFAULT 'hi-IN',
    voice TEXT NOT NULL DEFAULT 'Chetana',
    call_time TEXT DEFAULT '08:30',  -- HH:MM local time for the daily check-in
    family_name TEXT NOT NULL,       -- e.g. "Rahul"
    family_relation TEXT DEFAULT 'son',
    family_language TEXT DEFAULT 'en-IN',
    medicines TEXT DEFAULT '',       -- comma separated, helps speech recognition
    share_transcript INTEGER DEFAULT 0, -- elder agreed to share their exact words
    family_voice_embedding TEXT,     -- Gnani voice-clone embedding (JSON) of the son/daughter, with consent
    use_family_voice INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER NOT NULL,
    kind TEXT NOT NULL,              -- checkin | relay
    status TEXT NOT NULL,            -- ringing | in_progress | completed | no_answer
    relay_id INTEGER,
    plan_json TEXT,                  -- the scripted steps for this call
    step INTEGER DEFAULT 0,          -- index of the step whose answer we are waiting for
    answers_json TEXT,               -- what the elder said at each step
    level TEXT,                      -- green | yellow | red
    summary_json TEXT,
    retries INTEGER DEFAULT 0,       -- unclear-audio retries in a row
    started_at TEXT,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL,
    role TEXT NOT NULL,              -- agent | elder
    text TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS relays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER NOT NULL,
    message TEXT NOT NULL,           -- what the son/daughter typed
    status TEXT NOT NULL,            -- pending | calling | delivered | no_answer
    attempts INTEGER DEFAULT 0,
    reply_text TEXT,
    created_at TEXT,
    delivered_at TEXT,
    next_attempt_at TEXT
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER NOT NULL,
    question TEXT NOT NULL,          -- family wants this asked in the next check-in
    asked_call_id INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER NOT NULL,
    call_id INTEGER,
    level TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER NOT NULL,
    level TEXT,                      -- red updates trigger a loud notification on the family page
    body TEXT NOT NULL,
    audio TEXT,                      -- Gnani Timbre voice note file name
    created_at TEXT
);
"""


def now() -> datetime:
    return datetime.now(config.TZ)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    with session() as c:
        c.executescript(SCHEMA)


def row(r):
    if r is None:
        return None
    d = dict(r)
    for key in ("summary_json", "plan_json", "answers_json"):
        if d.get(key):
            try:
                d[key[:-5]] = json.loads(d[key])
            except ValueError:
                d[key[:-5]] = None
    return d


def one(sql: str, *args):
    with session() as c:
        return row(c.execute(sql, args).fetchone())


def all_(sql: str, *args) -> list[dict]:
    with session() as c:
        return [row(r) for r in c.execute(sql, args).fetchall()]


def execute(sql: str, *args) -> int:
    with session() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid


ELDER_FIELDS = [
    "name", "family_label", "language", "voice", "call_time", "family_name", "family_relation",
    "family_language", "medicines", "share_transcript", "use_family_voice", "active",
]


def get_elder(elder_id: int):
    return one("SELECT * FROM elders WHERE id=?", elder_id)


def get_call(call_id: int):
    return one("SELECT * FROM calls WHERE id=?", call_id)


def call_turns(call_id: int) -> list[dict]:
    return all_("SELECT role, text, created_at FROM turns WHERE call_id=? ORDER BY id", call_id)


def add_turn(call_id: int, role: str, text: str) -> None:
    execute("INSERT INTO turns(call_id, role, text, created_at) VALUES(?,?,?,?)", call_id, role, text, now_iso())


def recent_checkins(elder_id: int, limit: int = 5) -> list[dict]:
    """Most recent finished check-ins, newest first."""
    return all_(
        "SELECT * FROM calls WHERE elder_id=? AND kind='checkin' AND status IN ('completed','no_answer') "
        "ORDER BY id DESC LIMIT ?",
        elder_id, limit,
    )
