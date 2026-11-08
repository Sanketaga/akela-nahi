"""The conversation 'brain', in plain code (no language model).

A check-in is a short, fixed script in the elder's language. After each answer (transcribed by
Gnani Prisma) we match simple word lists to understand yes / no / good / bad / pain, react kindly,
and move on. The family always also gets the elder's exact words, so nothing is lost when a
word isn't recognised.

NOTE: the lines below were written with care but should be checked by a native speaker of the
language you demo in. Lines use the female voice form (default voice: Chetana)."""
import re
import unicodedata

# ---------------------------------------------------------------- what the caller says

LINES = {
    "hi-IN": {
        "sleep": "नमस्ते {name}! मैं अकेला नहीं से बोल रही हूँ, {family} ने मुझे आपसे बात करने के लिए कहा है। रात को नींद कैसी आई?",
        "followup": "कल आपने बताया था, \"{quote}\"। आज वो कैसा है?",
        "food": "सुबह कुछ खाया आपने?",
        "meds": "आज की दवाई ले ली?",
        "pain": "कहीं दर्द या कोई तकलीफ़ तो नहीं है?",
        "pain_where": "ओह। कहाँ तकलीफ़ है, थोड़ा बताइए?",
        "mood": "और आज मन कैसा है?",
        "question": "{family} ने पूछा है: {q}",
        "msg": "{family} के लिए कोई संदेश है? बोल दीजिए, मैं पहुँचा दूँगी।",
        "bye": "आपसे बात करके बहुत अच्छा लगा। अपना ख़याल रखिए, कल फिर बात करेंगे।",
        "ack_good": "बहुत बढ़िया।",
        "ack_bad": "अच्छा, ध्यान रखिए।",
        "ack_neutral": "अच्छा।",
        "meds_reminder": "याद से दवाई ले लीजिएगा।",
        "relay_intro": "नमस्ते {name}! {family} का संदेश है, सुनिए।",
        "relay_ask": "क्या आप {family} को कुछ कहना चाहेंगे? बोलिए।",
        "relay_bye": "ठीक है, मैं {family} तक पहुँचा दूँगी। अपना ख़याल रखिए।",
        "sos": "मैंने {family} को अभी बता दिया है। अगर तकलीफ़ ज़्यादा है तो एक सौ आठ पर फ़ोन कीजिए।",
    },
    "en-IN": {
        "sleep": "Namaste {name}! This is Akela Nahi calling, {family} asked me to check on you. How did you sleep last night?",
        "followup": "Yesterday you told me, \"{quote}\". How is it today?",
        "food": "Have you eaten something this morning?",
        "meds": "Did you take today's medicines?",
        "pain": "Any pain or discomfort anywhere?",
        "pain_where": "Oh. Where is the trouble, could you tell me a little?",
        "mood": "And how are you feeling today?",
        "question": "{family} asked: {q}",
        "msg": "Any message for {family}? Tell me and I'll pass it on.",
        "bye": "It was lovely talking to you. Take care, let's talk tomorrow.",
        "ack_good": "That's good.",
        "ack_bad": "I see, please take care.",
        "ack_neutral": "Okay.",
        "meds_reminder": "Please remember to take your medicines.",
        "relay_intro": "Namaste {name}! There's a message from {family}, please listen.",
        "relay_ask": "Would you like to say something to {family}? Please go ahead.",
        "relay_bye": "Alright, I'll pass it on to {family}. Take care.",
        "sos": "I have told {family} right now. If it is serious, please call one zero eight.",
    },
    "kn-IN": {
        "sleep": "ನಮಸ್ಕಾರ {name}! ನಾನು ಅಕೇಲಾ ನಹೀ ಇಂದ ಮಾತಾಡ್ತಾ ಇದೀನಿ, {family} ಅವರು ನಿಮ್ಮ ಜೊತೆ ಮಾತಾಡೋಕೆ ಹೇಳಿದ್ರು. ರಾತ್ರಿ ನಿದ್ದೆ ಹೇಗಿತ್ತು?",
        "followup": "ನಿನ್ನೆ ನೀವು ಹೇಳಿದ್ರಿ, \"{quote}\". ಇವತ್ತು ಹೇಗಿದೆ?",
        "food": "ಬೆಳಿಗ್ಗೆ ಏನಾದ್ರೂ ತಿಂದ್ರಾ?",
        "meds": "ಇವತ್ತಿನ ಮಾತ್ರೆ ತಗೊಂಡ್ರಾ?",
        "pain": "ಎಲ್ಲಾದ್ರೂ ನೋವು ಅಥವಾ ಏನಾದ್ರೂ ತೊಂದರೆ ಇದೆಯಾ?",
        "pain_where": "ಅಯ್ಯೋ. ಎಲ್ಲಿ ತೊಂದರೆ ಇದೆ, ಸ್ವಲ್ಪ ಹೇಳಿ?",
        "mood": "ಇವತ್ತು ಮನಸ್ಸು ಹೇಗಿದೆ?",
        "question": "{family} ಅವರು ಕೇಳಿದ್ದಾರೆ: {q}",
        "msg": "{family} ಅವರಿಗೆ ಏನಾದ್ರೂ ಸಂದೇಶ ಇದೆಯಾ? ಹೇಳಿ, ನಾನು ತಲುಪಿಸ್ತೀನಿ.",
        "bye": "ನಿಮ್ಮ ಜೊತೆ ಮಾತಾಡಿ ತುಂಬಾ ಖುಷಿ ಆಯ್ತು. ಹುಷಾರಾಗಿರಿ, ನಾಳೆ ಮತ್ತೆ ಮಾತಾಡೋಣ.",
        "ack_good": "ತುಂಬಾ ಒಳ್ಳೆಯದು.",
        "ack_bad": "ಹೌದಾ, ಹುಷಾರಾಗಿರಿ.",
        "ack_neutral": "ಸರಿ.",
        "meds_reminder": "ಮರೆಯದೆ ಮಾತ್ರೆ ತಗೊಳ್ಳಿ.",
        "relay_intro": "ನಮಸ್ಕಾರ {name}! {family} ಅವರ ಸಂದೇಶ ಇದೆ, ಕೇಳಿ.",
        "relay_ask": "{family} ಅವರಿಗೆ ಏನಾದ್ರೂ ಹೇಳಬೇಕಾ? ಹೇಳಿ.",
        "relay_bye": "ಸರಿ, ನಾನು {family} ಅವರಿಗೆ ತಲುಪಿಸ್ತೀನಿ. ಹುಷಾರಾಗಿರಿ.",
        "sos": "ನಾನು {family} ಅವರಿಗೆ ಈಗಲೇ ತಿಳಿಸಿದ್ದೀನಿ. ತೊಂದರೆ ಜಾಸ್ತಿ ಇದ್ದರೆ ನೂರ ಎಂಟು ಕರೆ ಮಾಡಿ.",
    },
    "ta-IN": {
        "sleep": "வணக்கம் {name}! நான் அகேலா நஹீ யிலிருந்து பேசுகிறேன், {family} உங்களிடம் பேசச் சொன்னார்கள். இரவு தூக்கம் எப்படி இருந்தது?",
        "followup": "நேற்று நீங்கள் சொன்னீர்கள், \"{quote}\". இன்று எப்படி இருக்கிறது?",
        "food": "காலையில் ஏதாவது சாப்பிட்டீர்களா?",
        "meds": "இன்றைய மாத்திரை எடுத்துக்கொண்டீர்களா?",
        "pain": "எங்காவது வலி அல்லது ஏதாவது சிரமம் இருக்கிறதா?",
        "pain_where": "அச்சச்சோ. எங்கே சிரமம், கொஞ்சம் சொல்லுங்கள்?",
        "mood": "இன்று மனசு எப்படி இருக்கிறது?",
        "question": "{family} கேட்டிருக்கிறார்கள்: {q}",
        "msg": "{family} க்கு ஏதாவது செய்தி இருக்கிறதா? சொல்லுங்கள், நான் சேர்த்துவிடுகிறேன்.",
        "bye": "உங்களிடம் பேசியது ரொம்ப சந்தோஷம். உடம்பைப் பார்த்துக்கொள்ளுங்கள், நாளை மறுபடி பேசலாம்.",
        "ack_good": "ரொம்ப நல்லது.",
        "ack_bad": "அப்படியா, கவனமாக இருங்கள்.",
        "ack_neutral": "சரி.",
        "meds_reminder": "மறக்காமல் மாத்திரை எடுத்துக்கொள்ளுங்கள்.",
        "relay_intro": "வணக்கம் {name}! {family} இடமிருந்து ஒரு செய்தி, கேளுங்கள்.",
        "relay_ask": "{family} க்கு ஏதாவது சொல்ல வேண்டுமா? சொல்லுங்கள்.",
        "relay_bye": "சரி, நான் {family} இடம் சொல்லிவிடுகிறேன். கவனமாக இருங்கள்.",
        "sos": "நான் {family} இடம் இப்போதே சொல்லிவிட்டேன். சிரமம் அதிகமாக இருந்தால் நூற்றி எட்டுக்கு அழையுங்கள்.",
    },
    "te-IN": {
        "sleep": "నమస్కారం {name}! నేను అకేలా నహీ నుండి మాట్లాడుతున్నాను, {family} మీతో మాట్లాడమని చెప్పారు. రాత్రి నిద్ర ఎలా పట్టింది?",
        "followup": "నిన్న మీరు చెప్పారు, \"{quote}\". ఈరోజు ఎలా ఉంది?",
        "food": "పొద్దున ఏమైనా తిన్నారా?",
        "meds": "ఈరోజు మందులు వేసుకున్నారా?",
        "pain": "ఎక్కడైనా నొప్పి లేదా ఏదైనా ఇబ్బంది ఉందా?",
        "pain_where": "అయ్యో. ఎక్కడ ఇబ్బంది ఉంది, కొంచెం చెప్పండి?",
        "mood": "ఈరోజు మనసు ఎలా ఉంది?",
        "question": "{family} అడిగారు: {q}",
        "msg": "{family} కి ఏదైనా సందేశం ఉందా? చెప్పండి, నేను అందజేస్తాను.",
        "bye": "మీతో మాట్లాడటం చాలా సంతోషంగా ఉంది. జాగ్రత్తగా ఉండండి, రేపు మళ్ళీ మాట్లాడుకుందాం.",
        "ack_good": "చాలా మంచిది.",
        "ack_bad": "అలాగా, జాగ్రత్తగా ఉండండి.",
        "ack_neutral": "సరే.",
        "meds_reminder": "మర్చిపోకుండా మందులు వేసుకోండి.",
        "relay_intro": "నమస్కారం {name}! {family} నుండి ఒక సందేశం ఉంది, వినండి.",
        "relay_ask": "{family} కి ఏమైనా చెప్పాలనుకుంటున్నారా? చెప్పండి.",
        "relay_bye": "సరే, నేను {family} కి చెప్తాను. జాగ్రత్తగా ఉండండి.",
        "sos": "నేను {family} కి ఇప్పుడే చెప్పాను. ఇబ్బంది ఎక్కువగా ఉంటే నూట ఎనిమిదికి కాల్ చేయండి.",
    },
    "mr-IN": {
        "sleep": "नमस्कार {name}! मी अकेला नहीं मधून बोलते आहे, {family} ने मला तुमच्याशी बोलायला सांगितलं आहे. रात्री झोप कशी लागली?",
        "followup": "काल तुम्ही सांगितलं होतं, \"{quote}\". आज ते कसं आहे?",
        "food": "सकाळी काही खाल्लं का?",
        "meds": "आजची औषधं घेतली का?",
        "pain": "कुठे दुखतंय किंवा काही त्रास आहे का?",
        "pain_where": "अरे. कुठे त्रास होतोय, थोडं सांगा?",
        "mood": "आज मन कसं आहे?",
        "question": "{family} ने विचारलं आहे: {q}",
        "msg": "{family} साठी काही निरोप आहे का? सांगा, मी पोहोचवते.",
        "bye": "तुमच्याशी बोलून खूप छान वाटलं. काळजी घ्या, उद्या परत बोलू.",
        "ack_good": "खूप छान.",
        "ack_bad": "अच्छा, काळजी घ्या.",
        "ack_neutral": "बरं.",
        "meds_reminder": "आठवणीने औषधं घ्या.",
        "relay_intro": "नमस्कार {name}! {family} चा निरोप आहे, ऐका.",
        "relay_ask": "{family} ला काही सांगायचं आहे का? बोला.",
        "relay_bye": "ठीक आहे, मी {family} ला सांगते. काळजी घ्या.",
        "sos": "मी {family} ला आत्ताच कळवलं आहे. त्रास जास्त असेल तर लगेच एकशे आठ ला फोन करा.",
    },
    "bn-IN": {
        "sleep": "নমস্কার {name}! আমি আকেলা নহি থেকে বলছি, {family} আমাকে আপনার সঙ্গে কথা বলতে বলেছেন। রাতে ঘুম কেমন হলো?",
        "followup": "কাল আপনি বলেছিলেন, \"{quote}\"। আজ কেমন আছে?",
        "food": "সকালে কিছু খেয়েছেন?",
        "meds": "আজকের ওষুধ খেয়েছেন?",
        "pain": "কোথাও ব্যথা বা কোনো কষ্ট আছে?",
        "pain_where": "ও। কোথায় কষ্ট হচ্ছে, একটু বলবেন?",
        "mood": "আজ মন কেমন আছে?",
        "question": "{family} জানতে চেয়েছেন: {q}",
        "msg": "{family}-এর জন্য কোনো বার্তা আছে? বলুন, আমি পৌঁছে দেব।",
        "bye": "আপনার সঙ্গে কথা বলে খুব ভালো লাগল। ভালো থাকবেন, কাল আবার কথা হবে।",
        "ack_good": "খুব ভালো।",
        "ack_bad": "আচ্ছা, সাবধানে থাকবেন।",
        "ack_neutral": "আচ্ছা।",
        "meds_reminder": "মনে করে ওষুধটা খেয়ে নেবেন।",
        "relay_intro": "নমস্কার {name}! {family}-এর একটা বার্তা আছে, শুনুন।",
        "relay_ask": "{family}-কে কিছু বলতে চান? বলুন।",
        "relay_bye": "ঠিক আছে, আমি {family}-কে জানিয়ে দেব। ভালো থাকবেন।",
        "sos": "আমি {family}-কে এখনই জানিয়েছি। কষ্ট বেশি হলে একশো আট নম্বরে ফোন করুন।",
    },
    "gu-IN": {
        "sleep": "નમસ્તે {name}! હું અકેલા નહીં માંથી બોલું છું, {family} એ મને તમારી સાથે વાત કરવા કહ્યું છે. રાત્રે ઊંઘ કેવી આવી?",
        "followup": "ગઈકાલે તમે કહ્યું હતું, \"{quote}\". આજે કેવું છે?",
        "food": "સવારે કંઈ ખાધું?",
        "meds": "આજની દવા લીધી?",
        "pain": "ક્યાંય દુખાવો કે કોઈ તકલીફ છે?",
        "pain_where": "અરે. ક્યાં તકલીફ છે, થોડું કહો?",
        "mood": "આજે મન કેવું છે?",
        "question": "{family} એ પૂછ્યું છે: {q}",
        "msg": "{family} માટે કોઈ સંદેશો છે? કહો, હું પહોંચાડી દઈશ.",
        "bye": "તમારી સાથે વાત કરીને બહુ આનંદ થયો. ધ્યાન રાખજો, કાલે ફરી વાત કરીશું.",
        "ack_good": "બહુ સરસ.",
        "ack_bad": "અચ્છા, ધ્યાન રાખજો.",
        "ack_neutral": "સારું.",
        "meds_reminder": "યાદ કરીને દવા લઈ લેજો.",
        "relay_intro": "નમસ્તે {name}! {family} નો સંદેશો છે, સાંભળો.",
        "relay_ask": "{family} ને કંઈ કહેવું છે? બોલો.",
        "relay_bye": "સારું, હું {family} ને કહી દઈશ. ધ્યાન રાખજો.",
        "sos": "મેં {family} ને હમણાં જ જાણ કરી છે. તકલીફ વધારે હોય તો એકસો આઠ પર ફોન કરો.",
    },
    "pa-IN": {
        "sleep": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ {name}! ਮੈਂ ਅਕੇਲਾ ਨਹੀਂ ਤੋਂ ਬੋਲ ਰਹੀ ਹਾਂ, {family} ਨੇ ਮੈਨੂੰ ਤੁਹਾਡੇ ਨਾਲ ਗੱਲ ਕਰਨ ਲਈ ਕਿਹਾ ਹੈ। ਰਾਤ ਨੂੰ ਨੀਂਦ ਕਿਵੇਂ ਆਈ?",
        "followup": "ਕੱਲ੍ਹ ਤੁਸੀਂ ਦੱਸਿਆ ਸੀ, \"{quote}\"। ਅੱਜ ਕਿਵੇਂ ਹੈ?",
        "food": "ਸਵੇਰੇ ਕੁਝ ਖਾਧਾ?",
        "meds": "ਅੱਜ ਦੀ ਦਵਾਈ ਲੈ ਲਈ?",
        "pain": "ਕਿਤੇ ਦਰਦ ਜਾਂ ਕੋਈ ਤਕਲੀਫ਼ ਤਾਂ ਨਹੀਂ?",
        "pain_where": "ਓਹ। ਕਿੱਥੇ ਤਕਲੀਫ਼ ਹੈ, ਥੋੜ੍ਹਾ ਦੱਸੋ?",
        "mood": "ਅੱਜ ਮਨ ਕਿਵੇਂ ਹੈ?",
        "question": "{family} ਨੇ ਪੁੱਛਿਆ ਹੈ: {q}",
        "msg": "{family} ਲਈ ਕੋਈ ਸੁਨੇਹਾ ਹੈ? ਦੱਸੋ, ਮੈਂ ਪਹੁੰਚਾ ਦਿਆਂਗੀ।",
        "bye": "ਤੁਹਾਡੇ ਨਾਲ ਗੱਲ ਕਰਕੇ ਬਹੁਤ ਚੰਗਾ ਲੱਗਾ। ਆਪਣਾ ਖ਼ਿਆਲ ਰੱਖਣਾ, ਕੱਲ੍ਹ ਫਿਰ ਗੱਲ ਕਰਾਂਗੇ।",
        "ack_good": "ਬਹੁਤ ਵਧੀਆ।",
        "ack_bad": "ਅੱਛਾ, ਧਿਆਨ ਰੱਖਣਾ।",
        "ack_neutral": "ਠੀਕ ਹੈ।",
        "meds_reminder": "ਯਾਦ ਨਾਲ ਦਵਾਈ ਲੈ ਲੈਣਾ।",
        "relay_intro": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ {name}! {family} ਦਾ ਸੁਨੇਹਾ ਹੈ, ਸੁਣੋ।",
        "relay_ask": "ਕੀ ਤੁਸੀਂ {family} ਨੂੰ ਕੁਝ ਕਹਿਣਾ ਚਾਹੋਗੇ? ਬੋਲੋ।",
        "relay_bye": "ਠੀਕ ਹੈ, ਮੈਂ {family} ਤੱਕ ਪਹੁੰਚਾ ਦਿਆਂਗੀ। ਖ਼ਿਆਲ ਰੱਖਣਾ।",
        "sos": "ਮੈਂ {family} ਨੂੰ ਹੁਣੇ ਦੱਸ ਦਿੱਤਾ ਹੈ। ਜੇ ਤਕਲੀਫ਼ ਜ਼ਿਆਦਾ ਹੈ ਤਾਂ ਇੱਕ ਸੌ ਅੱਠ ਤੇ ਫ਼ੋਨ ਕਰੋ।",
    },
    "ml-IN": {
        "sleep": "നമസ്കാരം {name}! ഞാൻ അകേലാ നഹീയിൽ നിന്നാണ് വിളിക്കുന്നത്, {family} നിങ്ങളോട് സംസാരിക്കാൻ പറഞ്ഞു. രാത്രി ഉറക്കം എങ്ങനെയുണ്ടായിരുന്നു?",
        "followup": "ഇന്നലെ നിങ്ങൾ പറഞ്ഞിരുന്നു, \"{quote}\". ഇന്ന് എങ്ങനെയുണ്ട്?",
        "food": "രാവിലെ എന്തെങ്കിലും കഴിച്ചോ?",
        "meds": "ഇന്നത്തെ മരുന്ന് കഴിച്ചോ?",
        "pain": "എവിടെയെങ്കിലും വേദനയോ എന്തെങ്കിലും ബുദ്ധിമുട്ടോ ഉണ്ടോ?",
        "pain_where": "അയ്യോ. എവിടെയാണ് ബുദ്ധിമുട്ട്, കുറച്ച് പറയാമോ?",
        "mood": "ഇന്ന് മനസ്സ് എങ്ങനെയുണ്ട്?",
        "question": "{family} ചോദിച്ചിട്ടുണ്ട്: {q}",
        "msg": "{family}ക്ക് എന്തെങ്കിലും സന്ദേശം ഉണ്ടോ? പറയൂ, ഞാൻ എത്തിക്കാം.",
        "bye": "നിങ്ങളോട് സംസാരിച്ചതിൽ വളരെ സന്തോഷം. ശ്രദ്ധിക്കണേ, നാളെ വീണ്ടും സംസാരിക്കാം.",
        "ack_good": "വളരെ നല്ലത്.",
        "ack_bad": "ആണോ, ശ്രദ്ധിക്കണേ.",
        "ack_neutral": "ശരി.",
        "meds_reminder": "മറക്കാതെ മരുന്ന് കഴിക്കണേ.",
        "relay_intro": "നമസ്കാരം {name}! {family}യുടെ ഒരു സന്ദേശമുണ്ട്, കേൾക്കൂ.",
        "relay_ask": "{family}യോട് എന്തെങ്കിലും പറയണോ? പറയൂ.",
        "relay_bye": "ശരി, ഞാൻ {family}യെ അറിയിക്കാം. ശ്രദ്ധിക്കണേ.",
        "sos": "ഞാൻ {family}യെ ഇപ്പോൾ തന്നെ അറിയിച്ചു. ബുദ്ധിമുട്ട് കൂടുതലാണെങ്കിൽ ഉടൻ നൂറ്റിയെട്ടിൽ വിളിക്കൂ.",
    },
}


def line(lang: str, key: str, **kw) -> str:
    table = LINES.get(lang, LINES["en-IN"])
    return table.get(key, LINES["en-IN"][key]).format(**kw)


# ---------------------------------------------------------------- understanding answers

# Single words are matched as whole words; entries with a space are matched as phrases.
# Every language also checks English and romanised Hindi, because elders mix them in.
WORDS = {
    "yes": {
        "hi-IN": ["हाँ", "हां", "हा", "जी", "बिल्कुल", "ले ली", "ली है", "खा लिया", "खाया", "हाँजी"],
        "en-IN": ["yes", "yeah", "yep", "done", "took", "ate", "sure", "haan", "han", "haa", "ji", "le li",
                  "kha liya", "bilkul", "haanji", "li hai"],
        "kn-IN": ["ಹೌದು", "ಹಾ", "ಹೂ", "ತಗೊಂಡೆ", "ತಿಂದೆ", "ತಗೊಂಡಿದೀನಿ", "ತಿಂದಿದೀನಿ"],
        "ta-IN": ["ஆமா", "ஆமாம்", "ஆம்", "சாப்பிட்டேன்", "எடுத்துக்கொண்டேன்", "போட்டுட்டேன்"],
        "te-IN": ["అవును", "ఆ", "తిన్నాను", "వేసుకున్నాను", "వేసుకున్నా", "తిన్నా"],
        "mr-IN": ["हो", "होय", "घेतली", "घेतलं", "घेतली आहे", "खाल्लं"],
        "bn-IN": ["হ্যাঁ", "হাঁ", "খেয়েছি", "হুম"],
        "gu-IN": ["હા", "લીધી", "ખાધું", "હાજી"],
        "pa-IN": ["ਹਾਂ", "ਜੀ", "ਲੈ ਲਈ", "ਖਾ ਲਿਆ", "ਹਾਂਜੀ"],
        "ml-IN": ["അതെ", "ഉവ്വ്", "കഴിച്ചു", "ഉം"],
    },
    "no": {
        "hi-IN": ["नहीं", "नही", "ना", "नहि", "भूल", "भूल गया", "भूल गई"],
        "en-IN": ["no", "not", "didn't", "haven't", "forgot", "nope", "nahi", "nahin", "nai", "na", "bhool"],
        "kn-IN": ["ಇಲ್ಲ", "ಇಲ್ಲಾ", "ಮರೆತೆ", "ಮರೆತುಹೋಯ್ತು"],
        "ta-IN": ["இல்லை", "இல்ல", "மறந்துட்டேன்", "மறந்துவிட்டேன்"],
        "te-IN": ["లేదు", "లేదండి", "మర్చిపోయా", "మర్చిపోయాను"],
        "mr-IN": ["नाही", "नाय", "विसरलो", "विसरले"],
        "bn-IN": ["না", "নেই", "ভুলে", "ভুলে গেছি"],
        "gu-IN": ["ના", "નથી", "ભૂલી", "ભૂલી ગયો", "ભૂલી ગઈ"],
        "pa-IN": ["ਨਹੀਂ", "ਨਾ", "ਭੁੱਲ", "ਭੁੱਲ ਗਿਆ", "ਭੁੱਲ ਗਈ"],
        "ml-IN": ["ഇല്ല", "മറന്നു", "ഇല്ലാ"],
    },
    "good": {
        "hi-IN": ["ठीक", "अच्छा", "अच्छी", "अच्छे", "बढ़िया", "मज़े", "मजे", "बहुत अच्छी"],
        "en-IN": ["good", "fine", "well", "great", "okay", "ok", "nice", "theek", "thik", "achha", "acha", "achhi",
                  "acchi", "badhiya", "mast", "maze"],
        "kn-IN": ["ಚೆನ್ನಾಗಿ", "ಚೆನ್ನಾಗಿತ್ತು", "ಚೆನ್ನಾಗಿದೆ", "ಆರಾಮ", "ಪರವಾಗಿಲ್ಲ", "ಸರಿ"],
        "ta-IN": ["நல்லா", "நன்றாக", "நல்லது", "சரி", "பரவாயில்லை"],
        "te-IN": ["బాగా", "బాగుంది", "బాగానే", "సరే", "పర్లేదు"],
        "mr-IN": ["छान", "बरं", "बरी", "ठीक", "मस्त"],
        "bn-IN": ["ভালো", "ভাল", "ঠিক", "ঠিক আছে"],
        "gu-IN": ["સારી", "સારું", "મજામાં", "બરાબર"],
        "pa-IN": ["ਵਧੀਆ", "ਠੀਕ", "ਚੰਗੀ", "ਚੰਗਾ"],
        "ml-IN": ["നന്നായി", "നല്ല", "സുഖം", "കുഴപ്പമില്ല"],
    },
    "bad": {
        "hi-IN": ["खराब", "ख़राब", "कम", "बेचैन", "बेचैनी", "उदास", "परेशान", "दर्द", "तकलीफ", "तकलीफ़", "अच्छी नहीं",
                  "ठीक नहीं", "नहीं आई"],
        "en-IN": ["bad", "poor", "not well", "sad", "tired", "terrible", "couldn't", "kharab", "kam", "udaas",
                  "pareshan", "dard", "bechain", "takleef", "achhi nahi", "theek nahi", "nahi aayi"],
        "kn-IN": ["ಸರಿಯಾಗಿ ಇಲ್ಲ", "ಬೇಜಾರು", "ಕಷ್ಟ", "ನೋವು", "ಚೆನ್ನಾಗಿಲ್ಲ"],
        "ta-IN": ["சரியில்ல", "சரியில்லை", "கஷ்டம்", "வருத்தம்", "வலி", "நல்லா இல்ல"],
        "te-IN": ["బాగాలేదు", "బాధ", "కష్టం", "నొప్పి", "బాగా లేదు"],
        "mr-IN": ["नीट नाही", "कमी", "उदास", "त्रास", "दुखतंय", "बरं नाही"],
        "bn-IN": ["ভালো না", "খারাপ", "কষ্ট", "ব্যথা", "মন খারাপ"],
        "gu-IN": ["સારી નહીં", "ખરાબ", "ઉદાસ", "દુખાવો", "તકલીફ"],
        "pa-IN": ["ਖ਼ਰਾਬ", "ਖਰਾਬ", "ਉਦਾਸ", "ਠੀਕ ਨਹੀਂ", "ਦਰਦ", "ਤਕਲੀਫ਼"],
        "ml-IN": ["മോശം", "വിഷമം", "സുഖമില്ല", "വേദന"],
    },
    "lonely": {
        "hi-IN": ["अकेला", "अकेली", "अकेलापन", "कोई नहीं"],
        "en-IN": ["lonely", "alone", "akela", "akeli", "koi nahi"],
        "kn-IN": ["ಒಬ್ಬನೇ", "ಒಬ್ಬಳೇ", "ಒಂಟಿ"],
        "ta-IN": ["தனியா", "தனிமை"],
        "te-IN": ["ఒంటరి", "ఒంటరిగా"],
        "mr-IN": ["एकटा", "एकटी", "एकटेपणा"],
        "bn-IN": ["একা", "একাকী"],
        "gu-IN": ["એકલો", "એકલી", "એકલું"],
        "pa-IN": ["ਇਕੱਲਾ", "ਇਕੱਲੀ"],
        "ml-IN": ["ഒറ്റയ്ക്ക്", "ഒറ്റപ്പെട്ട"],
    },
}

# Body parts: English label -> word stems in all languages (a word starting with the stem matches).
BODY = {
    "knee pain": ["knee", "ghutn", "ghutan", "घुटन", "घुटने", "ಮಂಡಿ", "முட்டி", "మోకాలు", "मोकाल", "गुडघ", "হাঁটু", "ઘૂંટણ", "ਗੋਡ", "മുട്ട്", "കാൽമുട്ട്"],
    "back pain": ["back", "kamar", "कमर", "ಸೊಂಟ", "ಬೆನ್ನು", "முதுகு", "నడుము", "వీపు", "पाठ", "কোমর", "પીઠ", "કમર", "ਕਮਰ", "ਪਿੱਠ", "നടുവ്"],
    "headache": ["head", "sir", "सिर", "सर", "ತಲೆ", "தலை", "తల", "डोकं", "डोके", "মাথা", "માથ", "ਸਿਰ", "തല"],
    "stomach trouble": ["stomach", "pet", "पेट", "ಹೊಟ್ಟೆ", "வயிறு", "வயித்து", "కడుపు", "पोट", "পেট", "પેટ", "ਪੇਟ", "വയറ്"],
    "leg pain": ["leg", "pair", "पैर", "टांग", "ಕಾಲು", "கால்", "కాలు", "पाय", "પગ", "ਲੱਤ", "ਪੈਰ", "കാല്"],
    "joint pain": ["joint", "jod", "जोड़", "ಕೀಲು", "மூட்டு", "కీళ్ల", "सांधे", "গাঁট", "સાંધા", "ਜੋੜ", "സന്ധി"],
    "tooth pain": ["tooth", "teeth", "daant", "दांत", "दाँत", "ಹಲ್ಲು", "பல்", "పన్ను", "दात", "দাঁত", "દાંત", "ਦੰਦ", "പല്ല്"],
    "eye trouble": ["eye", "aankh", "आँख", "आंख", "ಕಣ್ಣು", "கண்", "కన్ను", "కళ్ళు", "डोळ", "চোখ", "આંખ", "ਅੱਖ", "കണ്ണ്"],
    "fever": ["fever", "bukhar", "बुखार", "ಜ್ವರ", "காய்ச்சல்", "జ్వరం", "ताप", "জ্বর", "તાવ", "ਬੁਖ਼ਾਰ", "ਬੁਖਾਰ", "പനി"],
    "cough / cold": ["cough", "cold", "khansi", "खांसी", "खाँसी", "जुकाम", "ಕೆಮ್ಮು", "இருமல்", "దగ్గు", "खोकला", "কাশি", "ઉધરસ", "ਖੰਘ", "ചുമ"],
    "dizziness": ["dizzy", "chakkar", "चक्कर", "ತಲೆಸುತ್ತು", "மயக்கம்", "కళ్ళు తిరుగు", "चक्कर", "মাথা ঘোরা", "ચક્કર", "ਚੱਕਰ", "തലകറക്കം"],
}

BODY_HI = {
    "knee pain": "घुटने में दर्द", "back pain": "कमर दर्द", "headache": "सिर दर्द", "stomach trouble": "पेट की तकलीफ़",
    "leg pain": "पैर में दर्द", "joint pain": "जोड़ों में दर्द", "tooth pain": "दांत दर्द", "eye trouble": "आँख की तकलीफ़",
    "fever": "बुखार", "cough / cold": "खांसी-जुकाम", "dizziness": "चक्कर", "some pain": "कुछ तकलीफ़",
}

_SPLIT = re.compile(r"[\s,.!?।॥\"'“”‘’()\[\]:;-]+")


def normalise(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower().strip()


def tokens(text: str) -> list[str]:
    return [t for t in _SPLIT.split(normalise(text)) if t]


def _entries(kind: str, lang: str) -> list[str]:
    table = WORDS[kind]
    out = list(table.get(lang, []))
    for extra in ("en-IN", "hi-IN"):
        if extra != lang:
            out += table[extra]
    return out


def has(kind: str, text: str, lang: str) -> bool:
    norm = " " + " ".join(tokens(text)) + " "
    toks = set(norm.split())
    for w in _entries(kind, lang):
        w = normalise(w)
        if " " in w:
            if f" {w} " in norm:
                return True
        elif w in toks:
            return True
    return False


def body_parts(text: str) -> list[str]:
    found = []
    toks = tokens(text)
    for label, stems in BODY.items():
        for s in stems:
            s = normalise(s)
            if (" " in s and s in normalise(text)) or any(t == s or (len(s) >= 3 and t.startswith(s)) for t in toks):
                found.append(label)
                break
    return found


_NOTHING_MORE = {
    "बस", "इतना", "इतनी", "ही", "कुछ", "और", "है", "सब", "ठीक", "जी", "बेटा",
    "bas", "itna", "itni", "hi", "kuch", "aur", "hai", "sab", "theek", "thik", "ji", "beta",
    "that", "that's", "thats", "is", "all", "nothing", "else", "just", "thanks", "thank", "you",
}


def classify(key: str, text: str, lang: str) -> str:
    """Turn an answer into a simple tag. 'unknown' when unsure; the exact words are kept anyway."""
    yes, no = has("yes", text, lang), has("no", text, lang)
    good, bad = has("good", text, lang), has("bad", text, lang)
    if key == "sleep":
        if bad or (no and good):
            return "poor"
        return "good" if good or yes else "unknown"
    if key == "mood":
        if has("lonely", text, lang):
            return "lonely"
        if bad or (no and good):
            return "low"
        return "happy" if good or yes else "unknown"
    if key in ("food", "meds"):
        if no:
            return "no"
        return "yes" if yes or good else "unknown"
    if key == "pain":
        if body_parts(text):
            return "yes"
        if no or (good and not bad):
            return "no"
        return "yes" if yes or bad else "unknown"
    if key == "followup":
        if bad or (no and good):
            return "not_better"
        return "better" if good or yes else "unknown"
    if key == "msg":
        if no and len(tokens(text)) <= 3:
            return "none"
        # "No, that's all" / "नहीं, बस इतना ही" is still no message.
        if no and all(t in _NOTHING_MORE or has("no", t, lang) for t in tokens(text)):
            return "none"
        return "message"
    return "answer"


# ---------------------------------------------------------------- the call plan

def plan_checkin(elder: dict, yesterday_quote: str | None, questions: list[dict]) -> list[dict]:
    """The scripted steps for today's check-in. Each step is something to say and (except the
    last) an answer to wait for."""
    lang = elder["language"]
    kw = {"name": elder["name"], "family": elder["family_name"]}
    steps = [{"key": "sleep", "text": line(lang, "sleep", **kw)}]
    if yesterday_quote:
        steps.append({"key": "followup", "text": line(lang, "followup", quote=yesterday_quote[:120])})
    steps += [
        {"key": "food", "text": line(lang, "food")},
        {"key": "meds", "text": line(lang, "meds")},
        {"key": "pain", "text": line(lang, "pain")},
        {"key": "mood", "text": line(lang, "mood")},
    ]
    for q in questions:
        steps.append({"key": "question", "text": line(lang, "question", q=q["question"], **kw),
                      "question": q["question"]})
    steps.append({"key": "msg", "text": line(lang, "msg", **kw)})
    steps.append({"key": "bye", "text": line(lang, "bye"), "final": True})
    return steps


def reaction(key: str, tag: str, lang: str) -> str:
    """A short, kind reaction before the next question."""
    if key == "meds" and tag == "no":
        return line(lang, "meds_reminder")
    good = {("sleep", "good"), ("food", "yes"), ("meds", "yes"), ("pain", "no"), ("mood", "happy"),
            ("followup", "better")}
    bad = {("sleep", "poor"), ("food", "no"), ("mood", "low"), ("mood", "lonely"), ("followup", "not_better"),
           ("pain", "yes")}
    if (key, tag) in good:
        return line(lang, "ack_good")
    if (key, tag) in bad:
        return line(lang, "ack_bad")
    return line(lang, "ack_neutral")


# ---------------------------------------------------------------- the family's update

def build_summary(elder: dict, answers: list[dict]) -> dict:
    """Facts for the safety rules and a short update in the family's language."""
    by = {}
    for a in answers:
        by.setdefault(a["key"], a)
    tag = lambda k: by[k]["tag"] if k in by else "unknown"  # noqa: E731

    pain = []
    if tag("pain") == "yes":
        words = " ".join(a["answer"] for a in answers if a["key"] in ("pain", "pain_where"))
        pain = body_parts(words) or ["some pain"]
    pain_words = " / ".join(a["answer"] for a in answers if a["key"] in ("pain", "pain_where") and tag("pain") == "yes")

    meds = {"yes": True, "no": False}.get(tag("meds"))
    summary = {
        "sleep": tag("sleep") if tag("sleep") in ("good", "poor") else "unknown",
        "food": {"yes": "good", "no": "poor"}.get(tag("food"), "unknown"),
        "medicines_taken": meds,
        "pain": pain,
        "pain_words": pain_words,
        "mood": tag("mood") if tag("mood") in ("happy", "low", "lonely") else "unknown",
        "followup": tag("followup") if "followup" in by else None,
        "message_for_family": by["msg"]["answer"] if tag("msg") == "message" else "",
        "family_question_answers": [{"question": a.get("question", ""), "answer": a["answer"]}
                                    for a in answers if a["key"] == "question"],
        "answers": [{"key": a["key"], "answer": a["answer"], "tag": a["tag"]} for a in answers],
        "urgent": False,
        "urgent_reason": "",
        "concerns": [],
    }
    if summary["followup"] == "not_better":
        summary["concerns"].append("Yesterday's problem is not better yet")
    summary["talk_about"] = _talk_about(summary)
    summary["summary_for_family"] = family_text(elder, summary)
    return summary


def _talk_about(s: dict) -> list[str]:
    out = []
    if s["pain"]:
        out.append(f"how the {', '.join(s['pain'])} is")
    if s["mood"] in ("low", "lonely"):
        out.append("how they're feeling. A call today would mean a lot")
    if s["medicines_taken"] is False:
        out.append("whether they took their medicines later")
    return out


def family_text(elder: dict, s: dict) -> str:
    who = elder["family_label"]
    if (elder.get("family_language") or "en-IN") == "hi-IN":
        parts = []
        parts.append({"good": "नींद अच्छी आई", "poor": "नींद ठीक से नहीं आई"}.get(s["sleep"], ""))
        parts.append({"good": "खाना खा लिया", "poor": "अभी खाना नहीं खाया था"}.get(s["food"], ""))
        parts.append({True: "दवाई ले ली", False: "दवाई अभी नहीं ली थी"}.get(s["medicines_taken"], ""))
        if s["pain"]:
            parts.append(", ".join(BODY_HI.get(p, p) for p in s["pain"]) + " बताया")
        parts.append({"happy": "मन अच्छा है", "low": "मन थोड़ा उदास लगा", "lonely": "अकेलापन महसूस हो रहा है"}.get(s["mood"], ""))
        if s.get("followup") == "not_better":
            parts.append("कल वाली तकलीफ़ अभी ठीक नहीं हुई")
        text = f"{who}: " + "। ".join(p for p in parts if p) + "।"
        if s["message_for_family"]:
            text += f" आपके लिए संदेश: \"{s['message_for_family']}\""
        return text
    parts = []
    parts.append({"good": "slept well", "poor": "didn't sleep well"}.get(s["sleep"], ""))
    parts.append({"good": "has eaten", "poor": "hadn't eaten yet"}.get(s["food"], ""))
    parts.append({True: "took the medicines", False: "had NOT taken the medicines yet"}.get(s["medicines_taken"], ""))
    if s["pain"]:
        parts.append("mentioned " + ", ".join(s["pain"]))
    parts.append({"happy": "in a good mood", "low": "sounded a bit low", "lonely": "said they feel lonely"}.get(s["mood"], ""))
    if s.get("followup") == "not_better":
        parts.append("yesterday's problem isn't better yet")
    parts = [p for p in parts if p]
    text = f"{who} " + (", ".join(parts) if parts else "answered today's call") + "."
    if s["message_for_family"]:
        text += f" Message for you: \"{s['message_for_family']}\""
    return text
