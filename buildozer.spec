[app]

# Nome e identificador do app
title = Ponyflix
package.name = ponyflix
package.domain = com.scaryhollow

# Arquivo principal
source.dir = .
source.include_exts = py,png,jpg,json
source.include_patterns = assets/*.png,episodios.json

# Versao
version = 1.0

# Dependencias Python
requirements = python3,kivy==2.3.0,pillow

# Orientacao: landscape para video
orientation = landscape

# Icone e presplash (opcional — coloque icon.png e presplash.png na pasta)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png

# Android
fullscreen = 0
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.archs = arm64-v8a, armeabi-v7a

# Gradle / AAB
android.release_artifact = apk

# Aceitar licencas automaticamente
android.accept_sdk_license = True

# Habilita suporte a Python 3
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
