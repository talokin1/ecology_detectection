/**
 * Smoke test: every route and every case opens, draws its map and charts, and logs no errors.
 * "No click leads into a void" (plan v2 definition of done), plus the review's acceptance checks
 * that a browser can verify: answer above the fold, popup clamped and keyboard-closable, edge cases.
 * Run: npm run build && npm run smoke
 */
import { expect, test, type Page } from '@playwright/test';

const routes = [
  '/', '/?var=t2m&case=02', '/?var=precip&case=none',
  '/case/01', '/case/02', '/case/03', '/case/04',
  '/region/sahel?var=precip', '/region/north_europe?var=soil',
  '/compare/ukraine/sahel?var=t2m',
  '/catalog', '/catalog?topic=water', '/methods', '/methods?s=fdr',
];

function trackErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  return errors;
}

for (const r of routes) {
  test(`opens ${r}`, async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto(`/#${r}`);
    await expect(page.locator('.topbar')).toBeVisible();
    await expect(page.locator('.state h2')).toHaveCount(0); // no error state
    if (r.startsWith('/case') || r.startsWith('/region') || r.startsWith('/compare')) {
      await expect(page.locator('.series-chart .main-svg').first()).toBeVisible({ timeout: 15000 });
    }
    expect(errors).toEqual([]);
  });
}

test('the answer is above the fold on case, region and compare pages (P0-1)', async ({ page }) => {
  for (const r of ['/case/01', '/case/03', '/region/sahel?var=precip']) {
    await page.goto(`/#${r}`);
    const readout = page.locator('.readout');
    await expect(readout).toBeVisible();
    const box = (await readout.boundingBox())!;
    expect(box.y + box.height).toBeLessThan(900);
  }
});

test('unknown routes and regions show a way back, not a blank page', async ({ page }) => {
  await page.goto('/#/case/99');
  await expect(page.getByRole('link', { name: 'Back to the map' })).toBeVisible();
  await page.goto('/#/region/atlantis?var=t2m');
  await expect(page.getByRole('link', { name: 'Back to the map' })).toBeVisible();
});

test('the ledger opens an investigation', async ({ page }) => {
  await page.goto('/#/?var=t2m&case=none');
  await page.locator('.ledger__row', { hasText: 'Sahel' }).click();
  await expect(page).toHaveURL(/#\/region\/sahel\?var=t2m/);
  await expect(page.locator('.readout__headline')).toBeVisible();
});

test('open sea: the popup stays inside the map, hides the tooltip and closes with Escape (P0-6)', async ({ page }) => {
  await page.goto('/#/?var=t2m&case=none');
  const map = page.locator('.stage__map .trend-map__canvas');
  await map.waitFor();
  const box = (await map.boundingBox())!;
  for (const [fx, fy] of [[0.45, 0.62], [0.97, 0.66]]) {
    await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy); // Atlantic, then far east edge
    const dialog = page.getByRole('dialog', { name: 'Investigation not open yet' });
    await expect(dialog).toBeVisible();
    const d = (await dialog.boundingBox())!;
    const frame = (await page.locator('.stage__map').boundingBox())!;
    expect(d.x).toBeGreaterThanOrEqual(frame.x);
    expect(d.x + d.width).toBeLessThanOrEqual(frame.x + frame.width + 1);
    expect(d.y + d.height).toBeLessThanOrEqual(frame.y + frame.height + 1);
    await expect(page.locator('.map-tooltip')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  }
});

test('edge cases render without errors: too little data, gaps, no extremes, no findings (P1-12)', async ({ page }) => {
  const errors = trackErrors(page);
  await page.route('**/data/analysis/sahel__precip.json', async (route) => {
    const res = await route.fetch();
    const a = await res.json();
    a.verdict = { ...a.verdict, level: 'insufficient', headline: 'Not enough data to judge', answer: 'The record is too short or too patchy to judge a trend.', methods_disagree: false, disagree_text: null };
    a.trend = { ...a.trend, sen_per_decade: null, ci90: null, ci95: null, ci99: null, total_change: null, total_change_ci95: null, line: null, band95: null };
    a.series.anomaly = a.series.anomaly.map((v: number | null, i: number) => (i % 5 === 0 ? null : v));
    a.series.annual.anomaly = a.series.annual.anomaly.map((v: number | null, i: number) => (i % 4 === 0 ? null : v));
    a.extremes = null;
    a.insights = [];
    a.seasons = [];
    a.monthly_profile = [];
    a.emergence = { ...a.emergence, year: null, label: null };
    await route.fulfill({ response: res, json: a });
  });
  await page.goto('/#/region/sahel?var=precip');
  await expect(page.locator('.readout__headline')).toHaveText('Not enough data to judge');
  await expect(page.locator('.readout__value')).toHaveText('—');
  await expect(page.locator('.series-chart .main-svg').first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.chart-caption')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('keyboard: the map canvas is focusable and arrow keys read squares (P1-11)', async ({ page }) => {
  await page.goto('/#/?var=t2m&case=none');
  const canvas = page.locator('.stage__map .maplibregl-canvas');
  await canvas.waitFor();
  await canvas.focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.map-tooltip')).toBeVisible();
});
