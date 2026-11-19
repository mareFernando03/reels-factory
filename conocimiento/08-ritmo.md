# 8. Ritmo y duración

Por qué existe: los primeros reels de la factory cortaban cada 0,5-2 s y duraban 11-14 s. A Fernando le parecieron **rápidos y cortos**. Esta sección junta lo que se sabe para que el ritmo sea una decisión con fundamento y no un gusto. Los presets que se aplican están en `ritmo.yaml`.

## Lo que se sabe

- 🟢 **El tiempo de visualización es la primera señal.** Mosseri nombró tres métricas para el alcance: tiempo medio de visualización, me gusta por alcance y envíos por alcance. La duración es lo que más mueve el tiempo de visualización.
- 🟢 **Duración de reels:**
  - Hasta 3 minutos, un reel se recomienda a quienes no siguen la cuenta (enero de 2025: antes el límite era 90 s).
  - Mosseri: "seguimos enfocados en el video corto".
  - **No hay una duración ideal oficial.**
- 🟡 **Terceros, con metodologías dispares:**
  - 7-15 s da la tasa de finalización más alta (~74 %).
  - 15-30 s da la mejor tasa de interacción (~4,8 %).
  - En cuentas de empresa, el pico de vistas está en 45-60 s (Socialinsider; correlación: los reels largos que funcionan son de cuentas que saben retener).
  - **Lo que se repite en todas:** más largo solo funciona si cada segundo se gana el siguiente.
- 🟡 **Referencias de finalización** (terceros, 2026):
  - menos de 15 s: bueno arriba del ~65 %;
  - 15-30 s: bueno arriba del ~50 %;
  - 30-60 s: aceptable entre 40 y 50 %.
- ⚪ **Ritmo de corte.** En Instagram, el contenido estético funciona con un corte o cambio visual **cada 2,5-4 s**. Es más lento que en TikTok, donde lo habitual es una ráfaga de tomas cortísimas.
- ⚪ **Belleza:** tomas de 4-7 s para que se vea la textura y la técnica (el brillo, la definición del rulo), con algún cambio adentro de la toma cada 1,5-3 s (un acercamiento, un texto, un gesto).
- ⚪ **Zona de abandono:** una toma **quieta** de más de 4 s. Una toma larga con movimiento (acercamiento, giro de la clienta) no cuenta como quieta.
- ⚪ **Transformación:** planteo 0-3 s, proceso 3-8 s, revelado 8-12 s y después. Todo depende de que el revelado caiga en el momento justo y **se sostenga**: es lo que se vino a ver.

## Qué decidimos

1. **Los cortes de 0,5-2 s se van.** Ese es ritmo de TikTok. Para resultados de peluquería, la toma media va a 1,5-3 s y el revelado se sostiene 3-4 s.
2. **El ritmo depende del formato** (`ritmo.yaml`). Un proceso acelerado puede cortar más rápido porque cada toma cuenta un paso; un resultado necesita tiempo para mirarse.
3. **La duración sube a 15-20 s** para transformaciones y fotos. Queda en la zona donde la finalización sigue alta y entra el revelado sostenido.
4. **El tempo baja a 95-110 bpm.** Con beats de 0,55-0,63 s, una toma de 4 beats dura 2,2-2,5 s sin parecer lenta.
5. **Una tendencia trae su ritmo** (`14-tendencias.md`, preset `tendencia`): si la referencia es una tendencia, manda lo medido en sus ejemplos, aunque corte más rápido que el preset de la marca. «La artista» corta cada 1,5 s (un compás de «Pump It»).
6. **El tempo se verifica con los cortes.** librosa confunde octavas y relaciones 2/3 (dio 103 bpm para un tema de 156). `analizar_referencia.py` elige el tempo que deja los cortes de la referencia en números enteros de beats (`bpm_grilla`).
7. **Se calibra con sus datos** (ver `06-medicion.md`). Los números de terceros son promedios de cuentas que no son la suya. Después de 4-6 reels con el ritmo nuevo, se compara su tiempo medio de visualización y su tasa de salteo contra los reels rápidos, y se ajusta el preset de la marca.

## Fuentes

- Mosseri, Threads (enero de 2025): https://www.threads.com/@mosseri/post/DE-efFqyStv
- Social Media Today, reels de 3 minutos en Explorar: https://www.socialmediatoday.com/news/instagram-will-recommend-longer-3-minute-reels/737913/
- Duración con datos (2026): https://www.moonb.io/blog/instagram-reel-length
- Referencias de finalización: https://growcreator.pro/blog/instagram-reels-completion-rate-benchmark
- Ritmo de edición en video corto: https://shortzly.com/blog/short-form-video-pacing-editing-guide
- Estructura de transformaciones: https://www.influencers-time.com/then-and-now-transformation-reels-the-brief-keeping-results/
