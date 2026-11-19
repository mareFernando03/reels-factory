# 7. Edición y estética: que no parezca trucho y que sorprenda

Un reel parece "trucho" cuando **la edición se nota más que el contenido**: efectos de plantilla, todo con el mismo movimiento, textos que saltan, cortes a destiempo. Parece profesional cuando la edición es **invisible**: todo cae donde tiene que caer y nadie sabe explicar por qué se ve bien.

La mayor parte de esto es ⚪ (oficio de editores y motion designers), con dos bases más sólidas: la teoría de montaje de Walter Murch y las normas de subtítulos de la industria.

## 1. Por qué se corta: la regla de seis de Murch

Walter Murch (editor de *Apocalypse Now* y *El paciente inglés*) jerarquiza qué importa en un corte, en *In the Blink of an Eye*:

| Criterio | Peso |
|---|---|
| **Emoción** | 51 % |
| **Historia** | 23 % |
| **Ritmo** | 10 % |
| Trayectoria de la mirada | 7 % |
| Plano 2D de la pantalla | 5 % |
| Espacio 3D | 4 % |

Si el corte es emocionalmente correcto, el público perdona errores técnicos; al revés, no.

**Aplicado a un reel de peluquería:**
- La **emoción** es el "wow" del resultado y la cara de la clienta al verse.
- La **historia** es el antes → proceso → después.
- El **ritmo** es la música.
- **Se corta cuando el espectador "ya vio"**, no cuando termina la toma. Murch lo compara con el parpadeo: cortamos cuando termina una idea.
- **Trayectoria de la mirada:** si en una toma lo importante está a la derecha, la siguiente conviene que arranque con lo importante en el mismo lugar. El ojo no tiene que "buscar" después de cada corte.

## 2. Lo que delata una edición amateur ⚪

Las guías de editores coinciden en estas señales:

1. **Transiciones de efecto** (giros, cubos 3D, barridos de estrella, glitch sin motivo). Se ven viejas y distraen. **Un corte seco casi siempre es mejor.**
2. **Cada toma dura un poco de más.** El amateur deja respirar todo; el profesional corta apenas se entendió.
3. **El material va en el orden en que se grabó.** El profesional busca en todo el material los 2 segundos que frenan a un desconocido, los pone primero y reconstruye alrededor.
4. **Cortes, textos y transiciones fuera del beat.** Si la música marca un tiempo y el corte cae entre dos golpes, se siente torpe aunque nadie sepa por qué.
5. **Movimiento lineal.** Las animaciones a velocidad constante, que arrancan y frenan en seco, son "la señal número uno de trabajo inexperto" según la bibliografía de motion design.
6. **El mismo movimiento en todas las fotos.** Zoom, zoom, zoom: se vuelve monótono enseguida.
7. **Texto ilegible o sobre fondo del mismo tono.** Y texto que no dura lo suficiente para leerse.
8. **Color distinto entre tomas, o filtros fuertes.**
9. **Audio descuidado:** música que tapa la voz, saltos de volumen, distorsión.
10. **Encuadres que cortan cabezas** u horizontales recortados a vertical sin pensar.

### 2.b Lo que delata el "editor de Instagram" (aprendido en la factory)

La primera versión del reel de los pochoclos estaba bien según la rúbrica y aun así se veía pobre. Las causas:
- **Texto en una tipografía genérica** (Poppins, Inter, la de la app) **sobre una cajita oscura:** es el estilo por defecto de Instagram, CapCut y Edits, y el ojo lo reconoce como "hecho con la app".
- **Solo cortes secos**, ningún momento con transición diseñada.
- **Ningún elemento gráfico propio** (stickers, destellos, formas).
- **El video sin tratamiento de color.**
- **Cierre estático.**

La versión que funcionó (estilo `salon-pop`, ver `estilos/salon-pop/estilo.yaml`) tiene:
- **Tipografía de display con carácter:** serif itálica, palabra por palabra.
- **Palabra clave con resaltador** de la marca.
- **Sombra difusa en lugar de caja** para que el texto se lea.
- **Stickers de pasos.**
- **Transiciones con intención:** golpe de zoom en el beat, zoom con desenfoque, destello de luz en el revelado, apertura circular al cierre.
- **Corrección cálida, viñeta y grano**, que además disimulan una fuente de baja resolución.

## 3. Movimiento y animación

- **Siempre con easing (aceleración y frenado):**
  - lo que **entra**, rápido y frenando suave (*ease-out*)
  - lo que **sale**, arrancando suave (*ease-in*)
  - lo que **se mueve dentro del cuadro**, las dos cosas (*ease-in-out*)

  Ni en un zoom lento hay que usar velocidad constante.
- **Movimiento con destino.** El zoom o paneo de una foto va **hacia algo**: la cara, un rulo definido, el brillo del color. Un zoom al centro geométrico no dice nada.
- **Variedad con criterio.** Se alternan acercamientos, alejamientos y paneos según qué muestra cada foto, no por sorteo.
- **Lento se ve cinematográfico; rápido y nervioso se ve barato**, salvo en una sucesión rápida deliberada.
- **Animación de texto sutil:** entrada de 0,2 a 0,4 s con frenado suave (subir 10 a 20 px más un fundido). Nada de rebotes, giros ni "máquina de escribir" salvo que sea el estilo del reel.
- **Fotos fijas:** el paneo y zoom (efecto Ken Burns) es el piso. Para que se vea premium se puede llegar al **2.5D**: separar la persona del fondo y moverlos a distinta velocidad, como si hubiera profundidad. Requiere recortar a la persona (segmentación), así que queda como mejora futura.

## 4. Transiciones que no se notan ⚪

Las transiciones que se ven profesionales **esconden el corte en el movimiento**:

- **Corte por coincidencia (match cut):** dos tomas que comparten forma, encuadre o movimiento. Ejemplo: la espalda con el pelo mojado → la espalda con los rulos definidos, mismo encuadre y corte en el golpe de la música. **Es el corazón de un antes/después.**
- **Paneo rápido (whip pan):** la cámara barre rápido, el desenfoque esconde el corte y aparece la toma siguiente. Se graba así, no se agrega en la edición.
- **Tapar el lente:** la mano (o un cepillo, o la capa) tapa la cámara, corte, y la mano se corre con el resultado. Clásico de transformaciones.
- **Vuelta del pelo en cámara lenta:** el revelado típico del rubro.
- **Zoom a través:** acercar mucho a la textura de una toma y salir de la textura de la siguiente.

Las tres primeras **se graban, no se editan**: van en el pedido de tomas a Ana (sección 9).

## 5. Ritmo y sorpresa

- **Variar el ritmo arma tensión.** Si todos los cortes duran lo mismo, aplana. La estructura que funciona:
  - tomas de 3 beats al principio
  - **se acortan hacia el clímax** (2 beats, después 1-1-1)
  - el **revelado** sostiene más (4 beats) o pasa a cámara lenta
- **Cambio de velocidad en el revelado:** velocidad normal, cámara lenta justo en el golpe fuerte de la música, de vuelta a velocidad normal. Sirve solo si hay video (no fotos) y por pocos segundos.
- **Un momento "wow" por reel, diseñado:** el revelado, un corte por coincidencia en el golpe fuerte, la reacción de la clienta. Es lo que se recuerda y lo que hace que alguien lo mande. Si el guion no puede señalar cuál es, el reel no sorprende.
- **Reacción de la clienta:** las guías del rubro coinciden en que la reacción real (con permiso) supera incluso a la transformación más dramática.

## 6. Texto en pantalla

- **Tiempo de lectura:** las normas de subtítulos (Netflix y la industria) ponen un tope de **15 a 17 caracteres por segundo** para adultos, con mínimo de 1 s y máximo de 7 s en pantalla. Atajo: **una línea de 30 caracteres necesita unos 2 s.**
- **Como máximo 2 tipografías por reel**, siempre las de la marca.
- **Subtítulos palabra por palabra** (con color y escala en la palabra clave): son la firma de la estética 2026 para videos hablados. Para montajes con música alcanza un texto corto por momento.
- **Placa o sombra según el fondo**, nunca texto librado a la suerte (ver X1 de la rúbrica).

## 7. Color

- **Balance de blancos primero:** que lo blanco se vea blanco y la piel natural. Después, que **todas las tomas coincidan entre sí**.
- **El color del pelo es el producto:** ningún filtro, LUT ni "estética" puede cambiar su tono. Ojo con el balance automático del celular y la luz de la cámara frontal, que corren el color.
- La estética "raw-premium" del 2026 (luz natural, cámara en mano, pulido invisible por debajo) le sienta bien a una peluquería: parece real y está cuidada.

## 8. Sonido (cuando el reel lleva audio incluido)

- **Volumen de la mezcla:** alrededor de **-14 LUFS**, con picos de -1 dBTP como máximo. Instagram baja lo que viene más fuerte, así que pasarse no suma y puede distorsionar.
- **La voz por encima de la música:** bajar la música unos 4 dB cuando alguien habla.
- **Efectos sutiles en los momentos clave:** un *whoosh* en la transición principal, un *riser* que sube antes del revelado. Su pico tiene que coincidir con el corte. **En todos los cortes es demasiado:** se vuelve ruido de plantilla.
- Si la música se agrega en Instagram, los efectos van solos en `reel-efectos.mp4`, bajitos, debajo de la canción que se elija. Cuáles, cuándo y cuánto: `09-audio.md` › Efectos. **Si alguien habla, la voz manda:** `09-audio.md` › Voz.

## 9. Lo que la edición no puede arreglar: pedido de tomas para Ana

La mejor edición del mundo no salva material plano. Lo que más sube un reel de transformación, en orden:

1. **El "antes", con el mismo encuadre que el "después":** mismo lugar, misma altura, misma luz. Unos 3 segundos de video alcanzan.
2. **La reacción de la clienta** al verse, en video y con su permiso.
3. **Un revelado grabado:** una vuelta del pelo, tapar el lente con la mano y destaparlo, o girar la silla hacia el espejo.
4. **Detalle del proceso:** manos trabajando, producto, tijera, el rulo armándose. Unos 2 segundos cada uno.
5. **Luz:** de frente a una ventana o con el aro de luz que ya tiene (se ve en sus fotos). Nada de contraluz salvo a propósito.
6. **Celular quieto y en vertical**, con la lente limpia. Si se puede, cámara trasera y no frontal.

## Fuentes

- [La regla de seis de Walter Murch (StudioBinder)](https://www.studiobinder.com/blog/walter-murch-rule-of-six/) · [In the Blink of an Eye (resumen)](https://sobrief.com/books/in-the-blink-of-an-eye)
- [8 errores de edición que hacen ver amateur un video (Storyblocks)](https://www.storyblocks.com/resources/blog/editing-mistakes-beginners-make-with-video) · [errores de edición en reels](https://www.mediaalacarte.com/post/mistakes-that-make-your-reels-look-amateur-and-how-to-fix-them) · [no es la cámara](https://withmedia.in/blog/its-not-your-camera)
- [Principios de motion design y easing](https://madegooddesigns.com/motion-design-principles/) · [manual de curvas de easing](https://pow.rs/blog/animation-easings/)
- [Transiciones de edición (StudioBinder)](https://www.studiobinder.com/blog/types-of-editing-transitions-in-film/) · [transiciones grabadas en cámara (Motion Array)](https://motionarray.com/learn/filmmaking/in-camera-transitions/) · [cortes invisibles](https://medium.com/applaudience/invisible-cuts-a-new-trend-in-video-editing-b858ede7403d)
- [Efecto Ken Burns (Wikipedia)](https://en.wikipedia.org/wiki/Ken_Burns_effect) · [guía del efecto Ken Burns](https://kudoflix.com/blog/2026/08/04/ken-burns-effect/)
- [Velocidad de lectura de subtítulos (CPS)](https://www.closedcaptioncreator.com/blog/articles/subtitle-reading-speed.html) · [reglas de tiempos de subtítulos](https://soniox.com/wiki/captions-subtitles-srt-vtt)
- [Velocidad variable en short-form](https://www.nemovideo.com/blog/capcut-slow-motion-speed-ramp) · [speed ramping](https://riverside.com/video-editor/video-editing-glossary/speed-ramping)
- [Estéticas de edición 2026 (OpusClip)](https://www.opus.pro/blog/editing-aesthetics-dominating-short-form-2026)
- [Volumen para Reels: -14 LUFS](https://cutscore.io/blog/loudness-for-instagram-reels) · [audio para Reels](https://sfxengine.com/blog/reels-audio-editing-tips)
- [Corrección de color y tonos de piel](https://www.toolfarm.com/tutorial/achieve-perfect-skin-tones-when-color-grading/)
- [Ideas de reels para peluquerías](https://flowshorts.app/instagram-reels-ideas/hair-salon)
