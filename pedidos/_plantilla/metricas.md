---
# Métricas de una publicación. Va en pedidos/<pedido>/salida/metricas.md.
# Fuente principal: Metricool (herramientas/metricool.py la escribe sola, `fuente: metricool`).
# Respaldo: Claude lee una captura de Insights que manda Ana o Fernando (`fuente: captura`).
# Se mide a las 72 h y a los 7 días. Lo que no se ve o no viene queda vacío: no se estima.
# herramientas/metricas.py junta todos los pedidos en marcas/<marca>/metricas.md.
publicado:            # AAAA-MM-DD en que se subió
link:                 # URL de la publicación (con esto metricool.py la une sin mirar la descripción)
archivo:              # qué se subió (p. ej. reel-con-audio.mp4, v3)
mediciones:
  - a: 72h            # 72h | 7d (o la edad real, p. ej. 10d, si se midió en otro momento)
    fecha:            # AAAA-MM-DD de la medición
    fuente:           # metricool | captura
    visualizaciones:
    alcance:          # cuentas alcanzadas
    no_seguidores_pct:  # solo captura
    salteo_pct:       # tasa de salteo (se fueron antes de los 3 s)
    tiempo_medio_s:   # tiempo de visualización promedio
    retencion_pct:    # % medio del reel que se vio (Instagram, vía Metricool)
    me_gusta:
    comentarios:
    envios:           # veces que se compartió
    guardados:
    conversaciones:   # conversaciones iniciadas / clics a WhatsApp, si aparecen (solo captura)
    pozo_s:           # segundo donde cae la curva de retención, si se ve (solo captura)
    # solo historias (Metricool): salidas, toques_adelante, toques_atras, respuestas
    # solo fotos y carruseles (Metricool): seguidores_ganados
---

## Lectura

<!-- Claude, con conocimiento/06-medicion.md: qué funcionó (gancho, desarrollo, envíos)
y qué probar la próxima vez. Comparar con los reels anteriores de la cuenta, no con promedios. -->
