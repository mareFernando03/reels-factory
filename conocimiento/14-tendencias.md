# 14. Tendencias: medirlas antes de copiarlas

Por qué existe: en el pedido «la obra de arte» (10/10/2026), Ana mandó una referencia que resultó ser una tendencia («La artista / La energía / Las herramientas / El lienzo / El arte», sobre «Pump It» de The Black Eyed Peas). El primer guion se armó mirando ese único reel y salió mal en lo que más importa de una tendencia: el ritmo (tomas de 2,3 s que caían a mitad de compás). Midiendo cinco reels del rubro con la misma tendencia aparecieron el ritmo real, el orden, la tipografía y el final. Esta sección deja el método para la próxima.

## Cómo se reconoce una tendencia

- El audio tiene miles de reels (la página del audio lo dice: «609 mil reels»).
- Una estructura fija que se rellena: rótulos que se repiten de reel en reel, el mismo tipo de toma en el mismo lugar.
- Aparece en varios rubros (uñas, pestañas, cosmetología, peluquería, «un día conmigo»).

## El método

1. **Ir a la página del audio** desde la referencia (Chrome: tocar el nombre del audio). Ahí están los reels que lo usan, con sus vistas.
2. **Bajar 5-10 del rubro o de rubros vecinos** con `bajar.py` (a un directorio de trabajo, no al pedido) y medir cada uno con `analizar_referencia.py <video> --salida <dir>`.
3. **Una hoja con sus fotogramas** para leer lo que no se mide: orden, textos, tipografía, transiciones, final.
4. **Sacar la receta**: lo que se repite en la mayoría es la tendencia (audio, orden, ritmo, final). Lo visual (tipografía, color, gráficos) se hace con la marca, aunque todos los ejemplos usen el mismo.
5. **Tempo verificado.** `analizar_referencia.py` elige el bpm que explica los cortes y deja `bpm_grilla`. Las tendencias cortan en el **compás** (4 tiempos), no en cualquier beat.
6. **Audio:** casi siempre es una canción con derechos. Va por modo `instagram`, y **hay que confirmar que la cuenta de la marca la tenga** (las cuentas de empresa pueden tener solo la Meta Sound Collection, ver `05-publicidad.md`). Si no la tiene, la receta de ritmo no sirve tal cual: se retimea con el audio que haya.

## Lo que pesa más en una tendencia ⚪ (oficio, medido en pocos casos)

- **De la tendencia se toma la estructura; el look es de la marca.** Lo que hace que se reconozca es el audio, el orden de los pasos, el ritmo (un rótulo por compás) y el final. La tipografía, el color, los gráficos y el tratamiento del texto son los de la marca (rúbrica M1 y O11). Si el reel sale igual al de cualquier otra cuenta, no suma a la marca: lo que se recuerda tiene que ser de ella.
  - Error de «la obra de arte» (10/10/2026): se copió también la serif fina de la tendencia. Fernando: «no siempre hay que copiar las tipografías de los demás, sino imprimir una marca personal».
  - Para Salón Demo: rótulos de una o dos palabras con la tipografía del logo (Berkshire Swash: `marca.yaml` la reserva justo para títulos cortos) o la de salon-pop con la palabra clave en el resaltador magenta. Se conserva lo que es oficio y no estilo ajeno: una idea por toma, siempre a la misma altura y entrada sobria.
- **El texto siempre a la misma altura** cuando es un rótulo por toma: el ojo no busca después de cada corte (Murch, trayectoria de la mirada, `07-edicion-y-estetica.md`).
- **El final es el resultado, sostenido**, y en la mayoría el reel vuelve a empezar sin placa de marca (bucle). El CTA puede ir chico encima del resultado o en la descripción.

## Medido: «La artista» (Pump It), octubre de 2026 🟡

Cinco reels del rubro belleza tomados de la página del audio (vistas de esa página; la muestra es chica y elegida por Instagram, no al azar):

| Cuenta | Rubro | Vistas | Duración | Tomas (s) |
|---|---|---|---|---|
| @cuenta_1 | uñas | 234 mil | 10,9 s | 1,5 · 1,5 · 1,1 · 2,0 · 1,4 · 0,4 · 3,0 |
| @cuenta_2 | pelo | 101 mil | 10,9 s | 1,5 · 1,5 · 1,1 · 1,9 · 1,5 · 3,3 |
| @cuenta_3 | uñas | 91 mil | 10,9 s | 1,2 · 2,9 · 1,8 · giro · 1,5 · giro · 3,3 |
| @cuenta_4 | cosmetología | 66 mil | 13,0 s | 1,5 · 0,3 · 1,5 · 1,8 · 1,5 · 1,6 · 1,1 · 3,7 |
| @cuenta_5 | pestañas | 50 mil | 14,3 s | 1,5 · 1,5 · 1,4 · 1,5 · 1,6 · 6,7 |

- **Receta:** la artista (selfie en el espejo) → la energía (café o mate) → las manos / las herramientas → el lienzo (el antes) → el arte (el resultado). «La energía» está en casi todos: es parte de la tendencia.
- **Ritmo:** «Pump It» va a ~156 bpm (librosa dice 103). Un rótulo por compás, 4 tiempos ≈ 1,53 s; el resultado, 8 tiempos o más (3-7 s). Total 11-14 s más el cierre.
- **Texto:** una palabra o dos, centrada a media altura, la misma en todas las tomas. Los ejemplos usan una serif fina blanca: es la de ellos, no la receta (ver arriba).
- **Transición clave:** el lienzo y el arte **con el mismo encuadre** (corte por coincidencia); algunos meten un giro o un destello de 0,1-0,4 s justo antes. El resto, cortes secos en el compás.
- **Pedido de tomas:** filmar el resultado desde el mismo lugar, altura y distancia que el lienzo. Cada toma, 2-3 s quietos (alcanza con 1,5 s útiles).

## Medido: «Cosas que sí dan miedo en octubre», octubre de 2026 🟡

Audio original de @cuenta_6 (instrumental, 129 bpm, sin letra; 9,7 mil reels al 26/10). Siete reels del rubro belleza y estudios, de la página del audio (vistas de la API el 26/10):

| Cuenta | Rubro | Vistas | Duración | Tomas (s) |
|---|---|---|---|---|
| @cuenta_6 | pelo | 140 mil | 15,8 s | 2,2 · 2,4 · 4,5 · 2,5 · 4,2 |
| @cuenta_7 | pelo | 120 mil | 12,9 s | 2,1 · 2,0 · 2,1 · 2,0 · 2,1 · 2,6 |
| @cuenta_8 | piel | 66 mil | 14,3 s | 1,9 · 1,3 · 1,0 · 1,5 · 0,9 · 4,1 · 1,1 · 2,4 |
| @cuenta_9 | pelo | 16 mil | 12,1 s | 1,7 · 1,6 · 1,6 · 1,6 · 1,5 · 1,5 · 2,6 |
| @cuenta_10 | pelo | 5,6 mil | 15,9 s | otra variante: fotos de productos encima del pelo |
| @cuenta_11 | piel | 4,6 mil | 10,8 s | 3,5 · 2,1 · 2,8 · 2,4 |

- **Receta:** alguien disfrazado (máscara de terror o fantasma de sábana con anteojos) levanta un cartel escrito a mano por toma, con un «miedo» del rubro. En pelo se repiten tintura negra, productos del súper, cortarse el pelo sola, crecimiento de 6 meses, clienta impuntual y dormir con el pelo mojado. Cada toma, en un rincón distinto del local.
- **Ritmo:** un cartel cada 2-2,5 s. Con algo de acción antes del cartel (sentarse o darse vuelta), la toma llega a 4,5 s (CAPRI). Total de 11 a 16 s, sin placa de marca: termina en el último cartel, sostenido un poco más.
- **Texto:** un encabezado fijo durante todo el reel («Cosas que sí dan miedo en octubre»), arriba o sobre el cuerpo. Los carteles son el texto: no se rotulan aparte.
- **Por qué funciona:** humor del oficio que las clientas reconocen (R4: se manda). El disfraz es el gancho del primer cuadro.

## Cuándo no seguir la tendencia

- Si la cuenta no tiene el audio y no hay uno parecido en tempo y energía.
- Si el material no da para la estructura (sin «antes», el lienzo → arte no existe).
- Si la tendencia ya está gastada en el rubro local (muchas cuentas de la ciudad con lo mismo en la misma semana). Se mira en la página del audio filtrando por cercanía, a ojo.

## Fuentes

- Página del audio «Pump It» en Instagram: https://www.instagram.com/reels/audio/1154559479569864/ y los reels medidos (DdrdTkLxMim, Ddws-dDhTK2, DdRDO0VIYrC, DeAV9mIpl5x, DdkF5mRRJdh)
- La tendencia en TikTok («Artist Art Tools»): https://www.tiktok.com/discover/the-artist-art-tools-trend
- Versión en español en uñas: https://www.threads.com/@cuenta_12/post/Dd1pZlBEded/
