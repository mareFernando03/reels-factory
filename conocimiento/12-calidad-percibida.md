# 12. Calidad percibida: lo que hace que un reel se vea "trucho"

La rúbrica mide si un reel está bien hecho. Esto junta **qué percibe la gente (y el algoritmo) como mala calidad**, para evitarlo antes de que pase. Complementa a `07-edicion-y-estetica.md`, que cubre la estética (montaje, movimiento, tipografía).

Una idea guía (⚪, la repiten todas las guías de producción): **casi nadie nota cuando un video está bien hecho, pero todos notan cuando está mal.** La calidad no suma tanto como resta la falta de calidad.

## 1. Lo que Instagram mismo muestra menos 🟢

Instagram muestra menos los reels que:

| Señal | Qué hace la factory |
|---|---|
| **Están silenciados** | Nunca sale sin audio (T3) |
| **Son borrosos o de baja resolución** | Q1: avisa cuando una toma se amplía más de 1,5× (fuentes de 360-480p). La ampliación con IA se descartó (M-04) |
| **Tienen bordes, logos o marcas de agua** de otras apps | `preparar_clips.py` saca las barras negras. La biblioteca marca los reels con InShot o CapCut en `lecturas.yaml` y no se usan esos tramos. La firma de Ana va solo en el cierre o en la historia |
| **Están tapados de texto** en la mayor parte de la imagen | X2 y como máximo unas 10 palabras por texto (ver 4) |
| **No son originales** (contenido de otros) | Q3. El material ajeno (charlas, videos que filmaron clientas) está marcado en la biblioteca |

- 🟡 **Desde el 30/04/2026,** las cuentas que publican sobre todo contenido ajeno dejan de recomendarse. Medido por terceros: el original recibe un 40-60 % más de distribución que un repost.
- 🟡 **Los duplicados propios también pierden alcance.** Instagram detecta video casi idéntico (huella de imagen y de audio). Subir otra vez el mismo reel, o uno muy parecido, alcanza entre un 20 y un 40 % menos, y como *trial reel* lo frena con un aviso.
  - **Rehacer está bien; duplicar, no.** Por eso una reversión cambia el gancho, el orden, los encuadres, el color, los textos y el audio, y mejor si mezcla material de más de un reel (Q3).
  - Las reversiones de la factory (pochoclos, día de trabajo, antes y después) cambian todo eso. Igual conviene subirlas espaciadas del original.

## 2. Audio: lo que más resta 🟡

- **El audio malo hace que la persona parezca menos creíble.** En dos experimentos (USC y ANU, Schwarz y Newman), la misma charla con audio peor hizo que el orador pareciera menos inteligente y menos simpático, y su trabajo menos importante.
- Las guías de producción coinciden: el audio con eco, apagado o con saltos de volumen espanta más rápido que una imagen mediocre.
- **Lo que delata:**
  - música que tapa la voz;
  - saltos de volumen entre tomas;
  - distorsión por volumen alto (Instagram normaliza a -14 LUFS: más fuerte no suma);
  - voz lejos del micrófono, eco del local;
  - una canción de fondo distinta en cada toma: el audio original de cada clip.
- **En la factory:**
  - todo sale a -14 LUFS;
  - la voz se conserva y la música baja debajo (`09-audio.md` › Voz);
  - Q2 controla que la voz se entienda en la mezcla final (Whisper la tiene que poder transcribir);
  - el audio original de los clips sin voz se reemplaza: así no hay cortes de canción en cada toma.

## 3. Imagen: lo que se ve "de celular" ⚪

| Defecto | Por qué pasa | Qué hacer |
|---|---|---|
| **Movida o con temblor** | Celular en una mano | `estabilizar` (auto). Al grabar: dos manos, celular pegado al cuerpo |
| **Exposición que "respira"** (se aclara y oscurece sola) | La exposición automática sigue lo más brillante | Al grabar: tocar y mantener para fijar la exposición |
| **A contraluz** (la ventana atrás, la cara oscura) | El celular expone para la ventana | Al grabar: la luz de frente o de costado, nunca atrás |
| **Blanda o pixelada** | Fuente de 360-480p ampliada, o compresión de WhatsApp | Q1. Pedir los originales **como Documento**: WhatsApp baja el video a unos 960 px y 1-1,5 Mbps |
| **Color distinto en cada toma** | Distintas luces o momentos | Color igualado (M-05, `color.py`) |
| **Encuadre con cabeza cortada o sujeto chico** | Apuro | O9; el encuadre y el acercamiento los elige el guion |
| **Video horizontal con barras** | Se grabó acostado | Se recorta a 9:16; si no alcanza, mejor no usar la toma |

- 🟡 **En Instagram:** activar «Subir en la máxima calidad» (Configuración › Calidad del contenido). Subir con Wi-Fi, en MP4 H.264 de 1080×1920.

## 4. Texto: lo que se ve "hecho con la app" 🟡

- **Más de unas 10 palabras por texto:** la gente deja de leer y se va. La factory divide la frase en varios títulos (verificar avisa si un texto pasa de 10 palabras).
- **Texto donde lo tapa la interfaz** (abajo o a la derecha): la zona segura (T5).
- **Letra fina o chica, poco contraste:** contraste ≥ 3:1 medido (M-01), Fraunces 900 de 92-104 px y bloques magenta sobre fondo claro.
- **La fuente por defecto en una cajita** (Poppins, la de la app): O11.
- **Faltas de ortografía y renglones desparejos** (una palabra sola en un renglón): X4. Los subtítulos automáticos de Instagram se equivocan: se revisan antes de publicar.
- **Texto que tapa la cara o el trabajo:** M-02 (caras) y el criterio del guion (el pelo).

## 5. IA: cuándo resta 🟡

- **La gente desconfía de la IA que se nota.**
  - En Europa, un 42 % reacciona mal ante avisos hechos con IA que se ven de baja calidad, raros o "inquietantes", contra un 29 % cuando se ven prolijos.
  - La desconfianza viene en aumento: un 20 % decía en 2025 que el uso fuerte de IA le bajaría la confianza en una marca, y un 40 % en 2026.
  - Nueve de cada diez quieren que la marca diga cuándo usó IA.
- **Para Salón Demo:**
  - **Diseño gráfico con IA, sí.** Los vouchers están hechos con IA y son un recurso: se recortan, se amplían y se animan.
  - **Personas, pelo o local inventados por IA, no.** No se presentan como reales.
    - El resultado tiene que ser el que hizo Ana (M3).
    - Una cara o un pelo "redibujados" se notan. Por eso se descartaron Higgsfield y Real-ESRGAN para el pelo.
    - La publicidad retro de Ana estilo años 80 (`Dc9oO6bS3Uw`) funciona porque es un chiste declarado ("Según ChatGPT…"), no una foto que se hace pasar por real.

## 6. Cómo lo controla la factory

| Qué | Dónde |
|---|---|
| Resolución, codec, fps, duración | `verificar.py` (T1, T2) |
| Barras negras | `preparar_clips.py` (cropdetect) |
| Ampliación de más de 1,5× en alguna toma | `verificar.py` (Q1, aviso) |
| Contraste y textos sobre caras | `verificar.py` (`check`, caras) |
| Más de 10 palabras en un texto | `verificar.py` (aviso) |
| La voz se entiende en la mezcla final | `verificar.py` (Q2, Whisper sobre el reel terminado) |
| Marcas de agua y material ajeno | `lecturas.yaml` (notas) y criterio al elegir tramos |
| Duplicado de un reel ya publicado | Q3, criterio (guion de la reversión) |
| IA en personas o en el pelo | Q4 (bloqueante), criterio |

## Fuentes

- Lo que Instagram muestra menos (borroso, marcas de agua, texto, no original): https://sproutsocial.com/insights/instagram-algorithm/ · https://www.engadget.com/2160560/instagrams-recommendation-algorithm-will-penalize-unoriginal-photo-and-carousel-posts/ · https://almcorp.com/blog/instagram-restricts-reach-content-aggregators/
- Política de originalidad del 30/04/2026 (Mosseri): https://petapixel.com/2026/04/30/new-instagram-policies-target-reposted-content/ · https://www.tubefilter.com/2026/04/30/instagram-removes-algorithm-recommendations-repost-content-aggregator/
- Duplicados propios y trial reels: https://www.avramify.com/blogs/news/instagrams-new-penalty-for-duplicate-reels · https://www.lilachbullock.com/repost-someone-elses-reel-to-your-instagram/
- Audio y credibilidad (USC/ANU): https://today.usc.edu/why-we-believe-something-audio-sound-quality/ · https://dornsife.usc.edu/news/stories/norbert-schwarz-research-links-sound-quality-belief/
- Errores de video con celular (exposición, contraluz, temblor): https://www.equinetacademy.com/blog/mobile-videography_a-complete-guide-to-creating-high-quality-videos/ · https://peekatthis.com/beginners-guide-creating-better-smartphone-videos/
- Texto en reels (cantidad, zona segura, legibilidad): https://www.opus.pro/blog/instagram-reels-caption-subtitle-best-practices · https://overlaytext.com/blog/instagram-reels-text-overlay-best-practices
- IA y confianza en la marca: https://www.advanced-television.com/2026/08/06/study-ai-slop-poses-growing-risk-to-brand-trust · https://www.outlierreport.com/en/news/consumer-excitement-for-ai-content-crashed-from-60-to-26-and-now-anti-ai-is-the-premium
- Compresión de WhatsApp y subida en alta calidad: https://snapvid.org/blog/why-whatsapp-lowers-video-quality-and-what-actually-works · https://www.jasminealley.com/upload-high-quality-instagram-reels/
