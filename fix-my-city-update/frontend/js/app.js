/* FIX MY CITY – frontend (vanilla JavaScript, no build step). Texts: js/i18n.js */
"use strict";

const PFORZHEIM = [48.8915, 8.7040];
const LEVEL_COLORS = { Low: "#2E9E5B", Medium: "#D9A800", High: "#E5740B", Critical: "#D12F2F" };
const state = { config: null, user: null, token: localStorage.getItem("fmc_token") || null, maps: [], charts: [] };
const $ = (s, root = document) => root.querySelector(s);
const main = $("#main");

/* ------------------------------------------------------------- utilities */
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString(LANG === "de" ? "de-DE" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
}
function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove("show"), 3500);
}
async function api(path, opts = {}) {
  const headers = opts.headers || {};
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  let res;
  try { res = await fetch(path, { ...opts, headers }); }
  catch { throw new Error(t("err.server")); }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = data && data.detail;
    throw new Error(typeof detail === "string" ? tx(detail) : Array.isArray(detail) ? detail.map(d => d.msg).join(", ") : t("err.request", { s: res.status }));
  }
  return data;
}
const cat = k => t("cat." + k);
const st = s => t("st." + s);
const lvl = l => t("lvl." + l);
const sev = s => s ? t("sev." + s) : t("kv.notAssessed");
const lvlBadge = (l, score) => l
  ? `<span class="lvl lvl-${esc(l)}">${esc(lvl(l))}${score != null ? " " + esc(score) : ""}</span>`
  : `<span class="lvl lvl-none">${t("pr.notScored")}</span>`;
const src = k => ({
  official: `<span class="badge src-official">${t("src.official")}</span>`,
  ai: `<span class="badge src-ai">${t("src.ai")}</span>`,
  sim: `<span class="badge src-demo">${t("src.sim")}</span>`,
  demo: `<span class="badge src-demo">${t("src.demo")}</span>`,
  citizen: `<span class="badge src-citizen">${t("src.citizen")}</span>`,
  calc: `<span class="badge src-calc">${t("src.calc")}</span>`,
}[k]);
const aiTag = a => !a ? "" : a.mode === "live" ? src("ai") : a.mode === "simulated" ? src("sim") : src("demo");
function cleanup() {
  state.maps.forEach(m => m.remove()); state.maps = [];
  state.charts.forEach(c => c.destroy()); state.charts = [];
}
function dotIcon(level, isDemo) {
  const color = LEVEL_COLORS[level] || "#8796A5";
  return L.divIcon({
    className: "", iconSize: [26, 26], iconAnchor: [13, 13],
    html: `<span class="gem-marker${isDemo ? " demo" : ""}" style="--c:${color}"></span>`
  });
}
function baseMap(el, zoom = 14) {
  const map = L.map(el, { scrollWheelZoom: true }).setView(PFORZHEIM, zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);
  state.maps.push(map);
  return map;
}
const gem = (size = 18) => `<svg class="gem" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12l4 6-10 12L2 9z" fill="#C9A227"/><path d="M2 9h20M8.5 3 12 9l3.5-6M12 9v12M7 9l5 12 5-12" fill="none" stroke="#9A7A14" stroke-width="1" opacity=".7"/></svg>`;

/* ------------------------------------------------------------- language + static texts */
function applyStatic() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
  document.querySelectorAll(".lang-switch button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === LANG)));
  renderAuthLink();
  const bar = $("#modeBar");
  if (state.config && state.config.ai_mode !== "live") { bar.hidden = false; bar.innerHTML = `<div class="wrap">${t("mode.demo")}</div>`; }
}
document.querySelectorAll(".lang-switch button").forEach(b => b.onclick = () => {
  if (b.dataset.lang === LANG) return;
  setLang(b.dataset.lang); applyStatic(); router();
});

/* ------------------------------------------------------------- router */
const routes = { home: viewHome, report: viewReport, how: viewHow, map: viewMap, dashboard: viewDashboard, login: viewLogin, my: viewMy };
async function router() {
  cleanup();
  const name = location.hash.replace("#", "").split("/")[0] || "home";
  const view = routes[name] || viewHome;
  document.querySelectorAll("nav a").forEach(a => a.classList.toggle("active", a.dataset.route === name));
  $("#nav").classList.remove("open"); $("#menuBtn").setAttribute("aria-expanded", "false");
  main.innerHTML = `<div class="page wrap"><p class="muted">${t("common.loading")}</p></div>`;
  try { await view(); } catch (e) { main.innerHTML = `<div class="page wrap"><div class="notice notice-err">${esc(e.message)}</div></div>`; }
  window.scrollTo(0, 0);
}
$("#menuBtn").addEventListener("click", () => {
  const open = $("#nav").classList.toggle("open"); $("#menuBtn").setAttribute("aria-expanded", String(open));
});
function renderAuthLink() {
  const a = $("#authLink");
  if (state.user) { a.textContent = state.user.role === "admin" ? t("nav.admin") : t("nav.my"); a.href = "#my"; a.dataset.route = "my"; }
  else { a.textContent = t("nav.login"); a.href = "#login"; a.dataset.route = "login"; }
}

/* ------------------------------------------------------------- HOME */
function heroSvg() {
  return `
<svg viewBox="0 0 560 420" role="img" aria-label="${esc(t("home.heroCaption"))}">
  <defs>
    <pattern id="facets" width="28" height="28" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="28" height="28" fill="#10305A"/><path d="M0 0h28v28" fill="none" stroke="#1B406E" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="560" height="420" fill="url(#facets)"/>
  <!-- forest edge (Black Forest) -->
  <g fill="#0E4A45" opacity=".9">
    ${[20, 58, 96, 134, 172].map((x, i) => `<path d="M${x} ${410 - (i % 2) * 14}l18-46 18 46z"/>`).join("")}
    ${[30, 76, 122].map(x => `<path d="M${x} 372l14-36 14 36z" opacity=".7"/>`).join("")}
  </g>
  <!-- three rivers: Enz, Nagold, Würm -->
  <g fill="none" stroke-linecap="round">
    <path d="M-10 250 C 90 240, 170 215, 260 205" stroke="#13A89E" stroke-width="12"/>
    <path d="M120 430 C 150 340, 200 270, 260 205" stroke="#5BC0EB" stroke-width="9"/>
    <path d="M250 430 C 240 350, 255 270, 260 205" stroke="#5BC0EB" stroke-width="7"/>
    <path d="M260 205 C 350 190, 450 150, 580 120" stroke="#13A89E" stroke-width="16"/>
  </g>
  <g font-family="Public Sans, sans-serif" font-size="13" font-weight="700" fill="#BFE3F5">
    <text x="20" y="232">Enz</text><text x="122" y="320" transform="rotate(-52 122 320)">Nagold</text><text x="262" y="330">Würm</text>
    <text x="470" y="118" transform="rotate(-14 470 118)">Enz</text>
  </g>
  <!-- city blocks -->
  <g fill="#1E4C82" stroke="#2C5E98">
    <rect x="300" y="230" width="54" height="40" rx="5"/><rect x="364" y="222" width="40" height="56" rx="5"/>
    <rect x="414" y="236" width="60" height="38" rx="5"/><rect x="300" y="110" width="66" height="48" rx="5"/>
    <rect x="380" y="96" width="44" height="40" rx="5"/><rect x="170" y="120" width="70" height="44" rx="5"/>
  </g>
  <!-- gem-shaped incident markers -->
  ${[[330, 205, "#D12F2F"], [205, 150, "#E5740B"], [440, 285, "#D9A800"], [395, 140, "#2E9E5B"]].map(([x, y, c]) =>
    `<g transform="translate(${x - 14} ${y - 26})"><path d="M5 2h18l5 8-14 18L0 10z" fill="${c}" stroke="#fff" stroke-width="2.5"/><path d="M0 10h28M9 2l5 8 5-8M14 10v18" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.2"/></g>`).join("")}
  <!-- analysis card -->
  <g transform="translate(330 300)">
    <rect width="210" height="100" rx="14" fill="#fff"/>
    <rect x="14" y="14" width="56" height="56" rx="8" fill="#0B2545"/>
    <path d="M24 60l12-16 8 10 6-7 12 13z" fill="#5BC0EB"/>
    <rect x="82" y="18" width="104" height="9" rx="4.5" fill="#0B2545"/>
    <rect x="82" y="36" width="70" height="7" rx="3.5" fill="#DCE3EA"/>
    <rect x="82" y="52" width="54" height="16" rx="8" fill="#E5740B"/>
    <rect x="14" y="82" width="182" height="7" rx="3.5" fill="#F7F0DA"/>
    <rect x="14" y="82" width="132" height="7" rx="3.5" fill="#C9A227"/>
  </g>
</svg>`;
}

async function viewHome() {
  let s = null;
  try { s = await api("/api/public/stats"); } catch { /* shown below */ }
  const stat = (n, l, cls) => `<div class="card stat-card ${cls}"><div class="num">${s ? esc(n) : "–"}</div><div class="lbl">${l}</div></div>`;
  const steps = [1, 2, 3, 4].map(i => `<div class="card step"><div class="n"><span>${i}</span></div><h3>${t(`home.s${i}t`)}</h3><p class="muted">${t(`home.s${i}d`)}</p></div>`).join("");
  main.innerHTML = `
  <section class="hero"><div class="wrap hero-grid">
    <div>
      <p class="kicker">${gem(16)} ${t("home.kicker")}</p>
      <h1>${t("home.title")}</h1>
      <p class="lead">${t("home.lead")}</p>
      <div class="btn-row"><a class="btn btn-gold" href="#report">${t("home.ctaReport")}</a><a class="btn btn-ghost" href="#how">${t("home.ctaHow")}</a></div>
      <p class="slogan">${t("footer.tag")}</p>
    </div>
    <figure class="hero-visual">${heroSvg()}<figcaption>${t("home.heroCaption")}</figcaption></figure>
  </div></section>

  <section class="block stats-block"><div class="wrap">
    <div class="section-head"><h2>${t("home.statsTitle")}</h2>
    <p class="muted">${s ? (s.demo_records ? t("home.statsDemo", { n: esc(s.demo_records) }) : t("home.statsReal")) : t("home.statsNone")}</p></div>
    <div class="grid-4">
      ${stat(s?.total, t("home.stat.total"), "gold")}${stat(s?.resolved, t("home.stat.resolved"), "ok")}
      ${stat(s?.open, t("home.stat.open"), "warn")}${stat(s?.high_priority, t("home.stat.high"), "crit")}
    </div>
  </div></section>

  <section class="block grey"><div class="wrap">
    <div class="section-head"><h2>${t("home.howTitle")}</h2></div>
    <div class="grid-4 steps">${steps}</div>
  </div></section>

  <section class="band"><div class="wrap">
    <h2>${t("home.bandTitle")}</h2>
    <div class="grid-3">
      ${[1, 2, 3].map(i => `<div class="band-item"><div class="band-icon">${[
        `<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true"><path d="M4 30C12 26 16 20 20 18M10 38c2-8 6-14 10-20M22 38c0-8-1-14-2-20M20 18c6-2 10-6 16-10" fill="none" stroke="#5BC0EB" stroke-width="3" stroke-linecap="round"/></svg>`,
        gem(40),
        `<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true"><path d="M8 34l8-20 8 20zM20 34l8-24 8 24z" fill="#13A89E"/><path d="M4 36h34" stroke="#C9A227" stroke-width="2.5" stroke-linecap="round"/></svg>`][i - 1]}</div>
        <h3>${t(`home.band${i}t`)}</h3><p>${t(`home.band${i}d`)}</p></div>`).join("")}
    </div>
  </div></section>

  <section class="block"><div class="wrap benefits">
    <div class="grid-2">
      <div class="card"><h3>${t("home.citizens")}</h3><ul>${[1, 2, 3, 4].map(i => `<li>${t("home.c" + i)}</li>`).join("")}</ul></div>
      <div class="card"><h3>${t("home.admin")}</h3><ul>${[1, 2, 3, 4, 5, 6].map(i => `<li>${t("home.a" + i)}</li>`).join("")}</ul></div>
    </div>
    <div class="btn-row" style="margin-top:28px"><a class="btn btn-primary" href="#report">${t("home.ctaReport")}</a><a class="btn btn-outline" href="#map">${t("home.ctaMap")}</a></div>
  </div></section>`;
}

/* ------------------------------------------------------------- REPORT */
async function viewReport() {
  const keys = Object.keys(state.config.categories);
  const mb = state.config.max_upload_mb;
  main.innerHTML = `
  <div class="page wrap" id="reportPage">
    <p class="kicker dark">${gem(16)} Pforzheim</p>
    <h1>${t("rep.title")}</h1>
    <p class="muted" style="max-width:640px">${t("rep.lead")}</p>
    <div class="notice notice-info small">${t("rep.privacy")}</div>
    <form id="reportForm" class="form-grid" novalidate>
      <div class="card">
        <h3>${t("rep.photo")}</h3>
        <input type="file" id="photo" accept="image/jpeg,image/png,image/webp" hidden>
        <div id="photoArea"></div>
        <div class="field" style="margin-top:18px"><label for="desc">${t("rep.desc")} <span class="muted small">${t("rep.optional")}</span></label>
          <textarea id="desc" maxlength="1000" placeholder="${esc(t("rep.descPh"))}"></textarea></div>
        <div class="field"><label for="cat">${t("rep.cat")} <span class="muted small">${t("rep.optional")}</span></label>
          <select id="cat"><option value="">${t("rep.catAuto")}</option>${keys.map(k => `<option value="${k}">${esc(cat(k))}</option>`).join("")}</select></div>
      </div>
      <div class="card">
        <h3>${t("rep.loc")}</h3>
        <p class="hint muted small">${t("rep.locHint")}</p>
        <div id="pickMap" class="map-box"></div>
        <div class="btn-row" style="margin:12px 0"><button type="button" class="btn btn-outline btn-sm" id="geoBtn">${t("rep.geo")}</button><span id="geoMsg" class="small muted" style="align-self:center"></span></div>
        <div class="field"><label for="locText">${t("rep.street")} <span class="muted small">${t("rep.optional")}</span></label><input type="text" id="locText" maxlength="200" placeholder="${esc(t("rep.streetPh"))}"></div>
        <div class="check"><input type="checkbox" id="locOk"><label for="locOk" style="font-weight:600">${t("rep.confirmLoc")}</label></div>
        <p class="small muted" id="coords" style="margin-top:8px"></p>
        <div id="formErr"></div>
        <button class="btn btn-gold" type="submit" id="submitBtn" style="width:100%;margin-top:8px">${t("rep.submit")}</button>
      </div>
    </form>
  </div>`;

  let file = null;
  const photoArea = $("#photoArea"), input = $("#photo");
  function drawPhoto() {
    if (!file) {
      photoArea.innerHTML = `<div class="dropzone" id="drop" tabindex="0" role="button" aria-label="${esc(t("rep.drop"))}">
        <div><svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="#C9A227" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h3l2-2h6l2 2h3v12H4z"/><circle cx="12" cy="13" r="3.5"/></svg>
        <b>${t("rep.drop")}</b><br><span class="small muted">${t("rep.dropHint", { mb })}</span></div></div>`;
      const d = $("#drop");
      d.onclick = () => input.click();
      d.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } };
      ["dragenter", "dragover"].forEach(ev => d.addEventListener(ev, e => { e.preventDefault(); d.classList.add("over"); }));
      ["dragleave", "drop"].forEach(ev => d.addEventListener(ev, e => { e.preventDefault(); d.classList.remove("over"); }));
      d.addEventListener("drop", e => take(e.dataTransfer.files[0]));
    } else {
      const url = URL.createObjectURL(file);
      photoArea.innerHTML = `<div class="preview"><img src="${url}" alt="${esc(t("rep.previewAlt"))}"><button type="button" class="btn btn-outline btn-sm" id="replace">${t("rep.replace")}</button></div>`;
      $("#replace").onclick = () => input.click();
    }
  }
  function take(f) {
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) return toast(t("rep.errType"));
    if (f.size > mb * 1024 * 1024) return toast(t("rep.errSize", { mb }));
    file = f; drawPhoto();
  }
  input.onchange = () => { take(input.files[0]); input.value = ""; };
  drawPhoto();

  const map = baseMap($("#pickMap"), 14);
  const marker = L.marker(PFORZHEIM, { draggable: true }).addTo(map);
  const showCoords = () => { const p = marker.getLatLng(); $("#coords").textContent = t("rep.coords", { c: `${p.lat.toFixed(5)}, ${p.lng.toFixed(5)}` }); $("#locOk").checked = false; };
  map.on("click", e => { marker.setLatLng(e.latlng); showCoords(); });
  marker.on("dragend", showCoords);
  showCoords();
  $("#geoBtn").onclick = () => {
    if (!navigator.geolocation) { $("#geoMsg").textContent = t("rep.geoNo"); return; }
    $("#geoMsg").textContent = t("rep.geoBusy");
    navigator.geolocation.getCurrentPosition(
      p => { const ll = [p.coords.latitude, p.coords.longitude]; marker.setLatLng(ll); map.setView(ll, 17); showCoords(); $("#geoMsg").textContent = t("rep.geoOk"); },
      () => { $("#geoMsg").textContent = t("rep.geoDenied"); },
      { enableHighAccuracy: true, timeout: 10000 });
  };

  $("#reportForm").onsubmit = async e => {
    e.preventDefault();
    const err = $("#formErr"); err.innerHTML = "";
    if (!file) { err.innerHTML = `<div class="notice notice-err">${t("rep.errPhoto")}</div>`; return; }
    if (!$("#locOk").checked) { err.innerHTML = `<div class="notice notice-err">${t("rep.errLoc")}</div>`; return; }
    const p = marker.getLatLng();
    const fd = new FormData();
    fd.append("image", file); fd.append("latitude", p.lat); fd.append("longitude", p.lng);
    fd.append("description", $("#desc").value); fd.append("location_text", $("#locText").value);
    fd.append("citizen_category", $("#cat").value); fd.append("language", LANG);
    const preview = URL.createObjectURL(file);
    const live = state.config.ai_mode === "live";
    cleanup();
    main.innerHTML = `<div class="page wrap"><div class="card loading-card"><div class="spinner" aria-hidden="true"></div>
      <h2>${t(live ? "rep.analyzing" : "rep.simulating")}</h2><p class="muted">${t(live ? "rep.analyzingHint" : "rep.simulatingHint")}</p></div></div>`;
    try {
      const report = await api("/api/reports", { method: "POST", body: fd });
      viewAnalysis(report, preview);
    } catch (ex) {
      main.innerHTML = `<div class="page wrap"><div class="notice notice-err"><b>${t("rep.notSaved")}</b> ${esc(ex.message)}</div>
        <a class="btn btn-primary" href="#report" onclick="setTimeout(router,0)">${t("rep.retry")}</a></div>`;
    }
  };
}

const list = arr => (arr || []).length ? `<ul>${arr.map(x => `<li>${esc(tx(x))}</li>`).join("")}</ul>` : t("common.none");

function analysisBlock(r) {
  const a = r.analysis || {};
  const tag = aiTag(a);
  const dep = r.department ? `${esc(tx(r.department.name))}${r.department.provisional ? `<div class="small muted">${t("kv.deptProv")}</div>` : ""}` : t("kv.notAssigned");
  return `
  <dl class="kv">
    <dt>${t("kv.detected")}</dt><dd><b>${esc(tx(a.detected_incident) || "–")}</b>${tag}</dd>
    <dt>${t("kv.category")}</dt><dd>${esc(cat(r.category))}${tag}</dd>
    <dt>${t("kv.description")}</dt><dd>${esc(tx(a.description) || "–")}${tag}</dd>
    <dt>${t("kv.risks")}</dt><dd>${list(a.potential_risks)}${tag}</dd>
    <dt>${t("kv.severity")}</dt><dd>${esc(sev(a.severity))}${tag}</dd>
    <dt>${t("kv.dept")}</dt><dd>${dep} ${src("calc")}</dd>
    <dt>${t("kv.actions")}</dt><dd>${list(a.recommended_actions)}${tag}<div class="small muted">${t("kv.actionsHint")}</div></dd>
    <dt>${t("kv.confidence")}</dt><dd><span class="muted">${t("kv.confNone")}</span></dd>
  </dl>`;
}

function factorNote(f, a) {
  if (f.key === "severity") return t("f.sevNote", { v: sev(a?.severity) });
  if (f.key === "urgency") return t("f.urgNote", { v: sev(a?.urgency) });
  if (f.key === "public_exposure") return t("f.expNote") + (a?.exposure_reasoning ? " " + tx(a.exposure_reasoning) : "");
  if (f.key === "location_sensitivity") return f.value == null ? t("f.locNA") : f.note;
  return f.note;
}

function priorityBlock(r) {
  const p = r.priority_breakdown || {};
  const a = r.analysis;
  if (r.priority_score == null) {
    return `<div class="prio-card"><div>${lvlBadge(null)}<p class="small muted" style="margin:8px 0 0">${esc(tx((p.reasons || [])[0]) || t("pr.manual"))}</p></div></div>`;
  }
  const num = v => LANG === "de" ? String(v).replace(".", ",") : v;
  const rows = (p.factors || []).map(f => `<tr><td>${t("f." + f.key)}</td><td>${f.value == null ? `<b>${t("pr.na")}</b>` : esc(f.value)}</td>
    <td class="num">${(f.weight * 100).toFixed(0)}%${f.value != null && p.renormalized ? ` → ${num((f.effective_weight * 100).toFixed(1))}%` : ""}</td>
    <td class="num">${f.points == null ? "–" : esc(num(f.points))}</td>
    <td>${f.source === "ai_estimate" ? aiTag(a) : f.source === "open_data" ? src("official") : ""} <span class="small muted">${esc(factorNote(f, a))}</span></td></tr>`).join("");
  return `
  <div class="prio-card">
    <div class="prio-num" style="color:${LEVEL_COLORS[r.priority_level]}">${esc(r.priority_score)}</div>
    <div>${lvlBadge(r.priority_level)} ${src("calc")}${r.priority_overridden ? ` <span class="badge src-citizen">${t("pr.byAdmin")}</span>` : ""}
      <div class="small muted" style="margin-top:6px">${t("pr.formula")}</div></div>
  </div>
  ${p.escalated ? `<div class="notice notice-crit"><b>${t("pr.escalated")}</b> ${esc(tx(p.escalation_reason))}</div>` : ""}
  ${(p.reasons || []).length ? `<p style="margin-bottom:6px"><b>${t("pr.why")}</b></p><ul style="margin-top:0">${p.reasons.map(x => `<li>${esc(tx(x))}</li>`).join("")}</ul>` : ""}
  <div class="table-wrap" style="border-radius:10px"><table class="factors" style="min-width:560px">
    <thead><tr><th>${t("pr.factor")}</th><th>${t("pr.value")}</th><th class="num">${t("pr.weight")}</th><th class="num">${t("pr.points")}</th><th>${t("pr.source")}</th></tr></thead><tbody>${rows}</tbody></table></div>
  ${p.renormalized ? `<p class="small muted" style="margin-top:8px">${t("pr.renorm")}</p>` : ""}`;
}

function modeNotice(a) {
  if (!a) return "";
  if (a.mode === "live") return `<div class="notice notice-ai">${t("an.live", { m: esc(a.model) })}</div>`;
  if (a.mode === "simulated") return `<div class="notice notice-sim">${t("an.sim")}</div>`;
  return `<div class="notice notice-sim">${t("an.demo")}</div>`;
}

function viewAnalysis(r, previewUrl) {
  const a = r.analysis || {};
  const dups = r.duplicate_candidates || [];
  main.innerHTML = `
  <div class="page wrap">
    <h1>${t("an.title")}</h1>
    ${modeNotice(a)}
    ${!a.image_recognizable ? `<div class="notice notice-err">${t("an.unclear")}</div>` : ""}
    ${dups.length ? `<div class="notice notice-info">${t("an.dup", { n: dups.length })}</div>` : ""}
    <div class="analysis-grid">
      <div class="card"><img src="${previewUrl || r.image_url}" alt="${esc(t("an.photoAlt"))}" style="border-radius:10px;width:100%">
        <dl class="kv" style="margin-top:16px;grid-template-columns:1fr">
          <dt>${t("an.yourDesc")} ${src("citizen")}</dt><dd>${esc(r.description || "–")}</dd>
          <dt>${t("an.location")} ${src("citizen")}</dt><dd>${esc(r.location_text || "")} <span class="small muted">${r.latitude.toFixed(5)}, ${r.longitude.toFixed(5)}</span></dd>
        </dl></div>
      <div>
        <div class="card" style="margin-bottom:18px"><h3>${t("an.incident")}</h3>${analysisBlock(r)}</div>
        <div class="card"><h3>${t("an.priority")}</h3>${priorityBlock(r)}</div>
      </div>
    </div>
    <div class="btn-row" style="margin-top:24px">
      <button class="btn btn-gold" id="confirmBtn">${t("an.confirm")}</button>
      <a class="btn btn-outline" href="#report" id="restart">${t("an.discard")}</a>
    </div>
    <div id="confirmMsg" style="margin-top:12px"></div>
  </div>`;
  $("#restart").onclick = e => { e.preventDefault(); location.hash === "#report" ? router() : (location.hash = "#report"); };
  $("#confirmBtn").onclick = async () => {
    const btn = $("#confirmBtn"); btn.disabled = true; btn.textContent = t("an.submitting");
    try {
      const res = await api(`/api/reports/${r.id}/confirm`, { method: "POST", json: { edit_token: r.edit_token } });
      main.innerHTML = `<div class="page wrap"><div class="card thanks-card">
        <div class="thanks-gem">${gem(56)}</div>
        <h1>${t("an.thanks")}</h1><p>${t("an.saved")}</p>
        <p>${t("an.code")}</p><p class="code">${esc(res.code)}</p>
        <p class="muted small">${t("an.keep")}</p>
        <div class="btn-row" style="justify-content:center"><a class="btn btn-primary" href="#map">${t("an.seeMap")}</a><a class="btn btn-outline" href="#my">${t("an.track")}</a></div></div></div>`;
    } catch (ex) {
      btn.disabled = false; btn.textContent = t("an.confirm");
      $("#confirmMsg").innerHTML = `<div class="notice notice-err"><b>${t("an.notSubmitted")}</b> ${esc(ex.message)}</div>`;
    }
  };
}

/* ------------------------------------------------------------- HOW IT WORKS */
async function viewHow() {
  const s = await api("/api/sources");
  main.innerHTML = `
  <div class="page wrap">
    <h1>${t("how.title")}</h1>
    <p class="muted" style="max-width:700px">${t("how.lead")}</p>
    <div class="grid-4 steps" style="margin:28px 0">
      ${[1, 2, 3, 4].map(i => `<div class="card step"><div class="n"><span>${i}</span></div><h3>${t(`how.s${i}t`)}</h3><p class="muted">${t(`how.s${i}d`)}</p></div>`).join("")}
    </div>
    <div class="grid-2">
      <div class="card"><h3>${t("how.formulaTitle")}</h3>
        <p><b>${t("pr.formula")}</b></p><p class="muted">${t("how.formulaP1")}</p><p class="muted">${t("how.formulaP2")}</p>
        <div class="btn-row">${["Low", "Medium", "High", "Critical"].map(l => lvlBadge(l)).join("")}</div></div>
      <div class="card"><h3>${t("how.labelsTitle")}</h3>
        <p>${src("official")} ${t("how.lOfficial")}</p><p>${src("ai")} ${t("how.lAi")}</p>
        <p>${src("citizen")} ${t("how.lCitizen")}</p><p>${src("calc")} ${t("how.lCalc")}</p>
        <p>${src("sim")} ${src("demo")} ${t("how.lSim")}</p>
        <p class="muted small">${t("how.deptNote")}</p></div>
    </div>
    <h2 style="margin-top:40px">${t("how.sourcesTitle")}</h2>
    <p class="muted" style="max-width:720px">${t("how.sourcesLead")}</p>
    <div class="table-wrap"><table class="data" style="min-width:720px"><thead><tr><th>${t("how.platform")}</th><th>${t("how.purpose")}</th><th>${t("how.url")}</th><th>${t("how.status")}</th></tr></thead><tbody>
      ${s.platforms.map(p => `<tr><td><b>${esc(p.platform)}</b></td><td>${esc(p.purpose)}</td><td>${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.url)}</a>` : `<span class="muted">${t("how.noLink")}</span>`}</td>
        <td><span class="status">${p.status === "link_not_provided" ? t("how.notConnected") : esc(p.status)}</span></td></tr>`).join("")}
    </tbody></table></div>
    <h3 style="margin-top:28px">${t("how.datasets")}</h3>
    ${s.datasets.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>${t("how.ds.name")}</th><th>URL</th><th>${t("how.ds.desc")}</th><th>${t("how.ds.retrieved")}</th><th>${t("how.ds.fields")}</th><th>${t("how.ds.use")}</th></tr></thead><tbody>
      ${s.datasets.map(d => `<tr><td>${esc(d.name)}</td><td><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.url)}</a></td><td>${esc(d.description)}</td><td>${esc(d.retrieved_at)}</td><td>${esc(d.relevant_fields)}</td><td>${esc(d.usage)}</td></tr>`).join("")}
    </tbody></table></div>` : `<div class="notice notice-info">${t("how.noDatasets")}</div>`}
    <h3 style="margin-top:28px">${t("how.dupTitle")}</h3>
    <p class="muted" style="max-width:720px">${t("how.dupText")}</p>
  </div>`;
}

/* ------------------------------------------------------------- MAP */
async function viewMap() {
  const data = await api("/api/public/map");
  const keys = Object.keys(state.config.categories);
  main.innerHTML = `
  <div class="page wrap">
    <h1>${t("map.title")}</h1>
    <div class="toolbar">
      <select id="fCat" aria-label="${t("kv.category")}"><option value="">${t("map.allCat")}</option>${keys.map(k => `<option value="${k}">${esc(cat(k))}</option>`).join("")}</select>
      <select id="fLvl" aria-label="${t("an.priority")}"><option value="">${t("map.allPrio")}</option>${["Critical", "High", "Medium", "Low"].map(l => `<option value="${l}">${lvl(l)}</option>`).join("")}<option value="none">${t("pr.notScored")}</option></select>
      <select id="fSt" aria-label="Status"><option value="">${t("map.allSt")}</option>${state.config.statuses.map(s => `<option value="${s}">${st(s)}</option>`).join("")}</select>
      <select id="fDate" aria-label="Date"><option value="">${t("map.anyDate")}</option><option value="1">${t("map.d1")}</option><option value="7">${t("map.d7")}</option><option value="30">${t("map.d30")}</option></select>
      <select id="fType" aria-label="Type"><option value="">${t("map.allTypes")}</option><option value="real">${t("map.real")}</option><option value="demo">${t("map.demo")}</option></select>
    </div>
    <div id="bigMap" class="map-full"></div>
    <div class="legend-map">${Object.entries(LEVEL_COLORS).map(([l, c]) => `<span><span class="dot" style="background:${c}"></span>${lvl(l)}</span>`).join("")}
      <span><span class="dot" style="background:#8796A5"></span>${t("pr.notScored")}</span><span>${t("map.dashed")}</span><span id="countMsg"></span></div>
  </div>`;
  const map = baseMap($("#bigMap"), 14);
  const layer = L.layerGroup().addTo(map);
  function draw() {
    layer.clearLayers();
    const c = $("#fCat").value, l = $("#fLvl").value, s = $("#fSt").value, d = Number($("#fDate").value), ty = $("#fType").value;
    const since = d ? Date.now() - d * 864e5 : 0;
    const shown = data.filter(r => (!c || r.category === c) && (!l || (l === "none" ? !r.priority_level : r.priority_level === l))
      && (!s || r.status === s) && (!since || new Date(r.created_at).getTime() >= since)
      && (!ty || (ty === "demo" ? r.is_demo : !r.is_demo)));
    shown.forEach(r => {
      L.marker([r.latitude, r.longitude], { icon: dotIcon(r.priority_level, r.is_demo), title: cat(r.category) })
        .bindPopup(`<b>${esc(cat(r.category))}</b> ${r.is_demo ? `<span class="badge src-demo">${t("src.demoShort")}</span>` : ""}<br><span class="muted">${esc(r.code)}</span>
          ${r.image_url ? `<img src="${esc(r.image_url)}" alt="${esc(t("map.imgAlt"))}">` : `<div class="small muted" style="margin:6px 0">${t("common.noPhoto")}</div>`}
          <div>${esc(tx(r.location_text) || "")}</div><div style="margin:6px 0">${lvlBadge(r.priority_level, r.priority_score)} <span class="status">${esc(st(r.status))}</span></div>
          <div class="small muted">${fmtDate(r.created_at)}</div>`).addTo(layer);
    });
    $("#countMsg").textContent = t("map.count", { a: shown.length, b: data.length });
  }
  ["#fCat", "#fLvl", "#fSt", "#fDate", "#fType"].forEach(s => $(s).onchange = draw);
  draw();
}

/* ------------------------------------------------------------- AUTH */
async function viewLogin() {
  main.innerHTML = `
  <div class="page wrap"><div class="auth-box card">
    <div class="auth-gem">${gem(40)}</div>
    <div class="dash-tabs"><button class="active" data-t="login">${t("auth.login")}</button><button data-t="register">${t("auth.register")}</button></div>
    <form id="authForm" novalidate>
      <div class="field" id="nameField" hidden><label for="aName">${t("auth.name")}</label><input type="text" id="aName" autocomplete="name" maxlength="80"></div>
      <div class="field"><label for="aEmail">${t("auth.email")}</label><input type="email" id="aEmail" autocomplete="email" required></div>
      <div class="field"><label for="aPw">${t("auth.pw")}</label><input type="password" id="aPw" autocomplete="current-password" required minlength="8"><p class="hint" id="pwHint" hidden>${t("auth.pwHint")}</p></div>
      <div id="authErr"></div>
      <button class="btn btn-primary" style="width:100%" id="authBtn">${t("auth.login")}</button>
    </form>
    <p class="small muted" style="margin-top:14px">${t("auth.note")}</p>
  </div></div>`;
  let mode = "login";
  document.querySelectorAll(".dash-tabs button").forEach(b => b.onclick = () => {
    mode = b.dataset.t;
    document.querySelectorAll(".dash-tabs button").forEach(x => x.classList.toggle("active", x === b));
    $("#nameField").hidden = mode === "login"; $("#pwHint").hidden = mode === "login";
    $("#authBtn").textContent = mode === "login" ? t("auth.login") : t("auth.create");
    $("#aPw").autocomplete = mode === "login" ? "current-password" : "new-password";
  });
  $("#authForm").onsubmit = async e => {
    e.preventDefault(); $("#authErr").innerHTML = "";
    const body = { email: $("#aEmail").value, password: $("#aPw").value };
    if (mode === "register") body.name = $("#aName").value || "Citizen";
    try {
      const res = await api(`/api/auth/${mode}`, { method: "POST", json: body });
      state.token = res.token; state.user = res.user; localStorage.setItem("fmc_token", res.token);
      renderAuthLink(); toast(t("auth.welcome", { n: tx(res.user.name) }));
      location.hash = res.user.role === "admin" ? "#dashboard" : "#my";
    } catch (ex) { $("#authErr").innerHTML = `<div class="notice notice-err">${esc(ex.message)}</div>`; }
  };
}
async function logout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* ignore */ }
  state.token = null; state.user = null; localStorage.removeItem("fmc_token"); renderAuthLink();
  toast(t("auth.out")); location.hash = "#home";
}

/* ------------------------------------------------------------- MY REPORTS / TRACKING */
async function viewMy() {
  let mine = [];
  if (state.user) { try { mine = await api("/api/reports/mine"); } catch { /* shown empty */ } }
  main.innerHTML = `
  <div class="page wrap">
    <div class="page-head">
      <h1 style="margin:0">${state.user ? t("my.title") : t("my.track")}</h1>
      ${state.user ? `<div class="btn-row">${state.user.role === "admin" ? `<a class="btn btn-primary btn-sm" href="#dashboard">${t("my.openDash")}</a>` : ""}<button class="btn btn-outline btn-sm" id="logoutBtn">${t("auth.logout")}</button></div>` : ""}
    </div>
    <div class="card" style="margin:24px 0;max-width:560px"><h3>${t("my.byCode")}</h3>
      <form id="trackForm" class="btn-row"><input type="text" id="trackCode" placeholder="${esc(t("my.codePh"))}" style="flex:1 1 200px" aria-label="${esc(t("my.byCode"))}"><button class="btn btn-primary">${t("my.trackBtn")}</button></form>
      <div id="trackOut" style="margin-top:14px"></div></div>
    ${state.user ? (mine.length ? `<div class="grid-3">${mine.map(r => `<div class="card">
        ${r.image_url ? `<img src="${esc(r.image_url)}" alt="" style="border-radius:8px;height:160px;width:100%;object-fit:cover;margin-bottom:10px">` : ""}
        <b>${esc(cat(r.category))}</b><div class="small muted">${esc(r.code)}, ${fmtDate(r.created_at)}</div>
        <div style="margin-top:8px">${lvlBadge(r.priority_level, r.priority_score)} <span class="status">${esc(st(r.status))}</span></div></div>`).join("")}</div>`
      : `<p class="empty">${t("my.none")} <a href="#report">${t("nav.report")}</a></p>`) : `<p class="muted"><a href="#login">${t("auth.login")}</a>: ${t("my.loginHint")}</p>`}
  </div>`;
  if ($("#logoutBtn")) $("#logoutBtn").onclick = logout;
  $("#trackForm").onsubmit = async e => {
    e.preventDefault();
    const out = $("#trackOut");
    try {
      const r = await api(`/api/public/track/${encodeURIComponent($("#trackCode").value.trim())}`);
      out.innerHTML = `<p><b>${esc(cat(r.category))}</b>, ${t("my.status")} <span class="status">${esc(st(r.status))}</span> ${lvlBadge(r.priority_level)}</p>
        ${r.merged_into ? `<p class="small muted">${t("my.merged")}</p>` : ""}
        <ul class="timeline">${r.history.map(h => `<li><b>${esc(st(h.new_status))}</b> <span class="muted">${fmtDate(h.changed_at)}</span></li>`).join("")}</ul>`;
    } catch (ex) { out.innerHTML = `<div class="notice notice-err">${esc(ex.message)}</div>`; }
  };
}

/* ------------------------------------------------------------- DASHBOARD */
async function viewDashboard() {
  if (!state.user || state.user.role !== "admin") {
    main.innerHTML = `<div class="page wrap"><div class="card auth-box" style="text-align:center"><div class="auth-gem">${gem(40)}</div><h2>${t("dash.loginTitle")}</h2>
      <p class="muted">${t("dash.loginText")}</p><a class="btn btn-primary" href="#login">${t("auth.login")}</a></div></div>`;
    return;
  }
  main.innerHTML = `
  <div class="page wrap">
    <div class="page-head"><h1 style="margin:0">${t("dash.title")}</h1><span class="muted small">${t("dash.as", { n: esc(tx(state.user.name)) })}</span></div>
    <div class="dash-tabs" role="tablist">
      <button class="active" data-tab="reports">${t("dash.tReports")}</button><button data-tab="departments">${t("dash.tDepts")}</button><button data-tab="feedback">${t("dash.tLog")}</button></div>
    <div id="tab"></div>
  </div>`;
  const tabs = { reports: dashReports, departments: dashDepartments, feedback: dashFeedback };
  document.querySelectorAll(".dash-tabs button").forEach(b => b.onclick = () => {
    document.querySelectorAll(".dash-tabs button").forEach(x => x.classList.toggle("active", x === b));
    state.charts.forEach(c => c.destroy()); state.charts = [];
    tabs[b.dataset.tab]();
  });
  await dashReports();
}

async function dashReports() {
  const box = $("#tab");
  const s = await api("/api/admin/stats");
  const keys = Object.keys(state.config.categories);
  const catByLabel = Object.fromEntries(Object.entries(state.config.categories).map(([k, v]) => [v, k]));
  box.innerHTML = `
    ${s.demo_records ? `<div class="notice notice-sim small">${t("dash.demoNote", { n: esc(s.demo_records) })}</div>` : ""}
    <div class="grid-3" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:20px">
      ${[[t("dash.total"), s.total, "gold"], [t("dash.new"), s.new, "gold"], [t("dash.open"), s.open, "warn"], [t("dash.progress"), s.in_progress, "warn"], [t("dash.resolved"), s.resolved, "ok"], [t("dash.critical"), s.critical, "crit"]]
        .map(([l, n, c]) => `<div class="card stat-card ${c}"><div class="num">${esc(n)}</div><div class="lbl">${l}</div></div>`).join("")}
    </div>
    <div class="grid-2" style="margin-bottom:24px">
      <div class="card"><h3>${t("dash.byStatus")}</h3><div class="chart-box"><canvas id="chStatus"></canvas></div></div>
      <div class="card"><h3>${t("dash.byCat")}</h3><div class="chart-box"><canvas id="chCat"></canvas></div></div>
    </div>
    <div class="toolbar">
      <input type="search" id="q" placeholder="${esc(t("dash.search"))}" aria-label="${esc(t("dash.search"))}">
      <select id="dSt" aria-label="Status"><option value="">${t("map.allSt")}</option>${state.config.statuses.map(x => `<option value="${x}">${st(x)}</option>`).join("")}</select>
      <select id="dCat" aria-label="${t("kv.category")}"><option value="">${t("map.allCat")}</option>${keys.map(k => `<option value="${k}">${esc(cat(k))}</option>`).join("")}</select>
      <select id="dLvl" aria-label="${t("an.priority")}"><option value="">${t("map.allPrio")}</option>${["Critical", "High", "Medium", "Low"].map(l => `<option value="${l}">${lvl(l)}</option>`).join("")}</select>
      <select id="dSort" aria-label="Sort"><option value="priority">${t("dash.sortPrio")}</option><option value="newest">${t("dash.sortNew")}</option><option value="oldest">${t("dash.sortOld")}</option></select>
    </div>
    <div class="table-wrap"><table class="data"><thead><tr>${["id", "photo", "cat", "desc", "loc", "prio", "sev", "dept", "date", "status"].map(c => `<th>${t("dash.col." + c)}</th>`).join("")}</tr></thead>
      <tbody id="rows"><tr><td colspan="10" class="empty">${t("common.loading")}</td></tr></tbody></table></div>`;

  if (window.Chart) {
    Chart.defaults.font.family = "'Public Sans', system-ui, sans-serif";
    state.charts.push(new Chart($("#chStatus"), { type: "doughnut", data: { labels: Object.keys(s.by_status).map(st), datasets: [{ data: Object.values(s.by_status), backgroundColor: ["#C9A227", "#5BC0EB", "#13315C", "#13A89E", "#2E9E5B"], borderWidth: 2 }] },
      options: { maintainAspectRatio: false, cutout: "62%", plugins: { legend: { position: "right" } } } }));
    state.charts.push(new Chart($("#chCat"), { type: "bar", data: { labels: Object.keys(s.by_category).map(l => cat(catByLabel[l] || "other")), datasets: [{ data: Object.values(s.by_category), backgroundColor: "#0B2545", hoverBackgroundColor: "#C9A227", borderRadius: 6 }] },
      options: { maintainAspectRatio: false, indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { ticks: { precision: 0 } } } } }));
  }

  async function load() {
    const params = new URLSearchParams({ q: $("#q").value, status: $("#dSt").value, category: $("#dCat").value, level: $("#dLvl").value, sort: $("#dSort").value });
    const rows = await api("/api/admin/reports?" + params);
    if (!$("#rows")) return; // user navigated away
    $("#rows").innerHTML = rows.length ? rows.map(r => `
      <tr class="click" data-id="${r.id}" tabindex="0">
        <td><b>${esc(r.code)}</b>${r.is_demo ? `<br><span class="badge src-demo">${t("src.demoShort")}</span>` : ""}${(r.duplicate_candidates || []).length ? `<br><span class="badge src-official">${t("src.dup")}</span>` : ""}</td>
        <td>${r.image_url ? `<img class="thumb" src="${esc(r.image_url)}" alt="">` : `<div class="thumb">${t("common.noPhoto")}</div>`}</td>
        <td>${esc(cat(r.category))}</td><td><div class="clip">${esc(tx(r.analysis?.description || r.description) || "–")}</div></td>
        <td><div class="clip">${esc(tx(r.location_text) || "")}</div><span class="small muted">${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}</span></td>
        <td>${lvlBadge(r.priority_level, r.priority_score)}${r.escalated ? `<br><span class="small" style="color:var(--critical);font-weight:700">${t("dash.escalated")}</span>` : ""}</td>
        <td>${esc(r.severity ? sev(r.severity) : "–")}</td><td>${esc(tx(r.department?.name) || "–")}</td>
        <td class="small">${fmtDate(r.created_at)}</td><td><span class="status">${esc(st(r.status))}</span></td></tr>`).join("")
      : `<tr><td colspan="10" class="empty">${t("dash.noMatch")}</td></tr>`;
    document.querySelectorAll("tr.click").forEach(tr => {
      tr.onclick = () => openReport(Number(tr.dataset.id), load);
      tr.onkeydown = e => { if (e.key === "Enter") openReport(Number(tr.dataset.id), load); };
    });
  }
  let timer;
  $("#q").oninput = () => { clearTimeout(timer); timer = setTimeout(load, 300); };
  ["#dSt", "#dCat", "#dLvl", "#dSort"].forEach(x => $(x).onchange = load);
  await load();
}

function fbVal(field, v) {
  if (v == null || v === "") return "–";
  if (field === "category") return cat(v);
  if (field === "priority_level") return lvl(v);
  return tx(v);
}

async function openReport(id, reload) {
  const [r, depts] = await Promise.all([api(`/api/admin/reports/${id}`), api("/api/admin/departments")]);
  const keys = Object.keys(state.config.categories);
  const bg = document.createElement("div");
  bg.className = "drawer-bg";
  bg.innerHTML = `<div class="drawer" role="dialog" aria-modal="true" aria-label="${esc(r.code)}">
    <div class="drawer-head"><div><h2 style="margin:0">${esc(r.code)}, ${esc(cat(r.category))}</h2>
      <span class="small muted">${t("dr.submitted", { d: fmtDate(r.created_at) })}</span> ${r.is_demo ? src("demo") : ""}</div>
      <button class="btn btn-outline btn-sm" id="closeDrawer">${t("common.close")}</button></div>
    ${modeNotice(r.analysis)}
    ${r.human_review_required ? `<div class="notice notice-crit"><b>${t("dr.review")}</b> ${esc(tx(r.priority_breakdown?.escalation_reason) || t("dr.critical"))}</div>` : ""}
    ${r.duplicate_candidates.length ? `<div class="notice notice-info">${t("dr.dup")}
      <ul>${r.duplicate_candidates.map(d => `<li>${t("dr.dupItem", { c: esc(d.code), m: esc(d.distance_m), h: esc(d.hours_apart) })} <button class="btn btn-outline btn-sm" data-merge="${d.id}" data-code="${esc(d.code)}">${t("dr.mergeBtn", { c: esc(d.code) })}</button></li>`).join("")}</ul></div>` : ""}
    ${r.merged_into ? `<div class="notice notice-info">${t("dr.wasMerged")}</div>` : ""}
    <div class="analysis-grid">
      <div>
        ${r.image_url ? `<img src="${esc(r.image_url)}" alt="" style="border-radius:10px;width:100%">` : `<div class="card empty">${t("dr.noPhotoDemo")}</div>`}
        <dl class="kv" style="margin-top:16px;grid-template-columns:1fr">
          <dt>${t("dr.cDesc")} ${src("citizen")}</dt><dd>${esc(tx(r.description) || "–")}</dd>
          <dt>${t("dr.cCat")} ${src("citizen")}</dt><dd>${r.citizen_category ? esc(cat(r.citizen_category)) : t("common.notGiven")}</dd>
          <dt>${t("dr.loc")} ${src("citizen")}</dt><dd>${esc(tx(r.location_text) || "")} <span class="small muted">${r.latitude.toFixed(5)}, ${r.longitude.toFixed(5)}</span></dd>
        </dl>
        <div id="miniMap" class="map-box" style="height:200px;margin-top:12px"></div>
      </div>
      <div>
        <div class="card" style="margin-bottom:16px"><h3>${t("dr.update")}</h3>
          <form id="editForm">
            <div class="grid-2" style="gap:12px">
              <div class="field"><label for="eCat">${t("kv.category")}</label><select id="eCat">${keys.map(k => `<option value="${k}" ${k === r.category ? "selected" : ""}>${esc(cat(k))}</option>`).join("")}</select></div>
              <div class="field"><label for="eLvl">${t("field.priority_level")}</label><select id="eLvl"><option value="">${r.priority_level ? t("dr.keep", { l: lvl(r.priority_level) }) : t("pr.notScored")}</option>${["Low", "Medium", "High", "Critical"].map(l => `<option value="${l}" ${l === r.priority_level ? "disabled" : ""}>${lvl(l)}</option>`).join("")}</select></div>
              <div class="field"><label for="eDep">${t("dr.dept")}</label><select id="eDep">${depts.map(d => `<option value="${d.id}" ${d.id === r.department_id ? "selected" : ""}>${esc(tx(d.name))}${d.provisional ? " " + t("dr.provisional") : ""}</option>`).join("")}</select></div>
              <div class="field"><label for="eSt">Status</label><select id="eSt">${state.config.statuses.map(x => `<option value="${x}" ${x === r.status ? "selected" : ""}>${st(x)}</option>`).join("")}</select></div>
            </div>
            <div class="field"><label for="eAsg">${t("dr.assigned")}</label><input type="text" id="eAsg" maxlength="120" value="${esc(r.assigned_to || "")}" placeholder="${esc(t("dr.assignedPh"))}"></div>
            <div class="field"><label for="eCom">${t("dr.reason")} <span class="muted small">${t("dr.reasonHint")}</span></label><input type="text" id="eCom" maxlength="1000"></div>
            <button class="btn btn-gold">${t("dr.saveBtn")}</button> <span id="saveMsg" class="small muted"></span>
          </form></div>
        <div class="card" style="margin-bottom:16px"><h3>${t("dr.ai")}</h3>${analysisBlock(r)}</div>
        <div class="card" style="margin-bottom:16px"><h3>${t("an.priority")}</h3>${priorityBlock(r)}</div>
        <div class="card" style="margin-bottom:16px"><h3>${t("dr.notes")}</h3>
          ${r.notes.length ? `<ul class="timeline">${r.notes.map(n => `<li>${esc(n.note)}<br><span class="small muted">${esc(tx(n.admin_name) || "")}, ${fmtDate(n.created_at)}</span></li>`).join("")}</ul>` : `<p class="muted">${t("dr.noNotes")}</p>`}
          <form id="noteForm" class="btn-row" style="margin-top:10px"><input type="text" id="noteTxt" maxlength="2000" placeholder="${esc(t("dr.notePh"))}" style="flex:1 1 220px" aria-label="${esc(t("dr.notePh"))}"><button class="btn btn-primary btn-sm">${t("dr.addNote")}</button></form></div>
        <div class="grid-2">
          <div class="card"><h3>${t("dr.history")}</h3><ul class="timeline">${r.history.map(h => `<li><b>${esc(st(h.new_status))}</b>${h.old_status ? ` <span class="muted">(${t("dr.from", { s: esc(st(h.old_status)) })})</span>` : ""}<br><span class="small muted">${esc(tx(h.changed_by_name) || t("dr.system"))}, ${fmtDate(h.changed_at)}${h.note ? ", " + esc(tx(h.note)) : ""}</span></li>`).join("")}</ul></div>
          <div class="card"><h3>${t("dr.corrections")}</h3>${r.feedback.length ? `<ul class="timeline">${r.feedback.map(f => `<li><b>${t("field." + f.field)}</b>: ${esc(fbVal(f.field, f.original_value))} → ${esc(fbVal(f.field, f.corrected_value))}<br><span class="small muted">${esc(tx(f.admin_name) || "")}, ${fmtDate(f.created_at)}${f.comment ? ", " + esc(f.comment) : ""}</span></li>`).join("")}</ul>` : `<p class="muted">${t("dr.noCorr")}</p>`}</div>
        </div>
      </div>
    </div></div>`;
  document.body.appendChild(bg);
  document.body.style.overflow = "hidden";
  const mini = L.map($("#miniMap", bg), { zoomControl: false }).setView([r.latitude, r.longitude], 16);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(mini);
  L.marker([r.latitude, r.longitude], { icon: dotIcon(r.priority_level, r.is_demo) }).addTo(mini);
  const close = (refresh) => { mini.remove(); bg.remove(); document.body.style.overflow = ""; document.removeEventListener("keydown", onKey); if (refresh) reload(); };
  const onKey = e => { if (e.key === "Escape") close(true); };
  document.addEventListener("keydown", onKey);
  $("#closeDrawer", bg).onclick = () => close(true);
  bg.onclick = e => { if (e.target === bg) close(true); };
  $("#closeDrawer", bg).focus();

  $("#editForm", bg).onsubmit = async e => {
    e.preventDefault();
    const body = { category: $("#eCat", bg).value, department_id: Number($("#eDep", bg).value), status: $("#eSt", bg).value,
      assigned_to: $("#eAsg", bg).value, comment: $("#eCom", bg).value };
    if ($("#eLvl", bg).value) body.priority_level = $("#eLvl", bg).value;
    try { await api(`/api/admin/reports/${id}`, { method: "PATCH", json: body }); toast(t("dr.saved")); close(false); openReport(id, reload); }
    catch (ex) { $("#saveMsg", bg).textContent = ex.message; }
  };
  $("#noteForm", bg).onsubmit = async e => {
    e.preventDefault();
    const note = $("#noteTxt", bg).value.trim(); if (!note) return;
    try { await api(`/api/admin/reports/${id}/notes`, { method: "POST", json: { note } }); close(false); openReport(id, reload); }
    catch (ex) { toast(ex.message); }
  };
  bg.querySelectorAll("[data-merge]").forEach(b => b.onclick = async () => {
    if (!confirm(t("dr.mergeConfirm", { a: r.code, b: b.dataset.code }))) return;
    try { await api(`/api/admin/reports/${id}/merge`, { method: "POST", json: { into_id: Number(b.dataset.merge) } }); toast(t("dr.merged")); close(true); }
    catch (ex) { toast(ex.message); }
  });
}

async function dashDepartments() {
  const box = $("#tab");
  const depts = await api("/api/admin/departments");
  box.innerHTML = `
    <div class="notice notice-info">${t("dep.info")}</div>
    <div class="table-wrap"><table class="data" style="min-width:760px"><thead><tr><th>${t("dep.cat")}</th><th>${t("dep.name")}</th><th>${t("dep.notes")}</th><th>${t("dep.prov")}</th><th></th></tr></thead><tbody>
    ${depts.map(d => `<tr data-id="${d.id}"><td>${esc(cat(d.category))}</td>
      <td><input type="text" class="dn" value="${esc(d.name)}" maxlength="120" aria-label="${esc(t("dep.name"))}"></td>
      <td><input type="text" class="dno" value="${esc(d.notes || "")}" maxlength="500" aria-label="${esc(t("dep.notes"))}"></td>
      <td><input type="checkbox" class="dp" ${d.provisional ? "checked" : ""} aria-label="${esc(t("dep.prov"))}"></td>
      <td><button class="btn btn-primary btn-sm ds">${t("common.save")}</button></td></tr>`).join("")}</tbody></table></div>`;
  box.querySelectorAll(".ds").forEach(b => b.onclick = async () => {
    const tr = b.closest("tr");
    try {
      await api(`/api/admin/departments/${tr.dataset.id}`, { method: "PUT", json: { name: $(".dn", tr).value, notes: $(".dno", tr).value, provisional: $(".dp", tr).checked } });
      toast(t("dep.saved"));
    } catch (ex) { toast(ex.message); }
  });
}

async function dashFeedback() {
  const box = $("#tab");
  const rows = await api("/api/admin/feedback");
  box.innerHTML = `
    <div class="notice notice-info">${t("log.info")}</div>
    <div class="btn-row" style="margin-bottom:12px"><button class="btn btn-outline btn-sm" id="exp">${t("log.download")}</button></div>
    <div class="table-wrap"><table class="data" style="min-width:760px"><thead><tr>${["report", "field", "orig", "corr", "admin", "comment", "time"].map(c => `<th>${t("log." + c)}</th>`).join("")}</tr></thead><tbody>
    ${rows.length ? rows.map(f => `<tr><td>${esc(f.code)}</td><td>${t("field." + f.field)}</td><td>${esc(fbVal(f.field, f.original_value))}</td><td><b>${esc(fbVal(f.field, f.corrected_value))}</b></td><td>${esc(tx(f.admin_name) || "")}</td><td>${esc(f.comment || "")}</td><td class="small">${fmtDate(f.created_at)}</td></tr>`).join("")
      : `<tr><td colspan="7" class="empty">${t("log.none")}</td></tr>`}</tbody></table></div>`;
  $("#exp").onclick = () => {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "fixmycity-ai-corrections.json"; a.click();
  };
}

/* ------------------------------------------------------------- start */
(async function start() {
  setLang(LANG);
  applyStatic();
  try { state.config = await api("/api/config"); }
  catch (e) { main.innerHTML = `<div class="page wrap"><div class="notice notice-err">${esc(e.message)}</div></div>`; return; }
  if (state.token) {
    try { state.user = (await api("/api/auth/me")).user; } catch { state.user = null; }
    if (!state.user) { state.token = null; localStorage.removeItem("fmc_token"); }
  }
  applyStatic();
  window.addEventListener("hashchange", router);
  router();
})();
