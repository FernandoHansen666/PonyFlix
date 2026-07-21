package br.com.scary.ponyflix;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

public class MainActivity extends Activity {

    private static final String SITE = "https://ponyflix.scary.com.br";

    private WebView web;
    private FullscreenChrome chrome;         // client guardado (getWebChromeClient é API 26+)
    private View customView;                 // vídeo em tela cheia (HTML5)
    private WebChromeClient.CustomViewCallback customCallback;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setSupportMultipleWindows(false);   // ignora popups (window.open) de anúncio

        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, String url) {
                return false;                 // navega dentro da própria WebView
            }
        });
        chrome = new FullscreenChrome();
        web.setWebChromeClient(chrome);

        setContentView(web);
        immersive();

        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else web.loadUrl(SITE);
    }

    private void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
              | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
              | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
              | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
              | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
              | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) immersive();
    }

    // Botão VOLTAR do controle: se estiver em vídeo cheio, fecha; senão delega
    // pro app web (voltar tela) e só sai quando já está na home.
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (customView != null) {                 // sai do vídeo em tela cheia
                chrome.onHideCustomView();
                return true;
            }
            web.evaluateJavascript("(window.__ponyBack ? window.__ponyBack() : true)", value -> {
                if ("false".equals(value)) finish();  // já na home → fecha o app
            });
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override protected void onPause()  { super.onPause();  web.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); immersive(); }

    @Override protected void onDestroy() {
        if (web != null) {
            ((ViewGroup) web.getParent()).removeView(web);
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }

    // Vídeo HTML5 em tela cheia (alguns players usam requestFullscreen()).
    private class FullscreenChrome extends WebChromeClient {
        @Override public void onShowCustomView(View view, CustomViewCallback callback) {
            if (customView != null) { callback.onCustomViewHidden(); return; }
            customView = view;
            customCallback = callback;
            ((FrameLayout) getWindow().getDecorView())
                    .addView(customView, new FrameLayout.LayoutParams(-1, -1));
            web.setVisibility(View.GONE);
            immersive();
        }
        @Override public void onHideCustomView() {
            if (customView == null) return;
            ((FrameLayout) getWindow().getDecorView()).removeView(customView);
            customView = null;
            if (customCallback != null) customCallback.onCustomViewHidden();
            web.setVisibility(View.VISIBLE);
            immersive();
        }
    }
}

