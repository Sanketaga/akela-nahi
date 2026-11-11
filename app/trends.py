"""Health trends: turns daily check-ins into a 14-day picture for the family and their doctor.

1. timeline()  : one row per day (answered / missed) with sleep, food, medicines, pain and mood,
                 taken from the structured summary of each check-in.
2. compute_stats(): plain, testable numbers: medicine adherence, pain days and streaks per body
                 part, low-mood and poor-sleep days, missed calls, this week vs last week.
3. report()    : an AI model reads the timeline + numbers and writes the trend report: a headline,
                 the trends that matter (getting worse / better / steady), what to ask on the next
                 call, and a short factual note the family can show their doctor.

Safety: the model never diagnoses or suggests medicine changes, and every claim must come from the
numbers. Without an AI key (or if the model fails) a rules-based report is built from the same
numbers, and the page says which engine wrote it.
"""
import hashlib
import json
import logging
from datetime import date, timedelta

import httpx

from . import config, db

log = logging.getLogger("akela.trends")

DAYS = 14
PAIN_KEYS = ("pain",)

# ---------------------------------------------------------------- 1. timeline


def _day(iso: str) -> date:
    return date.fromisoformat(iso[:10])


def timeline(elder_id: int, days: int = DAYS, today: date | None = None) -> list[dict]:
    """Oldest first. status: answered | missed | none."""
    today = today or db.now().date()
    start = today - timedelta(days=days - 1)
    calls = db.all_(
        "SELECT id, status, level, summary_json, started_at FROM calls WHERE elder_id=? AND kind='checkin' "
        "AND status IN ('completed','no_answer') AND started_at >= ? ORDER BY id",
        elder_id, start.isoformat(),
    )
    by_day: dict[date, dict] = {}
    for c in calls:
        d = _day(c["started_at"])
        prev = by_day.get(d)
        # keep the answered call if there was both a missed and an answered one that day
        if prev is None or (prev["status"] == "no_answer" and c["status"] == "completed") or c["status"] == prev["status"]:
            by_day[d] = c
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        c = by_day.get(d)
        row = {"date": d.isoformat(), "status": "none", "level": None, "sleep": None, "food": None,
               "medicines_taken": None, "pain": [], "mood": None}
        if c and c["status"] == "no_answer":
            row.update(status="missed", level=c["level"])
        elif c:
            s = c.get("summary") or {}
            row.update(status="answered", level=c["level"], sleep=_known(s.get("sleep")), food=_known(s.get("food")),
                       medicines_taken=s.get("medicines_taken"), pain=list(s.get("pain") or []), mood=_known(s.get("mood")))
        out.append(row)
    return out


def _known(v):
    return None if v in (None, "", "unknown") else v


# ---------------------------------------------------------------- 2. numbers


def _half_stats(rows: list[dict]) -> dict:
    answered = [r for r in rows if r["status"] == "answered"]
    meds_known = [r for r in answered if r["medicines_taken"] is not None]
    pain_days = [r for r in answered if r["pain"]]
    return {
        "days": len(rows),
        "answered": len(answered),
        "missed": sum(r["status"] == "missed" for r in rows),
        "medicines_taken": sum(r["medicines_taken"] is True for r in meds_known),
        "medicines_asked": len(meds_known),
        "pain_days": len(pain_days),
        "low_mood_days": sum(r["mood"] in ("low", "lonely") for r in answered),
        "lonely_days": sum(r["mood"] == "lonely" for r in answered),
        "poor_sleep_days": sum(r["sleep"] == "poor" for r in answered),
        "poor_food_days": sum(r["food"] == "poor" for r in answered),
        "urgent_days": sum(r["level"] == "red" for r in rows),
    }


def _pct(n: int, d: int):
    return round(100 * n / d) if d else None


def compute_stats(rows: list[dict]) -> dict:
    half = len(rows) // 2
    prev, last = _half_stats(rows[:half]), _half_stats(rows[half:])
    total = _half_stats(rows)
    for s in (prev, last, total):
        s["adherence_pct"] = _pct(s["medicines_taken"], s["medicines_asked"])

    # pain per body part: days in the window and the current streak (ending at the latest answered day)
    parts: dict[str, dict] = {}
    for r in rows:
        for p in r["pain"]:
            info = parts.setdefault(p, {"days": 0, "last_week": 0, "first": r["date"], "last": r["date"]})
            info["days"] += 1
            info["last"] = r["date"]
    for i, r in enumerate(rows[half:]):
        for p in r["pain"]:
            parts[p]["last_week"] += 1
    answered = [r for r in rows if r["status"] == "answered"]
    for p, info in parts.items():
        streak = 0
        for r in reversed(answered):
            if p in r["pain"]:
                streak += 1
            else:
                break
        info["current_streak"] = streak

    missed_streak = 0
    for r in reversed(rows):
        if r["status"] == "missed":
            missed_streak += 1
        elif r["status"] == "answered":
            break
    return {"window_days": len(rows), "previous_week": prev, "this_week": last, "total": total,
            "pain_by_part": parts, "missed_streak": missed_streak}


# ---------------------------------------------------------------- rules (always computed)


def rule_signals(stats: dict) -> list[dict]:
    """Plain-code trend flags. Used as the fallback report and given to the AI as facts."""
    out: list[dict] = []
    tw, pw = stats["this_week"], stats["previous_week"]

    def direction(now, before, higher_is_worse=True):
        if now == before:
            return "steady"
        return "worse" if (now > before) == higher_is_worse else "better"

    if tw["adherence_pct"] is not None and tw["adherence_pct"] < 80:
        out.append({"title": "Medicines being missed",
                    "detail": f"Took medicines on {tw['medicines_taken']} of {tw['medicines_asked']} days this week"
                              + (f" (last week {pw['medicines_taken']} of {pw['medicines_asked']})." if pw["medicines_asked"] else "."),
                    "direction": direction(tw["adherence_pct"], pw["adherence_pct"] or 100, higher_is_worse=False),
                    "severity": "watch"})
    for part, info in sorted(stats["pain_by_part"].items(), key=lambda kv: -kv[1]["days"]):
        if info["current_streak"] >= 3 or info["last_week"] >= 3:
            before = info["days"] - info["last_week"]
            out.append({"title": f"{part.capitalize()} keeps coming up",
                        "detail": f"Mentioned on {info['last_week']} days this week (last week {before})"
                                  + (f", {info['current_streak']} days in a row now." if info["current_streak"] >= 2 else "."),
                        "direction": direction(info["last_week"], before), "severity": "watch"})
    if tw["low_mood_days"] >= 2:
        out.append({"title": "Low or lonely more often",
                    "detail": f"Sounded low or lonely on {tw['low_mood_days']} days this week (last week {pw['low_mood_days']}).",
                    "direction": direction(tw["low_mood_days"], pw["low_mood_days"]), "severity": "watch"})
    if tw["poor_sleep_days"] >= 2:
        out.append({"title": "Sleeping badly",
                    "detail": f"Poor sleep on {tw['poor_sleep_days']} nights this week (last week {pw['poor_sleep_days']}).",
                    "direction": direction(tw["poor_sleep_days"], pw["poor_sleep_days"]), "severity": "watch"})
    if tw["missed"] >= 2 or stats["missed_streak"] >= 2:
        out.append({"title": "Missing check-ins",
                    "detail": f"Didn't answer {tw['missed']} check-ins this week.",
                    "direction": direction(tw["missed"], pw["missed"]), "severity": "watch"})
    if tw["urgent_days"]:
        out.append({"title": "Urgent alert this week", "detail": f"{tw['urgent_days']} urgent alert(s) were raised.",
                    "direction": "worse", "severity": "urgent"})
    return out


def _rules_report(elder: dict, stats: dict) -> dict:
    who = elder["family_label"]
    signals = rule_signals(stats)
    tw = stats["this_week"]
    if not tw["answered"] and not tw["missed"]:
        headline = f"Not enough check-ins yet to see a trend for {who}."
    elif not signals:
        headline = f"{who} has been steady this week: no pattern to worry about."
    else:
        n = len(signals)
        headline = f"{n} thing{'s' if n > 1 else ''} to keep an eye on for {who} this week."
    ask = []
    for s in signals:
        if s["title"].startswith("Medicines"):
            ask.append("Are the medicines running out, or is something making them hard to take?")
        elif "keeps coming up" in s["title"]:
            ask.append(f"How bad is the {s['title'].split(' keeps')[0].lower()} and has a doctor seen it?")
        elif s["title"].startswith("Low"):
            ask.append("Who have they met or talked to this week?")
        elif s["title"].startswith("Sleeping"):
            ask.append("What is keeping them up at night?")
    note = _doctor_facts(stats)
    return {"headline": headline, "trends": signals, "ask_on_call": ask[:3], "doctor_note": note}


def _doctor_facts(stats: dict) -> str:
    t = stats["total"]
    parts = [f"Over {stats['window_days']} days: {t['answered']} check-ins answered, {t['missed']} missed."]
    if t["medicines_asked"]:
        parts.append(f"Medicines reported taken on {t['medicines_taken']} of {t['medicines_asked']} days ({t['adherence_pct']}%).")
    for part, info in stats["pain_by_part"].items():
        parts.append(f"{part.capitalize()} reported on {info['days']} days ({info['first']} to {info['last']}).")
    if t["poor_sleep_days"]:
        parts.append(f"Poor sleep on {t['poor_sleep_days']} days.")
    if t["low_mood_days"]:
        parts.append(f"Low or lonely mood on {t['low_mood_days']} days.")
    parts.append("Self-reported in daily voice check-ins; not a medical assessment.")
    return " ".join(parts)


# ---------------------------------------------------------------- 3. the AI report

SYSTEM = """You are the health-trends assistant inside Akela Nahi, an app that calls an elderly parent who lives alone every morning and asks about sleep, food, medicines, pain and mood. You write a short weekly trend report for their adult child.

You get: a 14-day timeline (one row per day, oldest first) and pre-computed numbers. Rules:
- Only state things supported by the timeline or the numbers. Quote the numbers (e.g. "4 of 7 days").
- Compare this week with last week and say whether each trend is getting worse, better or steady.
- Never diagnose, never name a condition, never suggest starting, stopping or changing a medicine. When a pattern persists (e.g. the same pain for several days, medicines missed repeatedly), suggest asking their doctor.
- Notice patterns across signals (for example poor sleep on the same days as pain, or low mood after missed calls) only if the timeline actually shows it.
- Be warm and plain. No jargon, no alarmism. Write for a busy son or daughter.
- "doctor_note" is a factual, neutral summary a doctor could read in 20 seconds: dates, counts, what was self-reported. End it with "Self-reported in daily voice check-ins; not a medical assessment."
Return ONLY a JSON object, no markdown:
{"headline": string (max 20 words),
 "trends": [{"title": string (max 6 words), "detail": string (1-2 sentences with numbers), "direction": "worse"|"better"|"steady", "severity": "ok"|"watch"|"urgent"}],  (max 4, most important first)
 "ask_on_call": [string] (max 3 short questions the child can ask on their next call),
 "doctor_note": string (max 80 words)}"""


def engine() -> str:
    if config.GEMINI_API_KEY:
        return f"gemini:{config.GEMINI_MODEL}"
    if config.ANTHROPIC_API_KEY:
        return f"anthropic:{config.ANTHROPIC_MODEL}"
    return "rules"


def engine_label(name: str) -> str:
    if name.startswith("gemini:"):
        return f"Written by AI (Google {name.split(':', 1)[1]})"
    if name.startswith("anthropic:"):
        return f"Written by AI (Anthropic {name.split(':', 1)[1]})"
    return "Rules-based (add an AI key in .env for the AI-written report)"


def _user_prompt(elder: dict, rows: list[dict], stats: dict) -> str:
    lang = "Hindi (Devanagari)" if elder.get("family_language") == "hi-IN" else "English"
    payload = {
        "parent": {"called": elder["family_label"], "medicines": elder.get("medicines") or ""},
        "write_in": lang,
        "timeline": rows,
        "numbers": stats,
        "rule_flags_already_found": rule_signals(stats),
    }
    return json.dumps(payload, ensure_ascii=False)


def _call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
    }
    r = httpx.post(url, params={"key": config.GEMINI_API_KEY}, json=body, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_anthropic(prompt: str) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
        json={"model": config.ANTHROPIC_MODEL, "max_tokens": 1200, "temperature": 0.3, "system": SYSTEM,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"])


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    trends = []
    for t in (data.get("trends") or [])[:4]:
        trends.append({
            "title": str(t.get("title", ""))[:60],
            "detail": str(t.get("detail", ""))[:300],
            "direction": t.get("direction") if t.get("direction") in ("worse", "better", "steady") else "steady",
            "severity": t.get("severity") if t.get("severity") in ("ok", "watch", "urgent") else "watch",
        })
    return {
        "headline": str(data.get("headline", ""))[:160],
        "trends": trends,
        "ask_on_call": [str(q)[:160] for q in (data.get("ask_on_call") or [])[:3]],
        "doctor_note": str(data.get("doctor_note", ""))[:700],
    }


# Medicine-change / diagnosis wording the report must never contain.
_FORBIDDEN = ("increase the dose", "decrease the dose", "stop taking", "start taking", "you have ", "diagnos",
              "arthritis", "depression", "diabetes", "hypertension", "dementia")


def _safe(report: dict) -> bool:
    text = json.dumps(report, ensure_ascii=False).lower()
    return bool(report.get("headline")) and not any(f in text for f in _FORBIDDEN)


def report(elder: dict, refresh: bool = False, today: date | None = None) -> dict:
    """Timeline + numbers + the trend report (cached until the data changes)."""
    rows = timeline(elder["id"], today=today)
    stats = compute_stats(rows)
    name = engine()
    key = hashlib.sha256(json.dumps([rows, name, elder.get("family_language")], sort_keys=True).encode()).hexdigest()
    cached = db.one("SELECT * FROM trend_reports WHERE elder_id=? ORDER BY id DESC LIMIT 1", elder["id"])
    if cached and cached["data_hash"] == key and not refresh:
        rep, used = json.loads(cached["report_json"]), cached["engine"]
    else:
        rep, used = None, "rules"
        enough = stats["total"]["answered"] >= 3
        if name != "rules" and enough:
            try:
                raw = _call_gemini(_user_prompt(elder, rows, stats)) if name.startswith("gemini:") else \
                    _call_anthropic(_user_prompt(elder, rows, stats))
                candidate = _parse(raw)
                if _safe(candidate):
                    rep, used = candidate, name
                else:
                    log.warning("AI trend report failed the safety check, using rules instead")
            except Exception as e:  # network, quota, bad JSON: never break the family page
                log.error("AI trend report failed, using rules: %s", e)
        if rep is None:
            rep = _rules_report(elder, stats)
        db.execute("INSERT INTO trend_reports(elder_id, data_hash, engine, report_json, created_at) VALUES(?,?,?,?,?)",
                   elder["id"], key, used, json.dumps(rep, ensure_ascii=False), db.now_iso())
    return {"timeline": rows, "stats": stats, "report": rep, "engine": used, "engine_label": engine_label(used),
            "generated_at": db.now_iso()}
