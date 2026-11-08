"""The call engine.

Check-in: the elder app rings -> Timbre says the first line -> the elder answers -> Prisma
transcribes -> the script reacts and asks the next question -> ... -> summary, alert level,
update + Timbre voice note for the family.

Relay: the family types a message -> the elder app rings -> the message is spoken (in the family
member's cloned voice if set up) -> the elder's spoken reply goes back to the family."""
import json
import logging
from datetime import timedelta

from . import brain, config, db, gnani, safety

log = logging.getLogger("akela.conversation")

UNCLEAR = {
    "hi-IN": "माफ़ कीजिए, आवाज़ साफ़ नहीं आई। क्या आप फिर से बोल सकते हैं?",
    "en-IN": "Sorry, I couldn't hear you clearly. Could you say that again?",
    "kn-IN": "ಕ್ಷಮಿಸಿ, ಸರಿಯಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ಇನ್ನೊಮ್ಮೆ ಹೇಳುತ್ತೀರಾ?",
    "ta-IN": "மன்னிக்கவும், சரியாகக் கேட்கவில்லை. மீண்டும் சொல்ல முடியுமா?",
    "te-IN": "క్షమించండి, సరిగ్గా వినిపించలేదు. మళ్ళీ చెప్పగలరా?",
    "ml-IN": "ക്ഷമിക്കണം, വ്യക്തമായി കേട്ടില്ല. ഒന്നുകൂടി പറയാമോ?",
    "mr-IN": "माफ करा, नीट ऐकू आलं नाही. पुन्हा सांगाल का?",
    "bn-IN": "দুঃখিত, পরিষ্কার শুনতে পাইনি। আরেকবার বলবেন?",
    "gu-IN": "માફ કરશો, બરાબર સંભળાયું નહીં. ફરી કહેશો?",
    "pa-IN": "ਮਾਫ਼ ਕਰਨਾ, ਸਾਫ਼ ਸੁਣਾਈ ਨਹੀਂ ਦਿੱਤਾ। ਕੀ ਤੁਸੀਂ ਦੁਬਾਰਾ ਬੋਲ ਸਕਦੇ ਹੋ?",
}


def _speak(elder: dict, text: str, language: str | None = None) -> list[str]:
    f = gnani.try_synthesize(text, language or elder["language"], elder["voice"])
    return [f] if f else []


def _say(call_id: int, text: str, audio: list[str], ended: bool, level: str | None = None) -> dict:
    db.add_turn(call_id, "agent", text)
    return {"call_id": call_id, "text": text, "audio": audio, "ended": ended, "level": level}


def post_update(elder: dict, body: str, level: str | None = None, voice_text: str | None = None) -> None:
    """Add an update to the family page, with a Gnani Timbre voice note when possible."""
    audio = None
    if voice_text:
        audio = gnani.try_synthesize(voice_text, elder.get("family_language") or "en-IN", elder["voice"])
    db.execute("INSERT INTO updates(elder_id, level, body, audio, created_at) VALUES(?,?,?,?,?)",
               elder["id"], level, body, audio, db.now_iso())


# ---------------------------------------------------------------- starting a call

def create_call(elder_id: int, kind: str, relay_id: int | None = None) -> int:
    return db.execute("INSERT INTO calls(elder_id, kind, status, relay_id, started_at) VALUES(?,?,?,?,?)",
                      elder_id, kind, "ringing", relay_id, db.now_iso())


def _yesterday_quote(elder_id: int) -> str | None:
    """If the last check-in mentioned pain or a low mood, quote their words to follow up."""
    last = db.recent_checkins(elder_id, 1)
    if not last or not last[0].get("summary"):
        return None
    s = last[0]["summary"]
    if s.get("pain_words"):
        return s["pain_words"]
    if s.get("mood") in ("low", "lonely"):
        mood = next((a["answer"] for a in s.get("answers", []) if a["key"] == "mood"), "")
        return mood or None
    return None


def open_call(call_id: int) -> dict:
    """The elder picked up: say the first line."""
    call = db.get_call(call_id)
    elder = db.get_elder(call["elder_id"])
    db.execute("UPDATE calls SET status='in_progress' WHERE id=?", call_id)
    kw = {"name": elder["name"], "family": elder["family_name"]}

    if call["kind"] == "relay":
        relay = db.one("SELECT * FROM relays WHERE id=?", call["relay_id"])
        intro = brain.line(elder["language"], "relay_intro", **kw)
        ask = brain.line(elder["language"], "relay_ask", **kw)
        audio = _speak(elder, intro)
        voice_file = None
        if elder.get("use_family_voice") and elder.get("family_voice_embedding") and config.gnani_enabled():
            try:
                voice_file = gnani.synthesize_cloned(relay["message"], json.loads(elder["family_voice_embedding"]))
            except (gnani.GnaniError, ValueError) as e:
                log.error("Cloned voice failed, using Timbre instead: %s", e)
        audio += [voice_file] if voice_file else _speak(elder, relay["message"], "auto")
        audio += _speak(elder, ask)
        plan = [{"key": "relay_reply", "text": ask}, {"key": "relay_bye", "text": brain.line(elder["language"], "relay_bye", **kw), "final": True}]
        db.execute("UPDATE calls SET plan_json=?, step=0, answers_json='[]' WHERE id=?", json.dumps(plan, ensure_ascii=False), call_id)
        db.execute("UPDATE relays SET status='calling', attempts=attempts+1 WHERE id=?", relay["id"])
        return _say(call_id, f"{intro} “{relay['message']}” {ask}", audio, ended=False)

    questions = db.all_("SELECT * FROM questions WHERE elder_id=? AND asked_call_id IS NULL ORDER BY id", elder["id"])
    for q in questions:
        db.execute("UPDATE questions SET asked_call_id=? WHERE id=?", call_id, q["id"])
    plan = brain.plan_checkin(elder, _yesterday_quote(elder["id"]), questions)
    db.execute("UPDATE calls SET plan_json=?, step=0, answers_json='[]' WHERE id=?", json.dumps(plan, ensure_ascii=False), call_id)
    first = plan[0]["text"]
    return _say(call_id, first, _speak(elder, first), ended=False)


# ---------------------------------------------------------------- each answer

def elder_says(call_id: int, text: str) -> dict:
    call = db.get_call(call_id)
    if call is None or call["status"] != "in_progress":
        return {"call_id": call_id, "text": "", "audio": [], "ended": True, "level": call and call["level"]}
    elder = db.get_elder(call["elder_id"])
    lang = elder["language"]
    text = (text or "").strip()
    if not text:
        return unclear_audio(call_id)

    db.add_turn(call_id, "elder", text)
    plan, step, answers = call["plan"], call["step"], call["answers"] or []
    current = plan[step]
    tag = brain.classify(current["key"], text, lang)
    answers.append({"key": current["key"], "answer": text, "tag": tag, **({"question": current["question"]} if "question" in current else {})})

    # Danger words end the call at once and alert the family.
    danger = safety.red_flag_phrase(text)
    if danger:
        answers[-1]["tag"] = "urgent"  # don't also read the danger sentence as an answer to the question
        db.execute("UPDATE calls SET answers_json=?, retries=0 WHERE id=?", json.dumps(answers, ensure_ascii=False), call_id)
        raise_red_alert(elder, call_id, f'said "{danger}"', text)
        msg = brain.line(lang, "sos", family=elder["family_name"])
        result = _say(call_id, msg, _speak(elder, msg), ended=True, level="red")
        finish_call(call_id)
        return result

    # Pain without a recognised place: ask where (once).
    if current["key"] == "pain" and tag == "yes" and not brain.body_parts(text):
        plan.insert(step + 1, {"key": "pain_where", "text": brain.line(lang, "pain_where")})

    step += 1
    nxt = plan[step]
    say = nxt["text"] if current["key"] == "pain" and nxt["key"] == "pain_where" else f"{brain.reaction(current['key'], tag, lang)} {nxt['text']}"
    if current["key"] == "relay_reply":
        say = nxt["text"]
    ended = bool(nxt.get("final"))
    db.execute("UPDATE calls SET plan_json=?, step=?, answers_json=?, retries=0 WHERE id=?",
               json.dumps(plan, ensure_ascii=False), step, json.dumps(answers, ensure_ascii=False), call_id)
    result = _say(call_id, say, _speak(elder, say), ended)
    if ended:
        finish_call(call_id)
    return result


def unclear_audio(call_id: int) -> dict:
    """Nothing usable was heard: ask again, twice, then move on to the next question."""
    call = db.get_call(call_id)
    elder = db.get_elder(call["elder_id"])
    if call["retries"] >= 2:
        db.execute("UPDATE calls SET retries=0 WHERE id=?", call_id)
        return elder_says(call_id, "(no clear answer)")
    db.execute("UPDATE calls SET retries=retries+1 WHERE id=?", call_id)
    again = UNCLEAR.get(elder["language"], UNCLEAR["en-IN"])
    return _say(call_id, again, _speak(elder, again), False)


# ---------------------------------------------------------------- alerts

def raise_red_alert(elder: dict, call_id: int | None, reason: str, said: str) -> None:
    if call_id and db.one("SELECT id FROM alerts WHERE call_id=? AND level='red'", call_id):
        return
    db.execute("INSERT INTO alerts(elder_id, call_id, level, reason, created_at) VALUES(?,?,?,?,?)",
               elder["id"], call_id, "red", reason, db.now_iso())
    if call_id:
        db.execute("UPDATE calls SET level='red' WHERE id=?", call_id)
    post_update(elder,
                f"URGENT: {elder['family_label']} needs attention.\n{reason}.\n"
                + (f"They said: \"{said}\"\n" if said else "")
                + f"Please call {elder['family_label']} now. They were told to dial 108 if it is serious.",
                level="red")


def sos(elder_id: int) -> dict:
    """The elder pressed the big HELP button on their app."""
    elder = db.get_elder(elder_id)
    raise_red_alert(elder, None, "Pressed the HELP button on the Akela Nahi app", "")
    msg = brain.line(elder["language"], "sos", family=elder["family_name"])
    return {"text": msg, "audio": _speak(elder, msg)}


# ---------------------------------------------------------------- after the call

def finish_call(call_id: int) -> None:
    call = db.get_call(call_id)
    if call is None or call["status"] in ("completed", "no_answer"):
        return
    answers = call["answers"] or []
    if not answers:
        mark_no_answer(call_id)
        return
    elder = db.get_elder(call["elder_id"])
    db.execute("UPDATE calls SET status='completed', ended_at=? WHERE id=?", db.now_iso(), call_id)

    if call["kind"] == "relay":
        relay = db.one("SELECT * FROM relays WHERE id=?", call["relay_id"])
        reply = next((a["answer"] for a in answers if a["key"] == "relay_reply"), "")
        if brain.classify("msg", reply, elder["language"]) == "none":
            reply = ""
        db.execute("UPDATE relays SET status='delivered', delivered_at=?, reply_text=? WHERE id=?", db.now_iso(), reply, relay["id"])
        db.execute("UPDATE calls SET level=COALESCE(level,'green'), summary_json=? WHERE id=?",
                   json.dumps({"message_for_family": reply}, ensure_ascii=False), call_id)
        t = db.now().strftime("%I:%M %p")
        body = f"{elder['family_label']} heard your message at {t}."
        body += f"\nTheir reply: \"{reply}\"" if reply else "\nNo reply this time."
        post_update(elder, body, level="green")
        return

    summary = brain.build_summary(elder, answers)
    history = [h["summary"] for h in db.recent_checkins(elder["id"], 4) if h["id"] != call_id and h.get("summary")]
    level, reasons = safety.decide_level(summary, history, call.get("level") == "red")
    db.execute("UPDATE calls SET level=?, summary_json=? WHERE id=?", level, json.dumps(summary, ensure_ascii=False), call_id)
    if level == "red":
        return  # the urgent alert was already posted; a routine update on top would bury it
    if level == "yellow":
        for r in reasons:
            db.execute("INSERT INTO alerts(elder_id, call_id, level, reason, created_at) VALUES(?,?,?,?,?)",
                       elder["id"], call_id, "yellow", r, db.now_iso())
    lines = [summary["summary_for_family"]]
    lines += [f"Keep an eye: {r}." for r in reasons if level == "yellow"]
    for qa in summary["family_question_answers"]:
        lines.append(f"You asked: {qa['question']}  They said: \"{qa['answer']}\"")
    if summary["talk_about"]:
        lines.append("When you call, ask about: " + "; ".join(summary["talk_about"]) + ".")
    post_update(elder, "\n".join(lines), level=level, voice_text=summary["summary_for_family"])


def mark_no_answer(call_id: int) -> None:
    call = db.get_call(call_id)
    if call is None or call["status"] in ("completed", "no_answer"):
        return
    elder = db.get_elder(call["elder_id"])
    db.execute("UPDATE calls SET status='no_answer', ended_at=? WHERE id=?", db.now_iso(), call_id)
    if call["kind"] == "relay":
        relay = db.one("SELECT * FROM relays WHERE id=?", call["relay_id"])
        if relay["attempts"] < 3:
            nxt = (db.now() + timedelta(minutes=30)).isoformat(timespec="seconds")
            db.execute("UPDATE relays SET status='pending', next_attempt_at=? WHERE id=?", nxt, relay["id"])
            post_update(elder, f"{elder['family_label']} didn't pick up. Trying again in 30 minutes "
                               f"(attempt {max(relay['attempts'], 1)} of 3).")
        else:
            db.execute("UPDATE relays SET status='no_answer' WHERE id=?", relay["id"])
            post_update(elder, f"Couldn't reach {elder['family_label']} after 3 tries. Maybe give them a call?",
                        level="yellow")
        return
    streak = safety.missed_call_streak([c["status"] for c in db.recent_checkins(elder["id"], 5)])
    if streak >= 2:
        reason = f"Did not answer the check-in {streak} times in a row"
        db.execute("INSERT INTO alerts(elder_id, call_id, level, reason, created_at) VALUES(?,?,?,?,?)",
                   elder["id"], call_id, "yellow", reason, db.now_iso())
        db.execute("UPDATE calls SET level='yellow' WHERE id=?", call_id)
        post_update(elder, f"{reason}. Please check on {elder['family_label']}.", level="yellow")
    else:
        post_update(elder, f"{elder['family_label']} didn't answer today's check-in.")


def handle_family_message(elder: dict, text: str, ask_only: bool = False) -> str:
    """The family typed something on their page: deliver it now, or save it for the next check-in."""
    text = text.strip()
    if ask_only:
        db.execute("INSERT INTO questions(elder_id, question, created_at) VALUES(?,?,?)", elder["id"], text, db.now_iso())
        return "question saved for the next check-in"
    relay_id = db.execute("INSERT INTO relays(elder_id, message, status, created_at) VALUES(?,?,?,?)",
                          elder["id"], text, "pending", db.now_iso())
    create_call(elder["id"], "relay", relay_id)
    return "ringing their app now"
