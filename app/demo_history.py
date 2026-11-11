"""Two weeks of SYNTHETIC check-in history, so the health-trend view can be tried right away.

Week 1 is mostly fine. In week 2 the knee pain keeps coming back, medicines get missed, sleep gets
worse and the parent sounds low: the kind of slow change a two-minute phone call never catches.

    python -m app.demo_history <elder_id>      (or the "Load 2 weeks of sample check-ins" button)
"""
import json
import sys
from datetime import datetime, time, timedelta

from . import brain, db, safety

# One entry per day, oldest first: sleep, food, meds, pain (list), mood, what they said about pain, or None = missed call
DAYS = [
    ("good", "good", True, [], "happy", ""),
    ("good", "good", True, [], "happy", ""),
    ("good", "good", True, [], "happy", ""),
    ("good", "good", False, [], "happy", ""),
    ("good", "good", True, ["knee pain"], "happy", "थोड़ा घुटने में दर्द है"),
    ("good", "good", True, [], "happy", ""),
    ("poor", "good", True, [], "happy", ""),
    ("good", "good", True, ["knee pain"], "happy", "घुटना फिर से दर्द कर रहा है"),
    ("good", "good", True, [], "low", ""),
    None,
    ("poor", "good", False, ["knee pain"], "happy", "घुटने में दर्द है, सीढ़ी नहीं चढ़ पा रहा"),
    ("poor", "poor", False, ["knee pain"], "low", "घुटना बहुत दर्द कर रहा है"),
    ("poor", "good", True, ["knee pain"], "lonely", "वही घुटने का दर्द"),
    ("good", "poor", False, ["knee pain"], "low", "घुटने में दर्द अभी भी है"),
]


def _answers(sleep, food, meds, pain, mood, pain_words):
    return [
        {"key": "sleep", "answer": "हाँ, अच्छी नींद आई" if sleep == "good" else "नींद ठीक से नहीं आई", "tag": sleep},
        {"key": "food", "answer": "हाँ, खा लिया" if food == "good" else "अभी नहीं खाया", "tag": "yes" if food == "good" else "no"},
        {"key": "meds", "answer": "हाँ, दवाई ले ली" if meds else "नहीं, भूल गया", "tag": "yes" if meds else "no"},
        {"key": "pain", "answer": pain_words or "नहीं, सब ठीक है", "tag": "yes" if pain else "no"},
        {"key": "mood", "answer": {"happy": "मन अच्छा है", "low": "थोड़ा उदास हूँ", "lonely": "बहुत अकेला लगता है"}[mood], "tag": mood},
        {"key": "msg", "answer": "नहीं, कुछ नहीं", "tag": "none"},
    ]


def seed(elder_id: int, today=None) -> int:
    elder = db.get_elder(elder_id)
    if elder is None:
        raise ValueError("no such elder")
    today = today or db.now().date()
    start = today - timedelta(days=len(DAYS))  # history ends yesterday; today's real check-in comes on top
    history: list[dict] = []
    made = 0
    for i, day in enumerate(DAYS):
        d = start + timedelta(days=i)
        hh, mm = map(int, (elder.get("call_time") or "08:30").split(":"))
        started = datetime.combine(d, time(hh, mm), tzinfo=db.config.TZ)
        if day is None:
            db.execute("INSERT INTO calls(elder_id, kind, status, level, started_at, ended_at) VALUES(?,?,?,?,?,?)",
                       elder_id, "checkin", "no_answer", None, started.isoformat(timespec="seconds"),
                       (started + timedelta(minutes=10)).isoformat(timespec="seconds"))
            made += 1
            continue
        answers = _answers(*day)
        summary = brain.build_summary(elder, answers)
        level, _ = safety.decide_level(summary, history, False)
        db.execute("INSERT INTO calls(elder_id, kind, status, level, summary_json, answers_json, started_at, ended_at) "
                   "VALUES(?,?,?,?,?,?,?,?)",
                   elder_id, "checkin", "completed", level, json.dumps(summary, ensure_ascii=False),
                   json.dumps(answers, ensure_ascii=False), started.isoformat(timespec="seconds"),
                   (started + timedelta(minutes=3)).isoformat(timespec="seconds"))
        history.insert(0, summary)
        made += 1
    return made


if __name__ == "__main__":
    db.init()
    n = seed(int(sys.argv[1]))
    print(f"Added {n} days of sample check-ins.")
