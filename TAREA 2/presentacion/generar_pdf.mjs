// Genera EventFlow-defensa.pdf desde presentacion.html con Chromium (Playwright).
// Uso (desde TAREA 2/, con Docker; no requiere nada instalado en el host):
//   docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/presentacion":/p -w /p \
//     mcr.microsoft.com/playwright:v1.47.2-jammy \
//     sh -c "npm i --no-save --silent playwright@1.47.2 && node generar_pdf.mjs"
// Necesita internet: los diagramas usan Mermaid y la tipografía Inter desde CDN.
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto('file://' + path.join(dir, 'presentacion.html'), { waitUntil: 'networkidle' });
await page.waitForFunction(() => window.__listo === true, null, { timeout: 60000 });
const error = await page.evaluate(() => window.__error || null);
if (error) throw new Error('Mermaid: ' + error);
await page.emulateMedia({ media: 'print' });
await page.pdf({ path: path.join(dir, 'EventFlow-defensa.pdf'), width: '1920px', height: '1080px',
                 printBackground: true, preferCSSPageSize: true });
await browser.close();
console.log('OK: presentacion/EventFlow-defensa.pdf');
