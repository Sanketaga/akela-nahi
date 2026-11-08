"""Background loop: rings the elder app for the daily check-in, retries undelivered messages,
and marks rings nobody answered."""
import asyncio
import logging
from datetime import datetime, timedelta

from . import config, conversation, db

log = logging.getLogger("akela.scheduler")


def _busy(elder_id: int) -> bool:
    return bool(db.one("SELECT id FROM calls WHERE elder_id=? AND status IN ('ringing','in_progress')", elder_id))


def tick() -> None:
    now = db.now()
    today = now.date().isoformat()

    # 1. Daily check-in at each elder's chosen time (once per day).
    for e in db.all_("SELECT * FROM elders WHERE active=1"):
        if not e.get("call_time") or now.strftime("%H:%M") < e["call_time"] or _busy(e["id"]):
            continue
        if not db.one("SELECT id FROM calls WHERE elder_id=? AND kind='checkin' AND substr(started_at,1,10)=?", e["id"], today):
            conversation.create_call(e["id"], "checkin")
            log.info("Daily check-in ringing for elder %s", e["id"])

    # 2. Retry family messages that weren't answered.
    for r in db.all_("SELECT * FROM relays WHERE status='pending' AND next_attempt_at IS NOT NULL"):
        if r["next_attempt_at"] <= now.isoformat(timespec="seconds") and not _busy(r["elder_id"]):
            db.execute("UPDATE relays SET next_attempt_at=NULL WHERE id=?", r["id"])
            conversation.create_call(r["elder_id"], "relay", r["id"])

    # 3. Rings nobody answered.
    for c in db.all_("SELECT * FROM calls WHERE status='ringing'"):
        if now - datetime.fromisoformat(c["started_at"]) > timedelta(minutes=config.RING_MINUTES):
            conversation.mark_no_answer(c["id"])


async def run_forever(interval: int = 20) -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("scheduler tick failed")
        await asyncio.sleep(interval)
