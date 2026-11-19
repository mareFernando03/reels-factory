# 9. Música y audio

Cómo se elige el sonido de cada publicación y qué hace la factory en cada caso. Herramientas: `analizar_audio.py` (bpm, beats reales, tramo y letra) y `audio.py` (mezcla).

## Reglas de Instagram

- 🟢 **Sin sonido se muestra menos.** Ningún reel sale sin audio (ver `01-como-distribuye-instagram.md`).
- 🟢 **Las cuentas de empresa** solo tienen la **Meta Sound Collection** (unos 14.000 temas habilitados para uso comercial). Muchas canciones en tendencia no aparecen para ellas. Las cuentas de creador tienen la biblioteca completa, pero un uso comercial (promo, precios) sigue en zona gris de derechos.
- 🟢 **El audio no se cambia después de publicar.** Para cambiarlo hay que borrar y volver a subir.
- 🟢 **Antes de publicar**, en la app se balancea el **sonido original** (el del video) contra la **música**, cada uno con su volumen.
- 🟡 **Canciones con derechos metidas en el MP4** (no elegidas desde la biblioteca): Instagram puede silenciarlas o restringir el reel. En cuentas de empresa, más todavía. **La factory nunca mete en el MP4 una canción con derechos.**
- ⚪ **Audios "originales"** de otros creadores (voces, frases graciosas, sonidos virales): se usan desde "Usar audio" en el reel que lo tiene. También son la opción segura para cuentas de empresa cuando no son canciones comerciales.

## Los tres modos (`musica.modo` en el guion o en `pedido.yaml`)

| Modo | Para qué | Qué entrega la factory |
|---|---|---|
| `archivo` (lo normal) | Un tema libre de derechos, **distinto en cada reel** (`musica.py`, catálogo de Mixkit) | `reel-con-audio.mp4`: el tema desde su mejor tramo, con los cortes en sus beats, más efectos suaves. Listo para subir |
| `sintetica` (default si el guion no dice nada; respaldo) | Cuando no hay tema que sirva | `reel-con-audio.mp4`: base propia al bpm del guion + efectos. La tonalidad, los acordes y el ritmo cambian según el pedido, pero sigue sonando a base hecha por computadora |
| `instagram` | Una canción en tendencia, un audio viral o gracioso, o el de otro reel | `reel.mp4` sin música, `reel-efectos.mp4` (solo efectos, bajito) y **la instrucción**: qué audio elegir y dónde arrancarlo |

En los modos `archivo` e `instagram` el reel se arma **sobre el audio**:
1. `analizar_audio.py <archivo o link de un reel que lo use> --largo <s> --letra` saca:
   - el bpm;
   - los beats reales;
   - los tiempos 1 de cada compás;
   - los 3 mejores tramos del largo pedido;
   - la letra con tiempos.
2. En el guion van `bpm` (el del audio), `musica.analisis` (ese JSON) y `musica.inicio` (dónde arranca el tramo). Cada corte cae en un **beat real**: las canciones no tienen tempo perfectamente parejo y una grilla teórica se corre hasta medio beat en 15 s (medido en el "día de trabajo").
3. **Audios hablados o graciosos:** el reel se corta en las frases. La transcripción con tiempos marca dónde está el remate, y el corte o el texto caen ahí.

### Un tema distinto en cada reel

**Con la misma música, todos los reels se ven iguales** (Fernando, 04/10/2026: la base propia era la misma canción en los cuatro).
- **De dónde salen los temas.** De **Mixkit** (de Envato). Su «Stock Music Free License» permite uso comercial, también en redes y en avisos, sin atribución. Algunos temas tienen licencia restringida (solo uso personal): `musica.py` lee la licencia de cada tema en la página y baja solo los libres. Pixabay Music bloquea las descargas automáticas.
- **El catálogo.** `musica/catalogo.yaml` (versionado) guarda título, artista, licencia, url, bpm y `voz_db` (cuánto suena una voz cantada, medido con `separar.py`; por debajo de -35 dB es instrumental). Los MP3 van en `musica/libre/`, fuera de git, y se vuelven a bajar desde `url`.
- **Cómo se elige.** `musica.py --sugerir <bpm> --rango a b [--voz]` lista los temas sin usar dentro del rango del formato (`ritmo.yaml`). Con `--voz` (alguien habla en el reel) solo muestra instrumentales: una voz cantada en inglés debajo de Ana compite con ella. Después, `analizar_audio.py` da el mejor tramo y los beats reales, y el guion toma el `bpm` del tema.
- **Control.** `verificar.py` (Q5) avisa si el tema ya está en otro pedido. `musica.py --usados` muestra cuál va en cada uno.
- **Asignados el 04/10:**
  - Día de la Madre: «A Special Feeling» (99 bpm, tierno);
  - pochoclos: «Gimme that Groove!» (112, funk);
  - antes y después: «Aerobic Fashion» (108);
  - rulos-pop: «Fashion» (103).

## Cómo indicarle a Ana dónde arrancar

En la app, al elegir el tramo de una canción, Instagram muestra la letra. La instrucción sale de `audio.py` y va al informe:
- **"Arrancalo donde dice «…»"**, cuando la canción tiene letra en el tramo.
- **"Arrancalo desde el principio"**, cuando el tramo empieza en 0. Es lo más fácil de acertar: conviene elegir ese tramo si es bueno.
- **"Usar audio" desde otro reel** arranca donde arrancó ese reel.

**Balance:** si el reel tiene efectos (`reel-efectos.mp4`), el sonido original va al 20-30 % y la música al 100 %. Si no se quieren efectos, se sube `reel.mp4` y el sonido original queda en 0.

## Las capas del sonido de un reel

Un reel tiene hasta cuatro capas. No todas van siempre:

| Capa | Qué es | Cuándo manda |
|---|---|---|
| **Voz** | Alguien que habla en el video, o una voz en off | Siempre que hay. Todo lo demás se acomoda debajo |
| **Sonido directo** | Lo que suena en el local: tijera, secador, agua, spray, la risa de la clienta | Procesos y momentos "reales": da cercanía y verdad ⚪ |
| **Música** | La base, el tema libre o la canción de Instagram | Montajes sin voz: marca el ritmo y la emoción |
| **Efectos** | Whoosh, tic, pop, brillo, subida | Solo en momentos puntuales, sincronizados con la imagen |

- 🟡 **El sonido importa en Reels.** Se cita que el 80 % se mira con sonido, como dato interno de Instagram, pero solo aparece en notas de terceros: no encontré la publicación original de Meta. Otra fuente da 60 %. Conclusión práctica: el audio se cuida, y los subtítulos cubren a quien mira sin sonido.
- 🟡 Según una medición de Meta citada por Marketing Week, los anuncios en Reels con música y voz tienen mejor respuesta que los que no tienen sonido.

## Efectos: cuáles, cuándo y cuánto

| Efecto | Para qué | En la factory |
|---|---|---|
| **Whoosh** (barrido) | Un movimiento rápido de cámara o una transición de barrido o zoom. Su largo tiene que coincidir con el del movimiento | `entrada: barrido` y `zoom`. Pica 0,35 s antes del corte |
| **Tic** (toque corto y seco) | Un corte común con golpe | `entrada: golpe` |
| **Impacto** (golpe grave) | El momento fuerte: un revelado, un precio, un remate | **Uno o dos por reel, como máximo** 🟡. Solo en la toma `rol: revelado` con golpe, o donde el guion lo pide con `sonido: impacto` |
| **Pop** | Aparece un sticker o un texto | Stickers de pasos y grilla de fotos |
| **Brillo** (destello sonoro) | Revelado con luz, "quedó hermoso" | `entrada: luz` y cierre |
| **Subida** (riser) | Tensión antes de un cambio: el cierre, un revelado | Antes del cierre |

- 🟡 **Medidos, no en todos los cortes.** Las guías de sonido para formatos cortos coinciden en esto:
  - un whoosh breve en las transiciones;
  - el efecto más fuerte, una sola vez, en el momento principal.

  En todos los cortes "suena a plantilla" (ver `07-edicion-y-estetica.md` › Sonido). Hasta el 03/10, cada golpe era un impacto: pochoclos llegaba a 18 efectos. Ahora los golpes comunes son un tic y el impacto queda para el revelado.
- ⚪ **Los efectos acompañan a la imagen:** cada uno tiene que corresponder a algo que se ve, como un movimiento, una aparición o un golpe de luz. Un efecto que no corresponde a nada distrae.
- ⚪ **El sonido directo vale más que un efecto agregado.** El *snip* de la tijera, el secador o el spray son el sonido de la peluquería. Los videos de peluquería en clave ASMR (tijera cerca del micrófono, cepillado, agua) son un género propio. Pedirle a Ana que grabe procesos **con el sonido del local** (sin música de fondo de la radio) abre esa variante.
- 🟡 **Edits**, la app de video de Instagram, tiene una biblioteca de efectos, mejora de voz con reducción de ruido y "Loudness Match" para igualar volúmenes. Sirve si algún día Ana edita sola.

## Voz: se respeta siempre

Si en una toma alguien habla (Ana saludando, explicando un tip, la clienta contando algo), **sacarle el sonido le quita sentido**: no se sabe qué dice. Desde el 03/10 la factory:

1. **Detecta la voz** en cada tramo (`voz.py`). Whisper transcribe el tramo y cuenta como habla si:
   - hay al menos 2 palabras con confianza ≥ 0,6;
   - los segmentos superan el avg_logprob de -0,6;
   - **el idioma es castellano.**

   Una canción de fondo en inglés («I shake it off» en el revelado de los pochoclos) queda afuera por el idioma. **Una canción en castellano cantada claro puede pasar como habla:** la fábrica muestra lo que transcribió, y el guion lo corrige con `voz: true | false` por toma.
2. **Conserva el audio** de esa toma (`render/assets/voz/NN.wav`), en su lugar exacto del reel. La toma tiene que ir a velocidad ~1 (±15 %, se corrige con `atempo` sin cambiar el tono). Una voz acelerada o en cámara lenta no se entiende: si la toma va más rápida o más lenta, avisa y hay que ajustar los beats o el tramo.
   - **El tramo corta en una pausa, nunca en mitad de una palabra.** Una frase cortada suena a que faltó algo: «Hola buen día, buen d…» en los pochoclos. `preparar_clips.py` escucha 0,8 s más allá de cada borde y avisa qué palabra queda partida. Una toma con `voz: true` dura lo que dura la frase, hasta 4 s (excepción a O12).
3. **Limpia la voz** (`separar.py`, desde el 04/10). Lo que ensucia la voz en los reels de Ana casi nunca es ruido: es **la canción que ya tenía el reel publicado**, y un filtro de ruido no la saca.
   - Un modelo de separación (MDX-Net Kim_Vocal_2, de los modelos públicos de UVR, el mismo tipo que usan los karaokes) se queda solo con la voz. Corre en la CPU, unos 2 s por toma.
   - Después: pasa-altos de 90 Hz (graves del local), reducción de ruido suave y un poco de compuerta entre palabras (`audio.py`).
   - Medido en el saludo de los pochoclos: donde suena solo la canción, baja de -20 a -34 dB, y Whisper entiende mejor la voz separada que la original.
4. **Baja la música mientras se habla** (*ducking*):
   - la música queda unos 6 dB por debajo de la voz cuando nadie habla, y baja 16 dB más mientras se habla, así que la voz queda unos 20 dB por encima 🟡 (las guías dan 15-25 dB);
   - los efectos también se corren;
   - la bajada usa los tiempos de las palabras, con ataque y relajación de 0,15 s para que la música no salte.
5. **Pone subtítulos** con las mismas palabras (`armar_pop.py`): frases de 2 a 4 palabras, en una píldora oscura al 64 % del alto. El título de esa toma esquiva su franja. `subtitulos: false` los apaga. `verificar.py` controla el criterio X3.
6. **En modo `instagram`**, el mensaje para Ana cambia: **sonido original al 100 %** (ahí está la voz) y la canción bajita, al 15-20 %.

Verificado en los pochoclos: Whisper transcribe el saludo «Hola buen día» sobre la mezcla final.

## La voz como recurso

Lo que dice la gente en los videos **es material**, no solo algo que proteger:

- **Ganchos y títulos con sus palabras (M2).** Una frase dicha por Ana vale más que una escrita por la factory: es su voz literal. Ejemplos de su biblioteca:
  - «discriminan el jueves»;
  - «no me van a decir que no tienen el pelo duro»;
  - «nunca jamás me levanto peinada»;
  - «no molesta su consulta».
- **El cierre o el CTA dicho por ella.** En el reel del Día de la Madre, el cierre es Ana diciendo «así que no molesta su consulta, nos vemos». Una cara y una voz reales al final dan más confianza que un texto (M5, ⚪).
- **Ideas de contenido.** En `DaQTHPrSRm_` propone una tarde de mimos con tortas y mate: es una idea de evento para promocionar.
- **Cómo se encuentra:**
  - `biblioteca.py --habla` transcribe los reels publicados (queda en el catálogo);
  - `lecturas.yaml` marca quién habla (`voz: ana | cancion | audio-viral | alucinacion`) y las frases útiles;
  - `--buscar` muestra lo que dice ella con sus segundos;
  - en los crudos nuevos, `inventario.py` transcribe y `preparar_clips.py` lo detecta por toma (`analisis/voz.json`).
- **Con criterio:** una voz fuera de contexto confunde. En el reel del Día de la Madre, debajo del platinado, Ana contaba que esa clienta «no quería cortarse…», que no tiene nada que ver con la promo: `voz: false` en esa toma. Toda voz detectada se lee antes de dejarla.
- **Lo que no es de ella no se usa como su voz:**
  - canciones en castellano (4 en su biblioteca) y audios virales de lip sync (2): se reconocen leyendo la transcripción;
  - el audio viral se puede reusar como tal, desde «Usar audio» en Instagram.

## Qué variante de sonido usar

| Situación | Sonido | Por qué |
|---|---|---|
| Montaje de resultado o proceso, sin voz | Canción de Instagram (modo `instagram`) si la cuenta es de creador; si no, tema libre (`musica.py`) | 🟡 El audio en tendencia ayuda al alcance en cuentas chicas (sobre todo de menos de 50 mil seguidores) |
| Habla a cámara (tip, saludo, aviso) | **Su voz** + música muy baja o ninguna + subtítulos | ⚪ El audio original genera confianza y es lo que convierte. Los subtítulos cubren a quien mira sin sonido |
| Proceso con sonido del local | Sonido directo + música baja | ⚪ Cercanía, estilo ASMR |
| Humor (POV, sketch) | El audio del chiste: su voz o un audio viral desde «Usar audio» | El remate depende del audio |
| Promo (precios, vouchers) | Tema libre para uso comercial (`musica.py`); nunca una canción con derechos | 🟢 Si se promociona, solo música autorizada para uso comercial |

- 🟡 **Las cuentas de empresa** solo acceden a la **Meta Sound Collection**: más de 14.000 temas y efectos habilitados para uso comercial, también en anuncios. Para anuncios, igual conviene revisar la licencia de cada tema.
- 🟡 **El audio en tendencia ayuda más al principio:** los conteos de terceros dicen que "en subida" y con pocos usos (menos de 10 mil) rinde más que cuando ya está gastado. Original y tendencia se complementan: la tendencia trae alcance y el audio propio, confianza.

## Niveles

- 🟡 **Instagram normaliza a unos -14 LUFS** con picos de -1 dBTP: subir más el volumen no suma, la app lo baja y puede distorsionar. La factory masteriza a -14 LUFS / -1,5 dBTP.
- **Solo efectos** (modo `instagram` sin voz): -20 LUFS, porque los pone debajo de la canción que elige Ana.
- **Voz:** su parte hablada queda a ~-15 dBFS de RMS antes del masterizado.
- **El audio se entrega en AAC**: la factory usa 192 kbps y algunas guías piden 256.

## Fuentes

- Cuentas de empresa y música en tendencia: https://www.trymaas.com/blog/instagram-business-account-trending-music-risks/
- Derechos de la música en Instagram para negocios: https://www.foximusic.com/blog/instagram-reels-music-copyright-legal-guide/
- Balance de volumen en la app: https://store.hollyland.com/blogs/creator-hub/keep-original-audio-on-reels-with-music
- Reels y sonido (80 % con sonido, dato citado por terceros): https://www.teleprompter.com/blog/2025-instagram-reels-statistics · https://adamconnell.me/instagram-reels-statistics/
- Música y voz en anuncios de Reels (estudio de Meta citado por Marketing Week): https://www.zebracat.ai/post/instagram-reels-statistics
- Efectos de transición (whoosh, riser, impacto) y cuánto usarlos: https://creatorsfx.in/blog/best-sound-effects-for-reels-and-shorts · https://www.mixclap.com/en/blog/transition-sound-effects · https://www.flexclip.com/learn/transition-sound-effects.html
- Voz y música, *ducking* y niveles: https://www.descript.com/blog/article/how-to-set-the-perfect-audio-levels-for-video · https://zellahq.com/blog/music-ducking-explained/ · https://pureaudioinsight.com/blogs/content-production/background-music-volume-how-loud-should-it-be
- Normalización de Instagram (-14 LUFS, -1 dBTP): https://cutscore.io/blog/loudness-for-instagram-reels · https://www.loudfix.com/lufs-standard-instagram-2026/
- Meta Sound Collection y cuentas de empresa: https://www.musicbusinessworldwide.com/meta-offers-royalty-free-music-library-to-instagram-reels-advertisers/ · https://www.soundstripe.com/blogs/instagram-music-library
- Audio en tendencia y audio original: https://www.chartlex.com/blog/marketing/trending-audio-instagram-reels-algorithm-2026 · https://metricool.com/trending-audio-on-instagram/
- Subtítulos automáticos de Instagram (sticker «Subtítulos», castellano incluido): https://vatis.tech/blog/benefits-of-reel-captions-for-instagram · https://www.kapwing.com/resources/a-complete-guide-to-instagram-subtitles/
- Edits (efectos, mejora de voz, Loudness Match): https://www.thereelstars.com/tech/instagram-edits-gets-major-audio-upgrade-with-imported-audio-200-new-sound-effects-smarter-editing-tools/ · https://www.epidemicsound.com/blog/instagram-edits/
