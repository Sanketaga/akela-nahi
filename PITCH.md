# Akela Nahi: one-page solution pitch

**Every morning someone asks how they are. Every evening you know.**
Built solo by Sanket Agrawal for the Great Indian AI Internship Challenge, only on Gnani AI.

## The problem
Millions of Indian parents live alone while their children work in other cities. On the phone they say *"sab theek hai, beta"* and hide the knee pain, the skipped BP tablet, the lonely week. Families don't know what to ask, and most apps don't work for elders who don't type or read English.

## The solution
A daily voice check-in for the parent, in their own language, with a page for the family.

- **The parent's app rings every morning** (a web app kept open on their phone). One big button to answer.
- **A calm voice asks about sleep, food, medicines, pain and mood** in Hindi or 9 other Indian languages, and **remembers yesterday**: "Yesterday you said your knee hurts. How is it today?"
- **The family gets an update** with a spoken voice note and **"When you call, ask about…"**.
- **Family messages:** the son or daughter types a message; the parent's app rings and reads it out (optionally in the family member's own cloned voice, with consent); the parent's spoken reply comes back as text.
- **Safety:** "chest pain", "I fell", "can't breathe" (in all 10 languages) end the call, tell the parent to dial 108 and alert the family at once. A big Help button does the same. Pain three days running, missed medicines, or two missed calls raise a "keep an eye" alert. It never gives medical advice.

## Gnani AI models and APIs used
| Gnani AI | What it does in Akela Nahi |
|---|---|
| **Prisma v3.0** speech-to-text API | Understands the parent's spoken answers in 10 languages, with their medicine and family names as key-term hints and the question as context |
| **Timbre v3.0** text-to-speech API | The caller's voice at 0.9× speed for elders; a spoken voice note of every family update |
| **Voice cloning API** (`vachana-vc-v1`) | Family messages read out in the family member's own voice, with consent |

No other AI service is used. The conversation and the safety rules are plain, testable code.

## Proof it works
- End-to-end Hindi check-in run through real Gnani calls: Prisma transcribed the spoken answers word for word; all answers (sleep, food, medicine not taken, knee pain, mood, "no message") were understood; the update and voice note were produced.
- Message relay and the Help alert tested end to end; 16 automated tests pass.
- Demo video: real screens of the running app, Hindi narration by Gnani Timbre.

## Privacy and dignity
No call audio is stored. The family sees exact words only if the parent agreed. Voice cloning needs a consent tick and can be deleted. All demo data is synthetic (made-up names; the parent's answers are Gnani-generated speech).

## Next
A real phone call (so a basic phone works), native-speaker review of every line, updates to the family WhatsApp group, and a small pilot with consenting families.

*Stack: FastAPI, SQLite, plain JavaScript. Run: see README.md.*
