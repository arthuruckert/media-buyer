// Builds assets/Arthur-Ruckert-CV.pdf from cv/cv.html with headless Chromium.
// Usage: node cv/build_cv.js
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const src = 'file://' + path.resolve(__dirname, 'cv.html');
  const out = path.resolve(__dirname, '..', 'assets', 'Arthur-Ruckert-CV.pdf');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(src, { waitUntil: 'networkidle' });
  const pending = await page.$$eval('.fill', els => els.map(e => e.textContent.trim()));
  if (pending.length) console.log('Left out of the PDF (still [PREENCHER]):\n- ' + pending.join('\n- '));
  await page.pdf({ path: out, format: 'Letter', printBackground: true, preferCSSPageSize: true });
  await browser.close();
  console.log('Wrote ' + out);
})();
