# Akela Nahi 🧓📞

**Every morning someone asks them how they are. Every evening you know.**

> **Judges:** the 1-page solution pitch is [PITCH.md](PITCH.md) · demo video: [video/akela-nahi-demo.mp4](video/akela-nahi-demo.mp4) · [LinkedIn post](https://www.linkedin.com/feed/update/urn:li:activity:7525267796491087872/)

A daily voice check-in for parents who live alone, in their own language, built only on
**Gnani AI**. Their Akela Nahi app rings every morning; a warm voice asks about sleep, food,
medicines, pain and mood, remembers what they said yesterday, and the family gets an update
with a spoken voice note. The family can also type a message, and the parent hears it read
out (in the family member's own cloned voice), then replies by speaking.

Built for the **Great Indian AI Internship Challenge** by Gnani AI.

## Gnani AI technology used

| What | Gnani model / API | Where in the code |
|---|---|---|
| Understanding the parent's spoken answers in 10 Indian languages, with English words mixed in, with their medicine names and family names as hints | **Prisma v3.0** speech-to-text (REST) | `app/gnani.py` → `transcribe()` |
| The caller's warm voice, slowed down for elders (every question, reaction, reminder) | **Timbre v3.0** text-to-speech | `app/gnani.py` → `synthesize()` |
| Family messages spoken in the son's / daughter's own voice | **Voice cloning** (`vachana-vc-v1`) | `app/gnani.py` → `create_voice_embedding()`, `synthesize_cloned()` |
| A spoken version of every family update | **Timbre v3.0** | `app/conversation.py` → `post_update()` |

No other AI service is used. Everything else is plain code:
- **The conversation** (`app/brain.py`) is a short script in all 10 languages. The parent's answers
  (from Prisma) are matched against word lists for yes / no / good / bad / lonely and body parts in every
  language. The family always sees the parent's exact words too, so nothing is lost if a word isn't recognised.
- **Safety** (`app/safety.py`): danger phrases in 10 languages (chest pain, fall, breathing…) end the call,
  tell the parent to dial 108 and raise an urgent alert at once. Pain 3 days in a row, missed medicines and
  2 missed check-ins raise a yellow alert. It never diagnoses or gives medical advice.
- **Memory**: if yesterday's call mentioned pain or a low mood, today's call quotes their words back
  ("Yesterday you told me ‘my knee hurts’. How is it today?").
- **Help button**: one big button on the parent's app sends an urgent alert.

## Run it

First time only:
```bash
python -m venv .venv
```
```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

1. Copy `.env.example` to `.env` and put your Gnani key in `GNANI_API_KEY=` (from https://app.gnani.ai/voice).
   Without a key it runs in **demo mode**: you type the parent's answers instead of speaking.
2. Double-click **`start.bat`** and open http://localhost:8000. That's the **family page**.
3. Click **＋ Add parent**, then **📱 Elder's app** to open the parent's app in another tab.

### On real phones (same Wi-Fi)
Phones only allow the microphone on **https** pages, so:
1. Double-click **`start_https.bat`**. It prints two addresses like `https://192.168.0.192:8443/elder`.
2. On the parent's phone open the `/elder` address. Chrome warns the certificate isn't trusted
   (it's one we made ourselves): tap **Advanced → Proceed**. Then tap **Start Akela Nahi** and allow the microphone.
3. On your phone open the `/family` address the same way.
4. If Windows asks whether Python may use the network, allow it on **Private networks**.

Keep the parent's app open (screen on, plugged in). It rings at the daily time, and whenever you send a message.

Run the tests:
```bash
.venv\Scripts\python -m pytest -q
```

## Saving your 5,000 Gnani credits
- Every spoken line is saved in `data/audio` and reused, so the same questions don't cost credits again.
- Each answer is one short Prisma request (up to 25 seconds).
- Test in demo mode (no key) while changing things; turn the key on for real runs and the video.

## Before you record the demo
- **Have a native speaker check the lines** for the language you demo in (`app/brain.py → LINES`).
  They're written for a female voice (default Timbre voice: Chetana).
- Use made-up names and no real phone numbers on screen (contest rule). Get the elder's consent to film.
- Be honest in the post: it's a web app that rings on the parent's phone, not a regular phone call.

### Suggested 60-second video
| Time | Shot |
|---|---|
| 0–6 s | "My grandparents live 800 km away. Every call: *'sab theek hai.'*" |
| 6–25 s | The app rings on Dadi's phone, she answers and talks in her language. It remembers yesterday's knee pain. |
| 25–35 s | Your phone shows the update and plays the Gnani voice note: "ask about her knee". |
| 35–45 s | You type a message → her app rings → she hears it **in your voice** → her spoken reply appears on your phone. |
| 45–55 s | She presses Help → urgent alert on your phone. |
| 55–60 s | "It doesn't replace your call. It tells you what to ask." Prisma v3 · Timbre v3 · Gnani voice cloning. |

## Privacy
- No call audio is stored, only text. The family sees the parent's exact words only if the parent agreed.
- Voice cloning only with the family member's own voice and a consent tick; deletable any time.
- Set `DASHBOARD_PASSWORD` in `.env` if other people can reach your laptop (username: `family`).

## Project layout
```
app/brain.py         the call script in 10 languages + understanding answers (no AI model)
app/conversation.py  the call engine (ring → answer → questions → update for the family)
app/gnani.py         Gnani Prisma STT, Timbre TTS, voice cloning
app/safety.py        alert rules
app/scheduler.py     daily ring, message retries, missed calls
app/main.py          web server and API
static/elder.html    the parent's app
static/family.html   the family page
tests/               automated tests (16)
```
