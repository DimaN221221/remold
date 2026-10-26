/* Remold — логіка інтерфейсу. Дані й конвертація живуть у Python (desktop.py). */
"use strict";

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const icon = (name, cls = "sm") => `<svg class="ic ${cls}"><use href="#i-${name}"/></svg>`;

const state = {
  tab: "conv", items: [], sel: null, settings: {}, history: [], cats: {},
  lossy: new Set(), audioRemoldts: [], bitrates: [], running: false, rules: {},
  shellMenu: false, version: "", update: { source: "none" }, repoUrl: "",
};
let api = null;

const VIDEO_HEIGHTS = [0, 1080, 720, 480];
const IMAGE_SIZES = [0, 3840, 1920, 1280, 800];

// --- Підказки «?» ------------------------------------------------------------------

const TIP_SHARED = new Set(["quality_image", "quality_audio", "quality_video", "resolution", "imageSize"]);

function tipHtml(key) {
  let html = t(`tip.${key}`);
  if (key === "quality_audio") html += `<br><span class="mono">${bitrateTable()}</span>`;
  if (TIP_SHARED.has(key)) html += t("tip.shared");
  return html;
}

function bitrateTable() {
  let from = 10;
  return state.bitrates.map(([lim, k]) => {
    const row = `${from}–${lim}% → ${k} ${t("kbps")}`;
    from = lim + 1;
    return row;
  }).join("<br>");
}

const help = (key) => `<span class="help" tabindex="0" data-tip="${key}">?</span>`;

const tipEl = document.createElement("div");
tipEl.className = "tip";

function showTip(el) {
  tipEl.innerHTML = tipHtml(el.dataset.tip);
  if (!tipEl.isConnected) document.body.appendChild(tipEl);
  const r = el.getBoundingClientRect(), tr = tipEl.getBoundingClientRect();
  const x = Math.min(Math.max(8, r.left + r.width / 2 - tr.width / 2), innerWidth - tr.width - 8);
  let y = r.bottom + 8;
  if (y + tr.height > innerHeight - 8) y = r.top - tr.height - 8;
  tipEl.style.left = `${x}px`;
  tipEl.style.top = `${y}px`;
  tipEl.classList.add("show");
}
const hideTip = () => tipEl.classList.remove("show");

// --- Утиліти -------------------------------------------------------------------

function fmtSize(bytes) {
  if (bytes == null) return "—";
  const [b, kb, mb, gb] = UNITS[LANG];
  const m = bytes / 1048576;
  if (m >= 1024) return `${(m / 1024).toFixed(1)} ${gb}`;
  if (m >= 10) return `${Math.round(m)} ${mb}`;
  if (m >= 0.1) return `${m.toFixed(1)} ${mb}`;
  if (bytes < 1024) return `${bytes} ${b}`;
  return `${Math.round(bytes / 1024)} ${kb}`;
}

function fmtDate(iso) {
  const d = new Date(iso), now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86400000);
  if (diff === 0) return t("hist.today");
  if (diff === 1) return t("hist.yesterday");
  const m = MONTHS[LANG][d.getMonth()];
  const s = LANG === "en" ? `${m} ${d.getDate()}` : `${d.getDate()} ${m}`;
  return s + (d.getFullYear() !== now.getFullYear() ? ` ${d.getFullYear()}` : "");
}

const bitrateFor = (q) => (state.bitrates.find(([lim]) => q <= lim) || [0, 320])[1];
const itemById = (id) => state.items.find((it) => it.id === id);
const selected = () => itemById(state.sel);
const catLabel = (cat) => CAT_LABELS[LANG][cat] || cat;

let toastTimer;
function toast(text) {
  const el = $("#toast");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 4200);
}

let saveTimer;
function saveSettings(partial, debounce = 0) {
  Object.assign(state.settings, partial);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api.save_settings(partial), debounce);
}

// --- Мова, тема, навігація -----------------------------------------------------------

function currentTheme() {
  return state.settings.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

function renderTheme() {
  document.documentElement.dataset.theme = currentTheme();
  const chosen = state.settings.theme || "system";
  document.querySelectorAll("[data-theme-btn]").forEach((b) => b.classList.toggle("active", b.dataset.themeBtn === chosen));
}

function renderAll() {
  applyStatic();
  document.querySelectorAll("[data-lang]").forEach((b) => b.classList.toggle("active", b.dataset.lang === LANG));
  renderTheme();
  renderSettings();
  renderOutDir();
  renderQueue();
  renderPanel();
  renderUpdateBar();
  if (state.tab === "batch") renderBatch();
  if (state.tab === "hist") renderHistory();
}

function setTab(tab) {
  state.tab = tab;
  hideTip();
  if (tab === "batch") state.rules = { ...state.settings.rules };
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  for (const name of ["conv", "batch", "hist", "settings"]) $(`#screen-${name}`).classList.toggle("visible", tab === name);
  $("#panel").classList.toggle("visible", tab === "conv");
  if (tab === "batch") renderBatch();
  if (tab === "hist") renderHistory();
  if (tab === "settings") renderSettings();
}

// --- Черга -------------------------------------------------------------------------

function rowSize(it) {
  if (it.status === "done") return `${fmtSize(it.size)} → <em>${fmtSize(it.resultSize)}</em>`;
  return fmtSize(it.size);
}

function rowStatus(it) {
  if (it.status === "running") return [`${Math.round(it.progress * 100)}%`, "run"];
  return [t(`status.${it.status}`), { done: "ok", error: "err" }[it.status] || ""];
}

function rowBar(it) {
  // готові рядки без смуги: стан «Готово» і так видно, а суцільні лінії лише шумлять
  if (it.status === "error") return ["100%", "err"];
  if (it.status === "running") return [`${(it.progress * 100).toFixed(1)}%`, ""];
  return ["0%", ""];
}

function rowHtml(it) {
  const [st, stCls] = rowStatus(it);
  const [w, barCls] = rowBar(it);
  const folder = it.path.slice(0, it.path.length - it.name.length - 1);
  return `<div class="row${it.id === state.sel ? " sel" : ""}" data-id="${it.id}">
    <span class="type t-${it.category}"><i></i>${esc(it.ext)}</span>
    <span class="name"><b title="${esc(it.path)}">${esc(it.name)}</b><small>‎${esc(folder)}‎</small></span>
    <span class="size">${rowSize(it)}</span>
    <span class="fmt">${esc(it.target.toUpperCase())}</span>
    <span class="st ${stCls}">${esc(st)}</span>
    <span class="bar"><div class="${barCls}" style="width:${w}"></div></span>
    <button class="row-x" title="${esc(t("row.remove"))}">${icon("x", "xs")}</button>
  </div>`;
}

function renderQueue() {
  const q = $("#queue");
  q.innerHTML = state.items.map(rowHtml).join("");
  q.classList.toggle("running", state.running);
  $("#screen-conv").classList.toggle("empty", !state.items.length);
  renderSummary();
  renderFooter();
}

function updateRow(it) {
  const el = document.querySelector(`.row[data-id="${it.id}"]`);
  if (!el) return renderQueue();
  const [st, stCls] = rowStatus(it);
  const [w, barCls] = rowBar(it);
  el.querySelector(".size").innerHTML = rowSize(it);
  el.querySelector(".fmt").textContent = it.target.toUpperCase();
  const status = el.querySelector(".st");
  status.textContent = st;
  status.className = `st ${stCls}`;
  const bar = el.querySelector(".bar > div");
  bar.className = barCls;
  bar.style.width = w;
}

function renderSummary() {
  const done = state.items.filter((it) => it.status === "done").length;
  $("#summary").textContent = state.items.length ? t("conv.summary", { files: filesWord(state.items.length), done }) : "";
}

function renderFooter() {
  const run = $("#btn-run");
  run.classList.toggle("running", state.running);
  $("#run-label").textContent = state.running ? t("btn.stop") : t("btn.run");
  $("#run-ic").innerHTML = `<use href="#i-${state.running ? "stop" : "play"}"/>`;
  $("#btn-reset").disabled = state.running || !state.items.length;
}

function select(id) {
  state.sel = id;
  document.querySelectorAll(".row").forEach((r) => r.classList.toggle("sel", +r.dataset.id === id));
  renderPanel();
}

function addItems({ added, skipped }) {
  if (added.length) {
    state.items.push(...added);
    if (state.sel == null || !selected()) state.sel = added[0].id;
    if (state.tab !== "conv") setTab("conv");
    renderQueue();
    renderPanel();
  }
  if (skipped.length) {
    const names = skipped.slice(0, 3).join(", ") + (skipped.length > 3 ? t("toast.more", { n: skipped.length - 3 }) : "");
    toast(t("toast.skipped", { files: filesWord(skipped.length), names }));
  }
}

async function removeItem(id) {
  const it = itemById(id);
  if (!it || state.running) return;
  await api.remove(id);
  const idx = state.items.indexOf(it);
  state.items.splice(idx, 1);
  if (state.sel === id) state.sel = (state.items[idx] || state.items[idx - 1] || {}).id ?? null;
  renderQueue();
  renderPanel();
}

// --- Оцінка розміру: рахує Python пробним стисненням з поточними налаштуваннями ---

const estCache = new Map();
let estTimer = null, estToken = 0;

const estimable = (it) => ["image", "audio", "video"].includes(it.category);
function estKey(it) {
  const s = state.settings;
  return [it.id, it.target, s.quality, s.image_max_size, s.video_height].join("|");
}

function estNote(it) {
  const tg = it.target;
  if (state.audioRemoldts.includes(tg) && it.category !== "image") {
    if (tg === "wav" || tg === "aiff") return t("est.pcm");
    if (tg === "flac") return t("est.lossless");
    return t("est.kbps", { fmt: tg.toUpperCase(), k: bitrateFor(state.settings.quality) });
  }
  if (it.category === "video") return tg === "gif" ? t("est.gif") : t("est.sample");
  return "";
}

function estimateHtml(it) {
  const head = (key, tip) => `<div class="caps"><span>${esc(t(key))}</span>${tip ? help("estimate") : ""}</div>`;
  if (it.status === "done" && it.resultSize != null) {
    return head("est.result") + `<div class="big">${fmtSize(it.resultSize)}</div>`;
  }
  if (!estimable(it)) return head("est.label") + `<div class="note">${esc(t("est.depends"))}</div>`;
  const big = (v, note) => head("est.label", true) + `<div class="big">${v}</div>` + (note ? `<div class="note">${esc(note)}</div>` : "");
  if (it.category !== "image" && it.duration === 0) return big("—", t("est.noDuration"));
  const key = estKey(it);
  if (!estCache.has(key)) {
    const slow = it.category === "video" && !state.audioRemoldts.includes(it.target);
    return big(`<small>${esc(t("est.pending"))}</small>`, slow ? t("est.slow") : "");
  }
  const bytes = estCache.get(key);
  if (bytes == null) return big("—", t("est.failed"));
  return big(`≈ ${fmtSize(bytes)}`, estNote(it));
}

function updateEstimate() {
  const it = selected(), el = $("#estimate");
  if (it && el) el.innerHTML = estimateHtml(it);
}

function requestEstimate(delay = 120) {
  clearTimeout(estTimer);
  const it = selected();
  if (!it || !estimable(it) || it.status === "done") return;
  if (it.category !== "image" && it.duration == null) return;  // чекаємо на тривалість (подія meta)
  const key = estKey(it);
  if (estCache.has(key)) return;
  estTimer = setTimeout(async () => {
    const token = ++estToken;
    const s = state.settings;
    const res = await api.estimate(it.id, it.target, {
      quality: s.quality, image_max_size: s.image_max_size, video_height: s.video_height,
    });
    if (token !== estToken) return;  // поки рахували, налаштування вже змінились
    estCache.set(key, res.bytes);
    if (selected() === it && estKey(it) === key) updateEstimate();
  }, delay);
}

// --- Інспектор -----------------------------------------------------------------------

function cell(label, active, attrs, disabled) {
  return `<button class="cell${active ? " active" : ""}" ${attrs}${disabled ? " disabled" : ""}>${esc(label)}</button>`;
}

function renderPanel() {
  hideTip();
  const p = $("#panel");
  const it = selected();
  if (!it) {
    p.innerHTML = `<div class="empty-insp">${esc(t("insp.none"))}</div>`;
    return;
  }
  const locked = it.status === "running" || it.status === "queued";
  const fmtCells = (list) => `<div class="cells">${list.map((f) =>
    cell(f.toUpperCase(), f === it.target, `data-fmt="${f}"`, locked)).join("")}</div>`;
  let fmts;
  if (it.category === "video") {
    fmts = fmtCells(it.formats.filter((f) => !state.audioRemoldts.includes(f)))
      + `<div class="caps"><span>${esc(t("insp.audioOnly"))}</span>${help("audioOnly")}</div>`
      + fmtCells(it.formats.filter((f) => state.audioRemoldts.includes(f)));
  } else {
    fmts = fmtCells(it.formats);
  }
  const folder = it.path.slice(0, it.path.length - it.name.length - 1);
  const dims = it.width && it.height ? `<div class="sub-hint">${esc(t("insp.now", { w: it.width, h: it.height }))}</div>` : "";

  let html = `<div class="sec"><div class="caps">${esc(t("insp.file"))}</div>
      <div class="f-name">${esc(it.name)}</div><div class="f-path" title="${esc(folder)}">‎${esc(folder)}‎</div></div>
    <div class="sec"><div class="caps"><span>${esc(t("insp.to"))}</span>${help("format")}</div>${fmts}</div>`;

  if (state.lossy.has(it.target)) {
    const q = state.settings.quality;
    const qTip = state.audioRemoldts.includes(it.target) ? "quality_audio" : `quality_${it.category === "video" ? "video" : "image"}`;
    html += `<div class="sec"><div class="caps"><span>${esc(t("insp.quality"))}</span>${help(qTip)}<span class="val" id="q-val">${q}%</span></div>
      <input type="range" min="10" max="100" value="${q}" id="q-range" style="--p:${((q - 10) / 90) * 100}%"></div>`;
  }
  if (it.category === "video" && !state.audioRemoldts.includes(it.target) && it.target !== "gif") {
    html += `<div class="sec"><div class="caps"><span>${esc(t("insp.resolution"))}</span>${help("resolution")}</div>${dims}
      <div class="cells">${VIDEO_HEIGHTS.map((v) => cell(v ? `${v}p` : t("insp.original"), state.settings.video_height === v, `data-vh="${v}"`)).join("")}</div></div>`;
  }
  if (it.category === "image") {
    html += `<div class="sec"><div class="caps"><span>${esc(t("insp.imageSize"))}</span>${help("imageSize")}</div>${dims}
      <div class="cells wide">${IMAGE_SIZES.map((v) => cell(v || t("insp.noChange"), state.settings.image_max_size === v, `data-is="${v}"`)).join("")}</div></div>`;
  }
  html += `<div class="sec estimate" id="estimate">${estimateHtml(it)}</div>`;

  if (it.status === "error") {
    html += `<div class="sec"><div class="err-box"><b>${esc(t("insp.errTitle"))}</b>${esc(it.error)}</div>
      <div class="actions"><button class="btn primary" data-act="retry">${esc(t("btn.retry"))}</button></div></div>`;
  } else if (it.status === "done") {
    html += `<div class="sec"><button class="btn" data-act="reveal">${icon("folder")}${esc(t("btn.reveal"))}</button></div>`;
  }
  p.innerHTML = html;
  requestEstimate();
}

// --- Пакетна обробка -------------------------------------------------------------

function renderBatch() {
  $("#rules").innerHTML = Object.entries(state.cats).map(([cat, info]) => {
    const n = state.items.filter((it) => it.category === cat).length;
    const opts = info.formats.map((f) => `<option value="${f}"${f === state.rules[cat] ? " selected" : ""}>${f.toUpperCase()}</option>`).join("");
    return `<div class="rule t-${cat}"><i></i><b>${esc(t("batch.all", { type: catLabel(cat) }))}</b>
      <span class="cnt">${esc(filesWord(n))}</span>${icon("arrow")}
      <select class="fmt-select" data-cat="${cat}">${opts}</select></div>`;
  }).join("");
  renderOutDir();
  $("#name-tpl").value = state.settings.name_template;
}

// --- Папка збереження ---------------------------------------------------------------

function renderOutDir() {
  const dir = state.settings.out_dir;
  $("#out-dir").textContent = dir || t("out.same");
  $("#out-dir").title = dir || "";
  $("#out-hint").innerHTML = dir ? `<button class="link" id="out-reset">${esc(t("out.reset"))}</button>` : esc(t("out.pick"));
  // ‎ утримує порядок символів шляху при direction: rtl (обрізання з початку)
  $("#out-pill-path").textContent = dir ? `‎${dir}‎` : t("out.same");
  $("#out-pill").title = dir ? `${dir}\n${t("out.change")}` : t("out.pick");
  $("#out-pill-x").hidden = !dir;
}

async function chooseOutDir() {
  const dir = await api.choose_out_dir();
  if (dir) { state.settings.out_dir = dir; renderOutDir(); }
}

function resetOutDir() {
  saveSettings({ out_dir: "" });
  renderOutDir();
}

// --- Історія ---------------------------------------------------------------------

function renderHistory() {
  const h = state.history;
  $("#btn-clear-hist").hidden = !h.length;
  if (!h.length) {
    $("#hist").innerHTML = `<div class="h-empty">${esc(t("hist.empty"))}</div>`;
    return;
  }
  $("#hist").innerHTML = h.map((e, i) => {
    let saved = "", grew = false;
    if (e.srcSize && e.outSize != null) {
      const ratio = e.outSize / e.srcSize;
      const pct = Math.round((1 - ratio) * 100);
      grew = pct < 0;
      if (ratio >= 10) saved = `×${Math.round(ratio)}`;  // напр. TXT → PDF: замість «+4589%»
      else saved = pct > 0 ? `−${pct}%` : pct < 0 ? `+${-pct}%` : "0%";
    }
    return `<div class="h-row" data-i="${i}" title="${esc(e.path || "")}"><b>${esc(e.name)}</b>
      <span class="h-fmt">${esc(e.from)} → ${esc(e.to)}</span>
      <span class="h-saved${grew ? " grew" : ""}">${saved}</span><span class="h-date">${esc(fmtDate(e.date))}</span></div>`;
  }).join("");
}

// --- Налаштування та оновлення --------------------------------------------------------

function setSwitch(el, on) { el.setAttribute("aria-checked", on ? "true" : "false"); }

function renderSettings() {
  setSwitch($("#sw-menu"), state.shellMenu);
  setSwitch($("#sw-auto"), state.settings.auto_update !== false);
  const u = state.update;
  $("#ver").textContent = `v${state.version}`;
  $("#about-ver").textContent = t("set.version", { v: state.version });
  $("#upd-info").textContent = `${t("set.version", { v: state.version })} · ${t(`set.source.${u.source}`)}`;
  $("#btn-check").disabled = u.source === "none" || u.busy;
  $("#sw-auto").disabled = u.source === "none";
  const status = $("#upd-status");
  status.className = "status-line";
  if (u.busy) status.textContent = t(u.busy === "install" ? "set.installing" : "set.checking");
  else if (u.error) { status.textContent = t("set.checkFailed", { err: u.error }); status.classList.add("err"); }
  else if (u.ready) { status.textContent = t(u.source === "git" ? "upd.readyGit" : "upd.ready", { v: u.latest }); status.classList.add("accent"); }
  else if (u.available) { status.textContent = t("set.available", { v: u.latest }); status.classList.add("accent"); }
  else if (u.checked) { status.textContent = t("set.latest"); status.classList.add("ok"); }
  else status.textContent = "";
  const inst = $("#btn-install");
  inst.hidden = !(u.available || u.ready) || !!u.busy;
  inst.textContent = u.ready ? t("upd.restart") : t("set.install");
  $("#upd-dot").hidden = !(u.available || u.ready);
}

function renderUpdateBar() {
  const u = state.update;
  const show = (u.available || u.ready) && !u.dismissed && !u.busy;
  $("#update-bar").hidden = !show;
  if (!show) return;
  $("#update-text").textContent = u.ready ? t(u.source === "git" ? "upd.readyGit" : "upd.ready", { v: u.latest }) : t("upd.available", { v: u.latest });
  $("#update-go").textContent = u.ready ? t("upd.restart") : t("upd.install");
}

async function installUpdate() {
  const u = state.update;
  if (u.ready) return api.restart_to_update();
  Object.assign(u, { busy: "install", error: "" });
  renderSettings(); renderUpdateBar();
  const res = await api.install_update();
  Object.assign(state.update, res, { busy: false });
  renderSettings(); renderUpdateBar();
}

async function checkUpdates() {
  Object.assign(state.update, { busy: "check", error: "" });
  renderSettings();
  const res = await api.check_updates();
  Object.assign(state.update, res, { busy: false, checked: true });
  renderSettings(); renderUpdateBar();
}

// --- Події з Python ----------------------------------------------------------------

window.app = {
  onEvent(kind, data) {
    if (kind === "item") {
      const it = itemById(data.id);
      if (!it) return;
      Object.assign(it, data);
      updateRow(it);
      renderSummary();
      if (it.id === state.sel) renderPanel();
    } else if (kind === "progress") {
      const it = itemById(data.id);
      if (!it || it.status !== "running") return;
      it.progress = data.progress;
      updateRow(it);
    } else if (kind === "meta") {
      const it = itemById(data.id);
      if (!it) return;
      Object.assign(it, data);
      if (it.id === state.sel) renderPanel();  // розміри кадру й оцінка з'являються після аналізу файлу
    } else if (kind === "running") {
      state.running = data;
      $("#queue").classList.toggle("running", data);
      renderFooter();
      if (selected()) renderPanel();
      if (!data) {
        const errs = state.items.filter((it) => it.status === "error").length;
        if (state.items.some((it) => it.status === "cancelled")) toast(t("toast.stopped"));
        else if (errs) toast(t("toast.errors", { n: errs }));
      }
    } else if (kind === "history") {
      state.history.unshift(data);
      if (state.tab === "hist") renderHistory();
    } else if (kind === "dropped") {
      addItems(data);
    } else if (kind === "update") {
      Object.assign(state.update, data);
      renderSettings(); renderUpdateBar();
    }
  },
};

// --- Обробники інтерфейсу ----------------------------------------------------------

function wire() {
  document.querySelectorAll(".nav-btn").forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));

  document.querySelectorAll("[data-lang]").forEach((b) => (b.onclick = async () => {
    if (b.dataset.lang === LANG) return;
    LANG = b.dataset.lang;
    await api.save_settings({ lang: LANG });  // Python також перереєструє меню провідника новою мовою
    state.settings.lang = LANG;
    renderAll();
  }));
  document.querySelectorAll("[data-theme-btn]").forEach((b) => (b.onclick = () => {
    saveSettings({ theme: b.dataset.themeBtn === "system" ? null : b.dataset.themeBtn });
    renderTheme();
  }));
  $("#sw-menu").onclick = async () => {
    const want = !state.shellMenu;
    const res = await api.set_shell_menu(want);
    state.shellMenu = res.enabled;
    renderSettings();
    toast(res.ok ? t(want ? "toast.menuOn" : "toast.menuOff") : t("toast.menuFail", { err: res.error }));
  };
  $("#sw-auto").onclick = () => {
    saveSettings({ auto_update: state.settings.auto_update === false });
    renderSettings();
  };
  $("#btn-check").onclick = checkUpdates;
  $("#btn-install").onclick = installUpdate;
  $("#update-go").onclick = installUpdate;
  $("#update-later").onclick = () => { state.update.dismissed = true; renderUpdateBar(); };
  $("#btn-repo").onclick = () => api.open_repo();

  const pick = async () => addItems(await api.pick_files());
  $("#dropzone").onclick = pick;
  $("#dropzone").onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } };
  $("#btn-add").onclick = pick;

  $("#queue").addEventListener("click", (e) => {
    const row = e.target.closest(".row");
    if (!row) return;
    const id = +row.dataset.id;
    if (e.target.closest(".row-x")) return removeItem(id);
    select(id);
  });
  $("#queue").addEventListener("dblclick", (e) => {
    const row = e.target.closest(".row");
    const it = row && itemById(+row.dataset.id);
    if (it && it.status === "done") api.reveal_item(it.id);
  });

  const run = async () => {
    if (state.running) { api.cancel(); return; }
    if (!state.items.length) return toast(t("toast.addFirst"));
    if (!(await api.start(null))) toast(t("toast.allDone"));
  };
  $("#btn-run").onclick = run;
  $("#btn-reset").onclick = async () => {
    if (state.running) return;
    await api.clear();
    state.items = [];
    state.sel = null;
    renderQueue();
    renderPanel();
  };

  const panel = $("#panel");
  panel.addEventListener("click", async (e) => {
    const it = selected();
    if (!it) return;
    const b = e.target.closest("button");
    if (!b || b.disabled) return;
    if (b.dataset.fmt) {
      await api.set_target(it.id, b.dataset.fmt);
      it.target = b.dataset.fmt;
      if (it.status !== "waiting" && it.status !== "running") Object.assign(it, { status: "waiting", progress: 0, error: "", resultSize: null });
      updateRow(it);
      renderSummary();
      renderPanel();
    } else if (b.dataset.vh != null) {
      saveSettings({ video_height: +b.dataset.vh });
      renderPanel();
    } else if (b.dataset.is != null) {
      saveSettings({ image_max_size: +b.dataset.is });
      renderPanel();
    } else if (b.dataset.act === "retry") {
      api.start([it.id]);
    } else if (b.dataset.act === "reveal") {
      api.reveal_item(it.id);
    }
  });
  panel.addEventListener("input", (e) => {
    if (e.target.id !== "q-range") return;
    const q = +e.target.value;
    e.target.style.setProperty("--p", `${((q - 10) / 90) * 100}%`);
    saveSettings({ quality: q }, 400);
    $("#q-val").textContent = `${q}%`;
    updateEstimate();
    requestEstimate(selected() && selected().category === "video" ? 600 : 300);
  });

  $("#rules").addEventListener("change", (e) => {
    const s = e.target.closest(".fmt-select");
    if (s) state.rules[s.dataset.cat] = s.value;
  });
  $("#out-card").addEventListener("click", (e) => {
    if (e.target.closest(".help")) return;
    e.target.id === "out-reset" ? resetOutDir() : chooseOutDir();
  });
  $("#out-pill").addEventListener("click", (e) => {
    if (e.target.closest(".help")) return;
    e.target.closest("#out-pill-x") ? resetOutDir() : chooseOutDir();
  });

  // підказки: наведення мишею або фокус з клавіатури
  document.addEventListener("mouseover", (e) => { const h = e.target.closest("[data-tip]"); if (h) showTip(h); });
  document.addEventListener("mouseout", (e) => { if (e.target.closest("[data-tip]")) hideTip(); });
  document.addEventListener("focusin", (e) => { if (e.target.dataset && e.target.dataset.tip) showTip(e.target); });
  document.addEventListener("focusout", hideTip);
  document.addEventListener("scroll", hideTip, true);

  const tpl = $("#name-tpl");
  tpl.addEventListener("change", () => saveSettings({ name_template: tpl.value.trim() || "{name}" }));
  tpl.addEventListener("keydown", (e) => { if (e.key === "Enter") tpl.blur(); });

  $("#btn-apply").onclick = async () => {
    state.items = await api.apply_rules(state.rules);
    state.settings.rules = { ...state.rules };
    setTab("conv");
    renderQueue();
    renderPanel();
  };

  $("#hist").addEventListener("click", (e) => {
    const row = e.target.closest(".h-row");
    const entry = row && state.history[+row.dataset.i];
    if (entry && entry.path) api.reveal_path(entry.path);
  });
  $("#btn-clear-hist").onclick = async () => {
    await api.clear_history();
    state.history = [];
    renderHistory();
  };

  // підсвічування зони під час перетягування (самі шляхи файлів отримує Python)
  let depth = 0;
  const dz = $("#dropzone");
  const dzText = dz.querySelector(".drop-text b");
  const setDrag = (on) => { dz.classList.toggle("drag", on); dzText.textContent = t(on ? "drop.release" : "drop.title"); };
  document.addEventListener("dragenter", (e) => { e.preventDefault(); depth++; if (state.tab !== "conv") setTab("conv"); setDrag(true); });
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; setDrag(false); } });
  document.addEventListener("drop", (e) => { e.preventDefault(); depth = 0; setDrag(false); });

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (e.ctrlKey && e.key === "o") { e.preventDefault(); pick(); return; }
    if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); run(); return; }
    if (!e.ctrlKey && !e.altKey && ["1", "2", "3", "4"].includes(e.key)) {
      setTab(["conv", "batch", "hist", "settings"][+e.key - 1]);
      return;
    }
    if (state.tab !== "conv" || !state.items.length) return;
    const idx = state.items.findIndex((it) => it.id === state.sel);
    if (e.key === "Delete" && state.sel != null) removeItem(state.sel);
    else if (e.key === "ArrowDown") { e.preventDefault(); select(state.items[Math.min(idx + 1, state.items.length - 1)].id); }
    else if (e.key === "ArrowUp") { e.preventDefault(); select(state.items[Math.max(idx - 1, 0)].id); }
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderTheme);
}

async function boot(apiImpl) {
  if (api) return;
  api = apiImpl;
  const d = await api.init();
  Object.assign(state, {
    settings: d.settings, history: d.history, items: d.items, cats: d.categories,
    lossy: new Set(d.lossy), audioRemoldts: d.audioRemoldts, bitrates: d.bitrates, running: d.running,
    shellMenu: !!d.shellMenu, version: d.version, update: { ...d.update }, repoUrl: d.repoUrl,
  });
  LANG = d.lang;
  state.sel = state.items.length ? state.items[0].id : null;
  wire();
  setTab("conv");
  renderAll();
}

window.addEventListener("pywebviewready", () => boot(window.pywebview.api));
if (window.pywebview && window.pywebview.api && window.pywebview.api.init) boot(window.pywebview.api);
// перегляд у браузері без Python: index.html?demo
if (location.search.includes("demo")) {
  const s = document.createElement("script");
  s.src = "demo.js";
  s.onload = () => boot(window.DemoApi());
  document.head.appendChild(s);
}
