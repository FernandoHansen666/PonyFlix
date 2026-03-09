"""
PonyFlix — streaming app
By: ScaryHollow

JSON: { "Titulo": { "Temporada N": { "Ep name": "embed_url" } } }
Imagens: assets/covers/titulo_slug.png  e  assets/tN.png
"""

import json, os, re, threading, urllib.request
from kivy.config import Config
Config.set("kivy", "exit_on_escape", "0")  # ESC não fecha o app
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.graphics import (Color, Rectangle, RoundedRectangle, Line,
                            StencilPush, StencilUse, StencilUnUse, StencilPop)
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.video import Video
from kivy.uix.widget import Widget
from kivy.animation import Animation

# ── Plataforma ────────────────────────────────────────────────────────────────

IS_ANDROID = False
try:
    import android
    from android.storage import app_storage_path
    from android import mActivity
    IS_ANDROID = True
except ImportError:
    pass

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = (app_storage_path() if IS_ANDROID else BASE_DIR)
ASSETS_DIR    = os.path.join(BASE_DIR, "assets")
PROGRESS_FILE = os.path.join(DATA_DIR, "progresso.json")

# ── Cores ─────────────────────────────────────────────────────────────────────

C_BG      = (0.03, 0.01, 0.07, 1)
C_PANEL   = (0.07, 0.03, 0.12, 1)
C_CARD    = (0.10, 0.05, 0.17, 1)
C_CARD_HL = (0.17, 0.08, 0.28, 1)
C_ACCENT  = (0.90, 0.22, 0.78, 1)
C_ACCENT2 = (0.55, 0.10, 0.95, 1)
C_GOLD    = (1.00, 0.88, 0.30, 1)
C_TEXT    = (0.98, 0.95, 1.00, 1)
C_SUB     = (0.65, 0.52, 0.82, 1)
C_DIM     = (0.35, 0.24, 0.50, 1)
R         = dp(14)

Window.clearcolor = C_BG

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_progress():
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_progress(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[save_progress] {e}")

def fmt_time(seconds):
    s = int(seconds or 0)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def find_asset(filename):
    for p in [
        os.path.join(ASSETS_DIR, filename),
        os.path.join(BASE_DIR, "assets", filename),
        os.path.join(DATA_DIR, "assets", filename),
        f"assets/{filename}", filename,
    ]:
        try:
            if os.path.exists(p): return p
        except Exception:
            pass
    return f"assets/{filename}"

def title_cover(title_name):
    """Capa do título: assets/covers/<slug>.png  ou  assets/cover.png"""
    slug = re.sub(r'[^a-z0-9]+', '_', title_name.lower()).strip('_')
    for f in [f"covers/{slug}.png", f"{slug}.png", "covers/default.png", "cover.png"]:
        p = find_asset(f)
        if os.path.exists(p): return p
    return None

def season_cover(season_name):
    """Capa da temporada: assets/tN.png"""
    num = season_name.strip().split()[-1]
    return find_asset(f"t{num}.png")

def load_episodes():
    for path in [
        os.path.join(BASE_DIR, "episodios.json"),
        os.path.join(DATA_DIR, "episodios.json"),
        os.path.join(ASSETS_DIR, "episodios.json"),
        "episodios.json",
    ]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[load] {path}")
                return data
        except Exception:
            pass
    raise FileNotFoundError("episodios.json nao encontrado.")

def apply_bg(widget, color):
    with widget.canvas.before:
        col  = Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *_: setattr(rect, 'pos', widget.pos),
        size=lambda *_: setattr(rect, 'size', widget.size),
    )

def get_direct_url(embed_url, callback):
    def _fetch():
        try:
            m    = re.search(r'/embed/([a-zA-Z0-9\-_]+)', embed_url)
            host = re.search(r'https?://([^/]+)', embed_url)
            if not m: Clock.schedule_once(lambda dt: callback(None)); return
            api = f"https://{host.group(1)}/api/v1/videos/{m.group(1)}"
            req = urllib.request.Request(api, headers={"User-Agent": "PonyflixApp/4.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
            hls = next((p.get("playlistUrl","") for p in d.get("streamingPlaylists",[])), None)
            mp4 = next((f.get("fileUrl") or f.get("fileDownloadUrl","")
                        for f in sorted(d.get("files",[]),
                            key=lambda f: f.get("resolution",{}).get("id",0), reverse=True)
                        ), None)
            url = mp4 or hls
            Clock.schedule_once(lambda dt, u=url: callback(u))
        except Exception as e:
            print(f"[API] {e}")
            Clock.schedule_once(lambda dt: callback(None))
    threading.Thread(target=_fetch, daemon=True).start()

# ── AndroidWebView ────────────────────────────────────────────────────────────

class AndroidWebView(Widget):
    def __init__(self, url="", **kwargs):
        super().__init__(**kwargs)
        self._url = url
        self._wv  = None
        self.bind(pos=self._sched, size=self._sched)
        Clock.schedule_once(self._create, 0.2)

    def _create(self, *_):
        try:
            from jnius import autoclass
            from android.runnable import run_on_ui_thread
            WebView      = autoclass("android.webkit.WebView")
            LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
            url = self._url

            @run_on_ui_thread
            def _do():
                try:
                    wv = WebView(mActivity)
                    s  = wv.getSettings()
                    s.setJavaScriptEnabled(True)
                    s.setMediaPlaybackRequiresUserGesture(False)
                    s.setLoadWithOverviewMode(True)
                    s.setUseWideViewPort(True)
                    s.setDomStorageEnabled(True)
                    s.setMixedContentMode(0)
                    lp = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)
                    mActivity.addContentView(wv, lp)
                    wv.loadUrl(url)
                    self._wv = wv
                    Clock.schedule_once(self._sync, 0.1)
                except Exception as e:
                    print(f"[WebView._do] {e}")
            _do()
        except Exception as e:
            print(f"[WebView._create] {e}")

    def _sched(self, *_):
        Clock.schedule_once(self._sync, 0.05)

    def _sync(self, *_):
        if not self._wv: return
        try:
            from android.runnable import run_on_ui_thread
            win_h = Window.height
            x = int(self.x); y = int(win_h - self.y - self.height)
            w = max(1, int(self.width)); h = max(1, int(self.height))
            wv = self._wv

            @run_on_ui_thread
            def _do():
                try:
                    wv.setX(float(x)); wv.setY(float(y))
                    lp = wv.getLayoutParams()
                    lp.width = w; lp.height = h
                    wv.requestLayout()
                except Exception as e:
                    print(f"[WebView._sync_do] {e}")
            _do()
        except Exception as e:
            print(f"[WebView._sync] {e}")

    def load_url(self, url):
        self._url = url
        if not self._wv: return
        try:
            from android.runnable import run_on_ui_thread
            wv = self._wv

            @run_on_ui_thread
            def _do():
                try: wv.loadUrl(url)
                except Exception as e: print(f"[WebView.loadUrl] {e}")
            _do()
        except Exception as e:
            print(f"[WebView.load_url] {e}")

    def destroy(self):
        if not self._wv: return
        try:
            from jnius import autoclass
            from android.runnable import run_on_ui_thread
            View = autoclass("android.view.View")
            wv = self._wv; self._wv = None

            @run_on_ui_thread
            def _do():
                try:
                    # 1. Some IMEDIATAMENTE da tela
                    wv.setVisibility(View.GONE)
                    # 2. Para tudo
                    wv.stopLoading()
                    wv.loadUrl("about:blank")
                    wv.clearHistory()
                    wv.clearCache(True)
                    # 3. Remove da hierarquia
                    parent = wv.getParent()
                    if parent:
                        try: parent.removeView(wv)
                        except Exception as e2: print(f"[removeView] {e2}")
                    # 4. Destroi
                    wv.destroy()
                except Exception as e:
                    print(f"[WebView.destroy_do] {e}")
            _do()
        except Exception as e:
            print(f"[WebView.destroy] {e}")

# ── Widgets base ──────────────────────────────────────────────────────────────

class FlatBtn(ButtonBehavior, Label):
    def __init__(self, bg=C_ACCENT, fg=C_TEXT, radius=None, **kwargs):
        super().__init__(**kwargs)
        self._bg_n = bg
        self._bg_d = tuple(max(0, c - .15) if i < 3 else c for i, c in enumerate(bg))
        self._radius = radius if radius is not None else R
        self.color = fg; self.font_size = dp(14); self.bold = True
        self.halign = 'center'; self.valign = 'middle'
        self.bind(size=self.setter('text_size'))
        with self.canvas.before:
            self._col  = Color(*bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self._radius])
        self.bind(pos=self._upd, size=self._upd, state=self._upd)

    def _upd(self, *_):
        self._col.rgba       = self._bg_d if self.state == 'down' else self._bg_n
        self._rect.pos       = self.pos
        self._rect.size      = self.size
        self._rect.radius    = [self._radius]


class TitleToast(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, None); self.height = dp(52); self.opacity = 0
        with self.canvas.before:
            Color(0, 0, 0, 0.72)
            self._r = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._r, 'pos', self.pos),
                  size=lambda *_: setattr(self._r, 'size', self.size))
        self.lbl = Label(text='', font_size=dp(15), bold=True, color=C_TEXT,
                         size_hint=(1, 1), halign='center', valign='middle')
        self.lbl.bind(size=self.lbl.setter('text_size'))
        self.add_widget(self.lbl)

    def show(self, text):
        self.lbl.text = text
        Animation.cancel_all(self); self.opacity = 0
        (Animation(opacity=1, duration=.3) + Animation(opacity=1, duration=3.5)
         + Animation(opacity=0, duration=.5)).start(self)

# ── Card genérico com capa ────────────────────────────────────────────────────

class CoverCard(Widget):
    """Card clicável com imagem de capa + gradiente + label."""
    def __init__(self, cover_path, label_text, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback  = callback
        self._pressed  = False
        self._tex      = None
        if cover_path:
            try: self._tex = CoreImage(cover_path).texture
            except Exception as e: print(f"[CoverCard] {e}")
        self._label = label_text
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        w, h = self.width, self.height
        if w <= 0 or h <= 0: return
        rad = [R]
        self.canvas.clear()
        with self.canvas:
            # Fundo arredondado
            Color(*(C_CARD_HL if self._pressed else C_CARD))
            RoundedRectangle(pos=self.pos, size=self.size, radius=rad)
            if self._tex:
                StencilPush()
                RoundedRectangle(pos=self.pos, size=self.size, radius=rad)
                StencilUse()
                tw, th = self._tex.width, self._tex.height
                scale  = max(w / tw, h / th)
                dw, dh = tw * scale, th * scale
                Color(1, 1, 1, 0.92 if not self._pressed else 0.7)
                Rectangle(texture=self._tex,
                          pos=(self.x + (w - dw) / 2, self.y + (h - dh) / 2),
                          size=(dw, dh))
                StencilUnUse()
                RoundedRectangle(pos=self.pos, size=self.size, radius=rad)
                StencilPop()
            # Gradiente escuro base (mais alto para respirar o texto)
            Color(0, 0, 0, 0.72)
            RoundedRectangle(pos=(self.x, self.y), size=(w, dp(56)), radius=rad)
            if self._pressed:
                Color(*C_ACCENT[:3], 0.18)
                RoundedRectangle(pos=self.pos, size=self.size, radius=rad)
            # Borda accent brilhante
            Color(*C_ACCENT[:3], 0.55 if self._pressed else 0.28)
            Line(rounded_rectangle=(self.x+1, self.y+1, w-2, h-2, R), width=1.4)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._pressed = True; self._draw(); touch.grab(self); return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self); self._pressed = False; self._draw()
            if self.collide_point(*touch.pos): self.callback()
            return True


def _grid_screen(items, on_back=None, back_label=None):
    """Monta uma tela de grid responsivo com cards. Retorna RelativeLayout."""
    root = RelativeLayout()
    containers = []

    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    grid   = GridLayout(cols=2, size_hint_y=None, spacing=dp(10), padding=[dp(10)] * 4)
    grid.bind(minimum_height=grid.setter('height'))

    for cover_path, label, sublabel, callback in items:
        c = FloatLayout(size_hint=(1, None), height=dp(160))
        c.add_widget(CoverCard(cover_path=cover_path, label_text=label,
                               callback=callback,
                               size_hint=(1, 1), pos_hint={'x': 0, 'y': 0}))
        lbl = Label(text=f"[b]{label}[/b]", markup=True,
                    font_size=dp(13), color=C_TEXT,
                    size_hint=(1, None), height=dp(36),
                    pos_hint={'x': 0, 'y': 0},
                    halign='center', valign='middle')
        lbl.bind(size=lbl.setter('text_size'))
        c.add_widget(lbl)
        if sublabel:
            c.add_widget(Label(text=sublabel, font_size=dp(9), color=C_GOLD,
                               size_hint=(None, None), size=(dp(70), dp(16)),
                               pos_hint={'right': 0.97, 'top': 0.99}))
        grid.add_widget(c)
        containers.append(c)

    scroll.add_widget(grid)
    root.add_widget(scroll)

    def _resize(*_):
        w    = root.width if root.width > 10 else Window.width
        cols = 4 if w >= dp(960) else 3 if w >= dp(640) else 2
        grid.cols = cols
        cw = (w - dp(12) - dp(6) * (cols - 1)) / cols
        ch = max(dp(100), cw * 9 / 16)
        grid.row_default_height = ch
        grid.row_force_default  = True
        for c in containers: c.height = ch

    def _sched(*_):
        Clock.unschedule(_resize); Clock.schedule_once(_resize, 0.05)

    Window.bind(size=_sched); root.bind(size=_sched)
    Clock.schedule_once(_resize, 0.1)
    return root

# ── Telas ─────────────────────────────────────────────────────────────────────

def TitlesScreen(data, progress, on_title):
    """Grid de títulos."""
    items = []
    for title, seasons in data.items():
        prog     = progress.get(title, {})
        last_s   = prog.get("temporada")
        sublabel = f"> {last_s}" if last_s else None
        items.append((title_cover(title), title, sublabel,
                      lambda t=title: on_title(t)))
    return _grid_screen(items)


def SeasonsScreen(title_name, seasons, progress, on_season, on_back):
    """Grid de temporadas de um título."""
    prog  = progress.get(title_name, {})
    items = []
    for season_name in seasons:
        sp       = prog.get(season_name, {})
        last_ep  = sp.get("episodio")
        sublabel = f"> ep.{last_ep}" if last_ep else None
        items.append((season_cover(season_name), season_name, sublabel,
                      lambda s=season_name: on_season(s)))

    root = BoxLayout(orientation='vertical')
    top  = BoxLayout(size_hint=(1, None), height=dp(58),
                     padding=[dp(10), dp(9)], spacing=dp(10))
    apply_bg(top, C_PANEL)
    back = FlatBtn(text="‹ Voltar", bg=C_CARD, size_hint=(None, 1), width=dp(86), radius=dp(10))
    back.bind(on_release=lambda x: on_back())
    lbl  = Label(text=f"[b]{title_name}[/b]", markup=True,
                 font_size=dp(15), color=C_TEXT,
                 size_hint=(1, 1), halign='left', valign='middle')
    lbl.bind(size=lbl.setter('text_size'))
    top.add_widget(back); top.add_widget(lbl)
    root.add_widget(top)
    root.add_widget(_grid_screen(items))
    return root


class EpRow(ButtonBehavior, BoxLayout):
    def __init__(self, num, name, pct, is_last, callback, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self.size_hint_y = None; self.height = dp(70)
        self.padding = [dp(14), dp(10)]; self.spacing = dp(14)
        self._sel = is_last; self.callback = callback
        with self.canvas.before:
            self._bg_col  = Color(*(C_CARD_HL if is_last else C_CARD))
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[R])
        self.bind(pos=self._upd, size=self._upd, state=self._upd)
        if is_last:
            with self.canvas.before:
                Color(*C_ACCENT)
                self._sl = Rectangle(pos=self.pos, size=(dp(3), self.height))
            self.bind(pos=lambda *_: setattr(self._sl, 'pos', self.pos),
                      size=lambda *_: setattr(self._sl, 'size', (dp(3), self.height)))
        nlbl = Label(text=f"[b]{num:02d}[/b]", markup=True,
                     font_size=dp(18), color=C_ACCENT if is_last else C_DIM,
                     size_hint=(None, 1), width=dp(42),
                     halign='center', valign='middle')
        nlbl.bind(size=nlbl.setter('text_size'))
        info = BoxLayout(orientation='vertical', size_hint=(1, 1), spacing=dp(3))
        namelbl = Label(text=name, font_size=dp(14), color=C_TEXT,
                        halign='left', valign='middle', size_hint=(1, 0.65))
        namelbl.bind(size=namelbl.setter('text_size'))
        info.add_widget(namelbl)
        bar = Widget(size_hint=(1, None), height=dp(3))
        with bar.canvas:
            Color(*C_DIM);    bar_bg = Rectangle()
            Color(*C_ACCENT); bar_fg = Rectangle()
        def _db(*_):
            bar_bg.pos = bar.pos; bar_bg.size = bar.size
            bar_fg.pos = bar.pos
            bar_fg.size = (bar.width * min(pct / 100., 1.) if pct else 0, bar.height)
        bar.bind(pos=_db, size=_db)
        info.add_widget(bar)
        plbl = Label(text="▶ Continuar" if is_last else "▶",
                     font_size=dp(13), color=C_GOLD if is_last else C_SUB,
                     size_hint=(None, 1), width=dp(90),
                     halign='center', valign='middle')
        plbl.bind(size=plbl.setter('text_size'))
        self.add_widget(nlbl); self.add_widget(info); self.add_widget(plbl)

    def _upd(self, *_):
        hl = self.state == 'down' or self._sel
        self._bg_col.rgba    = C_CARD_HL if hl else C_CARD
        self._bg_rect.pos    = self.pos
        self._bg_rect.size   = self.size
        self._bg_rect.radius = [R]

    def on_release(self): self.callback()


def EpisodesScreen(title_name, season_name, episodes, progress, on_play, on_back):
    prog        = progress.get(title_name, {}).get(season_name, {})
    last_ep_num = prog.get("episodio")
    root = BoxLayout(orientation='vertical')
    top  = BoxLayout(size_hint=(1, None), height=dp(58),
                     padding=[dp(10), dp(9)], spacing=dp(10))
    apply_bg(top, C_PANEL)
    back = FlatBtn(text="‹ Voltar", bg=C_CARD, size_hint=(None, 1), width=dp(86), radius=dp(10))
    back.bind(on_release=lambda x: on_back())
    lbl  = Label(text=f"[b]{season_name}[/b]", markup=True,
                 font_size=dp(17), color=C_TEXT,
                 size_hint=(1, 1), halign='left', valign='middle')
    lbl.bind(size=lbl.setter('text_size'))
    cnt  = Label(text=f"{len(episodes)} eps", font_size=dp(12), color=C_SUB,
                 size_hint=(None, 1), width=dp(52), halign='right', valign='middle')
    top.add_widget(back); top.add_widget(lbl); top.add_widget(cnt)
    root.add_widget(top)
    scroll = ScrollView(size_hint=(1, 1))
    vbox   = BoxLayout(orientation='vertical', size_hint_y=None,
                       spacing=dp(8), padding=[dp(12), dp(12), dp(12), dp(28)])
    vbox.bind(minimum_height=vbox.setter('height'))
    for idx, (name, link) in enumerate(episodes.items()):
        num   = idx + 1
        ep_p  = prog.get(f"ep_{num}", {})
        pos_s = ep_p.get("posicao", 0); dur_s = ep_p.get("duracao", 0)
        pct   = (pos_s / dur_s * 100) if dur_s else 0
        vbox.add_widget(EpRow(num=num, name=name, pct=pct,
                              is_last=(last_ep_num == num),
                              callback=lambda i=idx, l=link, n=num: on_play(i, l, n)))
    scroll.add_widget(vbox)
    root.add_widget(scroll)
    return root

# ── Android player ────────────────────────────────────────────────────────────

class AndroidPlayerScreen(FloatLayout):
    """WebView tela toda. Botão voltar do Android fecha o WebView e volta ao menu."""
    def __init__(self, title_name, season_name, ep_index, ep_num,
                 embed_url, on_back, on_save_progress, **kwargs):
        super().__init__(**kwargs)
        self.title_name       = title_name
        self.season_name      = season_name
        self.ep_num           = ep_num
        self.on_back          = on_back
        self.on_save_progress = on_save_progress
        self.wv               = None

        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, 'pos', self.pos),
                  size=lambda *_: setattr(self._bg, 'size', self.size))

        Clock.schedule_once(self._hide_chrome, 0.05)
        Clock.schedule_once(lambda dt: self._init_wv(embed_url), 0.4)

    def _hide_chrome(self, *_):
        try:
            rb = App.get_running_app().root.children[0]
            self._hdr_h = rb.children[2].height
            self._ftr_h = rb.children[0].height
            rb.children[2].height = 0; rb.children[2].opacity = 0
            rb.children[0].height = 0; rb.children[0].opacity = 0
        except Exception:
            self._hdr_h = dp(56); self._ftr_h = dp(26)

    def _show_chrome(self):
        try:
            rb = App.get_running_app().root.children[0]
            rb.children[2].height = self._hdr_h; rb.children[2].opacity = 1
            rb.children[0].height = self._ftr_h; rb.children[0].opacity = 1
        except Exception: pass

    def _init_wv(self, url):
        self.wv = AndroidWebView(url=url,
                                 size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self.add_widget(self.wv)

    def _back(self):
        self.on_save_progress(title=self.title_name, season=self.season_name,
                              ep_num=self.ep_num, posicao=1, duracao=1)
        self._show_chrome()
        if self.wv:
            self.wv.destroy()
            self.wv = None
        # Pequeno delay para o destroy processar na UI thread antes de trocar tela
        Clock.schedule_once(lambda dt: self.on_back(), 0.2)

# ── PC player ─────────────────────────────────────────────────────────────────

class PCPlayerScreen(FloatLayout):
    def __init__(self, title_name, season_name, ep_index, ep_num, ep_name,
                 embed_url, episodes_list, progress,
                 on_back, on_save_progress, **kwargs):
        super().__init__(**kwargs)
        self.title_name       = title_name
        self.season_name      = season_name
        self.ep_index         = ep_index
        self.ep_num           = ep_num
        self.ep_name          = ep_name
        self.episodes         = episodes_list
        self.on_back          = on_back
        self.on_save_progress = on_save_progress
        self.progress         = progress
        self._duration        = 0
        self._save_event      = None
        self._seeking         = False
        self._ctrl_vis        = True
        self._hide_evt        = None
        self._fullscreen      = False
        self._build()
        # Esconde header/footer do app enquanto o player está ativo
        Clock.schedule_once(self._hide_chrome, 0.05)
        get_direct_url(embed_url, lambda u: self._on_url(u, self._saved_pos()))

    def _hide_chrome(self, *_):
        try:
            rb = App.get_running_app().root.children[0]
            self._hdr_h = rb.children[2].height
            self._ftr_h = rb.children[0].height
            rb.children[2].height = 0; rb.children[2].opacity = 0
            rb.children[0].height = 0; rb.children[0].opacity = 0
        except Exception:
            self._hdr_h = dp(62); self._ftr_h = dp(30)

    def _show_chrome(self):
        try:
            rb = App.get_running_app().root.children[0]
            rb.children[2].height = self._hdr_h; rb.children[2].opacity = 1
            rb.children[0].height = self._ftr_h; rb.children[0].opacity = 1
        except Exception: pass

    def _build(self):
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, 'pos', self.pos),
                  size=lambda *_: setattr(self._bg, 'size', self.size))
        self.video = Video(source='', state='stop', size_hint=(None, None))
        self.video.bind(duration=self._on_dur, position=self._on_pos, eos=self._on_eos)
        self.add_widget(self.video)
        self.bind(pos=self._fill, size=self._fill)
        self.status_lbl = Label(text='Buscando vídeo...', font_size=dp(14), color=C_SUB,
                                size_hint=(.85, None), height=dp(50),
                                pos_hint={'center_x': .5, 'center_y': .5},
                                halign='center', valign='middle')
        self.status_lbl.bind(size=self.status_lbl.setter('text_size'))
        self.add_widget(self.status_lbl)
        self.overlay = BoxLayout(orientation='vertical', size_hint=(1, 1))
        top = BoxLayout(size_hint=(1, None), height=dp(54),
                        padding=[dp(8), dp(8)], spacing=dp(8))
        with top.canvas.before:
            Color(0, 0, 0, .65); tr = Rectangle()
        top.bind(pos=lambda *_: setattr(tr, 'pos', top.pos),
                 size=lambda *_: setattr(tr, 'size', top.size))
        back_btn = FlatBtn(text="< Voltar", bg=C_CARD, size_hint=(None, 1), width=dp(90))
        back_btn.bind(on_release=self._back)
        self.ep_lbl = Label(text=self.ep_name, font_size=dp(13), color=C_TEXT,
                            size_hint=(1, 1), halign='left', valign='middle',
                            shorten=True, shorten_from='right')
        self.ep_lbl.bind(size=self.ep_lbl.setter('text_size'))
        self.fs_btn = FlatBtn(text="[ ] Full", bg=C_CARD, size_hint=(None, 1), width=dp(90))
        self.fs_btn.bind(on_release=self._toggle_fs)
        top.add_widget(back_btn); top.add_widget(self.ep_lbl); top.add_widget(self.fs_btn)
        self.overlay.add_widget(top)
        center = FloatLayout(size_hint=(1, 1))
        center.bind(on_touch_down=self._touch_center)
        self.overlay.add_widget(center)
        bot = BoxLayout(orientation='vertical', size_hint=(1, None),
                        height=dp(100), padding=[dp(12), dp(6)], spacing=dp(2))
        with bot.canvas.before:
            Color(0, 0, 0, .65); br = Rectangle()
        bot.bind(pos=lambda *_: setattr(br, 'pos', bot.pos),
                 size=lambda *_: setattr(br, 'size', bot.size))
        self.slider = Slider(min=0, max=1, value=0, cursor_size=(dp(22), dp(22)),
                             size_hint=(1, None), height=dp(32))
        self.slider.bind(on_touch_down=self._slider_down, on_touch_up=self._slider_up)
        bot.add_widget(self.slider)
        row = BoxLayout(size_hint=(1, None), height=dp(46), spacing=dp(8))
        self.time_lbl = Label(text="0:00 / 0:00", font_size=dp(11), color=C_SUB,
                              size_hint=(None, 1), width=dp(110),
                              halign='left', valign='middle')
        self.time_lbl.bind(size=self.time_lbl.setter('text_size'))
        self.prev_btn = FlatBtn(text="Anterior", bg=C_CARD, size_hint=(None, 1), width=dp(80))
        self.prev_btn.bind(on_release=self._prev)
        self.play_btn = FlatBtn(text="Pausar", bg=C_ACCENT, size_hint=(None, 1), width=dp(80))
        self.play_btn.bind(on_release=self._toggle)
        self.next_btn = FlatBtn(text="Próximo", bg=C_CARD, size_hint=(None, 1), width=dp(80))
        self.next_btn.bind(on_release=self._next)
        row.add_widget(self.time_lbl); row.add_widget(Widget(size_hint=(1, 1)))
        row.add_widget(self.prev_btn); row.add_widget(self.play_btn); row.add_widget(self.next_btn)
        bot.add_widget(row)
        self.overlay.add_widget(bot)
        self.add_widget(self.overlay)
        self.toast = TitleToast(size_hint=(1, None), height=dp(52),
                                pos_hint={'x': 0, 'y': 0})
        self.add_widget(self.toast)
        self._hide_evt = Clock.schedule_once(self._hide_ctrl, 4)

    def _fill(self, *_): self.video.pos = self.pos; self.video.size = self.size

    def _on_url(self, url, seek_to=0):
        if not url:
            self.status_lbl.text = "Não foi possível obter o vídeo."; return
        self.status_lbl.text = ''
        self.video.state = 'stop'; self.video.source = ''
        Clock.schedule_once(lambda dt: self._start(url, seek_to), 0.15)

    def _start(self, url, seek_to):
        self._fill(); self.video.source = url; self.video.state = 'play'
        self.play_btn.text = "Pausar"
        if seek_to and seek_to > 5:
            Clock.schedule_once(lambda dt: self._do_seek(seek_to), 2.5)
        if self._save_event: self._save_event.cancel()
        self._save_event = Clock.schedule_interval(self._auto_save, 5)

    def _do_seek(self, pos):
        try:
            if self.video.duration and pos < self.video.duration:
                self.video.seek(pos / self.video.duration)
        except Exception: pass

    def _on_dur(self, i, v):
        if v: self._duration = v; self.slider.max = v

    def _on_pos(self, i, v):
        if v and self._duration and not self._seeking:
            self.slider.value  = v
            self.time_lbl.text = f"{fmt_time(v)} / {fmt_time(self._duration)}"

    def _on_eos(self, i, v):
        if v:
            self._auto_save()
            Clock.schedule_once(lambda dt: self._next(None), 1.5)

    def _slider_down(self, slider, touch):
        if slider.collide_point(*touch.pos): self._seeking = True

    def _slider_up(self, slider, touch):
        if self._seeking and self._duration:
            self._seeking = False; self.video.seek(slider.value / self._duration)

    def _toggle_fs(self, *_):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            Window.fullscreen = 'auto'
            self.fs_btn.text = "[X] Sair Full"
        else:
            Window.fullscreen = False
            self.fs_btn.text = "[ ] Full"
        self._show_ctrl()

    def _touch_center(self, wid, touch):
        if wid.collide_point(*touch.pos):
            self._hide_ctrl() if self._ctrl_vis else self._show_ctrl()

    def _show_ctrl(self):
        Clock.unschedule(self._hide_evt)
        Animation(opacity=1, duration=.2).start(self.overlay)
        self._ctrl_vis = True
        self._hide_evt = Clock.schedule_once(self._hide_ctrl, 4)

    def _hide_ctrl(self, *_):
        Animation(opacity=0, duration=.3).start(self.overlay)
        self._ctrl_vis = False

    def _toggle(self, *_):
        if self.video.state == 'play':
            self.video.state = 'pause'; self.play_btn.text = "Retomar"
        else:
            self.video.state = 'play';  self.play_btn.text = "Pausar"
        self._show_ctrl()

    def _prev(self, *_):
        if self.ep_index > 0: self._load_ep(self.ep_index - 1)

    def _next(self, *_):
        if self.ep_index < len(self.episodes) - 1: self._load_ep(self.ep_index + 1)

    def _load_ep(self, new_idx):
        self._auto_save()
        name, embed = self.episodes[new_idx]
        self.ep_index = new_idx; self.ep_num = new_idx + 1
        self.ep_name  = name;    self.ep_lbl.text = name
        self.video.state = 'stop'; self.video.source = ''
        self.status_lbl.text = 'Buscando vídeo...'
        get_direct_url(embed, lambda u: self._on_url(u, self._saved_pos()))

    def _saved_pos(self):
        return (self.progress.get(self.title_name, {})
                .get(self.season_name, {})
                .get(f"ep_{self.ep_num}", {}).get("posicao", 0))

    def _auto_save(self, *_):
        pos = self.video.position or 0; dur = self.video.duration or 0
        if pos < 2: return
        self.on_save_progress(title=self.title_name, season=self.season_name,
                              ep_num=self.ep_num, posicao=pos, duracao=dur)

    def _back(self, *_):
        self._auto_save()
        if self._save_event: self._save_event.cancel()
        if self._fullscreen:
            self._fullscreen = False
            Window.fullscreen = False
        self._show_chrome()
        self.video.state = 'stop'; self.video.source = ''
        self.on_back()

# ── Root + App ────────────────────────────────────────────────────────────────

class PonyflixRoot(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._title   = None
        self._season  = None
        apply_bg(self, C_BG)
        self._build_chrome()
        self._show_splash()
        # Carrega dados em background, splash some ao terminar
        threading.Thread(target=self._load_data, daemon=True).start()

    def _show_splash(self):
        """Tela de abertura animada."""
        splash = FloatLayout(size_hint=(1, 1))
        with splash.canvas.before:
            Color(*C_BG)
            bg = Rectangle(pos=splash.pos, size=splash.size)
        splash.bind(pos=lambda *_: setattr(bg, 'pos', splash.pos),
                    size=lambda *_: setattr(bg, 'size', splash.size))

        # Logo central
        logo = Label(
            text="[b]PONY[color=#e638c8]FLIX[/color][/b]",
            markup=True, font_size=dp(58), color=C_TEXT,
            size_hint=(None, None), size=(dp(300), dp(80)),
            pos_hint={'center_x': .5, 'center_y': .56},
            halign='center', valign='middle',
        )
        logo.bind(size=logo.setter('text_size'))

        # Linha accent abaixo do logo
        line_w = FloatLayout(size_hint=(None, None), size=(dp(160), dp(3)),
                             pos_hint={'center_x': .5, 'center_y': .50})
        with line_w.canvas:
            Color(*C_ACCENT)
            Rectangle(pos=line_w.pos, size=line_w.size)
        line_w.bind(pos=lambda *_: setattr(line_w.canvas.children[-1], 'pos', line_w.pos))

        # Tagline
        tag = Label(
            text="✦  Sua magia, quando quiser  ✦",
            font_size=dp(13), color=C_SUB,
            size_hint=(1, None), height=dp(28),
            pos_hint={'center_x': .5, 'center_y': .44},
            halign='center', valign='middle',
        )
        tag.bind(size=tag.setter('text_size'))

        # Spinner / loading dots animado
        self._dots_lbl = Label(
            text="carregando", font_size=dp(11), color=C_DIM,
            size_hint=(1, None), height=dp(24),
            pos_hint={'center_x': .5, 'center_y': .34},
            halign='center', valign='middle',
        )
        self._dots_lbl.bind(size=self._dots_lbl.setter('text_size'))
        self._dots_tick = 0
        self._dots_evt  = Clock.schedule_interval(self._anim_dots, 0.45)

        # By ScaryHollow
        by = Label(
            text="[b][color=#d94fc3]ScaryHollow[/color][/b]",
            markup=True, font_size=dp(11), color=C_DIM,
            size_hint=(1, None), height=dp(20),
            pos_hint={'center_x': .5, 'y': 0.03},
            halign='center', valign='middle',
        )
        by.bind(size=by.setter('text_size'))

        splash.add_widget(logo)
        splash.add_widget(line_w)
        splash.add_widget(tag)
        splash.add_widget(self._dots_lbl)
        splash.add_widget(by)
        self._splash = splash
        self.body.add_widget(splash)

        # Anima entrada do logo
        logo.opacity = 0
        Animation(opacity=1, duration=0.7).start(logo)

    def _anim_dots(self, *_):
        dots = ["carregando", "carregando ·", "carregando ··", "carregando ···"]
        self._dots_tick = (self._dots_tick + 1) % len(dots)
        self._dots_lbl.text = dots[self._dots_tick]

    def _load_data(self):
        data     = load_episodes()
        progress = load_progress()
        Clock.schedule_once(lambda dt: self._on_loaded(data, progress), 1.0)

    def _on_loaded(self, data, progress):
        self.data     = data
        self.progress = progress
        if hasattr(self, '_dots_evt'): self._dots_evt.cancel()
        # Fade out splash, depois vai para home
        if hasattr(self, '_splash'):
            anim = Animation(opacity=0, duration=0.4)
            anim.bind(on_complete=lambda *_: self._go_titles())
            anim.start(self._splash)

    def _build_chrome(self):
        self._rbox = BoxLayout(orientation='vertical', size_hint=(1, 1))
        self.hdr   = RelativeLayout(size_hint=(1, None), height=dp(62))
        apply_bg(self.hdr, C_PANEL)
        al = Widget(size_hint=(1, None), height=dp(2), pos_hint={'x': 0, 'y': 0})
        with al.canvas:
            Color(*C_ACCENT); alr = Rectangle()
        al.bind(pos=lambda *_: setattr(alr, 'pos', al.pos),
                size=lambda *_: setattr(alr, 'size', al.size))
        self.hdr.add_widget(al)
        self.hdr_lbl = Label(text="[b]PONYFLIX[/b]", markup=True,
                             font_size=dp(23), color=C_TEXT,
                             size_hint=(1, 1), pos_hint={'x': 0, 'y': 0},
                             halign='center', valign='middle')
        self.hdr_lbl.bind(size=self.hdr_lbl.setter('text_size'))
        self.hdr.add_widget(self.hdr_lbl)
        self._rbox.add_widget(self.hdr)
        self.body = BoxLayout(size_hint=(1, 1))
        self._rbox.add_widget(self.body)
        self.ftr = BoxLayout(size_hint=(1, None), height=dp(30), padding=[dp(12), dp(5)])
        apply_bg(self.ftr, C_PANEL)
        cr = Label(text="By:  [b][color=#d94fc3]ScaryHollow[/color][/b]",
                   markup=True, font_size=dp(11), color=C_DIM,
                   size_hint=(1, 1), halign='right', valign='middle')
        cr.bind(size=cr.setter('text_size'))
        self.ftr.add_widget(cr)
        self._rbox.add_widget(self.ftr)
        self.add_widget(self._rbox)

    def _set(self, w):
        self.body.clear_widgets(); self.body.add_widget(w)

    def _go_titles(self):
        self._title  = None
        self._season = None
        self.hdr_lbl.text = "[b]PONYFLIX[/b]"
        self._set(TitlesScreen(self.data, self.progress, self._go_seasons))

    def _go_seasons(self, title_name):
        self._title  = title_name
        self._season = None   # limpa season ao entrar em temporadas
        self.hdr_lbl.text = f"[b]{title_name.upper()}[/b]"
        self._set(SeasonsScreen(
            title_name=title_name,
            seasons=self.data[title_name],
            progress=self.progress,
            on_season=self._go_episodes,
            on_back=self._go_titles,
        ))

    def _go_episodes(self, season_name):
        self._season = season_name
        self.hdr_lbl.text = f"[b]{season_name.upper()}[/b]"
        self._set(EpisodesScreen(
            title_name=self._title,
            season_name=season_name,
            episodes=self.data[self._title][season_name],
            progress=self.progress,
            on_play=self._go_player,
            on_back=lambda: self._go_seasons(self._title),
        ))

    def _go_player(self, ep_index, embed_url, ep_num):
        episodes = list(self.data[self._title][self._season].items())
        if IS_ANDROID:
            self._set(AndroidPlayerScreen(
                title_name=self._title, season_name=self._season,
                ep_index=ep_index, ep_num=ep_num,
                embed_url=embed_url,
                on_back=lambda: self._go_episodes(self._season),
                on_save_progress=self._save_progress,
            ))
        else:
            self._set(PCPlayerScreen(
                title_name=self._title, season_name=self._season,
                ep_index=ep_index, ep_num=ep_num,
                ep_name=episodes[ep_index][0],
                embed_url=embed_url,
                episodes_list=episodes,
                progress=self.progress,
                on_back=lambda: self._go_episodes(self._season),
                on_save_progress=self._save_progress,
            ))

    def _save_progress(self, title, season, ep_num, posicao, duracao):
        if title not in self.progress:   self.progress[title]         = {}
        if season not in self.progress[title]: self.progress[title][season] = {}
        self.progress[title][season]["episodio"]      = ep_num
        self.progress[title][season][f"ep_{ep_num}"]  = {"posicao": posicao, "duracao": duracao}
        save_progress(self.progress)


class PonyflixApp(App):
    title = "Ponyflix"

    def build(self):
        if IS_ANDROID:
            Window.bind(on_keyboard=self._on_keyboard)
        return PonyflixRoot()

    def _on_keyboard(self, window, key, *args):
        if key != 27:  # 27 = BACK no Android
            return False
        root = self.root
        ch   = root.body.children
        if not ch:
            return True

        screen = ch[0]

        # Player → volta aos episódios
        if isinstance(screen, AndroidPlayerScreen):
            screen._back()
            return True

        # Episódios (tem _season) → volta às temporadas
        if root._season is not None:
            s = root._season
            root._season = None
            root._go_seasons(root._title)
            return True

        # Temporadas (tem _title, sem _season) → volta aos títulos
        if root._title is not None:
            root._title = None
            root._go_titles()
            return True

        # Títulos → minimiza
        try:
            from android import activity
            activity.moveTaskToBack(True)
        except Exception:
            pass
        return True

    def on_pause(self):
        ch = self.root.body.children
        if ch and isinstance(ch[0], PCPlayerScreen): ch[0]._auto_save()
        return True

    def on_resume(self): pass


if __name__ == "__main__":
    PonyflixApp().run()