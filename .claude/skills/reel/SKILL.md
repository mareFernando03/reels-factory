---
name: reel
description: >
  Orquesta un pedido de la factory de reels: crear el pedido, analizar referencia y crudos,
  escribir el guion, preparar clips, componer con armar_pop.py, renderizar con HyperFrames,
  ponerle audio, verificar con la rúbrica y dejar la salida lista para subir. También rehace
  ("reversiona") un reel ya publicado de la marca. Usar cuando Fernando pida un reel nuevo,
  una reversión, una variante o el audio de un reel.
---

# /reel

Guía operativa completa: `CLAUDE.md` del repo. Esto es el orden de los pasos y los comandos.
Todo corre desde la raíz del repo con `uv run python …`.

**Lo mecánico va en un solo comando:** `uv run python herramientas/fabrica.py pedidos/<pedido>`.
**Para iterar, `--borrador`:** sale `salida/borrador.mp4` (15 fps, draft, con audio, sin verificación) en una fracción del tiempo. Se revisa y corrige sobre el borrador y se corre la fábrica sin `--borrador` una sola vez, con el guion aprobado (M-28). Para mirar momentos sueltos, todavía más rápido: `npx hyperframes@0.8.113 snapshot render --at 3,10,25`.
Detecta el formato por el plan, corre los pasos que cambiaron (se puede volver a llamar
sin costo), pone ffmpeg en el PATH, y al final lista lo que falta escribir (caption,
informe, puntos) y deja `salida/para-<quien>.txt` (`para-ana.txt`, `para-pablo.txt`: `mensaje:` en `marca.yaml`). `--solo <paso>` corre un paso; `--forzar` rehace todo.

## Subcomandos

| Pedido | Qué hacer |
|---|---|
| `/reel nuevo <marca> <slug>` | Crear `pedidos/<AAAA-MM-DD>-<marca>-<slug>/` con `entrada/crudos/`, `analisis/`, `plan/`, y copiar `pedidos/_plantilla/pedido.yaml`. Si `marca.yaml › entrada_drive.local` existe, copiar de ahí a `entrada/crudos/` lo que Ana subió desde el último pedido (por fecha); si no, decirle a Fernando dónde soltar los archivos. Para ver qué hay sin la copia local, el conector de Drive (`search_files` con `parentId` = `entrada_drive.id`) lista los archivos, pero no bajar videos con él: llegan dentro de la conversación. |
| `/reel <pedido>` | Seguir el pedido desde el primer paso que falte (ver abajo). |
| `/reel reversionar <url o id>` | Bajar el reel con `bajar.py` a `entrada/original.mp4`, diagnosticar contra la rúbrica y rehacerlo con su mismo material. |
| `/reel audio <pedido> [tema.wav]` | `fabrica.py <pedido> --solo audio` (o `audio.py` con `--musica` para probar un tema). |
| `/reel foto <foto(s)>` · `/reel carrusel <fotos>` · `/reel precios` | Pedido con `plan/publicacion.yaml` (placas `portada` / `foto` / `precios` / `cierre`; datos solo de ella, nunca inventados) y `publicar`, `caption.txt` según `conocimiento/11-descripciones.md`, `puntos.yaml`, y `fabrica.py <pedido>`. |
| `/reel historia <foto o video> [plantilla]` | Pedido `…-historia-<slug>` con `plan/historia.yaml` (textos de ella, `adaptaciones`, `espacio_sticker`, `sticker_sugerido` escrito para Ana, y `publicar`) y `fabrica.py <pedido>`. Ver `conocimiento/10-historias.md`. |
| `/reel metricas [<pedido>] [<captura(s)>]` | **Desde Metricool (lo normal, M-22):** para cada tipo (`reels`, `posts`, `stories`), `metricool.py --campos <tipo>` da los fieldId. Pedirlos con `getAnalyticsDataByMetrics` (brandId de `getBrandSettings`; desde la fecha del pedido más viejo sin medición de 7 d hasta hoy; zona `America/Buenos_Aires`) y guardar la respuesta tal cual en `marcas/<marca>/metricool/<AAAA-MM-DD>-<tipo>.json` como `{"consultado": ahora ISO, "tipo", "campos", "filas"}`. Después, `metricool.py <volcado>`: une cada publicación con su pedido (por `link` o por la descripción) y carga la medición. Si un pedido publicado no se une solo, poner su `link` en `salida/metricas.md` y repetir. Solo lectura: las herramientas del planificador están bloqueadas. **Con captura (respaldo):** copiar la plantilla si falta y cargar solo los números que se ven (`fuente: captura`; nunca estimar). En los dos casos: escribir la lectura con `conocimiento/06-medicion.md` y correr `metricas.py`. Comparar dentro del mismo formato. Conviene correrlo al abrir cada sesión: la foto de las 72 h no se puede pedir después. |
| `/reel nuevos <marca>` | Ver en el perfil (Chrome) qué publicó que no esté en `biblioteca/reels.txt`, sumarlo, bajarlo con `bajar.py` y catalogarlo con `biblioteca.py` (después `--calidad`, y escribir su lectura en `lecturas.yaml` mirando la hoja). |
| `/reel buscar <qué>` | `biblioteca.py marcas/<marca>/biblioteca --buscar "<palabras>"` (servicio, persona, "ana", "humor", "1080p"…) para encontrar tramos reusables antes de pedirle material nuevo a Ana. |

## Pasos (cada uno deja un archivo; si existe, se saltea)

1. **Entrada.** `pedido.yaml` + `entrada/` (referencia, instrucciones `.txt`/`.ogg`, crudos). Instrucciones en audio → transcribir (`comun.transcribir`).
2. **Análisis.** `analizar_referencia.py <pedido>` → `analisis/referencia.json`; `inventario.py <pedido>` → `analisis/crudos.json` (incluye tramos de movimiento y aviso de baja resolución). Mirar las hojas de contactos y los tramos: elegir tomas estables y nítidas con criterio (gesto, cara), usar los barridos como transición, no por orden.
   - **El tempo de la referencia, verificado.** `analizar_referencia.py` elige el bpm que explica sus cortes (librosa confunde octavas y 2/3: «Pump It» daba 103 y es 156) y deja `bpm_grilla`; si avisa, usar ese en el guion y pasarlo a `analizar_audio.py --bpm`. Un corte que no cae en el compás de la canción se nota.
   - **Si la referencia es una tendencia** (un audio con miles de reels, rótulos que se repiten), **se mide la tendencia, no un reel** (`conocimiento/14-tendencias.md`): abrir la página del audio en Chrome, bajar con `bajar.py` 5-10 ejemplos del rubro, `analizar_referencia.py <video> --salida …` en cada uno y una hoja con sus fotogramas. De ahí salen el orden de los rótulos, la duración de toma y de revelado, dónde va el texto, la transición clave y cómo termina. **La tipografía, el color y los gráficos son los de la marca**, no los de los ejemplos: de la tendencia se toma la estructura, no el look. Formato `tendencia` en el guion (`ritmo.yaml`). El audio de una tendencia casi siempre es una canción con derechos: modo `instagram`, y confirmar que la cuenta de la marca lo tenga.
3. **Guion** → `plan/guion.yaml` (ver los de `pedidos/2026-10-03-*` como modelo). Obligatorio:
   - **Primero, el formato según el material** (`conocimiento/15-formato-segun-material.md`): si llegaron solo fotos, preguntar si el resultado se puede filmar (5-10 s, mismo encuadre que el antes, en movimiento) antes de escribir un pase de fotos; si no se puede, carrusel con música.
   - `adaptaciones`: toda palabra que no sea textual de ella, declarada.
   - `momento_wow`: cuál es y en qué toma.
   - textos ≤17 car/s; títulos entre el 14 % y el 65 % del alto, sin tapar caras ni el pelo. La altura (lejos de las caras) y el fondo (sombra o bloques magenta) los decide `armar_pop.py` mirando los clips; `textos[].base` / `textos[].fondo` solo para forzarlos. Si avisa "no hay lugar libre" o el título tapa el pelo que se muestra (un rodete, un resultado), partir el texto por toma o fijar `base`.
   - ritmo según `conocimiento/ritmo.yaml` (bpm, duración de toma y de revelado); `rol` en las tomas de revelado y barrido. Tramo de fuente ≈ largo de la toma (×0,8-1): estirar mucho un paneo lo deforma.
   - `publicar` (lo lee el mensaje para Ana): `nombre`, `permisos` (a quién pedirle el OK; `[]` si solo aparece Ana; con menores, la familia), `colaboradora` si corresponde, `antes` para pasos propios (p. ej. archivar el original en una reversión) y `portada` (segundo) si se quiere fijar. En modo `instagram`, `musica.fuente` se le escribe a ella ("abrí tu reel original, tocá el nombre de la canción y después «Usar audio»").
   - **Si alguien cuenta algo a cámara (reseña, efeméride, historia: formato `relato` o `tip-hablado`), primero la historia** (`conocimiento/13-divulgacion.md`):
     1. Escribir su relato en una línea **y / pero / por lo tanto** (`estructura:` en el guion).
     2. Elegir los tramos que la sostienen, con las causas antes que las consecuencias. Un solo momento puede adelantarse como gancho.
     3. Leer los tramos seguidos sin mirar el video: si no se entiende la historia, el corte está mal.
     4. **Gancho:** su frase más fuerte; el título es una versión corta (4-8 palabras), no la transcripción (`subtitulos: false` en esa toma); la frase siguiente nombra de qué se trata.
     5. **Recursos:** `insertos` en cada toma larga y encima de cada salto de corte (archivo de dominio público con su licencia en `plan/archivo.json`, placas con sus palabras clave, rótulos). La imagen cambia cada ≤7 s (O12b).
     6. **Duración:** la que pida la historia (relato 60-90 s); nunca se saca el "pero" para que entre en menos.
   - **Lo que se dice es material:** antes del guion, leer lo que se habla en los crudos (`analisis/crudos.json › habla`) y en la biblioteca (`--buscar`, `lecturas.yaml › frases`). Sus frases sirven de gancho o título literal, y su voz de toma o de CTA. Ver `09-audio.md` › La voz como recurso.
   - **Voz:** si alguna toma tiene a alguien hablando, la fábrica conserva esa voz, baja la música y pone subtítulos (`conocimiento/09-audio.md` › Voz). La toma tiene que ir a velocidad ~1: el tramo de fuente dura lo mismo que los beats. Revisar lo que transcribió (`analisis/voz.json`); si es una canción y no habla, `voz: false`.
   - Si el reel va sobre una canción (`archivo` o `instagram`), antes del guion: `analizar_audio.py <fuente> --largo <s> --letra` → `analisis/audio.json`, y en el guion `bpm`, `musica.analisis` y `musica.inicio` (`conocimiento/09-audio.md`). Composición a medida → cargar `sonidos:` en el guion.
   - **Punto de control: mostrar el guion a Fernando y esperar el OK** antes de renderizar (en pruebas que él pidió, avisar y seguir).
4. **Fábrica.** `fabrica.py <pedido>`, que corre en orden:
   - clips (`preparar_clips.py`; por toma `encuadre`, `espejar`, `comparar`, `solape`; la última toma antes del cierre lleva `solape: 0.6`);
   - composición (`armar_pop.py`, o `render/armar.py` si el pedido tiene una a medida; modelo: `pedidos/2026-10-03-salon-demo-rulos-pop/render/armar.py`);
   - render;
   - audio (`reel-con-audio.mp4`, o `reel-efectos.mp4` en modo instagram);
   - portada;
   - `verificar.py --pedido`: técnico, títulos en la zona segura (T5, medidos con la fuente de la marca), ritmo, caras y `hyperframes check` con el contraste de cada texto. Si falla, la fábrica se detiene;
   - puntaje;
   - mensaje (`para-<quien>.txt`).
5. **Control con criterio.** Mirar `reel-qa.jpg` (zona segura sombreada) y fotogramas sueltos de los momentos críticos (cortes, cierre). Después `conocimiento/rubrica.yaml` criterio por criterio → `salida/puntos.yaml` (formato, bloqueantes que fallan, no aplica, puntos) y `salida/evaluacion.md`. Si falla un bloqueante, corregir el guion y volver a correr la fábrica.
6. **Textos de salida.** `caption.txt` (`conocimiento/11-descripciones.md`: primera línea gancho con sus palabras, servicio y ciudad, CTA, ≤3 hashtags) e `informe.md` (decisiones y cómo publicarlo). Volver a correr la fábrica: con los pendientes completos escribe el mensaje (`salida/para-<quien>.txt`).
7. **Entrega.** Mandarle a Fernando el video final y el mensaje (`para-<quien>.txt`) con SendUserFile. Él le reenvía el mensaje tal cual, y el video y la portada **como Documento** para que WhatsApp no los comprima.

## Reglas que no se negocian

- Nunca publicar sin audio; la factory no publica, entrega archivos.
- Medios con caras de clientas: no van a git (`.gitignore` ya los cubre; revisar `git status` antes de un commit).
- Clientas que aparecen: su OK antes de publicar; menores, permiso de la familia y sin invitarlas como colaboradoras.
- Material editado por terceros (otra cuenta lo editó) no se reedita.
- Lo que no es textual de ella, se declara en `adaptaciones`.
