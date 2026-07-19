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
// config opcional da página (definida em window.APP_CONFIG antes deste script)
const CONFIG = window.APP_CONFIG || {};

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
function titleCover(title) { return `assets/covers/${slug(title)}.webp`; }
function seasonCover(season) {
  const num = season.trim().split(/\s+/).pop();
  return /^\d+$/.test(num) ? `assets/t${num}.png` : null;
}

// ── Capas automáticas (TMDB via meusdoramas) ───────────
// Extrai o id TMDB e a origem a partir do link do 1º episódio da série.
function seriesRef(title) {
  const seasons = DATA[title]; if (!seasons) return null;
  const firstSeason = Object.values(seasons)[0]; if (!firstSeason) return null;
  const firstUrl = Object.values(firstSeason)[0]; if (!firstUrl) return null;
  const m = firstUrl.match(/\/video\/(\d+)\//);
  try { return m ? { id: m[1], origin: new URL(firstUrl).origin } : null; }
  catch { return null; }
}

const posterCache = {};
async function fetchPoster(ref) {
  if (!ref) return null;
  if (posterCache[ref.id]) return posterCache[ref.id];
  const cached = localStorage.getItem("poster_" + ref.id);
  if (cached) return (posterCache[ref.id] = cached);
  try {
    const r = await fetch(`${ref.origin}/search.php?term=${ref.id}`);
    const arr = await r.json();
    const it = arr.find((x) => String(x.tmdb) === String(ref.id)) || arr[0];
    if (!it || !it.image_url) return null;
    const url = it.image_url.replace("/w185/", "/w500/"); // resolução maior
    localStorage.setItem("poster_" + ref.id, url);
    return (posterCache[ref.id] = url);
  } catch (e) { console.warn("[poster]", e); return null; }
}

// Carrega o pôster de forma assíncrona e injeta no card (mantém a inicial até chegar).
async function loadPoster(card, title) {
  const url = await fetchPoster(seriesRef(title));
  if (!url || !card.isConnected) return;
  const img = el("img");
  img.loading = "lazy"; img.alt = title; img.src = url;
  img.onerror = () => img.remove();
  img.onload = () => { const fb = card.querySelector(".fallback"); if (fb) fb.remove(); };
  card.insertBefore(img, card.firstChild);
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
  setHeader(CONFIG.homeTitle || "PONYFLIX", false);
  const grid = el("div", "grid");
  for (const title of Object.keys(DATA)) {
    const last = progress[title] && Object.keys(progress[title]).length
      ? Object.keys(progress[title]).slice(-1)[0] : null;
    const card = makeCard(CONFIG.autoCovers ? null : titleCover(title),
                          title, last ? "▸ " + last : null, () => goSeasons(title));
    if (CONFIG.autoCovers) loadPoster(card, title);
    grid.appendChild(card);
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
    // MLP usa a arte tN.png; animes reaproveitam o pôster da série em cada temporada.
    const card = makeCard(CONFIG.seasonCovers ? seasonCover(season) : null,
                          season, ep ? "▸ ep." + ep : null, () => goEpisodes(title, season));
    if (!CONFIG.seasonCovers && CONFIG.autoCovers) loadPoster(card, title);
    grid.appendChild(card);
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
  const audios = (window.PONYFLIX_AUDIOS && window.PONYFLIX_AUDIOS[title]) || null;
  playerCtx = { title, season, eps, idx, audios, audioId: null };
  // áudio padrão = o id que já está na URL do episódio (o base/legendado)
  const m = eps[0] && eps[0][1].match(/\/video\/(\d+)\//);
  playerCtx.audioId = m ? m[1] : null;
  buildAudioSelector();
  loadEp(idx);
  $("#player").classList.remove("hidden");
}

// URL do episódio já com o áudio (dub/leg) selecionado aplicado.
function epUrl(idx) {
  let u = playerCtx.eps[idx][1];
  if (playerCtx.audioId) u = u.replace(/(\/video\/)\d+(\/)/, `$1${playerCtx.audioId}$2`);
  return u;
}

// Botões Legendado/Dublado no topo do player (só quando há 2+ versões).
function buildAudioSelector() {
  const box = $("#audioSel"); box.innerHTML = "";
  const audios = playerCtx.audios;
  if (!audios || Object.keys(audios).length < 2) return;
  for (const [label, id] of Object.entries(audios)) {
    const b = el("button", "audio-btn");
    b.textContent = label;
    if (String(id) === String(playerCtx.audioId)) b.classList.add("active");
    b.addEventListener("click", () => {
      if (String(id) === String(playerCtx.audioId)) return;
      playerCtx.audioId = String(id);
      buildAudioSelector();       // re-destaca o ativo
      loadEp(playerCtx.idx);      // recarrega no mesmo episódio
    });
    box.appendChild(b);
  }
}

function loadEp(idx) {
  const { title, season, eps } = playerCtx;
  idx = Math.max(0, Math.min(idx, eps.length - 1));
  playerCtx.idx = idx;
  const [name] = eps[idx];
  $("#playerTitle").textContent = name;
  $("#prevEp").disabled = idx === 0;
  $("#nextEp").disabled = idx === eps.length - 1;
  markWatched(title, season, idx + 1);

  if (isCasting()) {
    // Toca na TV em vez do iframe
    $("#videoFrame").src = "";
    castLoadCurrent();
  } else {
    $("#castPanel").classList.add("hidden");
    $("#videoFrame").src = epUrl(idx);
  }
}
function closePlayer() {
  $("#player").classList.add("hidden");
  $("#videoFrame").src = "";  // para o vídeo (a TV, se estiver transmitindo, segue)
  if (playerCtx) goEpisodes(playerCtx.title, playerCtx.season); // reflete progresso
  playerCtx = null;
}

// ── Chromecast (Google Cast) ───────────────────────────
let castContext = null;

function isCasting() {
  return !!(castContext && castContext.getCurrentSession());
}

// O SDK chama isto quando cast_sender.js termina de carregar.
window.__onGCastApiAvailable = function (available) {
  if (!available || !window.cast || !window.chrome) return;
  castContext = cast.framework.CastContext.getInstance();
  castContext.setOptions({
    receiverApplicationId: chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
    autoJoinPolicy: chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
  });
  castContext.addEventListener(
    cast.framework.CastContextEventType.SESSION_STATE_CHANGED,
    (e) => {
      const S = cast.framework.SessionState;
      if (e.sessionState === S.SESSION_STARTED || e.sessionState === S.SESSION_RESUMED) {
        if (playerCtx) { $("#videoFrame").src = ""; castLoadCurrent(); }
      } else if (e.sessionState === S.SESSION_ENDED) {
        // Voltou pro celular/PC: retoma o iframe do episódio atual
        $("#castPanel").classList.add("hidden");
        if (playerCtx) $("#videoFrame").src = epUrl(playerCtx.idx);
      }
    }
  );
};

// Resolve a URL direta (HLS/MP4) a partir do embed do pony.tube (PeerTube API).
async function resolveDirectUrl(embedUrl) {
  const m    = embedUrl.match(/\/embed\/([a-zA-Z0-9\-_]+)/);
  const host = embedUrl.match(/https?:\/\/([^/]+)/);
  if (!m || !host) return null;
  const api = `https://${host[1]}/api/v1/videos/${m[1]}`;
  const res = await fetch(api);
  if (!res.ok) throw new Error("API " + res.status);
  const d = await res.json();

  const resId = (f) => (f.resolution && typeof f.resolution === "object")
    ? (f.resolution.id || 0) : (f.resolution || 0);

  // 1) MP4 progressivo na maior resolução (top-level ou dentro do HLS)
  let files = (d.files && d.files.length) ? d.files
            : (d.streamingPlaylists || []).flatMap((p) => p.files || []);
  files = files.slice().sort((a, b) => resId(b) - resId(a));
  const mp4 = files.map((f) => f.fileUrl || f.fileDownloadUrl).find(Boolean);
  if (mp4) return { url: mp4, type: "video/mp4" };

  // 2) HLS adaptativo
  const hls = (d.streamingPlaylists || []).map((p) => p.playlistUrl).find(Boolean);
  if (hls) return { url: hls, type: "application/x-mpegurl" };
  return null;
}

async function castLoadCurrent() {
  const session = castContext && castContext.getCurrentSession();
  if (!session || !playerCtx) return;
  const name = playerCtx.eps[playerCtx.idx][0];
  const panel = $("#castPanel");
  $("#castEp").textContent = name;
  $("#castStatus").textContent = "Carregando…";
  panel.classList.remove("hidden");
  try {
    const media = await resolveDirectUrl(epUrl(playerCtx.idx));
    if (!media) throw new Error("sem fonte de vídeo");
    const info = new chrome.cast.media.MediaInfo(media.url, media.type);
    info.metadata = new chrome.cast.media.GenericMediaMetadata();
    info.metadata.title = name;
    await session.loadMedia(new chrome.cast.media.LoadRequest(info));
    $("#castStatus").textContent = "Reproduzindo na TV";
  } catch (err) {
    console.error("[cast]", err);
    $("#castStatus").textContent = "Não foi possível transmitir este episódio.";
  }
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
