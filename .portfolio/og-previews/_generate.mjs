import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const portfolioDir = path.join(__dirname, '..');

const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1200, height: 630, deviceScaleFactor: 2 });
await page.goto(`file://${path.join(__dirname, 'og-home.html')}`, { waitUntil: 'networkidle0' });
await page.evaluateHandle('document.fonts.ready');
await new Promise(r => setTimeout(r, 600));

const el = await page.$('.og-card');
await el.screenshot({ path: path.join(portfolioDir, 'preview.png'), type: 'png' });
console.log('✓ wrote .portfolio/preview.png');

await browser.close();
