// render.js — screenshot de cada tarjeta de tarjetas.html -> <id>.png (2x, ancho 600 px lógico).
// Uso: NODE_PATH=$(npm root -g) node render.js <carpeta del informe>
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const dir = path.resolve(process.argv[2]);
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 700, height: 1200 }, deviceScaleFactor: 2 });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.join(dir, 'tarjetas.html'));
  const cards = await p.$$('.card');
  for (const c of cards) {
    const id = (await c.getAttribute('id')).replace('card-', '');
    await c.screenshot({ path: path.join(dir, id + '.png') });
    console.log('ok', id + '.png');
  }
  if (errs.length) { console.error('errores JS:', errs); process.exit(1); }
  await b.close();
})();
