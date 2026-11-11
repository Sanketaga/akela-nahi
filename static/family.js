let STATUS = null;
let ELDERS = [];
let current = null;
let editingId = null;
let lastUpdateId = null;
const $ = (id) => document.getElementById(id);

function lsGet(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }
function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (_) {} }

async function boot() {
  STATUS = await api("/api/status");
  $("engine").replaceChildren(h("span", { class: "dot" + (STATUS.gnani ? " on" : "") }),
    STATUS.gnani ? "Voice by Gnani AI: Prisma v3 listens, Timbre v3 speaks" : "Demo mode: no Gnani key, answers are typed");
  fillSelect($("f_language"), STATUS.languages);
  fillSelect($("f_family_language"), STATUS.family_languages);
  $("f_voice").replaceChildren(...STATUS.voices.map((v) => h("option", { value: v }, v)));
  updateNotifyBtn();
  await loadElders();
  setInterval(() => current && loadOverview(), 4000);
}

function fillSelect(sel, map) {
  sel.replaceChildren(...Object.entries(map).map(([code, name]) => h("option", { value: code }, name)));
}

async function loadElders(selectId) {
  ELDERS = await api("/api/elders");
  const has = ELDERS.length > 0;
  $("noElders").hidden = has;
  $("main").hidden = !has;
  $("elderSelect").replaceChildren(...ELDERS.map((e) => h("option", { value: e.id }, e.family_label === e.name ? e.name : `${e.family_label} (${e.name})`)));
  if (!has) { current = null; return; }
  const saved = Number(lsGet("akela.elder"));
  current = selectId || (ELDERS.some((e) => e.id === current) ? current : ELDERS.some((e) => e.id === saved) ? saved : ELDERS[0].id);
  $("elderSelect").value = current;
  lastUpdateId = null;
  await loadOverview();
}

async function loadOverview() {
  const data = await api(`/api/elders/${current}/overview`);
  const e = data.elder;
  document.querySelectorAll(".lbl").forEach((n) => (n.textContent = e.family_label));
  $("langName").textContent = STATUS.languages[e.language];
  $("voiceNote").textContent = e.has_family_voice && e.use_family_voice ? " in your own cloned voice" : " by Gnani Timbre";
  $("elderLink").href = `/elder?elder=${e.id}`;
  renderHero(e, data.calls);
  renderToday(e, data.calls);
  renderAlerts(data.alerts);
  renderHistory(data.calls);
  renderUpdates(e, data.updates);
  renderQuestions(data.questions);
  loadTrends();
}

// ---------------------------------------------------------------- health trends
let lastTrends = "";
async function loadTrends(refresh) {
  const id = current;
  const t = await api(`/api/elders/${id}/trends${refresh ? "?refresh=1" : ""}`);
  if (id !== current) return;
  const key = JSON.stringify([id, t.timeline, t.report, t.engine]);
  if (key === lastTrends && !refresh) return;
  lastTrends = key;
  renderTrends(t);
}

const CELL = {
  medicines_taken: (v) => v === true ? ["ok", "Taken"] : v === false ? ["bad", "Missed"] : ["unk", "Not clear"],
  sleep: (v) => v === "good" ? ["ok", "Slept well"] : v === "poor" ? ["bad", "Slept badly"] : ["unk", "Not clear"],
  food: (v) => v === "good" ? ["ok", "Ate"] : v === "poor" ? ["bad", "Not eaten"] : ["unk", "Not clear"],
  pain: (v) => v && v.length ? ["bad", v.join(", ")] : ["ok", "No pain"],
  mood: (v) => v === "happy" ? ["ok", "Good mood"] : v === "low" ? ["bad", "Low"] : v === "lonely" ? ["bad", "Lonely"] : ["unk", "Not clear"],
};
const ARROW = { worse: "↑ worse", better: "↓ better", steady: "→ steady" };

function renderTrends(t) {
  $("doctorBtn").href = `/report/${current}`;
  const answered = t.stats.total.answered;
  const kids = [];
  if (answered < 3) {
    kids.push(h("p", { class: "empty" }, "Trends appear after a few days of check-ins: missed medicines, pain that keeps coming back, sleep and mood, compared week by week."));
    if (answered === 0) kids.push(h("div", { class: "row", style: "margin-top:12px" },
      h("button", { onclick: loadSample }, "Load 2 weeks of sample check-ins"),
      h("span", { class: "muted small" }, "synthetic data, to try the view")));
    $("trendsBody").replaceChildren(...kids);
    return;
  }
  const r = t.report;
  kids.push(h("p", { class: "t-headline" }, r.headline));

  // the 14-day grid
  const days = t.timeline;
  const grid = h("div", { class: "t-grid", style: `grid-template-columns: 92px repeat(${days.length}, 1fr)` });
  grid.append(h("div"));
  days.forEach((d) => {
    const dt = new Date(d.date + "T12:00:00");
    grid.append(h("div", { class: "t-day" }, dt.toLocaleDateString(undefined, { weekday: "narrow" }), h("span", {}, String(dt.getDate()))));
  });
  for (const [key, label] of [["medicines_taken", "Medicines"], ["pain", "Pain"], ["sleep", "Sleep"], ["mood", "Mood"], ["food", "Food"]]) {
    grid.append(h("div", { class: "t-label" }, label));
    days.forEach((d) => {
      if (d.status === "missed") { grid.append(h("div", { class: "t-cell missed", title: `${d.date}: didn't answer` })); return; }
      if (d.status === "none") { grid.append(h("div", { class: "t-cell none", title: `${d.date}: no check-in` })); return; }
      const [cls, text] = CELL[key](d[key]);
      grid.append(h("div", { class: "t-cell " + cls, title: `${d.date}: ${text}` }));
    });
  }
  kids.push(grid);
  kids.push(h("div", { class: "t-legend small muted" },
    h("span", { class: "t-cell ok" }), "fine", h("span", { class: "t-cell bad" }), "a problem",
    h("span", { class: "t-cell unk" }), "not clear", h("span", { class: "t-cell missed" }), "missed call"));

  if (r.trends.length) {
    kids.push(h("ul", { class: "clean t-list" }, ...r.trends.map((x) => h("li", {},
      h("div", { class: "row" }, h("b", {}, x.title), h("span", { class: "t-dir " + x.direction }, ARROW[x.direction] || x.direction)),
      h("div", { class: "small" }, x.detail)))));
  }
  if (r.ask_on_call.length) kids.push(h("div", { class: "ask-about" }, h("b", {}, "On your next call, ask"), r.ask_on_call.join(" · ")));
  kids.push(h("div", { class: "row t-foot" },
    h("span", { class: "engine-tag " + (t.engine === "rules" ? "" : "ai") }, t.engine_label),
    h("span", { class: "spacer" }),
    h("button", { class: "ghost", onclick: () => loadTrends(true).then(() => toast("Trend report updated")) }, "Refresh")));
  $("trendsBody").replaceChildren(...kids);
}

async function loadSample() {
  await api(`/api/elders/${current}/sample-history`, { method: "POST" });
  toast("Added 2 weeks of sample check-ins");
  lastTrends = "";
  loadOverview();
}

function lastCheckin(calls) { return calls.find((c) => c.kind === "checkin" && (c.status === "completed" || c.status === "no_answer")); }

function renderHero(e, calls) {
  const last = lastCheckin(calls);
  $("heroEyebrow").textContent = `${e.name !== e.family_label ? e.name + " · " : ""}${STATUS.languages[e.language]} · daily at ${e.call_time}`;
  $("heroName").textContent = e.family_label;
  const line = [levelBadge(last && last.level)];
  if (last) line.push(h("span", { class: "muted" }, last.status === "no_answer" ? `missed the call, ${fmtTime(last.started_at)}` : `checked in ${fmtTime(last.started_at)}`));
  else line.push(h("span", { class: "muted" }, "waiting for the first check-in"));
  $("heroStatus").replaceChildren(...line);
}

function renderToday(e, calls) {
  const last = lastCheckin(calls);
  const live = calls.find((c) => c.status === "ringing" || c.status === "in_progress");
  const kids = [];
  if (live) kids.push(h("div", { class: "live" }, live.status === "ringing" ? `Ringing ${e.family_label}'s app` : `${e.family_label} is on the call now`));
  kids.push(h("div", { class: "panel-head" }, h("h2", {}, "Latest check-in"), h("span", { class: "spacer" }),
    last && last.status === "completed" ? h("button", { class: "ghost", onclick: () => openCall(last.id) }, "Full call") : null));
  if (!last) {
    kids.push(h("p", { class: "empty-today" }, `Nothing yet. Their app rings at ${e.call_time} every day, or press “Ring for a check-in” to try it now.`));
  } else if (last.status === "no_answer") {
    kids.push(h("p", { class: "empty-today" }, `${e.family_label} didn't pick up on ${fmtTime(last.started_at)}. It's worth giving them a call yourself.`));
  } else {
    const s = last.summary || {};
    const med = s.medicines_taken === true ? "Taken" : s.medicines_taken === false ? "Not yet" : "–";
    const pain = (s.pain || []).length ? s.pain.join(", ") : "None mentioned";
    kids.push(h("p", { class: "when" }, fmtTime(last.started_at)));
    if (s.summary_for_family) kids.push(h("p", { class: "lead" }, s.summary_for_family));
    const say = (map, v) => map[v] || "Not clear";
    kids.push(h("dl", { class: "facts" },
      fact("Sleep", say({ good: "Slept well", poor: "Slept badly" }, s.sleep), s.sleep === "poor"),
      fact("Food", say({ good: "Has eaten", poor: "Not yet" }, s.food), s.food === "poor"),
      fact("Medicines", med, s.medicines_taken === false),
      fact("Pain", pain, (s.pain || []).length > 0),
      fact("Mood", say({ happy: "Good", low: "A bit low", lonely: "Lonely" }, s.mood), s.mood === "low" || s.mood === "lonely")));
    if ((s.talk_about || []).length) kids.push(h("div", { class: "ask-about" }, h("b", {}, "When you call, ask about"), s.talk_about.join("; ")));
  }
  $("todayCard").replaceChildren(...kids);
}

function fact(label, val, bad) { return h("div", { class: "fact" }, h("dt", {}, label), h("dd", { class: bad ? "bad" : null }, val || "–")); }

function renderAlerts(alerts) {
  const ul = $("alerts");
  // An alert from the last day also goes at the top of the page.
  const fresh = alerts.find((a) => a.level !== "green" && Date.now() - new Date(a.created_at) < 24 * 3600 * 1000);
  $("alertStrip").replaceChildren(...(fresh ? [h("div", { class: "alert-strip " + fresh.level, role: "alert" },
    h("b", {}, fresh.level === "red" ? "Urgent" : "Keep an eye"), h("span", {}, fresh.reason), h("span", { class: "when" }, fmtTime(fresh.created_at)))] : []));
  if (!alerts.length) { ul.replaceChildren(h("li", { class: "empty" }, "No alerts so far.")); return; }
  ul.replaceChildren(...alerts.map((a) => h("li", {}, levelBadge(a.level), h("div", {}, a.reason), h("div", { class: "muted small" }, fmtTime(a.created_at)))));
}

function renderHistory(calls) {
  const ul = $("history");
  if (!calls.length) { ul.replaceChildren(h("li", { class: "empty" }, "No calls yet.")); return; }
  ul.replaceChildren(...calls.map((c) => {
    const s = c.summary || {};
    const status = c.status === "completed" ? levelBadge(c.level) : h("span", { class: "tag" }, c.status.replace("_", " "));
    const sum = s.summary_for_family || (s.message_for_family ? `Reply: “${s.message_for_family}”` : "");
    return h("li", { tabindex: 0, onclick: () => openCall(c.id), onkeydown: (ev) => ev.key === "Enter" && openCall(c.id) },
      h("div", { class: "h-time" }, fmtTime(c.started_at)),
      h("div", { class: "h-what" }, c.kind === "relay" ? "Your message" : "Check-in", status),
      sum ? h("div", { class: "h-sum" }, sum) : null);
  }));
}

function renderUpdates(e, items) {
  const box = $("updates");
  if (items.length && lastUpdateId !== null && items[0].id > lastUpdateId) notify(e, items[0]);
  lastUpdateId = items.length ? items[0].id : 0;
  if (!items.length) { box.replaceChildren(h("p", { class: "empty" }, "Updates appear here after each call.")); return; }
  box.replaceChildren(...items.map((m) => h("article", { class: "update " + (m.level || "") },
    h("div", { class: "u-time" }, fmtTime(m.created_at)),
    h("div", { class: "u-body" }, m.body),
    m.audio ? h("audio", { controls: true, preload: "none", src: `/audio/${m.audio}` }) : null,
    h("div", { class: "u-actions" }, h("a", { href: "https://wa.me/?text=" + encodeURIComponent(m.body), target: "_blank", rel: "noopener" }, "Share on WhatsApp")))));
}

function renderQuestions(qs) {
  const ul = $("questions");
  if (!qs.length) { ul.replaceChildren(h("li", { class: "empty" }, "None. “Ask in next check-in” adds one.")); return; }
  ul.replaceChildren(...qs.map((q) => h("li", { class: "row" }, h("span", { style: "flex:1" }, q.question), h("span", { class: "tag" }, q.asked_call_id ? "asked" : "waiting"))));
}

async function openCall(id) {
  const c = await api(`/api/calls/${id}`);
  const s = c.summary || {};
  const body = [h("div", { class: "dlg-head" }, h("h2", {}, c.kind === "relay" ? "Your message" : "Check-in"),
    h("p", { class: "row muted small" }, `${fmtTime(c.started_at)} · ${c.status.replace("_", " ")}`, c.level ? levelBadge(c.level) : null))];
  if (s.summary_for_family) body.push(h("p", { style: "margin-bottom:12px" }, s.summary_for_family));
  (s.family_question_answers || []).forEach((qa) => body.push(h("p", { style: "margin-bottom:8px" }, h("b", {}, qa.question), " ", `“${qa.answer}”`)));
  if (c.turns) {
    body.push(h("h3", { style: "margin:18px 0 6px;font-size:1.05rem" }, "What was said"));
    c.turns.forEach((t) => body.push(h("div", { class: "bubble " + t.role }, t.text)));
  } else {
    body.push(h("p", { class: "muted small" }, "Their exact words are private. They haven't agreed to share them, so you see the summary and safety alerts only."));
  }
  $("callBody").replaceChildren(...body);
  $("callDlg").showModal();
}

// ---------------- notifications on this device
function updateNotifyBtn() {
  const ok = "Notification" in window;
  $("notifyBtn").hidden = !ok || Notification.permission === "granted";
}
$("notifyBtn").addEventListener("click", async () => {
  if (!("Notification" in window)) return;
  await Notification.requestPermission();
  updateNotifyBtn();
  toast(Notification.permission === "granted" ? "You'll get a pop-up while this page is open" : "Notifications are blocked in this browser");
});
function notify(e, u) {
  if ("Notification" in window && Notification.permission === "granted") {
    try { new Notification(u.level === "red" ? `${e.family_label} needs you` : `Akela Nahi · ${e.family_label}`, { body: u.body.slice(0, 180), requireInteraction: u.level === "red" }); } catch (_) {}
  }
  toast(u.body.split("\n")[0]);
}

// ---------------- actions
$("elderSelect").addEventListener("change", (ev) => { current = Number(ev.target.value); lsSet("akela.elder", current); lastUpdateId = null; loadOverview(); });
$("closeCallDlg").addEventListener("click", () => $("callDlg").close());
$("callNowBtn").addEventListener("click", async () => {
  try { await api(`/api/elders/${current}/call`, { method: "POST" }); toast("Their app is ringing"); loadOverview(); }
  catch (e) { toast(e.message); }
});
$("relayBtn").addEventListener("click", () => sendFamily(false));
$("askBtn").addEventListener("click", () => sendFamily(true));

async function sendFamily(askOnly) {
  const text = $("relayText").value.trim();
  if (!text) { toast("Type a message first"); return; }
  try {
    await api(`/api/elders/${current}/family-message`, { json: { text, ask_only: askOnly } });
    $("relayText").value = "";
    toast(askOnly ? "Saved for the next check-in" : "Ringing their app to deliver it");
    loadOverview();
  } catch (e) { toast(e.message); }
}

// ---------------- add / edit parent
const FIELDS = ["name", "family_label", "language", "voice", "call_time", "medicines", "family_name", "family_relation", "family_language"];
function openElderForm(e) {
  editingId = e ? e.id : null;
  $("elderDlgTitle").textContent = e ? `Settings for ${e.family_label}` : "Add parent";
  FIELDS.forEach((f) => ($("f_" + f).value = e ? e[f] || "" : ""));
  if (!e) { $("f_language").value = "hi-IN"; $("f_family_language").value = "en-IN"; $("f_voice").value = "Chetana"; $("f_call_time").value = "08:30"; $("f_family_relation").value = "son"; }
  $("f_share_transcript").checked = !!(e && e.share_transcript);
  $("f_active").checked = e ? !!e.active : true;
  $("f_use_family_voice").checked = !!(e && e.use_family_voice);
  $("voiceBox").hidden = !e;
  $("recVoiceStatus").textContent = e && e.has_family_voice ? "Your voice is saved" : STATUS.gnani ? "" : "Needs GNANI_API_KEY";
  $("elderDlg").showModal();
}
$("addElderBtn").addEventListener("click", () => openElderForm(null));
$("addFirstBtn").addEventListener("click", () => openElderForm(null));
$("editElderBtn").addEventListener("click", () => openElderForm(ELDERS.find((x) => x.id === current)));

$("saveElderBtn").addEventListener("click", async (ev) => {
  ev.preventDefault();
  if (!$("elderForm").reportValidity()) return;
  const body = {};
  FIELDS.forEach((f) => (body[f] = $("f_" + f).value.trim()));
  body.share_transcript = $("f_share_transcript").checked;
  body.active = $("f_active").checked;
  body.use_family_voice = $("f_use_family_voice").checked;
  try {
    const saved = await api(editingId ? `/api/elders/${editingId}` : "/api/elders", { method: editingId ? "PUT" : "POST", json: body });
    $("elderDlg").close();
    toast("Saved");
    await loadElders(saved.id);
  } catch (e) { toast(e.message); }
});

let voiceRec = null;
$("recVoiceBtn").addEventListener("click", async () => {
  if (voiceRec) { voiceRec.stop(); return; }
  if (!$("f_voice_consent").checked) { toast("Please tick the consent box first"); return; }
  voiceRec = new WavRecorder();
  $("recVoiceBtn").textContent = "Stop";
  $("recVoiceStatus").textContent = "Recording… speak naturally for 10–20 seconds";
  let blob = null;
  try { blob = await voiceRec.start({ autoStop: false, maxSeconds: 28 }); }
  catch (e) { toast("Microphone not available: " + e.message); }
  voiceRec = null;
  $("recVoiceBtn").textContent = "Record";
  if (!blob) { $("recVoiceStatus").textContent = "Didn't hear anything. Try again."; return; }
  $("recVoiceStatus").textContent = "Creating your voice with Gnani…";
  const fd = new FormData();
  fd.append("audio", blob, "voice.wav");
  try {
    await api(`/api/elders/${editingId}/family-voice`, { method: "POST", body: fd });
    $("recVoiceStatus").textContent = "Your voice is saved";
    $("f_use_family_voice").checked = true;
    await loadElders(editingId);
  } catch (e) { $("recVoiceStatus").textContent = e.message; }
});
$("delVoiceBtn").addEventListener("click", async () => {
  if (!editingId || !confirm("Delete your cloned voice?")) return;
  await api(`/api/elders/${editingId}/family-voice`, { method: "DELETE" });
  $("f_use_family_voice").checked = false;
  $("recVoiceStatus").textContent = "Deleted";
  await loadElders(editingId);
});

boot().catch((e) => toast(e.message));
