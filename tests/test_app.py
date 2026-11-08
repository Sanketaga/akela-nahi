from app import brain, safety
from tests.conftest import ELDER


# ---------------------------------------------------------------- understanding answers

def test_yes_no_in_many_languages():
    assert brain.classify("meds", "haan le li", "hi-IN") == "yes"
    assert brain.classify("meds", "नहीं, भूल गया", "hi-IN") == "no"
    assert brain.classify("meds", "ಹೌದು ತಗೊಂಡೆ", "kn-IN") == "yes"
    assert brain.classify("meds", "இல்லை", "ta-IN") == "no"
    assert brain.classify("food", "అవును తిన్నాను", "te-IN") == "yes"
    assert brain.classify("food", "नाही", "mr-IN") == "no"
    assert brain.classify("food", "something unrelated", "en-IN") == "unknown"


def test_sleep_mood_and_pain():
    assert brain.classify("sleep", "अच्छी नींद आई", "hi-IN") == "good"
    assert brain.classify("sleep", "neend achhi nahi aayi", "hi-IN") == "poor"
    assert brain.classify("mood", "bahut akela lagta hai", "hi-IN") == "lonely"
    assert brain.classify("pain", "haan ghutne mein dard hai", "hi-IN") == "yes"
    assert brain.classify("pain", "nahi, sab theek hai", "hi-IN") == "no"
    assert brain.body_parts("कमर में दर्द है") == ["back pain"]
    assert brain.body_parts("ಮಂಡಿ ನೋವು") == ["knee pain"]


def test_every_language_has_every_line():
    keys = set(brain.LINES["en-IN"])
    for lang, table in brain.LINES.items():
        assert set(table) == keys, lang
        for k, v in table.items():
            v.format(name="X", family="Y", quote="Z", q="Q")  # no broken placeholders


# ---------------------------------------------------------------- safety rules

def test_red_flags_in_many_forms():
    assert safety.red_flag_phrase("haan beta, seene mein dard ho raha hai")
    assert safety.red_flag_phrase("मुझे सीने में दर्द है")
    assert safety.red_flag_phrase("I fell in the bathroom")
    assert safety.red_flag_phrase("ಎದೆ ನೋವು ಇದೆ")
    assert safety.red_flag_phrase("sab theek hai, neend achhi aayi") is None


def test_pain_three_days_and_missed_medicine():
    level, reasons = safety.decide_level({"pain": ["knee pain"]}, [{"pain": ["knee pain"]}, {"pain": ["knee pain"]}], False)
    assert level == "yellow" and "3 days" in reasons[0]
    assert safety.decide_level({"medicines_taken": False}, [], False)[0] == "yellow"
    assert safety.decide_level({}, [], True)[0] == "red"


# ---------------------------------------------------------------- helpers

def ring_and_answer(client, elder_id):
    r = client.get(f"/api/elders/{elder_id}/incoming").json()
    assert r["call"], "the elder app should be ringing"
    first = client.post(f"/api/calls/{r['call']['id']}/answer").json()
    return r["call"]["id"], first


def say(client, call_id, text):
    r = client.post(f"/api/calls/{call_id}/turn", data={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def overview(client, elder_id):
    return client.get(f"/api/elders/{elder_id}/overview").json()


# ---------------------------------------------------------------- full flows (demo mode)

def test_daily_checkin(client, elder):
    client.post(f"/api/elders/{elder['id']}/call")
    call_id, first = ring_and_answer(client, elder["id"])
    assert "Sharma ji" in first["text"] and "Rahul" in first["text"]
    answers = ["achhi neend aayi", "haan kha liya", "haan dawai le li", "haan ghutne mein dard hai",
               "theek hai", "nahi"]
    res = None
    for a in answers:
        res = say(client, call_id, a)
    assert res["ended"]
    call = client.get(f"/api/calls/{call_id}").json()
    s = call["summary"]
    assert call["status"] == "completed" and call["level"] == "green"
    assert s["sleep"] == "good" and s["medicines_taken"] is True and s["pain"] == ["knee pain"]
    assert "slept well" in s["summary_for_family"] and "knee pain" in s["summary_for_family"]
    assert overview(client, elder["id"])["updates"][0]["body"].startswith("Papa")


def test_pain_without_place_asks_where(client, elder):
    client.post(f"/api/elders/{elder['id']}/call")
    call_id, _ = ring_and_answer(client, elder["id"])
    for a in ["theek", "haan", "haan"]:
        say(client, call_id, a)
    r = say(client, call_id, "haan thodi takleef hai")
    assert "कहाँ" in r["text"]
    r = say(client, call_id, "kamar mein")
    assert "मन" in r["text"]  # moves on to the mood question


def test_followup_quotes_yesterdays_words(client, elder):
    client.post(f"/api/elders/{elder['id']}/call")
    cid, _ = ring_and_answer(client, elder["id"])
    for a in ["theek", "haan", "haan", "ghutne mein dard hai", "theek", "nahi"]:
        say(client, cid, a)
    client.post(f"/api/elders/{elder['id']}/call")
    cid2, _ = ring_and_answer(client, elder["id"])
    r = say(client, cid2, "theek thi")
    assert "ghutne mein dard hai" in r["text"]  # "yesterday you told me ..."


def test_danger_word_ends_call_and_alerts(client, elder):
    client.post(f"/api/elders/{elder['id']}/call")
    call_id, _ = ring_and_answer(client, elder["id"])
    r = say(client, call_id, "beta seene mein dard ho raha hai")
    assert r["ended"] and r["level"] == "red" and "एक सौ आठ" in r["text"]
    ov = overview(client, elder["id"])
    assert ov["alerts"][0]["level"] == "red"
    assert ov["updates"][0]["body"].startswith("URGENT") and ov["updates"][0]["level"] == "red"


def test_help_button(client, elder):
    r = client.post(f"/api/elders/{elder['id']}/sos").json()
    assert "Rahul" in r["text"]
    assert overview(client, elder["id"])["alerts"][0]["reason"].startswith("Pressed the HELP button")


def test_family_message_and_reply(client, elder):
    client.post(f"/api/elders/{elder['id']}/family-message", json={"text": "Papa, main Sunday ko aa raha hoon"})
    call_id, first = ring_and_answer(client, elder["id"])
    assert "Sunday" in first["text"]
    r = say(client, call_id, "haan beta, main kheer banaunga")
    assert r["ended"]
    up = overview(client, elder["id"])["updates"][0]["body"]
    assert "heard your message" in up and "kheer" in up


def test_question_is_asked_and_answer_returned(client, elder):
    client.post(f"/api/elders/{elder['id']}/family-message", json={"text": "plumber aaya tha kya?", "ask_only": True})
    client.post(f"/api/elders/{elder['id']}/call")
    cid, _ = ring_and_answer(client, elder["id"])
    texts = [say(client, cid, a)["text"] for a in ["theek", "haan", "haan", "nahi", "theek"]]
    assert "plumber aaya tha kya?" in texts[-1]
    say(client, cid, "haan kal aaya tha")
    say(client, cid, "nahi")
    assert "haan kal aaya tha" in overview(client, elder["id"])["updates"][0]["body"]


def test_two_missed_calls_raise_yellow(client, elder):
    for _ in range(2):
        client.post(f"/api/elders/{elder['id']}/call")
        cid = client.get(f"/api/elders/{elder['id']}/incoming").json()["call"]["id"]
        client.post(f"/api/calls/{cid}/decline")
    ov = overview(client, elder["id"])
    assert ov["alerts"][0]["level"] == "yellow" and "2 times" in ov["alerts"][0]["reason"]


def test_words_private_without_consent(client):
    e = client.post("/api/elders", json={**ELDER, "share_transcript": False}).json()
    client.post(f"/api/elders/{e['id']}/call")
    cid, _ = ring_and_answer(client, e["id"])
    say(client, cid, "theek")
    client.post(f"/api/calls/{cid}/hangup")
    detail = client.get(f"/api/calls/{cid}").json()
    assert detail["turns"] is None and "answers" not in detail["summary"]


def test_unclear_audio_asks_again_then_moves_on(client, elder):
    client.post(f"/api/elders/{elder['id']}/call")
    cid, _ = ring_and_answer(client, elder["id"])
    assert "साफ़ नहीं" in say(client, cid, "")["text"]
    say(client, cid, "")
    r = say(client, cid, "")
    assert "खाया" in r["text"]  # gave up on the sleep question, asks about food


def test_validation(client):
    assert client.post("/api/elders", json={**ELDER, "voice": "Nalini"}).status_code == 400
    assert client.post("/api/elders", json={**ELDER, "family_language": "ta-IN"}).status_code == 400
    assert client.get("/audio/..%2F..%2Fetc%2Fpasswd").status_code == 404
