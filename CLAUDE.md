# CLAUDE.md

## Qué es

Una factory de reels de Instagram operada desde Claude Code. Entra un **reel de referencia** + **instrucciones** (texto o audio de WhatsApp) + **clips crudos**; sale un **reel listo para subir**. Claude toma las decisiones creativas; Fernando aprueba el guion antes del render.

Es multimarca: cada marca vive en `marcas/<marca>/marca.yaml`, con su estética en `estilo:`. El repo trae dos marcas de ejemplo ficticias: un salón de peluquería (`salon-demo`) y una cuenta de divulgación de historia (`historia-breve`), que muestra cómo una marca pisa la estética por defecto sin tocar código.

**Formatos:** reel (el flujo de abajo), historia (`armar_historia.py`), foto y carrusel (`armar_foto.py`). Todos usan el estilo de la marca, textos de ella y la rúbrica filtrada por formato. La descripción de cada uno sigue `conocimiento/11-descripciones.md`.

## Flujo de un pedido

Todo pasa por archivos dentro de `pedidos/<AAAA-MM-DD>-<marca>-<slug>/`, así cada paso se puede rehacer sin repetir los anteriores:

1. **Entrada**: `pedido.yaml` (copiado de `pedidos/_plantilla/`) y `entrada/` con `referencia.mp4` o `referencia.url`, `instrucciones.txt|ogg` y `crudos/`.
2. **Análisis**: `analisis/referencia.json` (cortes, ritmo, beats, estructura, textos en pantalla) y `analisis/crudos.json` (tomas útiles, silencios, calidad).
3. **Guion**: `plan/guion.yaml`, la lista de edición. Cada decisión (gancho, ritmo, textos, cierre) tiene que poder justificarse con `conocimiento/`. **Punto de control: no renderizar sin el OK de Fernando.**
4. **Render** según el formato: montajes con música → HyperFrames `music-to-video`; habla a cámara → cortes con ffmpeg + `embedded-captions`; promo → composición HyperFrames. Remotion es el respaldo.
5. **Fábrica y control de calidad**: `herramientas/fabrica.py` corre los pasos mecánicos (clips, composición, render, audio, `verificar.py`) (técnico + hoja con la zona segura oficial 14/35/6 sombreada) y después **`conocimiento/rubrica.yaml`**: los puntos van a `salida/puntos.yaml`, `puntaje.py` calcula, y se escribe `salida/evaluacion.md`. Si un bloqueante falla, se corrige antes de entregar.
6. **Salida**: `salida/reel.mp4`, `portada.jpg`, `caption.txt` (servicio y ciudad con palabras, ≤3 hashtags), `informe.md` (decisiones, cómo publicarlo: audio, colaboradora, carrusel si son fotos), `evaluacion.md` y `para-<quien>.txt` (el mensaje para quien publica, `mensaje:` en `marca.yaml`: `para-ana.txt`, `para-pablo.txt`; lo arma la fábrica a partir de `publicar` en el plan).
7. **Después de publicar**: métricas a las 72 h y a los 7 días en `salida/metricas.md`, leídas con `conocimiento/06-medicion.md`. Salen del MCP de Metricool (`metricool.py`) y la captura queda de respaldo. Solo lectura: las herramientas que programan o editan publicaciones están en `permissions.deny`.

**Reversiones:** un reel ya publicado se rehace bajándolo de la biblioteca como `entrada/original.mp4`. Instagram no deja cambiar el video de un reel publicado: se archiva el original y se sube el nuevo.

Un reel que salió bien se puede promover a `estilos/<estilo>/` para reusarlo cambiando clips y textos.

## Herramientas (`herramientas/`, con `uv run python …`)

- **`fabrica.py <pedido> [--solo PASO] [--forzar] [--sin-check]`**: el comando de todos los días.
  - Detecta el formato por el plan (`guion.yaml`, `historia.yaml` o `publicacion.yaml`) y corre en orden los pasos de abajo.
  - Saltea los pasos que no cambiaron: guarda una huella de sus entradas en `render/.fabrica.json`. Si solo cambian notas o `publicar`, rehace solo el mensaje.
  - Al final lista lo que falta escribir con criterio (caption, informe, puntos, `publicar.permisos`).
  - Rehace la portada cuando cambia el video, salvo que se haya reemplazado a mano.
  - Cuando no falta nada, escribe `salida/para-<quien>.txt`, el mensaje de WhatsApp para reenviarle tal cual: OK de la clienta, qué subir, qué audio y desde dónde, portada, colaboradora y descripción.

- `bajar.py <url|id> … [--destino] [--forzar]`: baja reels en la mejor calidad (video y audio por separado: así llega a 1080p, el archivo combinado se queda en 720p). Usa `secretos/instagram-cookies.txt` si existe (sesión exportada del navegador, nunca a git) para los reels viejos que sin sesión no pasan de 360-480p.
- `movimiento.py <video>`: clasifica cada medio segundo en estable / paneo / barrido / temblor / borroso (flujo óptico sobre los bordes del cuadro; los cortes de plano no cuentan como movimiento) → JSON + gráfico. El análisis del video entero se guarda junto a él (`<video>.movimiento.json`, se invalida si cambia el video o el código) y `inventario.py` y `preparar_clips.py` lo recortan por tramo: cada fuente se analiza una sola vez.
- `analizar_referencia.py <pedido>`: tomas, ritmo, beats y habla de la referencia → `analisis/referencia.json`. El bpm se verifica con los cortes (librosa confunde octavas y 2/3) y deja `bpm_grilla` para el guion; `analizar_audio.py --bpm` sigue ese tempo.
- `inventario.py <pedido>`: crudos (fotos y videos) → `analisis/crudos.json`.
- `biblioteca.py marcas/<marca>/biblioteca [--calidad | --buscar "rulos 1080p"]`: cataloga los reels ya publicados (bajados con yt-dlp a `biblioteca/reels/`), distinguiendo foto de video, con una hoja por reel (en los de más de 18 tomas, 18 repartidas). `--calidad` suma resolución y movimiento. Lo que hay adentro de cada reel está en `lecturas.yaml` (servicio, quién aparece, si está Ana, mejores tramos con segundos, notas como marca de agua o texto quemado, etiquetas), escrito por Claude mirando las hojas; los reels nuevos se leen al catalogarlos. `--buscar` cruza todo eso y lista los tramos útiles. Sirve cuando no hay material nuevo: su mejor material suele estar adentro de reels largos.
- `preparar_clips.py <pedido>`: corta los tramos del guion, saca las barras negras, llena 9:16, ajusta la velocidad a los beats e interpola en cámara lenta → `render/assets/clips/`. Por toma: `encuadre` (recorte a mano, p. ej. para sacar un texto quemado), `espejar`, `comparar` (dos clips para la pantalla dividida), `estabilizar` (auto por defecto: vidstab si hay temblor) y `rol` (toma / revelado / barrido, para el chequeo de ritmo). La cámara lenta interpolada se usa solo en tomas quietas; con paneo, mezcla de cuadros (la interpolación deforma). `realce: true` (guion o toma) suma nitidez de luminancia y +8 % de saturación sin tocar el tono. Al final iguala el color entre tomas (`color.py`): acerca brillo (gamma) y balance (medido en píxeles neutros) a la toma del revelado, a mitad de camino y con topes. No toca la referencia ni los lados de una comparación; se apaga con `igualar_color: false` (guion) o `color: false` (toma). Deja `analisis/color.json`.
- `armar_pop.py <pedido> [--texto gancho="…"]`: **el motor de reels.** Arma `render/index.html` desde el guion con la dirección de arte de la marca (`estilo.py`): tipografía de display, stickers, destellos, transiciones, color y grano. `--texto` sirve para variantes. Escenas: tomas con `entrada` (corte/golpe/zoom/barrido/luz/temblor/humo), `comparar` (antes | después), `insertos` (archivo enmarcado, placas de sección, rótulos y mapas con la ruta de un viaje encima de la toma mientras la voz sigue) y cierre; La altura de cada título también la elige solo: busca caras en sus tomas (`caras.py`) y usa la línea libre más cercana al 62 % (`textos[].base` la fija a mano). Mide cada título con la fuente de la marca (`legibilidad.franja_titulo`) y, si no entra entre la base y el 14 %, lo achica (hasta el 70 %). El fondo de cada título lo elige solo, midiendo el clip (`legibilidad.py`): sobre fondo claro, palabras en bloques del resaltador de la marca; sobre oscuro o medio, sombra difusa (`textos[].fondo` lo fuerza). `estilo_ajustes:` en el guion pisa tokens del estilo solo para ese reel (la tipografía de una tendencia, menos grano con material nítido).
- `analizar_audio.py <audio|video|link de reel> --largo s [--letra]`: bpm, beats reales, tiempos 1, mejores tramos y letra con tiempos. Se guarda en `analisis/audio.json` y el guion lo referencia en `musica.analisis`: los cortes caen en los beats reales (`comun.duraciones`).
- `musica.py [--buscar tag | --bajar id… --tag t | --sugerir bpm --rango a b [--voz] | --usados]`: temas libres de derechos de Mixkit (solo los de licencia libre comercial) en `musica/catalogo.yaml`; sugiere los no usados por bpm y nunca repite un tema entre pedidos (Q5).
- `separar.py entrada.wav voz.wav`: separa la voz de la música (MDX-Net Kim_Vocal_2, `herramientas/bin/modelos/`). `voz.py` la usa al extraer la voz de una toma: lo que la ensucia suele ser la canción del reel original.
- `audio.py <pedido> [--musica tema.wav --inicio s]`: según `musica.modo` (`conocimiento/09-audio.md`): `archivo` (tema libre, uno distinto por reel), `sintetica` (respaldo: base propia que varía según el pedido) → `salida/reel-con-audio.mp4` a -14 LUFS; `instagram` → `salida/reel-efectos.mp4` (solo efectos) + la instrucción de qué audio elegir y dónde arrancarlo.
- `armar_historia.py <pedido>`: historia de Instagram desde `plan/historia.yaml` (foto o video, plantilla novedad / turno / resultado / detras / teaser, título, nota, firma con su logo, franja libre para el sticker) → `salida/historia.mp4` + `historia.jpg`. Ver `conocimiento/10-historias.md`.
- `armar_foto.py <pedido>`: publicación de foto o carrusel 3:4 (1080×1440) desde `plan/publicacion.yaml`, con placas `portada`, `foto`, `precios` y `cierre` → `salida/placa-NN.jpg`. Por placa, `foco` (qué se conserva al recortar a 3:4) y `zoom` (acerca alrededor del foco, para dejar afuera lo que distrae en un borde).
- `metricool.py <volcado> [--probar] | --campos <tipo>`: carga en cada pedido las métricas de un volcado del MCP de Metricool (`marcas/<marca>/metricool/`, versionado: es la única foto de las 72 h). Une cada publicación con su pedido por `link` o por la descripción (excluye los reels que el plan cita como material), pasa las unidades (ms → s, salteo = 100 − vistas de 3 s) y no pisa lo que solo da una captura (pozo, no seguidores).
- `metricas.py [--marca]`: junta los `salida/metricas.md` de todos los pedidos (plantilla en `pedidos/_plantilla/`) con el formato, el bpm y la duración de cada guion, y escribe `marcas/<marca>/metricas.md`. Arma una tabla por formato con retención (tiempo medio / duración), salteo, envíos y me gusta sobre alcance, y marca lo que queda fuera del objetivo de `06-medicion.md`.
- `puntaje.py <pedido>`: puntaje de la rúbrica desde `salida/puntos.yaml`, filtrado por formato (`aplica_a` de cada criterio), con el veredicto. Si falta puntuar un criterio, no calcula.
- `caras.py`: caras en las tomas con YuNet (umbral 0,85: una mano con un cepillo daba 0,83) (`herramientas/modelos/face_detection_yunet_2023mar.onnx`, opencv_zoo, MIT; OpenCV 5 ya no trae las cascadas Haar) y la altura de título que no las tapa. No ve el pelo como sujeto (un rodete): eso se mira en la hoja.
- `estilo.py`: la dirección de arte en un solo lugar (M-23). Un `Estilo` con los tokens (claro, sombra, calidez, destellos, fondo, corrección, viñeta, grano, cierre, resaltador, subtítulos y fuentes), el CSS base, las capas del look, la animación del grano, `palabras`, `destellos` y la copia de logo y fuentes. Los valores por defecto son los de salon-pop; cada marca pisa lo que quiera con `estilo:` en su `marca.yaml` (`de_marca`). Lo importan `armar_pop.py`, `armar_historia.py`, `armar_foto.py` y las composiciones a medida (`salon_pop.py` quedó como alias de las viejas).
- `render.py`: la versión fijada de HyperFrames, ffmpeg en el PATH y la llamada a `render` y `check`.
- `voz.py`: si alguien habla en un tramo (Whisper; descarta canciones por idioma y confianza). `preparar_clips.py` conserva esa voz, `audio.py` baja la música debajo y `armar_pop.py` le pone subtítulos. `voz: true | false` por toma lo fuerza. Ver `conocimiento/09-audio.md` › Voz.
- `retoque.py`: afina un contorno de una foto (un brazo), como el «licuar» de un editor. En el guion, `afinar:` por toma (puntos del borde, radio y corrimiento); `preparar_clips.py` lo aplica antes del recorte. Conviene que del lado de afuera del borde haya algo liso: el ladrillo y los carteles se doblan. Mostrar el antes y después antes de mandarlo.
- `mapa.py`: los mapas de los insertos `{tipo: mapa}` (Mercator vertical, costas de Natural Earth en `herramientas/datos/`, dominio público): rutas que se dibujan de a poco y lugares que aparecen y se apagan. Es un gráfico propio, sin problema de derechos (`13-divulgacion.md` › 6).
- `legibilidad.py`: brillo (luminancia WCAG) detrás de un título en sus clips o su foto; lo usan `armar_pop.py` y `armar_historia.py` para elegir sombra o bloques.
- `verificar.py <reel.mp4|imagen> [--pedido <pedido>] [--formato reel|historia|foto] [--sin-check]`: chequeo técnico y hoja con la zona segura sombreada; con `--pedido`, también los títulos dentro de la zona segura (T5, bloqueante), el ritmo del guion contra `conocimiento/ritmo.yaml` (R2, O12), si algún título tapa una cara y `hyperframes check` sobre `render/` con el contraste medido en cada texto ya asentado (durante la entrada no: `check` no ve la máscara y da falsos avisos).

El flujo entero está en la skill **`/reel`** (`.claude/skills/reel/SKILL.md`).

## Base de conocimiento

Antes del guion, el material decide el formato (`15-formato-segun-material.md`): un antes y después va en video, corto y con el resultado en movimiento; con solo fotos, carrusel con música o pedir que filmen el resultado. Un pase de fotos largo es la última opción.

Si la referencia es una tendencia (un audio con miles de reels y una estructura que se repite), `14-tendencias.md`: se miden 5-10 ejemplos del rubro antes del guion, no uno.

Para reels donde alguien cuenta algo a cámara (reseñas, efemérides), `13-divulgacion.md`: gancho en tres capas, relato y / pero / por lo tanto, archivo de dominio público y duración según la historia.

`conocimiento/` reúne lo relevado sobre Instagram, marca, contenido, publicidad y medición, con un nivel de evidencia en cada afirmación (🟢 oficial, 🟡 medido por terceros, ⚪ práctica de la industria). Las cifras de blogs sin metodología no se usan como argumento. Revisar los puntos 🟢 cada seis meses: Instagram cambia seguido.

## Convenciones

- **Ritmo:** cada formato tiene su preset en `conocimiento/ritmo.yaml` (fundamento en `08-ritmo.md`). Para Salón Demo, 95-110 bpm y tomas de 1,5-3 s; los primeros reels (cortes de 0,5-2 s a 120 bpm) quedaron apurados.

- Lo mecánico (ffmpeg, Whisper, detección de cortes) va en scripts de `herramientas/`, corridos con `uv run`. El criterio (qué toma va, qué texto, qué ritmo) lo pone Claude mirando fotogramas y transcripciones.
- **Nunca se publica sin audio** (Instagram muestra menos los reels sin sonido). **Nunca se mete en el MP4 una canción con derechos:** esas van por el modo `instagram` (las pone Ana en la app). Una cuenta de empresa solo tiene la Meta Sound Collection. Si el reel se va a promocionar, siempre música libre de derechos.
- Los medios de los pedidos no se versionan (ver `.gitignore`): tienen caras de clientas.

## Entorno

- Python: proyecto uv (`uv run ...`). Dependencias en `pyproject.toml`.
- Tests: `uv run pytest` (`tests/`, sin medios ni red, ~2 s). Cubren tiempos y grilla de beats, efectos, ritmo, recortes, textos, legibilidad, caras, puntaje, huellas de la fábrica y métricas. Correrlos antes de un commit que toque `herramientas/`.
- ffmpeg 9 en el PATH (en Windows: `winget install Gyan.FFmpeg`).
- HyperFrames fijado en `0.8.113` (`npx --yes hyperframes@0.8.113 ...`): sigue en 0.x y cambia seguido. Telemetría apagada en `.claude/settings.json`.
- Skills de HyperFrames y Remotion: no vienen en el repo; se instalan a nivel proyecto en `.claude/skills/` desde las fuentes de `skills-lock.json`.
- Remotion: licencia gratuita para individuos y empresas de hasta 3 empleados.
