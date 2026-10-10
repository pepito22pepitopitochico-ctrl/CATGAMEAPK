[app]
title = Meow Mayhem
package.name = meowmayhem
package.domain = org.meowmayhem

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ico

version = 1.0

requirements = python3,pygame

icon.filename = %(source.dir)s/icon_512.png
presplash.filename = %(source.dir)s/presplash.png

orientation = landscape
fullscreen = 1

# El juego dibuja sus propios botones tactiles cuando corre en Android
# (variable de entorno ANDROID_ARGUMENT, que python-for-android define solo).

android.permissions =

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
