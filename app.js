/*
 * PonyFlix Web — versão leve estática
 * By: ScaryHollow
 *
 * Dados: episodios.json  { "Titulo": { "Temporada N": { "Ep": "embed_url" } } }
 * Capas: assets/covers/<slug>.png (título)  e  assets/tN.png (temporada)
 * Progresso: localStorage
 */

const $  = (sel) => document.querySelector(sel);
const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };

const PROGRESS_KEY = "ponyflix_progress";

let DATA = {};
let progress = loadProgress();

// estado de navegação
const state = { title: null, season: null };
// contexto do player
let playerCtx = null;

// ── Progresso ──────────────────────────────────────────
function loadProgress() {
  try { return JSON.parse(localStorage.getItem(PROGRESS_KEY)) || {}; }
  catch { return {}; }
}
function saveProgress() {
  try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress)); }
  catch (e) { console.warn("saveProgress", e); }
}
function markWatched(title, season, epNum) {
  progress[title] = progress[title] || {};
  progress[title][season] = progress[title][season] || {};
  progress[title][season].episodio = epNum;
  saveProgress();
}

// ── Helpers de capa ────────────────────────────────────
function slug(name) {
  return name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
             .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}
function titleCover(title) { return `assets/covers/${slug(title)}.png`; }
function seasonCover(season) {
  const num = season.trim().split(/\s+/).pop();
  return /^\d+$/.test(num) ? `assets/t${num}.png` : null;
}

// ── Componente card ────────────────────────────────────
function makeCard(coverSrc, label, badge, onClick) {
  const card = el("div", "card");
  card.addEventListener("click", onClick);

  if (coverSrc) {
    const img = el("img");
    img.loading = "lazy";
    img.alt = label;
    img.src = coverSrc;
    img.onerror = () => { img.remove(); addFallback(card, label); };
    card.appendChild(img);
  } else {
    addFallback(card, label);
  }

  const shade = el("div", "shade"); card.appendChild(shade);
  const lbl = el("div", "label"); lbl.textContent = label; card.appendChild(lbl);
  if (badge) { const b = el("div", "badge"); b.textContent = badge; card.appendChild(b); }
  return card;
}
function addFallback(card, label) {
  const fb = el("div", "fallback");
  fb.textContent = (label[0] || "?").toUpperCase();
  card.appendChild(fb);
}

// ── Telas ──────────────────────────────────────────────
function showView(node) {
  const view = $("#view");
  view.innerHTML = "";
  view.appendChild(node);
  view.scrollTop = 0;
  // reinicia animação
  view.style.animation = "none"; view.offsetHeight; view.style.animation = "";
}

function goTitles() {
  state.title = null; state.season = null;
  setHeader("PONYFLIX", false);
  const grid = el("div", "grid");
  for (const title of Object.keys(DATA)) {
    const last = progress[title] && Object.keys(progress[title]).length
      ? Object.keys(progress[title]).slice(-1)[0] : null;
    grid.appendChild(makeCard(titleCover(title), title, last ? "▸ " + last : null,
                              () => goSeasons(title)));
  }
  showView(grid);
}

function goSeasons(title) {
  state.title = title; state.season = null;
  setHeader(title.toUpperCase(), true);
  const seasons = DATA[title];
  const grid = el("div", "grid");
  for (const season of Object.keys(seasons)) {
    const ep = progress[title]?.[season]?.episodio;
    grid.appendChild(makeCard(seasonCover(season), season, ep ? "▸ ep." + ep : null,
                              () => goEpisodes(title, season)));
  }
  showView(grid);
}

function goEpisodes(title, season) {
  state.season = season;
  setHeader(season.toUpperCase(), true);
  const eps = Object.entries(DATA[title][season]); // [ [name, url], ... ]
  const lastEp = progress[title]?.[season]?.episodio;

  const list = el("div", "ep-list");
  eps.forEach(([name, url], idx) => {
    const num = idx + 1;
    const isCurrent = lastEp === num;
    const row = el("div", "ep-row" + (isCurrent ? " current" : ""));
    row.addEventListener("click", () => openPlayer(title, season, eps, idx));

    const n = el("div", "ep-num"); n.textContent = String(num).padStart(2, "0");
    const info = el("div", "ep-info");
    const nm = el("div", "ep-name"); nm.textContent = name; info.appendChild(nm);
    const bar = el("div", "ep-bar"); const fill = el("i");
    fill.style.width = isCurrent ? "100%" : "0";
    bar.appendChild(fill); info.appendChild(bar);
    const play = el("div", "ep-play"); play.textContent = isCurrent ? "▶ Continuar" : "▶";

    row.append(n, info, play);
    list.appendChild(row);
  });
  showView(list);
}

// ── Player ─────────────────────────────────────────────
function openPlayer(title, season, eps, idx) {
  playerCtx = { title, season, eps, idx };
  loadEp(idx);
  $("#player").classList.remove("hidden");
}
function loadEp(idx) {
  const { title, season, eps } = playerCtx;
  idx = Math.max(0, Math.min(idx, eps.length - 1));
  playerCtx.idx = idx;
  const [name, url] = eps[idx];
  $("#videoFrame").src = url;
  $("#playerTitle").textContent = name;
  $("#prevEp").disabled = idx === 0;
  $("#nextEp").disabled = idx === eps.length - 1;
  markWatched(title, season, idx + 1);
}
function closePlayer() {
  $("#player").classList.add("hidden");
  $("#videoFrame").src = "";  // para o vídeo
  if (playerCtx) goEpisodes(playerCtx.title, playerCtx.season); // reflete progresso
  playerCtx = null;
}

// ── Header / navegação ─────────────────────────────────
function setHeader(text, showBack) {
  $("#headerTitle").textContent = text;
  $("#backBtn").classList.toggle("hidden", !showBack);
}
function goBack() {
  if (state.season !== null) goSeasons(state.title);
  else if (state.title !== null) goTitles();
}

// ── Boot ───────────────────────────────────────────────
async function boot() {
  try {
    // Preferência: dados embutidos (episodios.js) — funciona ate via file://
    if (window.PONYFLIX_DATA) {
      DATA = window.PONYFLIX_DATA;
    } else {
      const res = await fetch("episodios.json");
      if (!res.ok) throw new Error("HTTP " + res.status);
      DATA = await res.json();
    }
  } catch (e) {
    $("#loading").textContent = "Erro ao carregar episódios.";
    $("#loading").style.color = "var(--accent)";
    console.error(e);
    return;
  }
  goTitles();
  setTimeout(() => {
    const sp = $("#splash");
    sp.style.opacity = "0";
    setTimeout(() => sp.classList.add("hidden"), 500);
    $("#app").classList.remove("hidden");
  }, 900);
}

// animação dos "..." do loading
let dotsTick = 0;
const dotsTimer = setInterval(() => {
  const d = ["carregando", "carregando ·", "carregando ··", "carregando ···"];
  dotsTick = (dotsTick + 1) % d.length;
  const l = $("#loading");
  if (l && l.style.color !== "var(--accent)") l.textContent = d[dotsTick];
}, 450);

// listeners
$("#backBtn").addEventListener("click", goBack);
$("#playerBack").addEventListener("click", closePlayer);
$("#prevEp").addEventListener("click", () => loadEp(playerCtx.idx - 1));
$("#nextEp").addEventListener("click", () => loadEp(playerCtx.idx + 1));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("#player").classList.contains("hidden")) closePlayer();
    else goBack();
  }
});

window.addEventListener("beforeunload", () => clearInterval(dotsTimer));
boot();
