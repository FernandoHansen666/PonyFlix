"""
PonyFlix — My Little Pony streaming app
By: ScaryHollow
"""

import json, os, re, threading, urllib.request
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.graphics import (Color, Rectangle, Line,
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

#  DETECÇÃO DE PLATAFORMA

IS_ANDROID = False
try:
    import android
    from android.storage import app_storage_path
    from android import mActivity
    IS_ANDROID = True
except ImportError:
    pass

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = (app_storage_path() if IS_ANDROID
              else BASE_DIR)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
PROGRESS_FILE = os.path.join(DATA_DIR, "progresso.json")

#  CORES

C_BG      = (0.04, 0.02, 0.08, 1)
C_PANEL   = (0.08, 0.04, 0.13, 1)
C_CARD    = (0.11, 0.06, 0.18, 1)
C_CARD_HL = (0.18, 0.08, 0.28, 1)
C_ACCENT  = (0.87, 0.28, 0.76, 1)
C_GOLD    = (1.00, 0.84, 0.26, 1)
C_TEXT    = (0.97, 0.93, 1.00, 1)
C_SUB     = (0.62, 0.52, 0.78, 1)
C_DIM     = (0.38, 0.28, 0.52, 1)

Window.clearcolor = C_BG

#  HELPERS
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
        print(f"[Ponyflix] save_progress error: {e}")

def fmt_time(seconds):
    s = int(seconds or 0)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def find_asset(filename):
    """
    Localiza arquivo de asset em qualquer plataforma.
    No Android o Buildozer copia assets para dentro do APK;
    o Kivy os expõe via caminho relativo 'assets/arquivo'.
    """
    candidates = [
        os.path.join(ASSETS_DIR, filename),          # PC normal
        os.path.join(BASE_DIR, "assets", filename),
        os.path.join(BASE_DIR, filename),
        os.path.join(DATA_DIR, "assets", filename),  # Android data dir
        os.path.join(DATA_DIR, filename),
        f"assets/{filename}",                        # caminho relativo (Android APK)
        filename,
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return f"assets/{filename}"   # Kivy resolve internamente no APK

def season_cover(season_name):
    num = season_name.strip().split()[-1]
    return find_asset(f"t{num}.png")

def load_episodes():
    """Carrega episodios.json de forma robusta."""
    candidates = [
        os.path.join(BASE_DIR, "episodios.json"),
        os.path.join(DATA_DIR, "episodios.json"),
        "episodios.json",
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    raise FileNotFoundError("episodios.json não encontrado.")

def apply_bg(widget, color):
    with widget.canvas.before:
        col  = Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *_: setattr(rect, 'pos', widget.pos),
        size=lambda *_: setattr(rect, 'size', widget.size),
    )

def get_direct_url(embed_url, callback):
    """
    Busca URL via API PeerTube.
    Android: HLS preferido (ExoPlayer nativo), MP4 como fallback.
    PC:      MP4 preferido (kivy.uix.video), HLS como fallback.
    """
    def _fetch():
        try:
            m = re.search(r'/embed/([a-zA-Z0-9\-_]+)', embed_url)
            if not m:
                Clock.schedule_once(lambda dt: callback(None, None)); return
            vid  = m.group(1)
            hm   = re.search(r'https?://([^/]+)', embed_url)
            host = hm.group(1) if hm else 'pony.tube'
            api  = f"https://{host}/api/v1/videos/{vid}"
            req  = urllib.request.Request(api, headers={"User-Agent": "PonyflixApp/3.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            title = data.get("name", "")

            # HLS (master playlist)
            hls_url = None
            for pl in data.get("streamingPlaylists", []):
                u = pl.get("playlistUrl", "")
                if u: hls_url = u; break

            # MP4 maior resolucao
            mp4_url = None
            for f in sorted(data.get("files", []),
                            key=lambda f: f.get("resolution", {}).get("id", 0),
                            reverse=True):
                u = f.get("fileUrl") or f.get("fileDownloadUrl", "")
                if u: mp4_url = u; break

            # Sempre: MP4 primeiro, HLS fallback (em ambas plataformas)
            url = mp4_url or hls_url

            if url:
                Clock.schedule_once(lambda dt, u=url, t=title: callback(u, t))
            else:
                Clock.schedule_once(lambda dt, t=title: callback(None, t))
        except Exception as e:
            print(f"[Ponyflix] API error: {e}")
            Clock.schedule_once(lambda dt: callback(None, None))
    threading.Thread(target=_fetch, daemon=True).start()

def open_video_android(url):
    """Abre URL no player nativo do Android via Intent."""
    try:
        from jnius import autoclass
        Intent = autoclass('android.content.Intent')
        Uri    = autoclass('android.net.Uri')
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(Uri.parse(url), "video/*")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        mActivity.startActivity(intent)
        return True
    except Exception as e:
        print(f"[Ponyflix] Intent error: {e}")
        return False

#  WIDGETS BASE

class FlatBtn(ButtonBehavior, Label):
    def __init__(self, bg=C_ACCENT, fg=C_TEXT, **kwargs):
        super().__init__(**kwargs)
        self._bg_n = bg
        self._bg_d = tuple(max(0, c-.2) if i<3 else c for i,c in enumerate(bg))
        self.color = fg; self.font_size = dp(13); self.bold = True
        self.halign = 'center'; self.valign = 'middle'
        self.bind(size=self.setter('text_size'))
        with self.canvas.before:
            self._col  = Color(*bg)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd, state=self._upd)

    def _upd(self, *_):
        self._col.rgba  = self._bg_d if self.state == 'down' else self._bg_n
        self._rect.pos  = self.pos; self._rect.size = self.size


class TitleToast(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint=(1,None); self.height=dp(52); self.opacity=0
        with self.canvas.before:
            Color(0,0,0,0.72)
            self._r = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self.lbl = Label(text='', font_size=dp(15), bold=True, color=C_TEXT,
                         size_hint=(1,1), pos_hint={'x':0,'y':0},
                         halign='center', valign='middle')
        self.lbl.bind(size=self.lbl.setter('text_size'))
        self.add_widget(self.lbl)

    def _upd(self, *_):
        self._r.pos=self.pos; self._r.size=self.size

    def show(self, text):
        self.lbl.text = text
        Animation.cancel_all(self); self.opacity=0
        (Animation(opacity=1,duration=.3)+Animation(opacity=1,duration=3.5)
         +Animation(opacity=0,duration=.5)).start(self)

#  HOME
class SeasonCard(Widget):
    def __init__(self, season_name, last_ep, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self._pressed = False
        self._tex     = None
        cover = season_cover(season_name)
        if cover:
            try: self._tex = CoreImage(cover).texture
            except Exception as e: print(f"[Ponyflix] capa erro: {e}")
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        w, h = self.width, self.height
        if w<=0 or h<=0: return
        self.canvas.clear()
        with self.canvas:
            Color(*(C_CARD_HL if self._pressed else C_CARD))
            Rectangle(pos=self.pos, size=self.size)
            if self._tex:
                StencilPush()
                Rectangle(pos=self.pos, size=self.size)
                StencilUse()
                tw, th = self._tex.width, self._tex.height
                scale  = max(w/tw, h/th)
                dw, dh = tw*scale, th*scale
                Color(1,1,1,1)
                Rectangle(texture=self._tex,
                          pos=(self.x+(w-dw)/2, self.y+(h-dh)/2),
                          size=(dw, dh))
                StencilUnUse()
                Rectangle(pos=self.pos, size=self.size)
                StencilPop()
            Color(0,0,0,0.55)
            Rectangle(pos=(self.x, self.y), size=(w, dp(40)))
            if self._pressed:
                Color(*C_ACCENT[:3], 0.25)
                Rectangle(pos=self.pos, size=self.size)
            Color(*C_ACCENT[:3], 0.45)
            Line(rectangle=(self.x+1,self.y+1,w-2,h-2), width=1.2)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._pressed=True; self._draw(); touch.grab(self); return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self); self._pressed=False; self._draw()
            if self.collide_point(*touch.pos): self.callback()
            return True


class HomeScreen(RelativeLayout):
    def __init__(self, data, progress, on_season, **kwargs):
        super().__init__(**kwargs)
        self._containers = []
        scroll = ScrollView(size_hint=(1,1), do_scroll_x=False)
        self._grid = GridLayout(cols=2, size_hint_y=None,
                                spacing=dp(6), padding=[dp(6)]*4)
        self._grid.bind(minimum_height=self._grid.setter('height'))

        for season, eps in data.items():
            prog    = progress.get(season, {})
            last_ep = prog.get("episodio")
            num     = season.split()[-1]
            c = FloatLayout(size_hint=(1,None), height=dp(160))
            c.add_widget(SeasonCard(
                season_name=season, last_ep=last_ep,
                callback=lambda s=season: on_season(s),
                size_hint=(1,1), pos_hint={'x':0,'y':0},
            ))
            lbl = Label(text=f"[b]Temporada {num}[/b]", markup=True,
                        font_size=dp(13), color=C_TEXT,
                        size_hint=(1,None), height=dp(36),
                        pos_hint={'x':0,'y':0},
                        halign='center', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            c.add_widget(lbl)
            if last_ep:
                c.add_widget(Label(text=f"> ep.{last_ep}", font_size=dp(9),
                                   color=C_GOLD, size_hint=(None,None),
                                   size=(dp(56),dp(16)),
                                   pos_hint={'right':0.97,'top':0.99}))
            self._grid.add_widget(c)
            self._containers.append(c)

        scroll.add_widget(self._grid)
        self.add_widget(scroll)
        Window.bind(size=self._sched)
        self.bind(size=self._sched)
        Clock.schedule_once(self._resize, 0.1)

    def _sched(self, *_):
        Clock.unschedule(self._resize)
        Clock.schedule_once(self._resize, 0.05)

    def _resize(self, *_):
        w = self.width if self.width>10 else Window.width
        cols = 4 if w>=dp(960) else 3 if w>=dp(640) else 2
        self._grid.cols = cols
        cw = (w - dp(12) - dp(6)*(cols-1)) / cols
        ch = max(dp(100), cw*9/16)
        self._grid.row_default_height = ch
        self._grid.row_force_default  = True
        for c in self._containers: c.height = ch

#  SEASON SCREEN

class EpRow(ButtonBehavior, BoxLayout):
    def __init__(self, num, name, pct, is_last, callback, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self.size_hint_y=None; self.height=dp(62)
        self.padding=[dp(12),dp(8)]; self.spacing=dp(10)
        self._sel=is_last; self.callback=callback
        with self.canvas.before:
            self._bg_col  = Color(*(C_CARD_HL if is_last else C_CARD))
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd, state=self._upd)
        if is_last:
            with self.canvas.before:
                Color(*C_ACCENT)
                self._sl = Rectangle(pos=self.pos, size=(dp(3),self.height))
            self.bind(pos=self._upd_sl, size=self._upd_sl)

        nlbl = Label(text=f"[b]{num:02d}[/b]", markup=True,
                     font_size=dp(15), color=C_ACCENT if is_last else C_SUB,
                     size_hint=(None,1), width=dp(38),
                     halign='center', valign='middle')
        nlbl.bind(size=nlbl.setter('text_size'))

        info = BoxLayout(orientation='vertical', size_hint=(1,1), spacing=dp(3))
        namelbl = Label(text=name, font_size=dp(13), color=C_TEXT,
                        halign='left', valign='middle', size_hint=(1,0.65))
        namelbl.bind(size=namelbl.setter('text_size'))
        info.add_widget(namelbl)

        bar = Widget(size_hint=(1,0.14))
        with bar.canvas:
            Color(*C_DIM);    bar_bg = Rectangle()
            Color(*C_ACCENT); bar_fg = Rectangle()
        def _db(*_):
            bar_bg.pos=bar.pos; bar_bg.size=bar.size; bar_fg.pos=bar.pos
            bar_fg.size=(bar.width*min(pct/100.,1.) if pct else 0, bar.height)
        bar.bind(pos=_db, size=_db)
        info.add_widget(bar)

        plbl = Label(text="Continuar" if is_last else "Play",
                     font_size=dp(11), color=C_GOLD if is_last else C_DIM,
                     size_hint=(None,1), width=dp(80),
                     halign='center', valign='middle')
        plbl.bind(size=plbl.setter('text_size'))
        self.add_widget(nlbl); self.add_widget(info); self.add_widget(plbl)

    def _upd(self, *_):
        hl = self.state=='down' or self._sel
        self._bg_col.rgba=C_CARD_HL if hl else C_CARD
        self._bg_rect.pos=self.pos; self._bg_rect.size=self.size

    def _upd_sl(self, *_):
        self._sl.pos=self.pos; self._sl.size=(dp(3),self.height)

    def on_release(self): self.callback()


class SeasonScreen(BoxLayout):
    def __init__(self, season_name, episodes, progress, on_play, on_back, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        prog=progress.get(season_name,{}); last_ep_num=prog.get("episodio")

        top = BoxLayout(size_hint=(1,None), height=dp(52),
                        padding=[dp(8),dp(7)], spacing=dp(8))
        apply_bg(top, C_PANEL)
        back = FlatBtn(text="< Voltar", bg=C_CARD, size_hint=(None,1), width=dp(90))
        back.bind(on_release=lambda x: on_back())
        title = Label(text=f"[b]{season_name}[/b]", markup=True,
                      font_size=dp(15), color=C_TEXT,
                      size_hint=(1,1), halign='left', valign='middle')
        title.bind(size=title.setter('text_size'))
        cnt = Label(text=f"{len(episodes)} ep.", font_size=dp(11), color=C_SUB,
                    size_hint=(None,1), width=dp(46), halign='right', valign='middle')
        top.add_widget(back); top.add_widget(title); top.add_widget(cnt)
        self.add_widget(top)

        scroll = ScrollView(size_hint=(1,1))
        vbox = BoxLayout(orientation='vertical', size_hint_y=None,
                         spacing=dp(5), padding=[dp(8),dp(8),dp(8),dp(20)])
        vbox.bind(minimum_height=vbox.setter('height'))
        for idx,(name,link) in enumerate(episodes.items()):
            num=idx+1
            ep_p=prog.get(f"ep_{num}",{})
            pos_s=ep_p.get("posicao",0); dur_s=ep_p.get("duracao",0)
            pct=(pos_s/dur_s*100) if dur_s else 0
            vbox.add_widget(EpRow(num=num, name=name, pct=pct,
                                  is_last=(last_ep_num==num),
                                  callback=lambda i=idx,l=link,n=num: on_play(i,l,n)))
        scroll.add_widget(vbox); self.add_widget(scroll)

#  PLAYER — Android abre intent nativo, PC usa Video embutido

class AndroidPlayerScreen(BoxLayout):
    """Tela de player para Android — abre vídeo no app nativo via Intent."""
    def __init__(self, season_name, ep_index, ep_num, ep_name,
                 embed_url, episodes_list, progress,
                 on_back, on_save_progress, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.season_name=season_name; self.ep_index=ep_index
        self.ep_num=ep_num; self.ep_name=ep_name
        self.episodes=episodes_list; self.on_back=on_back
        self.on_save_progress=on_save_progress; self.progress=progress
        apply_bg(self, C_BG)

        # Topo
        top = BoxLayout(size_hint=(1,None), height=dp(52),
                        padding=[dp(8),dp(7)], spacing=dp(8))
        apply_bg(top, C_PANEL)
        back = FlatBtn(text="< Voltar", bg=C_CARD, size_hint=(None,1), width=dp(90))
        back.bind(on_release=lambda x: on_back())
        self.title_lbl = Label(text=f"[b]{ep_name}[/b]", markup=True,
                               font_size=dp(13), color=C_TEXT,
                               size_hint=(1,1), halign='left', valign='middle',
                               shorten=True, shorten_from='right')
        self.title_lbl.bind(size=self.title_lbl.setter('text_size'))
        top.add_widget(back); top.add_widget(self.title_lbl)
        self.add_widget(top)

        # Centro
        center = FloatLayout(size_hint=(1,1))
        apply_bg(center, C_BG)
        self.status_lbl = Label(
            text="Buscando link do episódio...",
            font_size=dp(14), color=C_SUB,
            size_hint=(.8,None), height=dp(60),
            pos_hint={'center_x':.5,'center_y':.65},
            halign='center', valign='middle')
        self.status_lbl.bind(size=self.status_lbl.setter('text_size'))
        center.add_widget(self.status_lbl)

        self.play_btn = FlatBtn(
            text="▶  Abrir no Player", bg=C_ACCENT,
            size_hint=(None,None), size=(dp(220),dp(54)),
            pos_hint={'center_x':.5,'center_y':.42}, opacity=0)
        self.play_btn.bind(on_release=self._open_player)
        center.add_widget(self.play_btn)
        self.add_widget(center)

        # Nav
        nav = BoxLayout(size_hint=(1,None), height=dp(52),
                        padding=[dp(8),dp(6)], spacing=dp(8))
        apply_bg(nav, C_PANEL)
        pb = FlatBtn(text="< Anterior", bg=C_CARD, size_hint=(1,1))
        pb.bind(on_release=self._prev)
        nb = FlatBtn(text="Próximo >", bg=C_CARD, size_hint=(1,1))
        nb.bind(on_release=self._next)
        nav.add_widget(pb); nav.add_widget(nb)
        self.add_widget(nav)

        self._current_url = None
        get_direct_url(embed_url, self._on_url)

    def _on_url(self, url, title):
        if not url:
            self.status_lbl.text = "Não foi possível obter o link.\nVerifique a conexão."
            return
        self._current_url = url
        ep_title = title or self.ep_name
        self.title_lbl.text = f"[b]{ep_title}[/b]"
        self.status_lbl.text = f"{ep_title}\n\nToque no botão para assistir."
        self.play_btn.opacity = 1

    def _open_player(self, *_):
        if self._current_url:
            open_video_android(self._current_url)
            self.on_save_progress(season=self.season_name,
                                  ep_num=self.ep_num, posicao=1, duracao=1)

    def _prev(self, *_):
        if self.ep_index > 0: self._load_ep(self.ep_index-1)

    def _next(self, *_):
        if self.ep_index < len(self.episodes)-1: self._load_ep(self.ep_index+1)

    def _load_ep(self, new_idx):
        name, embed = self.episodes[new_idx]
        self.ep_index=new_idx; self.ep_num=new_idx+1; self.ep_name=name
        self.title_lbl.text=f"[b]{name}[/b]"
        self.status_lbl.text="Buscando link do episódio..."
        self.play_btn.opacity=0; self._current_url=None
        get_direct_url(embed, self._on_url)


class PCPlayerScreen(FloatLayout):
    """Player embutido para PC usando kivy.uix.video."""
    def __init__(self, season_name, ep_index, ep_num, ep_name,
                 embed_url, episodes_list, progress,
                 on_back, on_save_progress, **kwargs):
        super().__init__(**kwargs)
        self.season_name=season_name; self.ep_index=ep_index
        self.ep_num=ep_num; self.ep_name=ep_name; self.embed_url=embed_url
        self.episodes=episodes_list; self.on_back=on_back
        self.on_save_progress=on_save_progress; self.progress=progress
        self._duration=0; self._save_event=None
        self._ctrl_vis=True; self._hide_evt=None; self._fullscreen=False
        self._build()
        saved=self._saved_pos()
        self._set_status("Buscando vídeo...")
        get_direct_url(embed_url, lambda u,t: self._on_url(u,t,saved))

    def _build(self):
        with self.canvas.before:
            Color(0,0,0,1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        self.video = Video(source='', state='stop', size_hint=(None,None))
        self.video.bind(duration=self._on_dur, position=self._on_pos, eos=self._on_eos)
        self.add_widget(self.video)
        self.bind(pos=self._fill, size=self._fill)

        self.status_lbl = Label(text='', font_size=dp(14), color=C_SUB,
                                size_hint=(.85,None), height=dp(50),
                                pos_hint={'center_x':.5,'center_y':.5},
                                halign='center', valign='middle')
        self.status_lbl.bind(size=self.status_lbl.setter('text_size'))
        self.add_widget(self.status_lbl)

        self.overlay = BoxLayout(orientation='vertical', size_hint=(1,1),
                                 pos_hint={'x':0,'y':0})
        top = BoxLayout(size_hint=(1,None), height=dp(54),
                        padding=[dp(8),dp(8)], spacing=dp(8))
        with top.canvas.before:
            Color(0,0,0,.6)
            tr=Rectangle()
        top.bind(pos=lambda *_: setattr(tr,'pos',top.pos),
                 size=lambda *_: setattr(tr,'size',top.size))
        back_btn = FlatBtn(text="< Voltar", bg=C_CARD, size_hint=(None,1), width=dp(90))
        back_btn.bind(on_release=self._back)
        self.ep_lbl = Label(text=self.ep_name, font_size=dp(13), color=C_TEXT,
                            size_hint=(1,1), halign='left', valign='middle',
                            shorten=True, shorten_from='right')
        self.ep_lbl.bind(size=self.ep_lbl.setter('text_size'))
        self.fs_btn = FlatBtn(text="[ ] Tela Cheia", bg=C_CARD,
                              size_hint=(None,1), width=dp(115))
        self.fs_btn.bind(on_release=self._toggle_fs)
        top.add_widget(back_btn); top.add_widget(self.ep_lbl); top.add_widget(self.fs_btn)
        self.overlay.add_widget(top)

        center = Widget(size_hint=(1,1))
        center.bind(on_touch_down=self._touch_center)
        self.overlay.add_widget(center)

        bot = BoxLayout(orientation='vertical', size_hint=(1,None),
                        height=dp(100), padding=[dp(12),dp(6)], spacing=dp(2))
        with bot.canvas.before:
            Color(0,0,0,.65)
            br=Rectangle()
        bot.bind(pos=lambda *_: setattr(br,'pos',bot.pos),
                 size=lambda *_: setattr(br,'size',bot.size))
        self.slider = Slider(min=0, max=1, value=0, cursor_size=(dp(22),dp(22)),
                             size_hint=(1,None), height=dp(32))
        self.slider.bind(on_touch_up=self._seek)
        bot.add_widget(self.slider)
        row = BoxLayout(size_hint=(1,None), height=dp(46), spacing=dp(8))
        self.time_lbl = Label(text="0:00 / 0:00", font_size=dp(11), color=C_SUB,
                              size_hint=(None,1), width=dp(110),
                              halign='left', valign='middle')
        self.time_lbl.bind(size=self.time_lbl.setter('text_size'))
        sp=Widget(size_hint=(1,1))
        self.prev_btn=FlatBtn(text="Anterior",bg=C_CARD,size_hint=(None,1),width=dp(80))
        self.prev_btn.bind(on_release=self._prev)
        self.play_btn=FlatBtn(text="Pausar",bg=C_ACCENT,size_hint=(None,1),width=dp(80))
        self.play_btn.bind(on_release=self._toggle)
        self.next_btn=FlatBtn(text="Próximo",bg=C_CARD,size_hint=(None,1),width=dp(80))
        self.next_btn.bind(on_release=self._next)
        row.add_widget(self.time_lbl); row.add_widget(sp)
        row.add_widget(self.prev_btn); row.add_widget(self.play_btn); row.add_widget(self.next_btn)
        bot.add_widget(row); self.overlay.add_widget(bot)
        self.add_widget(self.overlay)

        self.toast=TitleToast(size_hint=(1,None), height=dp(52),
                              pos_hint={'x':0,'y':0})
        self.add_widget(self.toast)
        self._hide_evt=Clock.schedule_once(self._hide_ctrl,4)

    def _upd_bg(self,*_): self._bg.pos=self.pos; self._bg.size=self.size
    def _fill(self,*_): self.video.pos=self.pos; self.video.size=self.size
    def _set_status(self,msg): self.status_lbl.text=msg

    def _on_url(self, url, title, seek_to=0):
        if not url:
            self._set_status("Não foi possível obter o vídeo.\nVerifique a conexão.")
            return
        self._set_status("")
        if title:
            self.ep_lbl.text=title
            Clock.schedule_once(lambda dt: self.toast.show(title), 0.4)
        self.video.state='stop'; self.video.source=''
        Clock.schedule_once(lambda dt: self._start(url,seek_to), 0.15)

    def _start(self, url, seek_to):
        self._fill(); self.video.source=url; self.video.state='play'
        self.play_btn.text="Pausar"
        if seek_to and seek_to>5:
            Clock.schedule_once(lambda dt: self._do_seek(seek_to), 2.5)
        if self._save_event: self._save_event.cancel()
        self._save_event=Clock.schedule_interval(self._auto_save,5)

    def _do_seek(self,pos):
        try:
            if self.video.duration and pos<self.video.duration:
                self.video.seek(pos/self.video.duration)
        except Exception: pass

    def _on_dur(self,i,v):
        if v: self._duration=v; self.slider.max=v

    def _on_pos(self,i,v):
        if v and self._duration:
            self.slider.value=v
            self.time_lbl.text=f"{fmt_time(v)} / {fmt_time(self._duration)}"

    def _on_eos(self,i,v):
        if v:
            self._auto_save()
            Clock.schedule_once(lambda dt: self._next(None), 1.5)

    def _toggle_fs(self,*_):
        self._fullscreen=not self._fullscreen
        try:
            rb=App.get_running_app().root.children[0]
            hdr=rb.children[2]; ftr=rb.children[0]
            if self._fullscreen:
                hdr.height=0; hdr.opacity=0; ftr.height=0; ftr.opacity=0
                self.fs_btn.text="[X] Sair"
            else:
                hdr.height=dp(56); hdr.opacity=1
                ftr.height=dp(26); ftr.opacity=1
                self.fs_btn.text="[ ] Tela Cheia"
        except Exception as e: print(f"[FS] {e}")
        self._show_ctrl()

    def _touch_center(self,wid,touch):
        if wid.collide_point(*touch.pos):
            self._hide_ctrl() if self._ctrl_vis else self._show_ctrl()

    def _show_ctrl(self):
        Clock.unschedule(self._hide_evt)
        Animation(opacity=1,duration=.2).start(self.overlay)
        self._ctrl_vis=True
        self._hide_evt=Clock.schedule_once(self._hide_ctrl,4)

    def _hide_ctrl(self,*_):
        Animation(opacity=0,duration=.3).start(self.overlay)
        self._ctrl_vis=False

    def _toggle(self,*_):
        if self.video.state=='play':
            self.video.state='pause'; self.play_btn.text="Retomar"
        else:
            self.video.state='play'; self.play_btn.text="Pausar"
        self._show_ctrl()

    def _seek(self,slider,touch):
        if slider.collide_point(*touch.pos) and self._duration:
            self.video.seek(slider.value/self._duration)

    def _prev(self,*_):
        if self.ep_index>0: self._load_ep(self.ep_index-1)

    def _next(self,*_):
        if self.ep_index<len(self.episodes)-1: self._load_ep(self.ep_index+1)

    def _load_ep(self, new_idx):
        self._auto_save()
        name,embed=self.episodes[new_idx]
        self.ep_index=new_idx; self.ep_num=new_idx+1
        self.ep_name=name; self.embed_url=embed
        self.ep_lbl.text=name
        self.video.state='stop'; self.video.source=''
        self._set_status("Buscando vídeo...")
        saved=self._saved_pos()
        get_direct_url(embed, lambda u,t: self._on_url(u,t,saved))

    def _saved_pos(self):
        return (self.progress.get(self.season_name,{})
                .get(f"ep_{self.ep_num}",{}).get("posicao",0))

    def _auto_save(self,*_):
        pos=self.video.position or 0; dur=self.video.duration or 0
        if pos<2: return
        self.on_save_progress(season=self.season_name, ep_num=self.ep_num,
                              posicao=pos, duracao=dur)

    def _back(self,*_):
        self._auto_save()
        if self._save_event: self._save_event.cancel()
        if self._fullscreen: self._fullscreen=True; self._toggle_fs()
        self.video.state='stop'; self.video.source=''
        self.on_back()


def PlayerScreen(**kwargs):
    """Retorna o player correto para a plataforma atual."""
    if IS_ANDROID:
        return AndroidPlayerScreen(**kwargs)
    return PCPlayerScreen(**kwargs)


#  ROOT + APP

class PonyflixRoot(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data=load_episodes()
        self.progress=load_progress(); self._cur_season=None
        apply_bg(self, C_BG)
        self._build_chrome(); self._go_home()

    def _build_chrome(self):
        self._rbox=BoxLayout(orientation='vertical', size_hint=(1,1))
        self.hdr=RelativeLayout(size_hint=(1,None), height=dp(56))
        apply_bg(self.hdr, C_PANEL)
        al=Widget(size_hint=(1,None), height=dp(2), pos_hint={'x':0,'y':0})
        with al.canvas:
            Color(*C_ACCENT)
            alr=Rectangle()
        al.bind(pos=lambda *_: setattr(alr,'pos',al.pos),
                size=lambda *_: setattr(alr,'size',al.size))
        self.hdr.add_widget(al)
        self.hdr_lbl=Label(text="[b]PONYFLIX[/b]", markup=True,
                           font_size=dp(21), color=C_TEXT,
                           size_hint=(1,1), pos_hint={'x':0,'y':0},
                           halign='center', valign='middle')
        self.hdr_lbl.bind(size=self.hdr_lbl.setter('text_size'))
        self.hdr.add_widget(self.hdr_lbl)
        self._rbox.add_widget(self.hdr)

        self.body=BoxLayout(size_hint=(1,1))
        self._rbox.add_widget(self.body)

        self.ftr=BoxLayout(size_hint=(1,None), height=dp(26), padding=[dp(10),dp(4)])
        apply_bg(self.ftr, C_PANEL)
        cr=Label(text="By:  [b][color=#d94fc3]ScaryHollow[/color][/b]",
                 markup=True, font_size=dp(11), color=C_DIM,
                 size_hint=(1,1), halign='right', valign='middle')
        cr.bind(size=cr.setter('text_size'))
        self.ftr.add_widget(cr)
        self._rbox.add_widget(self.ftr)
        self.add_widget(self._rbox)

    def _set_screen(self,w): self.body.clear_widgets(); self.body.add_widget(w)

    def _go_home(self):
        self.hdr_lbl.text="[b]PONYFLIX[/b]"
        self._set_screen(HomeScreen(data=self.data, progress=self.progress,
                                    on_season=self._go_season))

    def _go_season(self, season_name):
        self._cur_season=season_name
        self.hdr_lbl.text=f"[b]{season_name.upper()}[/b]"
        self._set_screen(SeasonScreen(season_name=season_name,
                                      episodes=self.data[season_name],
                                      progress=self.progress,
                                      on_play=self._go_player,
                                      on_back=self._go_home))

    def _go_player(self, ep_index, embed_url, ep_num):
        season=self._cur_season
        episodes=list(self.data[season].items())
        self.hdr_lbl.text=f"[b]{season}[/b]"
        self._set_screen(PlayerScreen(
            season_name=season, ep_index=ep_index, ep_num=ep_num,
            ep_name=episodes[ep_index][0], embed_url=embed_url,
            episodes_list=episodes, progress=self.progress,
            on_back=lambda: self._go_season(season),
            on_save_progress=self._save_progress,
        ))

    def _save_progress(self, season, ep_num, posicao, duracao):
        if season not in self.progress: self.progress[season]={}
        self.progress[season]["episodio"]=ep_num
        self.progress[season][f"ep_{ep_num}"]={"posicao":posicao,"duracao":duracao}
        save_progress(self.progress)


class PonyflixApp(App):
    title="Ponyflix"

    def build(self): return PonyflixRoot()

    def on_pause(self):
        ch=self.root.body.children
        if ch and isinstance(ch[0], PCPlayerScreen): ch[0]._auto_save()
        return True

    def on_resume(self): pass


if __name__=="__main__":
    PonyflixApp().run()
