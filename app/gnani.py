"""Gnani AI speech APIs: Prisma (speech-to-text) and Timbre (text-to-speech)."""
import hashlib
import json
import logging

import httpx

from . import config

log = logging.getLogger("akela.gnani")

CHECKIN_TOPIC = (
    "A short, friendly daily phone call with an elderly person living alone in India. "
    "They talk about sleep, food, medicines, blood pressure or sugar readings, pain, mood, "
    "visitors and family. Speech may be slow, soft and mixed with English words."
)
COMMON_KEYTERMS = ["BP", "sugar", "tablet", "dawai", "goli", "doctor", "hospital", "dard"]


class GnaniError(RuntimeError):
    pass


def _stt_languages(language: str) -> str:
    # Prisma v3.0 accepts up to 4 hint languages. Elders often mix English words in.
    if config.GNANI_STT_MODEL == "prisma-v3.0" and language != "en-IN":
        return f"{language},en-IN"
    return language


def transcribe(audio: bytes, filename: str, elder: dict, previous_text: str = "") -> str:
    """Return the transcript for a short (<30 s) clip. Empty string means no speech."""
    if not config.gnani_enabled():
        raise GnaniError("GNANI_API_KEY is not set")
    if not audio:
        return ""
    data = {"language_code": _stt_languages(elder["language"])}
    if config.GNANI_STT_MODEL == "prisma-v3.0":
        data["model"] = "prisma-v3.0"
        terms = list(COMMON_KEYTERMS)
        terms += [m.strip() for m in (elder.get("medicines") or "").split(",") if m.strip()]
        terms += [elder["name"], elder["family_name"]]
        data["keyterms"] = json.dumps(terms[:200], ensure_ascii=False)
        data["topic"] = CHECKIN_TOPIC
        if previous_text:
            data["previous_text"] = previous_text[-600:]
    files = {"audio_file": (filename, audio)}
    r = httpx.post(
        config.GNANI_STT_URL,
        headers={"X-API-Key-ID": config.GNANI_API_KEY},
        data=data,
        files=files,
        timeout=45,
    )
    if r.status_code != 200:
        raise GnaniError(f"Prisma STT error {r.status_code}: {r.text[:300]}")
    body = r.json()
    return (body.get("transcript") or "").strip()


def synthesize(text: str, language: str, voice: str, sample_rate: int = 24000) -> str:
    """Synthesize speech, cache it under data/audio, and return the file name."""
    if not config.gnani_enabled():
        raise GnaniError("GNANI_API_KEY is not set")
    model = config.GNANI_TTS_MODEL
    if model == "timbre-v3.0" and voice not in config.TIMBRE_V3_VOICES:
        voice = config.GNANI_DEFAULT_VOICE
    key = hashlib.sha256(
        json.dumps([text, language, voice, model, sample_rate, config.GNANI_TTS_SPEED]).encode()
    ).hexdigest()[:32]
    name = f"tts_{key}.wav"
    path = config.AUDIO_DIR / name
    if path.exists():
        return name
    payload = {
        "text": text,
        "voice": voice,
        "model": model,
        "language": language,
        "speed": config.GNANI_TTS_SPEED,
        "audio_config": {
            "sample_rate": sample_rate,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    r = httpx.post(
        config.GNANI_TTS_URL,
        headers={"X-API-Key-ID": config.GNANI_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    if r.status_code != 200 or not r.content:
        raise GnaniError(f"Timbre TTS error {r.status_code}: {r.text[:300]}")
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return name


def create_voice_embedding(audio: bytes, filename: str) -> dict:
    """Gnani voice cloning, step 1: 5-30 s of clean speech -> speaker embedding (store it)."""
    if not config.gnani_enabled():
        raise GnaniError("GNANI_API_KEY is not set")
    r = httpx.post(
        config.GNANI_VC_URL,
        headers={"X-API-Key-ID": config.GNANI_API_KEY},
        files={"audio_file": (filename, audio)},
        timeout=60,
    )
    if r.status_code != 200:
        raise GnaniError(f"Voice clone error {r.status_code}: {r.text[:300]}")
    emb = (r.json().get("data") or {}).get("voice_clone_embedding")
    if not emb or not emb.get("embedding"):
        raise GnaniError("Voice clone response had no embedding")
    return {"embedding": emb["embedding"], "shape": emb.get("shape", [1, 768]), "dtype": emb.get("dtype", "torch.bfloat16")}


def synthesize_cloned(text: str, embedding: dict, sample_rate: int = 24000) -> str:
    """Gnani voice cloning, step 2: speak text in the cloned voice. Returns the cached file name."""
    if not config.gnani_enabled():
        raise GnaniError("GNANI_API_KEY is not set")
    key = hashlib.sha256(json.dumps([text, embedding["embedding"][:64], sample_rate]).encode()).hexdigest()[:32]
    name = f"vc_{key}.wav"
    path = config.AUDIO_DIR / name
    if path.exists():
        return name
    payload = {
        "text": text,
        "model": "vachana-vc-v1",
        "audio_config": {"sample_rate": sample_rate, "num_channels": 1, "sample_width": 2,
                         "encoding": "linear_pcm", "container": "wav"},
        "speaker_embedding": embedding,
    }
    r = httpx.post(
        config.GNANI_TTS_URL,
        headers={"X-API-Key-ID": config.GNANI_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    if r.status_code != 200 or not r.content:
        raise GnaniError(f"Cloned TTS error {r.status_code}: {r.text[:300]}")
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return name


def try_synthesize(text: str, language: str, voice: str, sample_rate: int = 24000) -> str | None:
    """Like synthesize(), but returns None in demo mode or on error (the call keeps going)."""
    if not config.gnani_enabled():
        return None
    try:
        return synthesize(text, language, voice, sample_rate)
    except (GnaniError, httpx.HTTPError) as e:
        log.error("TTS failed: %s", e)
        return None
