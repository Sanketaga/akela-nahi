"""Safety rules. The AI extracts facts; this plain code decides the alert level,
so alerts are predictable and testable."""
import re
import unicodedata

# Danger phrases in English, romanised Hindi and native scripts. Matched as substrings
# on a normalised transcript. The LLM also flags danger, this list is the safety net.
RED_PHRASES = [
    # English
    "chest pain", "heart attack", "can't breathe", "cannot breathe", "breathless", "fainted",
    "fell down", "i fell", "unconscious", "stroke", "bleeding", "blood in", "suicide",
    "kill myself", "want to die", "paralysis", "can't move", "cannot move",
    # Romanised Hindi / Hinglish
    "seene mein dard", "seene me dard", "chhati mein dard", "chhati me dard", "saans nahi",
    "saans lene mein", "saans phool", "gir gaya", "gir gayi", "gir padi", "gir pada",
    "behosh", "chakkar aake gir", "khoon aa", "lakwa", "marna chahta", "marna chahti",
    "jeena nahi", "haath nahi hil", "pair nahi hil",
    # Hindi (Devanagari)
    "सीने में दर्द", "सीने मे दर्द", "छाती में दर्द", "छाती मे दर्द", "सांस नहीं", "साँस नहीं",
    "सांस लेने में", "साँस लेने में", "सांस फूल", "साँस फूल", "गिर गया", "गिर गई", "गिर गयी",
    "गिर पड़", "बेहोश", "खून आ", "लकवा", "मरना चाहत", "जीना नहीं",
    # Marathi
    "छातीत दुख", "श्वास घेता येत नाही", "मी पडलो", "मी पडले",
    # Kannada
    "ಎದೆ ನೋವು", "ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ", "ಕೆಳಗೆ ಬಿದ್ದೆ",
    # Tamil
    "நெஞ்சு வலி", "மூச்சு விட முடிய", "விழுந்துட்ட", "கீழே விழுந்த",
    # Telugu
    "ఛాతీ నొప్పి", "ఊపిరి ఆడ", "కింద పడ్డ",
    # Malayalam
    "നെഞ്ചുവേദന", "ശ്വാസം മുട്ട", "ഞാൻ വീണു",
    # Bengali
    "বুকে ব্যথা", "শ্বাস নিতে কষ্ট", "পড়ে গেছি",
    # Gujarati
    "છાતીમાં દુખ", "શ્વાસ લેવામાં તકલીફ", "પડી ગયો", "પડી ગઈ",
    # Punjabi
    "ਛਾਤੀ ਵਿੱਚ ਦਰਦ", "ਸਾਹ ਨਹੀਂ", "ਡਿੱਗ ਪਿਆ",
]

EMERGENCY_LINE = {
    "hi-IN": "अगर तकलीफ़ ज़्यादा है तो अभी एक सौ आठ पर फ़ोन कीजिए। मैं {family} को तुरंत बता रही हूँ।",
    "en-IN": "If it is serious, please call one zero eight right now. I am informing {family} immediately.",
    "kn-IN": "ತೊಂದರೆ ಜಾಸ್ತಿ ಇದ್ದರೆ ಈಗಲೇ ನೂರ ಎಂಟು ಕರೆ ಮಾಡಿ. ನಾನು {family} ಅವರಿಗೆ ತಕ್ಷಣ ತಿಳಿಸುತ್ತೇನೆ.",
    "ta-IN": "சிரமம் அதிகமாக இருந்தால் உடனே நூற்றி எட்டுக்கு அழையுங்கள். நான் {family} அவர்களிடம் உடனே சொல்கிறேன்.",
    "te-IN": "ఇబ్బంది ఎక్కువగా ఉంటే ఇప్పుడే నూట ఎనిమిదికి కాల్ చేయండి. నేను {family} కి వెంటనే చెబుతున్నాను.",
    "ml-IN": "ബുദ്ധിമുട്ട് കൂടുതലാണെങ്കിൽ ഉടൻ നൂറ്റിയെട്ടിൽ വിളിക്കൂ. ഞാൻ {family}നെ ഇപ്പോൾ തന്നെ അറിയിക്കുന്നു.",
    "mr-IN": "त्रास जास्त असेल तर लगेच एकशे आठ ला फोन करा. मी {family} ला लगेच कळवते.",
    "bn-IN": "কষ্ট বেশি হলে এখনই একশো আট নম্বরে ফোন করুন। আমি {family}কে এখনই জানাচ্ছি।",
    "gu-IN": "તકલીફ વધારે હોય તો હમણાં જ એકસો આઠ પર ફોન કરો. હું {family}ને તરત જાણ કરું છું.",
    "pa-IN": "ਜੇ ਤਕਲੀਫ਼ ਜ਼ਿਆਦਾ ਹੈ ਤਾਂ ਹੁਣੇ ਇੱਕ ਸੌ ਅੱਠ ਤੇ ਫ਼ੋਨ ਕਰੋ। ਮੈਂ {family} ਨੂੰ ਤੁਰੰਤ ਦੱਸ ਰਹੀ ਹਾਂ।",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower()
    return re.sub(r"\s+", " ", text)


def red_flag_phrase(text: str) -> str | None:
    """Return the danger phrase found in an elder's words, or None."""
    t = _norm(text)
    for phrase in RED_PHRASES:
        if _norm(phrase) in t:
            return phrase
    return None


def emergency_line(language: str, family_name: str) -> str:
    return EMERGENCY_LINE.get(language, EMERGENCY_LINE["en-IN"]).format(family=family_name)


def decide_level(summary: dict, history: list[dict], red_during_call: bool) -> tuple[str, list[str]]:
    """Combine today's extracted summary with recent days into green / yellow / red.

    summary: today's structured summary (see llm.SUMMARY_SCHEMA)
    history: previous check-in summaries, newest first (dicts, may be empty)
    """
    reasons: list[str] = []
    if red_during_call or summary.get("urgent"):
        why = summary.get("urgent_reason") or "danger sign mentioned during the call"
        return "red", [why]

    # Medicines missed today and on the last call too.
    if summary.get("medicines_taken") is False:
        if history and history[0].get("medicines_taken") is False:
            reasons.append("Missed medicines two check-ins in a row")
        else:
            reasons.append("Missed medicines today")

    # The same pain complaint on 3 consecutive days.
    today_pain = {p.strip().lower() for p in summary.get("pain") or [] if p.strip()}
    if today_pain:
        streak = 1
        for h in history:
            prev = {p.strip().lower() for p in h.get("pain") or []}
            if prev & today_pain:
                streak += 1
            else:
                break
        if streak >= 3:
            reasons.append(f"Pain reported {streak} days in a row: {', '.join(sorted(today_pain))}")

    # Low mood for 3 days.
    if summary.get("mood") in ("low", "sad", "lonely"):
        low_days = 1
        for h in history:
            if h.get("mood") in ("low", "sad", "lonely"):
                low_days += 1
            else:
                break
        if low_days >= 3:
            reasons.append("Sounded low or lonely 3 days in a row")
        elif summary.get("mood") == "lonely":
            reasons.append("Said they feel lonely today")

    if summary.get("sleep") == "poor":
        if history and history[0].get("sleep") == "poor":
            reasons.append("Poor sleep two nights in a row")

    for c in summary.get("concerns") or []:
        if c.strip():
            reasons.append(c.strip())

    return ("yellow" if reasons else "green"), reasons


def missed_call_streak(statuses: list[str]) -> int:
    """How many of the most recent check-ins (newest first) went unanswered."""
    n = 0
    for s in statuses:
        if s == "no_answer":
            n += 1
        else:
            break
    return n
