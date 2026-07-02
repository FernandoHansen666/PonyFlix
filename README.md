<div align="center">


# PonyFlix

Versão web leve do app PonyFlix — HTML, CSS e JavaScript puro. Sem build, sem backend, sem framework. Só abrir e assistir.

Assiste a todas as temporadas de **My Little Pony** direto do [pony.tube](https://pony.tube), com o mesmo visual roxo/rosa do app original.


</div>

---

## ✨ Funcionalidades

- 🎬 **Streaming direto** dos episódios via embed do pony.tube
- 📺 **Grade responsiva** de títulos e temporadas com capas personalizadas (2 a 5 colunas conforme a tela)
- 💾 **Continuar assistindo** — marca o último episódio de cada temporada (salvo no `localStorage`)
- ⏭️ **Anterior / Próximo** episódio dentro do player
- 🌐 **100% estático** — roda no GitHub Pages ou até abrindo o `index.html` direto
- 📱 Funciona em celular, tablet e PC

---

## 🚀 Rodar localmente

Os dados ficam embutidos em `episodios.js`, então **basta abrir o `index.html`** no navegador (duplo-clique) — o vídeo precisa de internet, o resto funciona offline.

Se preferir servir por HTTP (recomendado, evita qualquer limitação de `file://`):

```bash
python -m http.server 8000
# abra http://localhost:8000
```

---

## 🗂️ Estrutura

```
PonyFlix/
├── index.html        # marcação: splash, grid e player
├── style.css         # tema PonyFlix (roxo/rosa)
├── app.js            # navegação + progresso (localStorage)
├── episodios.js      # dados embutidos (window.PONYFLIX_DATA)
├── episodios.json    # mesma base, para servidores/scraper
└── assets/
    ├── covers/*.png  # capa por título (nome = slug do título)
    └── tN.png        # capa da temporada N
```

Navegação: **Títulos → Temporadas → Episódios → Player**.


---

## 📱 Gerar APK (opcional)

Por ser uma página web, dá pra empacotar num APK Android — é basicamente o que o app Kivy original fazia (um WebView).

- **[Capacitor](https://capacitorjs.com)** — empacota os arquivos dentro do APK (funciona sem depender do Pages). Precisa de Node.js + Android Studio.
- **[PWABuilder](https://www.pwabuilder.com)** — zero código: cola a URL do GitHub Pages e ele gera o APK.

---

## 🔄 Atualizar episódios


É só editar o `episodios.json`, seguindo o formato `{ "Título": { "Temporada": { "Episódio": "embed_url" } } }`.

---

## 🛠️ Stack

- HTML5 + CSS3 (grid responsivo, tema custom)
- JavaScript puro (sem dependências)
- [pony.tube](https://pony.tube) — fonte dos vídeos (embeds PeerTube)

---

<div align="center">

By: **[ScaryHollow](https://github.com/)**

</div>
=======

