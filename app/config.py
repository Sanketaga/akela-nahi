"""Settings loaded from .env. Gnani AI does the voice (Prisma STT, Timbre TTS, voice cloning).
An optional AI key (Gemini or Anthropic) writes the weekly health-trend report.
Without GNANI_API_KEY the app runs in demo mode (answers are typed)."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("AKELA_DATA_DIR") or (ROOT / "data"))
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "akela_nahi.db"
STATIC_DIR = ROOT / "static"


def _get(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


GNANI_API_KEY = _get("GNANI_API_KEY")
GNANI_STT_MODEL = _get("GNANI_STT_MODEL", "prisma-v3.0")
GNANI_TTS_MODEL = _get("GNANI_TTS_MODEL", "timbre-v3.0")
GNANI_DEFAULT_VOICE = _get("GNANI_DEFAULT_VOICE", "Chetana")
GNANI_TTS_SPEED = float(_get("GNANI_TTS_SPEED", "0.9"))
GNANI_STT_URL = "https://api.vachana.ai/stt/v3"
GNANI_TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
GNANI_VC_URL = "https://api.vachana.ai/api/v1/tts/voice-clone/embeddings"

# Health-trend report (optional). Gemini has a free tier: https://aistudio.google.com/apikey
GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

DASHBOARD_PASSWORD = _get("DASHBOARD_PASSWORD")
TZ = ZoneInfo(_get("TIMEZONE", "Asia/Kolkata"))

# How long the elder app rings before it counts as "not answered".
RING_MINUTES = int(_get("RING_MINUTES", "10"))


def gnani_enabled() -> bool:
    return bool(GNANI_API_KEY)


def status() -> dict:
    trends = "gemini" if GEMINI_API_KEY else "anthropic" if ANTHROPIC_API_KEY else "rules"
    return {"gnani": gnani_enabled(), "stt_model": GNANI_STT_MODEL, "tts_model": GNANI_TTS_MODEL, "trends_ai": trends}


LANGUAGES = {
    "hi-IN": "Hindi",
    "en-IN": "English",
    "kn-IN": "Kannada",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "ml-IN": "Malayalam",
    "mr-IN": "Marathi",
    "bn-IN": "Bengali",
    "gu-IN": "Gujarati",
    "pa-IN": "Punjabi",
}

# The family's update text is written from templates in these languages.
FAMILY_LANGUAGES = {"en-IN": "English", "hi-IN": "Hindi"}

TIMBRE_V3_VOICES = [
    "Chetana", "Kalpana", "Shivani", "Lakshmi", "Vasudha", "Riyaa", "Tarika",
    "Prakash", "Avinash", "Shubham", "Devansh", "Yashraj", "Harshad",
]
