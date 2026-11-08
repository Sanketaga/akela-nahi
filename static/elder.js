// The parent's Akela Nahi app. Keep it open on their phone or a tablet at home.
// It rings for the daily check-in and for family messages, listens with the mic
// (Gnani Prisma), and speaks with Gnani Timbre or the family member's cloned voice.
const app = document.getElementById("app");
let STATUS = null;
let elder = null;
let state = "setup"; // setup | idle | help | ringing | incall | ended
let callId = null;
let recorder = null;
let ringTimer = null;
let ringCtx = null;
let wakeLock = null;
let clockTimer = null;
let pollTimer = null;
let callTimer = null;

// Screen words. Hindi for Hindi speakers, English otherwise (the voice itself speaks their language).
const WORDS = {
  en: {
    start: "Start", setupNote: "Keep this screen open. It rings every morning, and when your family sends a message.",
    notAdded: "Ask your family to add you on their Akela Nahi page.", notAddedNote: "This screen updates by itself once you're added.",
    whoUses: "Who uses this phone?",
    morning: "Good morning", afternoon: "Good afternoon", evening: "Good evening",
    nextCall: (t) => `Your daily call is at ${t}`,
    talkNow: "Talk now", help: "Help",
    helpSure: "Send an urgent alert to your family?", yes: "Yes, send", no: "No",
    incoming: "Incoming call", checkin: "Morning check-in", message: (n) => `Message from ${n}`,
    answer: "Answer", later: "Later",
    listening: "Listening… go ahead", speaking: "Speaking…", thinking: "One moment…",
    done: "I'm done", hangup: "End", ended: "Call ended", onCall: "On call",
  },
  hi: {
    start: "शुरू करें", setupNote: "यह स्क्रीन खुली रखें। यह हर सुबह बजेगी, और जब परिवार संदेश भेजे तब भी।",
    notAdded: "अपने परिवार से कहें कि वे आपको Akela Nahi पेज पर जोड़ें।", notAddedNote: "जुड़ते ही यह स्क्रीन अपने आप बदल जाएगी।",
    whoUses: "यह फ़ोन कौन इस्तेमाल करता है?",
    morning: "सुप्रभात", afternoon: "नमस्ते", evening: "शुभ संध्या",
    nextCall: (t) => `रोज़ की कॉल ${t} बजे`,
    talkNow: "अभी बात करें", help: "मदद",
    helpSure: "परिवार को तुरंत खबर भेजें?", yes: "हाँ, भेजें", no: "नहीं",
    incoming: "कॉल आ रही है", checkin: "सुबह का हालचाल", message: (n) => `${n} का संदेश`,
    answer: "उठाएँ", later: "बाद में",
    listening: "सुन रही हूँ… बोलिए", speaking: "बोल रही हूँ…", thinking: "एक पल…",
    done: "बोल दिया", hangup: "रखें", ended: "कॉल खत्म हुई", onCall: "कॉल चल रही है",
  },
};
const T = () => WORDS[elder && elder.language === "hi-IN" ? "hi" : "en"];

async function boot() {
  STATUS = await api("/api/status");
  const elders = await api("/api/elders");
  const want = Number(new URLSearchParams(location.search).get("elder") || localGet("akela.elderApp"));
  elder = elders.find((e) => e.id === want) || (elders.length === 1 ? elders[0] : null);
  showSetup(elders);
}

// replaceChildren would print "null" for a skipped piece, so drop those first.
function show(...kids) { app.replaceChildren(...kids.filter((k) => k !== null && k !== undefined && k !== false)); }

function localGet(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }
function localSet(k, v) { try { localStorage.setItem(k, v); } catch (_) {} }

function topBar(right) {
  return h("div", { class: "top" }, h("span", { class: "brand" }, "Akela Nahi"), h("span", {}, right || ""));
}

// One tap is needed so the browser allows sound, the microphone and keeping the screen on.
function showSetup(elders) {
  state = "setup";
  const t = T();
  const center = [h("div", { class: "greet", style: "margin-top:0" }, "Akela Nahi")];
  let sel = null;
  let actions = null;
  if (!elders.length) {
    center.push(h("p", { class: "sub", style: "margin-top:20px" }, t.notAdded), h("p", { class: "note", style: "margin-top:12px" }, t.notAddedNote));
    // Check again every few seconds, so nobody has to reload this page.
    const wait = setInterval(async () => {
      try {
        const list = await api("/api/elders");
        if (list.length) { clearInterval(wait); elder = list.length === 1 ? list[0] : null; showSetup(list); }
      } catch (_) {}
    }, 3000);
  } else {
    if (!elder || elders.length > 1) {
      sel = h("select", { "aria-label": t.whoUses }, ...elders.map((e) => h("option", { value: e.id }, e.name)));
      if (elder) sel.value = elder.id;
      center.push(h("p", { class: "sub", style: "margin-top:28px" }, t.whoUses), sel);
    }
    center.push(h("p", { class: "note", style: "margin-top:24px" }, t.setupNote));
    actions = h("div", { class: "actions" }, h("button", { class: "bigbtn light", onclick: async () => {
      if (sel) elder = elders.find((e) => e.id === Number(sel.value));
      localSet("akela.elderApp", elder.id);
      await unlock();
      showIdle();
      clearInterval(pollTimer);
      pollTimer = setInterval(poll, 2000);
    } }, T().start));
  }
  show(h("div", { class: "center" }, ...center), actions);
}

async function unlock() {
  try { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); s.getTracks().forEach((t) => t.stop()); }
  catch (e) { toast("Microphone: " + e.message); }
  // This tap also counts as the user gesture that lets the page play sound later.
  keepAwake();
  document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && keepAwake());
}

async function keepAwake() {
  try { if ("wakeLock" in navigator) wakeLock = await navigator.wakeLock.request("screen"); } catch (_) {}
}

function greeting() {
  const hr = new Date().getHours(), t = T();
  return hr < 12 ? t.morning : hr < 17 ? t.afternoon : t.evening;
}

function showIdle() {
  state = "idle";
  stopRing();
  clearInterval(callTimer);
  const t = T();
  const clock = h("div", { class: "clock" }), date = h("div", { class: "date" });
  const locale = elder.language === "hi-IN" ? "hi-IN" : undefined;
  const tick = () => {
    const d = new Date();
    clock.textContent = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).replace(/\s?[AP]M$/i, "");
    date.textContent = d.toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" });
  };
  tick();
  clearInterval(clockTimer);
  clockTimer = setInterval(tick, 10000);
  show(
    topBar(),
    h("div", { class: "center" }, clock, date,
      h("div", { class: "greet" }, `${greeting()}, ${elder.name}`),
      h("div", { class: "sub" }, t.nextCall(elder.call_time))),
    h("div", { class: "actions two" },
      h("button", { class: "bigbtn green tall", onclick: talkNow }, icon("phone"), t.talkNow),
      h("button", { class: "bigbtn red tall", onclick: confirmHelp }, icon("help"), t.help)),
  );
}

async function poll() {
  if (state !== "idle") return;
  try {
    const r = await api(`/api/elders/${elder.id}/incoming`);
    if (r.call && state === "idle") showRinging(r.call);
  } catch (_) {}
}

async function talkNow() {
  try { await api(`/api/elders/${elder.id}/call`, { method: "POST" }); } catch (e) { toast(e.message); return; }
  const r = await api(`/api/elders/${elder.id}/incoming`);
  if (r.call) answer(r.call);
}

function confirmHelp() {
  state = "help";
  const t = T();
  show(
    topBar(),
    h("div", { class: "center" }, h("div", { class: "who" }, t.helpSure)),
    h("div", { class: "actions" },
      h("button", { class: "bigbtn red", onclick: sendHelp }, icon("help"), t.yes),
      h("button", { class: "bigbtn grey", onclick: showIdle }, t.no)),
  );
}

async function sendHelp() {
  try {
    const r = await api(`/api/elders/${elder.id}/sos`, { method: "POST" });
    show(topBar(), h("div", { class: "center" }, h("div", { class: "big" }, r.text)));
    for (const f of r.audio || []) await playFile(`/audio/${f}`);
  } catch (e) { toast(e.message); }
  setTimeout(showIdle, 6000);
}

function initial(name) { return (name || "A").trim().charAt(0).toUpperCase(); }

function showRinging(call) {
  state = "ringing";
  startRing();
  const t = T();
  const relay = call.kind === "relay";
  show(
    topBar(),
    h("div", { class: "center" },
      h("div", { class: "caller ring" }, h("div", { class: "disc" }, relay ? initial(elder.family_name) : icon("phone"))),
      h("div", { class: "kicker" }, t.incoming),
      h("div", { class: "who" }, relay ? t.message(elder.family_name) : t.checkin)),
    h("div", { class: "actions" },
      h("button", { class: "bigbtn green", onclick: () => answer(call) }, icon("phone"), t.answer),
      h("button", { class: "bigbtn grey", onclick: () => decline(call) }, t.later)),
  );
  const disc = app.querySelector(".disc svg");
  if (disc) { disc.style.width = "56px"; disc.style.height = "56px"; }
}

async function decline(call) {
  stopRing();
  await api(`/api/calls/${call.id}/decline`, { method: "POST" }).catch(() => {});
  showIdle();
}

async function answer(call) {
  stopRing();
  state = "incall";
  callId = call.id;
  const t = T();
  const typing = !STATUS.gnani;
  const timer = h("span", { id: "timer" }, "0:00");
  const began = Date.now();
  clearInterval(callTimer);
  callTimer = setInterval(() => {
    const s = Math.floor((Date.now() - began) / 1000);
    timer.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 1000);
  show(
    topBar(h("span", {}, t.onCall, " · ", timer)),
    h("div", { class: "incall" },
      h("div", { class: "captions", id: "captions" }),
      h("div", { class: "now", id: "now" }),
      h("div", { class: "state", id: "state" }, h("div", { class: "bars", id: "bars" }, ...Array.from({ length: 7 }, () => h("i"))), h("span", { id: "stateText" }, t.thinking))),
    typing ? h("div", { class: "typebox" },
      h("input", { id: "typeIn", placeholder: "Demo mode: type the answer", onkeydown: (e) => e.key === "Enter" && sendTyped() }),
      h("button", { onclick: sendTyped }, "Send")) : null,
    h("div", { class: "actions two" },
      typing ? null : h("button", { class: "bigbtn grey", id: "doneBtn", onclick: () => recorder && recorder.stop() }, icon("check"), t.done),
      h("button", { class: "bigbtn red", onclick: hangup, style: typing ? "grid-column: span 2" : null }, icon("phoneOff"), t.hangup)),
  );
  try { await handleAgent(await api(`/api/calls/${callId}/answer`, { method: "POST" })); }
  catch (e) { toast(e.message); endCall(); }
}

function setStatus(text, listening) {
  const st = document.getElementById("state"), tx = document.getElementById("stateText");
  if (tx) tx.textContent = text;
  if (st) st.classList.toggle("listening", !!listening);
}

// The newest line from the caller is shown big; earlier lines move up into a small scrolling history.
function bubble(role, text) {
  const c = document.getElementById("captions"), now = document.getElementById("now");
  if (!c || !text) return;
  if (now && now.textContent) { c.append(h("div", { class: "bubble agent" }, now.textContent)); now.textContent = ""; }
  if (role === "agent" && now) now.textContent = text;
  else c.append(h("div", { class: "bubble " + role }, text));
  c.scrollTop = c.scrollHeight;
}

async function handleAgent(r) {
  bubble("agent", r.text);
  setStatus(T().speaking);
  for (const f of r.audio || []) { if (state !== "incall") return; await playFile(`/audio/${f}`); }
  if (r.ended || state !== "incall") { endCall(); return; }
  if (STATUS.gnani) listen();
  else { setStatus("Type the answer below"); const t = document.getElementById("typeIn"); if (t) t.focus(); }
}

let currentAudio = null;
function playFile(src) {
  return new Promise((resolve) => {
    const a = new Audio(src);
    currentAudio = a;
    a.onended = resolve; a.onerror = resolve;
    a.play().catch(resolve);
  });
}

function showLevel(rms) {
  const bars = document.querySelectorAll("#bars i");
  const base = Math.min(1, rms * 9);
  bars.forEach((b, i) => {
    const shape = 1 - Math.abs(i - 3) / 4;
    b.style.height = 8 + Math.round(32 * base * (0.5 + shape * 0.5) * (0.75 + Math.random() * 0.25)) + "px";
  });
}

async function listen() {
  setStatus(T().listening, true);
  recorder = new WavRecorder();
  let blob = null;
  try { blob = await recorder.start({ onLevel: showLevel }); }
  catch (e) { toast("Microphone: " + e.message); }
  recorder = null;
  showLevel(0);
  if (state !== "incall") return;
  setStatus(T().thinking);
  const fd = new FormData();
  if (blob) fd.append("audio", blob, "answer.wav"); else fd.append("text", "");
  await sendTurn(fd);
}

async function sendTyped() {
  const t = document.getElementById("typeIn");
  if (!t || !t.value.trim()) return;
  const fd = new FormData();
  fd.append("text", t.value.trim());
  t.value = "";
  setStatus(T().thinking);
  await sendTurn(fd);
}

async function sendTurn(fd) {
  try {
    const r = await api(`/api/calls/${callId}/turn`, { method: "POST", body: fd });
    if (r.heard) bubble("elder", r.heard);
    await handleAgent(r);
  } catch (e) { toast(e.message); endCall(); }
}

async function hangup() {
  state = "ended";
  if (recorder) recorder.stop();
  if (currentAudio) currentAudio.pause();
  await api(`/api/calls/${callId}/hangup`, { method: "POST" }).catch(() => {});
  endCall();
}

function endCall() {
  state = "ended";
  clearInterval(callTimer);
  setStatus(T().ended);
  const d = document.getElementById("doneBtn"); if (d) d.disabled = true;
  setTimeout(showIdle, 3500);
}

function startRing() {
  stopRing();
  try {
    ringCtx = new (window.AudioContext || window.webkitAudioContext)();
    const beep = () => {
      if (!ringCtx) return;
      [0, 0.5].forEach((t) => {
        const o = ringCtx.createOscillator(), g = ringCtx.createGain();
        o.frequency.value = 520; g.gain.value = 0.15;
        o.connect(g); g.connect(ringCtx.destination);
        o.start(ringCtx.currentTime + t); o.stop(ringCtx.currentTime + t + 0.35);
      });
    };
    beep();
    ringTimer = setInterval(beep, 2000);
  } catch (_) {}
  if (navigator.vibrate) navigator.vibrate([400, 200, 400]);
}
function stopRing() {
  clearInterval(ringTimer); ringTimer = null;
  if (ringCtx) { ringCtx.close().catch(() => {}); ringCtx = null; }
}

boot().catch((e) => toast(e.message));
