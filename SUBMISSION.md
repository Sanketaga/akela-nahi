# Akela Nahi — posts and submission text

Fill in the [brackets] before posting. Attach the 60-second demo video to both posts.

---

## LinkedIn post

My parents' every phone call ends the same way: "sab theek hai, beta."

But a bad knee, a skipped BP tablet or a lonely week never comes up in a two-minute call.

So for the Great Indian AI Internship Challenge, I built **Akela Nahi** ("not alone"): a daily voice check-in for parents who live alone, in their own language.

How it works:
• Every morning, an app on the parent's phone rings. They tap one big green button.
• A warm voice asks about sleep, food, medicines, pain and mood, in Hindi or any of 10 Indian languages.
• It remembers: "Yesterday you said your knee hurts. How is it today?"
• The family gets a short summary, a spoken voice note, and what to ask when they call.
• The family can type a message. The parent hears it in their son's or daughter's own voice, and their spoken reply comes back.
• Words like chest pain, a fall or "can't breathe" end the call, tell them to dial 108, and alert the family at once. There's a big Help button too.

Built only on Gnani AI:
🎙️ Prisma v3 (speech-to-text) understands the parent's spoken answers, with their medicine and family names as hints
🔊 Timbre v3 (text-to-speech) is the caller's calm voice, slowed down for elders
🧬 Gnani voice cloning delivers family messages in the family member's own voice (with consent)

Honest note: today it's a web app that rings on the parent's phone, not a regular phone call. No call audio is stored, and the family sees the exact words only if the parent agrees. The demo uses made-up names.

It doesn't replace your call. It tells you what to ask.

Thank you @Gnani.ai for building speech models for Indian languages. 🙏

#GnaniAI #GreatIndianAIInternshipChallenge #VoiceAI #IndianLanguages #ElderCare

---

## X post (fits in 280 characters with the video attached)

Every call home ends with "sab theek hai."

I built Akela Nahi: a daily voice check-in for parents who live alone, in their language. Family gets a summary and can send messages in their own voice.

Built on @Gnani_ai Prisma v3 + Timbre v3

#GnaniAI #GreatIndianAIInternshipChallenge

(Check the exact X handle of Gnani AI before posting.)

### Optional X thread replies
2/ Every morning the app rings. A warm voice asks about sleep, food, medicines, pain and mood, and remembers yesterday: "Your knee hurt yesterday. Better today?"

3/ Type a message → your parent hears it in your cloned voice (with consent) → their spoken reply comes back to you.

4/ "Chest pain", "I fell", "can't breathe" → the call stops, tells them to dial 108, and alerts the family at once. 10 Indian languages.

5/ Gnani Prisma v3 listens, Timbre v3 speaks, Gnani voice cloning carries your voice. It doesn't replace your call. It tells you what to ask.

---

## Submission form

**Project title:** Akela Nahi

**The problem you are solving:**
Millions of Indian parents live alone while their children work in other cities. On calls they say "sab theek hai" and hide pain, missed medicines and loneliness. Families don't know what to ask, and most apps are not usable for elders who don't type or read English.

**Who will use it:**
Elderly parents living alone (they only answer and talk, in their own language), and their children or relatives living elsewhere (they read updates, send messages and get alerts).

**Gnani AI models / APIs used:**
- Prisma v3.0 speech-to-text (REST `/stt/v3`), with keyterms (medicine and family names), topic and previous-text context, in 10 Indian languages
- Timbre v3.0 text-to-speech (`/api/v1/tts/inference`), voice Chetana at 0.9× speed, for every question, reaction and the spoken family update
- Gnani voice cloning (`/api/v1/tts/voice-clone/embeddings` + `vachana-vc-v1`) to speak family messages in the family member's own voice, with consent

**Each member's contribution:** Solo project. I designed and built all of it: the call flow, the 10-language script, the safety rules, the parent's app, the family page and the Gnani integration.

**Written project explanation:**
Akela Nahi is a daily voice check-in for parents who live alone. Their app (a web app kept open on their phone) rings every morning at a set time. A calm Gnani Timbre voice asks about sleep, food, medicines, pain and mood in the parent's language; Gnani Prisma v3 transcribes each spoken answer, with their medicine and family names given as hints. Plain-code rules understand the answers in 10 languages, including romanised Hindi and English words mixed in. If yesterday's call mentioned pain or a low mood, today's call quotes their words back and asks if it's better.

After the call the family gets a short summary, a Timbre voice note and "what to ask when you call". The family can type a message: the parent's app rings, the message is spoken in the family member's own cloned voice (Gnani voice cloning, with consent), and the parent's spoken reply comes back as text.

Safety: danger phrases (chest pain, a fall, can't breathe) in all 10 languages end the call, tell the parent to dial 108 and raise an urgent alert. A big Help button does the same. Pain three days in a row, missed medicines, or two missed check-ins raise a "keep an eye" alert. It never gives medical advice.

Privacy: no call audio is stored; the family sees exact words only if the parent agreed; a cloned voice can be deleted any time. Tested end to end with real Gnani API calls on a Hindi check-in (synthetic speech); 16 automated tests. Stack: FastAPI, SQLite, plain JavaScript. Today it rings an app, not a phone line; telephony is the next step.

**Demo video:** video/akela-nahi-demo.mp4

**Nominated posts:** LinkedIn: https://www.linkedin.com/feed/update/urn:li:activity:7525267796491087872/ (X: none, the X account is suspended)
