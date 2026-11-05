# Presentación de la defensa

[`EventFlow-defensa.pdf`](./EventFlow-defensa.pdf): 15 diapositivas 16:9 para acompañar la defensa, con poco texto y prioridad a los diagramas.

| # | Tema |
|---|------|
| 1-2 | Portada y el problema |
| 3 | Arquitectura (servicios y qué base usa cada uno) |
| 4-5 | Selección de bases y estrategia de tres bases |
| 6 | Modelado: embebido vs referencia |
| 7 | Consistencia por operación (AP/CP) y caché |
| 8 | Diagrama de la cadena (Chain of Responsibility) |
| 9-10 | SAGA orquestada y compensaciones (con una auditoría real) |
| 11-12 | Atomicidad (Lua + JMeter) e idempotencia |
| 13 | Event log + CQRS |
| 14-15 | Resultados y límites, cierre |

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
