# 10. Historias

Las historias duran 24 horas y las ven sobre todo quienes ya siguen la cuenta. No sirven para que la descubran: sirven para **mantenerse presente y convertir**, con turnos, novedades y el detrás de escena. Herramienta: `armar_historia.py`.

## Lo que se sabe

- 🟢 **Medidas:** 1080×1920. Una historia de video dura hasta 60 s por tramo; una foto se muestra unos 5 s.
- 🟢 **Zona segura** (Meta, 2026): 14 % arriba (nombre y foto de perfil), 20 % abajo (barra de respuesta) y 6 % a los costados. `verificar.py --formato historia` la sombrea.
- 🟢 **Lo que no se puede incrustar:** los stickers interactivos (link, encuesta, pregunta, mención, cuenta regresiva) se agregan en la app. La composición les **deja una franja libre** (`espacio_sticker`) y el informe dice cuál poner.
- 🟢 **Destacadas:** las historias que valen más de un día (precios, turnos, resultados) se guardan en Destacadas del perfil. Ella ya las usa.
- ⚪ **Una idea por historia**, legible en 1 s: la foto o el video manda, y el texto acompaña.
- ⚪ **Acompañar cada reel nuevo** con una historia (`teaser`, o compartir el reel con un sticker de link) lleva a los seguidores al reel en sus primeras horas.

## Plantillas de `armar_historia.py`

| Plantilla | Para qué | Bloque de texto | Sticker sugerido |
|---|---|---|---|
| `novedad` | Producto, servicio nuevo, aviso | arriba (hasta el 38 %) | encuesta o pregunta |
| `turno` | Turnos libres, "las espero" | al medio (hasta el 52 %) | link a WhatsApp, abajo |
| `resultado` | Una foto de un trabajo | abajo (hasta el 70 %) | mención a la clienta, arriba |
| `detras` | Video del día a día | arriba (hasta el 34 %) | — |
| `teaser` | Anunciar un reel nuevo | arriba, con una tarjeta al medio | link al reel, abajo |

**En todas:**
- **Firma:** su logo chico en una placa clara. Va arriba a la derecha, o abajo si el sticker va arriba o si el título va arriba (novedad, detras, teaser), porque si no le tapa el primer renglón.
- **Estilo salon-pop:**
  - acercamiento lento sobre la foto;
  - corrección cálida, viñeta y grano;
  - título en Fraunces palabra por palabra con resaltador;
  - nota manuscrita en Caveat;
  - destellos.
- **Salida:** `historia.mp4` y `historia.jpg` (el último cuadro, para subirla fija).
- **Textos:** de ella. Lo que no sea textual va declarado en `adaptaciones` del `historia.yaml`.

## Fuentes

- Zonas seguras de historias: https://behaviour.digital/post/instagram-story-safe-zones-2026-the-definitive-guide-for-professional-brand-design-69834
- Medidas: https://www.argil.ai/blog/instagram-story-dimensions
