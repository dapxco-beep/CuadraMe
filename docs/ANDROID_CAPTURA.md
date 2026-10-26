# CuadraMe Captura (app de Android)

Equivale a los Atajos de iPhone: lee las notificaciones de pago (Google Wallet, Nequi, Nu, bancos) y las manda a CuadraMe,
donde quedan «por confirmar». Código en `android/` (Kotlin, solo librerías base de AndroidX; permiso: solo `INTERNET`).

## Cómo funciona
1. La app tiene un servicio de «Acceso a notificaciones» (la persona lo activa en los ajustes de Android).
2. Solo mira las apps de la lista del servidor (`GET /movimientos/notificaciones-apps`, con copia de respaldo en `Apps.kt`).
   Cualquier otra app (chats, correo, redes) ni se lee ni se envía.
3. Manda el texto crudo a `POST /movimientos/rapido-notificacion` con la clave de conexión (`X-Api-Key`, la misma de los Atajos).
4. El servidor (`backend/app/notificaciones.py`) decide si es un movimiento (ignora códigos, promociones, avisos sin monto),
   lo crea «por confirmar» y NO duplica una notificación repetida. Si no hay internet, la app lo guarda y reintenta.

Para cubrir un banco o un formato nuevo NO hay que reinstalar la app: se agrega el paquete en `APPS` y/o una fila al corpus de
`backend/tests/test_notificaciones_android.py`.

## Compilar
Requisitos: JDK 17, Android SDK (plataforma 35) y `android/local.properties` con `sdk.dir=C:/Users/<usuario>/AppData/Local/Android/Sdk`.

```
cd android
./gradlew assembleDebug        # APK de pruebas (firma de depuración)
```

APK de lanzamiento, firmado con la llave de CuadraMe (vive en `DAPX/.secretos/`, NUNCA en el repositorio):

```
set -a; . ../../.secretos/daniel.env; set +a      # desde la carpeta del worktree
export ANDROID_KEYSTORE="$DANIEL_ANDROID_KEYSTORE" ANDROID_KEY_ALIAS="$DANIEL_ANDROID_KEY_ALIAS" \
       ANDROID_KEYSTORE_PASSWORD="$DANIEL_ANDROID_KEYSTORE_PASSWORD"
./gradlew assembleRelease      # app/build/outputs/apk/release/app-release.apk
cp app/build/outputs/apk/release/app-release.apk lanzamiento/cuadrame-captura-<versión>.apk   # copia guardada en el repositorio
# Publicarlo (solo cuando el backend ya tenga el endpoint de notificaciones desplegado):
cp lanzamiento/cuadrame-captura-<versión>.apk ../pwa/public/descargas/cuadrame-captura.apk
```

**La llave de firma no se puede perder ni cambiar:** Android solo deja actualizar la app instalada si el APK nuevo está firmado
con la misma llave. Para una versión nueva, sube `versionCode` en `app/build.gradle.kts`.

## Distribución
La pantalla «Registro automático» de la PWA ofrece la descarga en `/descargas/cuadrame-captura.apk` (si el archivo no está
publicado, muestra «estamos terminando de publicar»). No pasa por Play Store ni terceros; Android pide una vez «permitir instalar
desde esta fuente».

## Pendiente de probar con un teléfono real
- Los nombres de paquete de bancos (`com.todo1.mobile`, `com.davivienda.*`, etc.) y los textos reales de cada notificación.
- Que Samsung/Xiaomi/Huawei no cierren el servicio en segundo plano (batería «sin restricciones»).
