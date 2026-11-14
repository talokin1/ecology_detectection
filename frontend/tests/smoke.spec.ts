/**
 * Smoke test: every route and every case opens, draws its map and charts, and logs no errors.
 * "No click leads into a void" (plan v2 definition of done).
 * Run: npm run build && npm run smoke
 */
import { expect, test } from '@playwright/test';

const routes = [
  '/', '/?var=t2m&case=02', '/?var=precip&case=none',
  '/case/01', '/case/02', '/case/03',
  '/region/sahel?var=precip', '/region/north_europe?var=soil',
  '/compare/ukraine/sahel?var=t2m',
  '/catalog', '/catalog?topic=water', '/methods', '/methods?s=fdr',
];

for (const r of routes) {
  test(`opens ${r}`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
    await page.goto(`/#${r}`);
    await expect(page.locator('.topbar')).toBeVisible();
    await expect(page.locator('.state h2')).toHaveCount(0); // no error state
    if (r.startsWith('/case') || r.startsWith('/region') || r.startsWith('/compare')) {
      await expect(page.locator('.series-chart .main-svg').first()).toBeVisible({ timeout: 15000 });
    }
    expect(errors).toEqual([]);
  });
}

test('unknown routes and regions show a way back, not a blank page', async ({ page }) => {
  await page.goto('/#/case/99');
  await expect(page.getByRole('link', { name: 'Back to the map' })).toBeVisible();
  await page.goto('/#/region/atlantis?var=t2m');
  await expect(page.getByRole('link', { name: 'Back to the map' })).toBeVisible();
});

test('clicking a prepared region on the map opens its investigation', async ({ page }) => {
  await page.goto('/#/?var=t2m&case=none');
  await page.locator('.region-label', { hasText: 'Sahel' }).click();
  await expect(page).toHaveURL(/#\/region\/sahel\?var=t2m/);
  await expect(page.locator('.verdict__headline')).toBeVisible();
});

test('clicking open ocean says the investigation is not open yet', async ({ page }) => {
  await page.goto('/#/?var=t2m&case=none');
  const map = page.locator('.mappage__map .trend-map__canvas');
  await map.waitFor();
  const box = (await map.boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.45, box.y + box.height * 0.7); // South Atlantic, clear of the legend
  await expect(page.getByRole('dialog', { name: 'Investigation not open yet' })).toBeVisible();
});
