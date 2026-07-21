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

// ── Catálogo (padrão do JSON + dinâmico via API) ───────
const SITE = "https://serv01.meusdoramas.club";
const TMDB_KEY = window.TMDB_KEY || CONFIG.tmdbKey || "";  // chave grátis (read-only)
const dynCatalog = {};   // títulos carregados sob demanda (busca/favoritos)

function seasonsOf(title) { return dynCatalog[title] || DATA[title]; }
function fetchJson(url) {
  return fetch(url).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
}
function cleanName(t) { return String(t).replace(/^\d+\s*-\s*/, "").trim(); }

// Constrói { "Temporada N": { "Episódio M": url } } a partir do get-post.php.
function buildSeasons(d) {
  const out = {}, eps = d.episodes || {};
  for (const s of Object.keys(eps).sort((a, b) => a - b)) {
    const season = {};
    for (const e of Object.keys(eps[s]).sort((a, b) => a - b))
      season[`Episódio ${e}`] = `${SITE}/#/video/${d.tmdb}/${s}/${e}/`;
    out[`Temporada ${s}`] = season;
  }
  return out;
}

// Abre um título: usa o que já existe, ou carrega os episódios sob demanda.
async function openTitle(item) {
  if (seasonsOf(item.name)) return goSeasons(item.name);
  if (!item.post_id) return;
  try {
    const d = await fetchJson(`${SITE}/posts/get-post.php?id=${item.post_id}`);
    dynCatalog[item.name] = buildSeasons(d);
    goSeasons(item.name);
  } catch (e) { console.error("[openTitle]", e); }
}

// ── Favoritos (localStorage, separado por página via CONFIG.favKey) ──
function favKey() { return CONFIG.favKey || "favs"; }
function loadFavs() { try { return JSON.parse(localStorage.getItem(favKey())) || []; } catch { return []; } }
function saveFavs(f) { try { localStorage.setItem(favKey(), JSON.stringify(f)); } catch {} }
function isFav(name) { return loadFavs().some((x) => x.name === name); }
function toggleFav(item) {
  const f = loadFavs();
  saveFavs(f.some((x) => x.name === item.name)
    ? f.filter((x) => x.name !== item.name) : f.concat([item]));
}

// ── Capas automáticas (TMDB via meusdoramas) ───────────
function seriesRef(title) {
  const seasons = seasonsOf(title); if (!seasons) return null;
  const firstSeason = Object.values(seasons)[0]; if (!firstSeason) return null;
  const firstUrl = Object.values(firstSeason)[0]; if (!firstUrl) return null;
  const m = firstUrl.match(/\/video\/(\d+)\//);
  try { return m ? { id: m[1], origin: new URL(firstUrl).origin } : null; }
  catch { return null; }
}
function tmdbOf(name) { const r = seriesRef(name); return r ? r.id : null; }

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

// Injeta o pôster no card (mantém a inicial até chegar).
async function loadPosterByTmdb(card, ref) {
  const url = await fetchPoster(ref);
  if (!url || !card.isConnected) return;
  const img = el("img");
  img.loading = "lazy"; img.alt = ""; img.src = url;
  img.onerror = () => img.remove();
  img.onload = () => { const fb = card.querySelector(".fallback"); if (fb) fb.remove(); };
  card.insertBefore(img, card.firstChild);
}
function loadPoster(card, title) { return loadPosterByTmdb(card, seriesRef(title)); }

// ── Componente card ────────────────────────────────────
function makeCard(coverSrc, label, badge, onClick) {
  const card = el("div", "card");
  card.tabIndex = 0; card.setAttribute("role", "button");
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
  setHeader(CONFIG.homeTitle || "PONYFLIX", false, CONFIG.search);
  if (CONFIG.search) setupHeaderSearch();
  renderHome();
}

// Home = favoritos do usuário; se não tiver nenhum, os títulos do JSON.
function renderHome() {
  const favs = loadFavs();
  const items = favs.length
    ? favs
    : Object.keys(DATA).map((name) => ({ name, tmdb: tmdbOf(name) }));
  showView(buildTitleGrid(items, favs.length === 0));
}

// Monta a grade de cards a partir de uma lista { name, tmdb, post_id, poster }.
function buildTitleGrid(items, isDefaults) {
  const grid = el("div", "grid");
  if (!items.length) { grid.appendChild(msgEl("Nada por aqui.")); return grid; }
  for (const it of items) {
    const prog = progress[it.name];
    const last = prog && Object.keys(prog).length ? Object.keys(prog).slice(-1)[0] : null;
    const cover = it.poster || (CONFIG.autoCovers ? null : titleCover(it.name));
    const card = makeCard(cover, it.name, last ? "▸ " + last : null, () => openTitle(it));
    card.dataset.q = slug(it.name);
    if (!it.poster && CONFIG.autoCovers && it.tmdb)
      loadPosterByTmdb(card, { id: it.tmdb, origin: SITE });
    if (CONFIG.favKey) addStar(card, it, isDefaults);
    grid.appendChild(card);
  }
  return grid;
}

function msgEl(text) { const d = el("div", "empty-msg"); d.textContent = text; return d; }

// Estrela de favoritar/desfavoritar no canto do card.
function addStar(card, item, rerenderOnRemove) {
  const star = el("button", "fav-star");
  star.tabIndex = -1;
  const upd = () => {
    const on = isFav(item.name);
    star.textContent = on ? "★" : "☆";
    star.classList.toggle("on", on);
    star.setAttribute("aria-label", on ? "Remover dos favoritos" : "Adicionar aos favoritos");
  };
  upd();
  star.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleFav({ name: item.name, tmdb: item.tmdb, post_id: item.post_id, poster: item.poster });
    upd();
  });
  card.appendChild(star);
}

// Busca dinâmica no catálogo do site (debounce); vazio volta pra home.
function setupHeaderSearch() {
  const input = $("#headerSearch");
  if (!input) return;
  input.value = "";
  let timer;
  input.oninput = () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (!q) return renderHome();
    timer = setTimeout(() => runSearch(q), 300);
  };
}
// Classifica um resultado como anime (Animação + origem Japão) via TMDB.
// dublado usa id base (id sem o último dígito). Cacheia o resultado.
// Anime = gênero Animação (id 16). Não exige Japão (inclui donghua etc.).
const tmdbCache = {};
async function classifyIsAnime(item) {
  const k = item.tmdb;
  if (k in tmdbCache) return tmdbCache[k];
  const ls = localStorage.getItem("tmdbanim_" + k);
  if (ls !== null) return (tmdbCache[k] = ls === "1");
  if (!TMDB_KEY) return null;
  const dub = /dublado/i.test(item.rawtitle || item.name);
  const id = dub ? String(item.tmdb).slice(0, -1) : String(item.tmdb);
  const type = item.is_movie ? "movie" : "tv";
  try {
    const d = await fetchJson(`https://api.themoviedb.org/3/${type}/${id}?api_key=${TMDB_KEY}`);
    const res = (d.genres || []).some((g) => g.id === 16);
    tmdbCache[k] = res;
    localStorage.setItem("tmdbanim_" + k, res ? "1" : "0");
    return res;
  } catch (e) { return null; }
}

async function runSearch(q) {
  showView(msgEl("Buscando…"));
  try {
    const arr = await fetchJson(`${SITE}/search.php?term=${encodeURIComponent(q)}`);
    let items = arr.map((x) => ({
      name: cleanName(x.title),
      rawtitle: x.title,
      tmdb: String(x.tmdb),
      post_id: x.post_id,
      is_movie: x.is_movie === "1" || x.is_movie === 1,
      poster: (x.image_url || "").replace("/w185/", "/w500/"),
    }));
    // Filtra por categoria (anime / live-action) usando o TMDB, se houver chave.
    if (CONFIG.cat && TMDB_KEY) {
      const flags = await Promise.all(items.map(classifyIsAnime));
      const want = CONFIG.cat === "anime";
      const filtered = items.filter((_, i) => flags[i] === want);
      items = flags.every((f) => f === null) ? items : filtered;  // tudo falhou → não esconde
    }
    showView(items.length ? buildTitleGrid(items) : msgEl("Nada encontrado."));
  } catch (e) {
    console.error("[busca]", e);
    showView(msgEl("Erro na busca. Tente de novo."));
  }
}

function goSeasons(title) {
  state.title = title; state.season = null;
  setHeader(title.toUpperCase(), true);
  const seasons = seasonsOf(title);
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
  const eps = Object.entries(seasonsOf(title)[season]); // [ [name, url], ... ]
  const lastEp = progress[title]?.[season]?.episodio;

  const list = el("div", "ep-list");
  eps.forEach(([name, url], idx) => {
    const num = idx + 1;
    const isCurrent = lastEp === num;
    const row = el("div", "ep-row" + (isCurrent ? " current" : ""));
    row.tabIndex = 0; row.setAttribute("role", "button");
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
  if (!audios) return;   // sem info de áudio (MLP, séries sem dub) → não mostra
  // Sempre Legendado + Dublado; Dublado desabilitado se não existir.
  for (const label of ["Legendado", "Dublado"]) {
    const id = audios[label];
    const b = el("button", "audio-btn");
    b.textContent = label;
    if (!id) {
      b.disabled = true;   // ex.: sem dublado
    } else {
      if (String(id) === String(playerCtx.audioId)) b.classList.add("active");
      b.addEventListener("click", () => {
        if (String(id) === String(playerCtx.audioId)) return;
        playerCtx.audioId = String(id);
        buildAudioSelector();       // re-destaca o ativo
        loadEp(playerCtx.idx);      // recarrega no mesmo episódio
      });
    }
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
function setHeader(text, showBack, showSearch) {
  const t = $("#headerTitle");
  t.textContent = text;
  t.classList.toggle("header-title--logo", !!showSearch);   // logo compacta à esquerda
  $("#backBtn").classList.toggle("hidden", !showBack);
  const hs = $("#headerSearch");
  if (hs) hs.classList.toggle("hidden", !showSearch);
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

// ── Navegação por controle (D-pad / teclado) ───────────
// Foco espacial: as setas movem o foco para o elemento vizinho na direção.
function navScope() {
  if (!$("#player").classList.contains("hidden")) return $("#player");
  if (!$("#app").classList.contains("hidden")) return $("#app");
  return document.body;
}
function focusables() {
  return [...navScope().querySelectorAll('.card,.ep-row,button:not(.fav-star),a[href],input,[tabindex="0"]')]
    .filter((el) => !el.disabled && el.offsetParent !== null && el.getClientRects().length
                    && el.style.display !== "none");
}
function spatialNav(dir) {
  const list = focusables();
  if (!list.length) return;
  const cur = document.activeElement;
  if (!cur || !list.includes(cur)) { list[0].focus(); return; }
  const r = cur.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  let best = null, bestScore = Infinity;
  for (const el of list) {
    if (el === cur) continue;
    const b = el.getBoundingClientRect();
    const dx = b.left + b.width / 2 - cx, dy = b.top + b.height / 2 - cy;
    let primary, cross;
    if (dir === "right")     { if (dx <= 1)  continue; primary = dx;  cross = Math.abs(dy); }
    else if (dir === "left") { if (dx >= -1) continue; primary = -dx; cross = Math.abs(dy); }
    else if (dir === "down") { if (dy <= 1)  continue; primary = dy;  cross = Math.abs(dx); }
    else                     { if (dy >= -1) continue; primary = -dy; cross = Math.abs(dx); }
    const score = primary + cross * 2;   // prioriza a direção, penaliza desvio lateral
    if (score < bestScore) { bestScore = score; best = el; }
  }
  if (best) best.focus();
}

// listeners
$("#backBtn").addEventListener("click", goBack);
$("#playerBack").addEventListener("click", closePlayer);
$("#prevEp").addEventListener("click", () => loadEp(playerCtx.idx - 1));
$("#nextEp").addEventListener("click", () => loadEp(playerCtx.idx + 1));
document.addEventListener("keydown", (e) => {
  const inPlayer = !$("#player").classList.contains("hidden");
  // Digitando na busca: setas/OK ficam nativos; só ArrowDown "sai" p/ a grade.
  const ae = document.activeElement;
  if (ae && (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA")) {
    if (e.key === "ArrowDown") { e.preventDefault(); spatialNav("down"); }
    else if (e.key === "Escape") { ae.blur(); }
    return;
  }
  switch (e.key) {
    case "ArrowRight": e.preventDefault(); spatialNav("right"); break;
    case "ArrowLeft":  e.preventDefault(); spatialNav("left");  break;
    case "ArrowDown":  e.preventDefault(); spatialNav("down");  break;
    case "ArrowUp":    e.preventDefault(); spatialNav("up");    break;
    case "Enter": case " ": {
      const el = document.activeElement;
      if (el && (el.classList.contains("card") || el.classList.contains("ep-row"))) {
        e.preventDefault(); el.click();
      }
      break;
    }
    // Voltar do controle (Escape / Backspace / tecla BACK do Android)
    case "Escape": case "Backspace": case "GoBack": case "BrowserBack":
      e.preventDefault();
      if (inPlayer) closePlayer(); else goBack();
      break;
  }
});

window.addEventListener("beforeunload", () => clearInterval(dotsTimer));

// PWA: registra o service worker (necessário para instalar / gerar APK)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}

boot();
