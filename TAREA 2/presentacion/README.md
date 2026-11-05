# Presentación de la defensa

[`EventFlow-defensa.pdf`](./EventFlow-defensa.pdf): 20 diapositivas 16:9 para acompañar la defensa.

| # | Tema |
|---|------|
| 1-3 | Portada, agenda, el problema y los requisitos |
| 4 | Arquitectura (servicios y qué base usa cada uno) |
| 5-6 | Selección de bases y estrategia de tres bases |
| 7 | Modelado: embebido vs referencia |
| 8-9 | Consistencia por operación y caché AP |
| 10-11 | Chain of Responsibility (diagrama y código) |
| 12-13 | SAGA orquestada y compensaciones (con una auditoría real) |
| 14-15 | Atomicidad (Lua + JMeter) e idempotencia/resiliencia |
| 16-17 | Event log + CQRS y export anonimizado |
| 18-20 | Resultados, límites y cierre |

## Editar y regenerar

La fuente es [`presentacion.html`](./presentacion.html) (una `<section class="slide">` por diapositiva, diagramas en Mermaid). Para regenerar el PDF:

```bash
# desde TAREA 2/, con Docker (no hace falta instalar nada en el host)
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/presentacion":/p -w /p \
  mcr.microsoft.com/playwright:v1.47.2-jammy \
  sh -c "npm i --no-save --silent playwright@1.47.2 && node generar_pdf.mjs"
```

Alternativa sin Docker: abrir `presentacion.html` en Chrome → Imprimir → Guardar como PDF, con "Gráficos de fondo" activado (el tamaño de página ya está definido en el CSS).

Necesita internet (Mermaid y la tipografía Inter se cargan desde CDN). Los datos de las diapositivas salen del código y de las mediciones documentadas en `jmeter/README.md` y `brain/`.
