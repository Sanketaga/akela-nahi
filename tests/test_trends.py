import json

from app import config, db, demo_history, trends


def _seeded(client, elder):
    r = client.post(f"/api/elders/{elder['id']}/sample-history")
    assert r.status_code == 200 and r.json()["added"] == len(demo_history.DAYS)
    return db.get_elder(elder["id"])


def test_timeline_and_numbers(client, elder):
    e = _seeded(client, elder)
    rows = trends.timeline(e["id"])
    assert len(rows) == trends.DAYS
    assert rows[-1]["status"] == "none"            # today: no check-in yet
    assert any(r["status"] == "missed" for r in rows)
    s = trends.compute_stats(rows)
    tw, pw = s["this_week"], s["previous_week"]
    assert tw["medicines_asked"] and tw["medicines_taken"] < tw["medicines_asked"]
    assert tw["adherence_pct"] < pw["adherence_pct"]
    knee = s["pain_by_part"]["knee pain"]
    assert knee["last_week"] >= 4 and knee["current_streak"] >= 3


def test_rules_report_flags_the_right_things(client, elder):
    e = _seeded(client, elder)
    out = trends.report(e)
    assert out["engine"] == "rules"
    titles = " ".join(t["title"] for t in out["report"]["trends"])
    assert "Medicines" in titles and "Knee pain" in titles and "Low or lonely" in titles
    assert "not a medical assessment" in out["report"]["doctor_note"]


def test_ai_report_is_used_when_safe(client, elder, monkeypatch):
    e = _seeded(client, elder)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test")
    seen = {}

    def fake(prompt):
        seen["prompt"] = json.loads(prompt)
        return json.dumps({"headline": "Knee pain and missed medicines are rising this week.",
                           "trends": [{"title": "Knee pain more often", "detail": "5 of 6 days this week vs 1 last week.",
                                       "direction": "worse", "severity": "watch"}],
                           "ask_on_call": ["Has the knee been seen by a doctor?"],
                           "doctor_note": "Knee pain on 6 days. Self-reported in daily voice check-ins; not a medical assessment."})
    monkeypatch.setattr(trends, "_call_gemini", fake)
    out = trends.report(e, refresh=True)
    assert out["engine"].startswith("gemini:")
    assert out["report"]["trends"][0]["direction"] == "worse"
    assert len(seen["prompt"]["timeline"]) == trends.DAYS     # the model sees the real timeline
    # cached: no second model call until the data changes
    monkeypatch.setattr(trends, "_call_gemini", lambda p: (_ for _ in ()).throw(AssertionError("called again")))
    assert trends.report(e)["engine"].startswith("gemini:")


def test_unsafe_or_broken_ai_output_falls_back_to_rules(client, elder, monkeypatch):
    e = _seeded(client, elder)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(trends, "_call_gemini", lambda p: json.dumps(
        {"headline": "He likely has arthritis", "trends": [], "ask_on_call": [], "doctor_note": "Stop taking the BP tablet."}))
    assert trends.report(e, refresh=True)["engine"] == "rules"
    monkeypatch.setattr(trends, "_call_gemini", lambda p: "not json")
    assert trends.report(e, refresh=True)["engine"] == "rules"


def test_trend_endpoints_and_doctor_report(client, elder):
    _seeded(client, elder)
    r = client.get(f"/api/elders/{elder['id']}/trends").json()
    assert r["report"]["headline"] and r["engine_label"]
    page = client.get(f"/report/{elder['id']}")
    assert page.status_code == 200 and "Summary for the doctor" in page.text
    # sample history can't be added on top of real check-ins
    assert client.post(f"/api/elders/{elder['id']}/sample-history").status_code == 400
