/**
 * Smoke test: every route opens, draws its map and charts, and logs no errors ("no click leads
 * into a void", plan v2). Plus the acceptance checks a browser can verify from the review plan and
 * the production UX plan (closable panels, map with filters, hints, noise budget, keyboard).
 * Run: npm run build && npm run smoke
 */
import { expect, test, type Page } from '@playwright/test';

const routes = [
  '/', '/?var=t2m', '/?var=precip&show=clear', '/?panel=quick&region=ukraine&q=02', '/?var=precip&panel=regions&q=03',
  '/case/01', '/case/02', '/case/03', '/case/04',
  '/region/sahel?var=precip', '/region/north_europe?var=soil',
  '/compare/ukraine/sahel?var=t2m',
  '/?in=world', '/?in=stories', '/?var=sea_ice', '/?var=haze&panel=regions', '/?panel=quick&region=c_bra&var=haze', '/?var=snow_cover',
  '/region/c_fra?var=sunlight', '/region/ar6_med?var=ozone', '/region/ukraine?var=evap',
  '/?var=t2m&s=mam', '/?var=t2m&vs=world', '/?var=precip&s=djf&vs=world', '/?var=sea_ice&s=son&vs=world',
  '/?var=t2m&panel=area&area=-46,46,-20,62', '/?var=soil&s=jja&panel=area&area=-12,34,4,46&area2=10,45,30,55',
  '/methods?s=area', '/?var=t2m_sat&s=jja', '/?var=vapour_sat&panel=area&area=10,40,30,55',
  '/catalog', '/catalog?topic=water', '/methods', '/methods?s=fdr', '/about', '/about?s=data',
];

function trackErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  return errors;
}

/** A returning visitor: the one-time banner and tour offer are already dismissed. */
async function returning(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('td-banner-off', '1');
    localStorage.setItem('td-tour-seen', '1');
  });
}

/** Visible HTML text items, words and controls in the first viewport (SVG chart labels excluded). */
async function noise(page: Page) {
  return page.evaluate(() => {
    const vis = (el: Element) => {
      const b = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return b.width > 1 && b.height > 1 && b.bottom > 0 && b.top < innerHeight && b.right > 0 && b.left < innerWidth && s.visibility !== 'hidden' && s.display !== 'none';
    };
    let items = 0;
    let words = 0;
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const t = (w.currentNode.textContent ?? '').trim();
      const p = w.currentNode.parentElement;
      if (t && p && !p.closest('svg') && vis(p)) {
        items++;
        words += t.split(/\s+/).length;
      }
    }
    const controls = [...document.querySelectorAll('a, button, select, input')].filter(vis).length;
    return { items, words, controls, screens: document.documentElement.scrollHeight / innerHeight };
  });
}

for (const r of routes) {
  test(`opens ${r}`, async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto(`/#${r}`);
    await expect(page.locator('.topbar')).toBeVisible();
    await expect(page.locator('.state h2')).toHaveCount(0); // no error state
    if (/^\/(case|region|compare)/.test(r) || r.includes('panel=quick') || r.includes('panel=area')) {
      await expect(page.locator('.series-chart .main-svg').first()).toBeVisible({ timeout: 15000 });
    }
    expect(errors).toEqual([]);
  });
}

test('noise budget: the default Explore view stays quiet and the map fills the page (U1, B8)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/');
  await page.locator('.explore__map .maplibregl-canvas').waitFor();
  await page.waitForTimeout(1500);
  const n = await noise(page);
  expect(n.items).toBeLessThanOrEqual(30);
  expect(n.words).toBeLessThanOrEqual(80);
  // 18 + 1 for the AI assistant button in the top bar (ADR-009; absent when no assistant URL is set)
  // + 3 for the map views and the area tool (months, view, "Draw an area"; ADR-011)
  // + 1 for "Year by year" (map playback, 2026-11-15).
  expect(n.controls).toBeLessThanOrEqual(23);
  const map = (await page.locator('.explore').boundingBox())!;
  const top = (await page.locator('.topbar').boundingBox())!;
  expect((map.width * map.height) / (1440 * (900 - top.height))).toBeGreaterThanOrEqual(0.85);
  await expect(page.locator('.rail, .ledger')).toHaveCount(0); // nothing but the map and its controls
});

test('noise budget: the full analysis page (A11)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/case/01');
  await page.locator('.series-chart .main-svg').first().waitFor();
  const n = await noise(page);
  expect(n.items).toBeLessThanOrEqual(45);
  expect(n.screens).toBeLessThanOrEqual(2.2);
  await expect(page.locator('.readout__headline')).toBeVisible();
  await expect(page.locator('.vdetails__sure').first()).toBeVisible(); // "How sure?" never collapsed
});

test('internal vocabulary is gone: no "Case 0X" anywhere (A7, A13)', async ({ page }) => {
  for (const r of ['/', '/case/01', '/case/03', '/methods']) {
    await page.goto(`/#${r}`);
    await page.locator('.topbar').waitFor();
    await page.waitForTimeout(800);
    await expect(page.locator('body')).not.toContainText(/\bCase\s?0\d/);
    await expect(page.locator('body')).not.toContainText('Investigation');
  }
});

test('a hint opens its answer next to the map; hints can be hidden and brought back (A7)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/');
  const hint = page.getByRole('complementary', { name: 'Suggested question' });
  await expect(hint).toBeVisible();
  await hint.locator('.hint__q').click();
  await expect(page).toHaveURL(/panel=quick/);
  await expect(page.locator('.quick__value')).toBeVisible({ timeout: 15000 });
  await page.keyboard.press('Escape');
  await expect(page.locator('.quick__value')).toHaveCount(0);
  await page.getByRole('button', { name: 'Hide suggestions' }).click();
  await page.reload();
  await expect(page.locator('.hint')).toHaveCount(0);
  await page.getByRole('button', { name: 'Show suggested questions again' }).click();
  await expect(page.locator('.hint')).toBeVisible();
});

test('every panel closes with its button and with Escape, and the legend comes back (A1, A4)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m&panel=regions&in=stories');
  const panel = page.getByRole('dialog', { name: 'Regions compared' });
  await expect(panel).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await page.getByRole('button', { name: 'Compare the prepared regions' }).click();
  await expect(panel).toBeVisible();
  await panel.getByRole('button', { name: 'Close: Regions compared' }).click();
  await expect(panel).toHaveCount(0);
  await page.getByRole('button', { name: 'Hide legend' }).click();
  await expect(page.locator('.lchip')).toHaveCount(0);
  await page.getByRole('button', { name: 'Legend' }).click();
  await expect(page.locator('.lchip')).toBeVisible();
});

test('a row in "Regions compared" opens the quick look (A5, A6)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m&panel=regions&in=stories');
  await page.locator('.ledger__row', { hasText: 'Sahel' }).click();
  await expect(page).toHaveURL(/panel=quick&region=sahel/);
  await expect(page.locator('.quick__headline')).toBeVisible({ timeout: 15000 });
  await page.getByRole('link', { name: 'Full analysis →' }).click();
  await expect(page).toHaveURL(/#\/region\/sahel\?var=t2m/);
  await expect(page.locator('.readout__headline')).toBeVisible();
});

test('the "Show" filter is in the URL and an empty result offers a reset (A3)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m');
  await page.locator('#show-desktop').selectOption('clear_neg');
  await expect(page).toHaveURL(/show=clear_neg/);
  await page.getByRole('button', { name: 'Reset' }).first().click();
  await expect(page).not.toHaveURL(/show=/);
});

test('search finds places and opens their answer (B2)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/');
  const box = page.getByRole('combobox', { name: 'Search places, variables and questions' });
  await box.fill('ukr');
  await expect(page.getByRole('option', { name: /Southern Ukraine/ })).toBeVisible();
  await page.getByRole('option', { name: /^Ukraine/ }).first().click();
  await expect(page).toHaveURL(/panel=quick&region=ukraine/);
});

test('the tour runs end to end and leaves a normal page (B1)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?tour=1');
  for (let i = 1; i <= 3; i++) {
    await expect(page.getByText(`Step ${i} of 4`)).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Next' }).click();
  }
  await expect(page.getByText('Step 4 of 4')).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(page.locator('.tour')).toHaveCount(0);
  await expect(page.locator('.state h2')).toHaveCount(0);
});

test('unknown routes and regions show a way back, not a blank page', async ({ page }) => {
  await page.goto('/#/case/99');
  await expect(page.getByRole('link', { name: 'Back to the map' })).toBeVisible();
  await page.goto('/#/region/atlantis?var=t2m');
  await expect(page.getByRole('link', { name: 'Back to the map' })).toBeVisible();
});

test('open sea: the popup stays inside the map, hides the tooltip and closes with Escape', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m');
  await page.getByRole('button', { name: 'Hide suggestions' }).click();
  const map = page.locator('.explore__map .trend-map__canvas');
  await map.waitFor();
  const box = (await map.boundingBox())!;
  for (const [fx, fy] of [[0.45, 0.6], [0.97, 0.6]]) {
    await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
    const dialog = page.getByRole('dialog', { name: 'No region here' });
    await expect(dialog).toBeVisible();
    const d = (await dialog.boundingBox())!;
    const frame = (await page.locator('.explore').boundingBox())!;
    expect(d.x).toBeGreaterThanOrEqual(frame.x);
    expect(d.x + d.width).toBeLessThanOrEqual(frame.x + frame.width + 1);
    expect(d.y + d.height).toBeLessThanOrEqual(frame.y + frame.height + 1);
    await expect(page.locator('.map-tooltip')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  }
});

test('edge cases render without errors: too little data, gaps, no extremes, no findings', async ({ page }) => {
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
  await page.getByText('Seasons and months').click();
  expect(errors).toEqual([]);
});

test('keyboard: the map canvas is focusable and arrow keys read squares', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m');
  const canvas = page.locator('.explore__map .maplibregl-canvas');
  await canvas.waitFor();
  await canvas.focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.map-tooltip')).toBeVisible();
});

test('a stale cached data file right after a deploy is refetched, not shown as an error', async ({ page }) => {
  let calls = 0;
  await page.route('**/data/index.json', async (route) => {
    const res = await route.fetch();
    const json = await res.json();
    calls += 1;
    if (calls === 1) for (const c of json.cases) delete c.answer; // what an old cached copy looks like
    await route.fulfill({ response: res, json });
  });
  await page.goto('/#/case/01');
  await expect(page.locator('.readout__headline')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.state h2')).toHaveCount(0);
  expect(calls).toBeGreaterThanOrEqual(2);
});

test('countries: clicking a country on the map opens its answer; the ranking lists countries', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m');
  await page.locator('.explore__map .maplibregl-canvas').waitFor();
  await page.waitForFunction(() => Boolean((document.querySelector('.trend-map__canvas') as HTMLElement & { __map?: { getSource: (s: string) => unknown } })?.__map?.getSource('trend')));
  const pt = await page.evaluate(() => {
    const el = document.querySelector('.trend-map__canvas') as HTMLElement & { __map: { project: (c: [number, number]) => { x: number; y: number } } };
    const p = el.__map.project([2.5, 46.5]); // central France
    const b = el.getBoundingClientRect();
    return { x: b.left + p.x, y: b.top + p.y };
  });
  await page.mouse.click(pt.x, pt.y);
  await expect(page).toHaveURL(/panel=quick&region=c_fra/);
  await expect(page.getByRole('dialog', { name: 'France' })).toBeVisible();
  await expect(page.locator('.quick__value')).toBeVisible({ timeout: 15000 });
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Compare the prepared regions' }).click();
  await expect(page.getByRole('dialog', { name: 'Countries ranked' })).toBeVisible();
  expect(await page.locator('.ledger__row').count()).toBeGreaterThan(100);
});

test('world regions and stories are separate sets of places', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=precip&in=world&panel=regions');
  await expect(page.getByRole('dialog', { name: 'World regions ranked' })).toBeVisible();
  expect(await page.locator('.ledger__row').count()).toBeGreaterThan(30);
  await page.goto('/#/?var=precip&in=stories&panel=regions');
  await expect(page.locator('.ledger__row')).toHaveCount(5);
});


test('year by year: the world map and a place record play back without errors', async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto('/#/');
  await page.locator('.explore__map .maplibregl-canvas').waitFor();
  await page.getByRole('button', { name: /Year by year/ }).click();
  const slider = page.getByRole('slider', { name: 'Year' });
  await slider.waitFor({ timeout: 20000 });
  await slider.fill('29');
  await expect(page.locator('.time-player__year')).toHaveText('2010');
  await page.getByRole('button', { name: 'Back to the trend' }).click();
  await expect(page.getByRole('button', { name: /Year by year/ })).toBeVisible();
  await page.goto('/#/region/ukraine?var=t2m');
  await page.locator('.series-chart .main-svg').first().waitFor();
  await page.getByRole('button', { name: /Play this record year by year/ }).click();
  await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
  expect(errors).toEqual([]);
});

/** Screen point of a longitude/latitude on the Explore map. */
async function onMap(page: Page, lon: number, lat: number) {
  return page.evaluate(([x, y]) => {
    const el = document.querySelector('.trend-map__canvas') as HTMLElement & { __map: { project: (c: [number, number]) => { x: number; y: number } } };
    const p = el.__map.project([x, y]);
    const b = el.getBoundingClientRect();
    return { x: b.left + p.x, y: b.top + p.y };
  }, [lon, lat]);
}

async function drag(page: Page, from: [number, number], to: [number, number]) {
  const a = await onMap(page, from[0], from[1]);
  const b = await onMap(page, to[0], to[1]);
  await page.mouse.move(a.x, a.y);
  await page.mouse.down();
  await page.mouse.move((a.x + b.x) / 2, (a.y + b.y) / 2, { steps: 4 });
  await page.mouse.move(b.x, b.y, { steps: 4 });
  await page.mouse.up();
}

test('map views: a season and "compared with the world" are in the URL and in the legend (ADR-011)', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m');
  await page.locator('.explore__map .maplibregl-canvas').waitFor();
  await page.getByLabel('Months').selectOption('mam');
  await expect(page).toHaveURL(/s=mam/);
  await page.getByRole('button', { name: 'Explain the colours' }).click();
  await expect(page.locator('.lchip__more')).toContainText('March to May mean of each year');
  await page.getByLabel('View').selectOption('world');
  await expect(page).toHaveURL(/vs=world/);
  await expect(page.locator('.lchip__word').first()).toHaveText('below the world trend');
  await expect(page.locator('.lchip__more')).toContainText('after subtracting the world average');
  await page.getByRole('button', { name: 'Reset' }).click();
  await expect(page).not.toHaveURL(/s=mam|vs=world/);
  // precipitation has no sound world average (ADR-011): the view is not offered, even from an old link
  await page.goto('/#/?var=precip&vs=world');
  await expect(page.getByLabel('View')).toBeDisabled();
  await expect(page.locator('.lchip__word').first()).toHaveText('drier');
});

test('your own area: draw it, read the answer, compare with a second area (ADR-011)', async ({ page }) => {
  const errors = trackErrors(page);
  await returning(page);
  await page.goto('/#/?var=t2m');
  await page.locator('.explore__map .maplibregl-canvas').waitFor();
  await page.waitForFunction(() => Boolean((document.querySelector('.trend-map__canvas') as HTMLElement & { __map?: { getSource: (s: string) => unknown } })?.__map?.getSource('trend')));
  await page.getByRole('button', { name: 'Draw an area' }).click();
  await expect(page.getByText('Drag on the map to mark your area.')).toBeVisible();
  await drag(page, [-46, 62], [-20, 46]);
  await expect(page).toHaveURL(/panel=area/);
  await expect(page).toHaveURL(/area=-4\d(\.\d)?%2C4\d/);
  const panel = page.getByRole('dialog', { name: 'Your area' });
  await expect(panel).toBeVisible();
  await expect(panel.locator('.quick__value')).toBeVisible({ timeout: 15000 });
  await expect(panel).toContainText('World average');
  await expect(panel.locator('.series-chart .main-svg').first()).toBeVisible({ timeout: 15000 });

  // exact box by keyboard: the number must be the one the Python reference gives for this box
  await panel.getByText('Edit the coordinates').click();
  for (const [name, value] of [['West', '-46'], ['South', '46'], ['East', '-20'], ['North', '62']]) await panel.getByLabel(name).fill(value);
  await panel.getByRole('button', { name: 'Apply' }).click();
  await expect(page).toHaveURL(/area=-46%2C46%2C-20%2C62/);
  await expect(panel.locator('.quick__value')).toHaveText('+0.13');
  await expect(panel.locator('.quick__headline')).toHaveText('No clear trend yet');
  await expect(panel.locator('.area__caution')).toHaveCount(0); // the warning appears only under a clear-looking result

  await panel.getByRole('button', { name: 'Draw a second area' }).click();
  await drag(page, [-75, 44], [-50, 34]);
  await expect(page).toHaveURL(/area2=/);
  await expect(panel).toContainText('Your area minus the second area');
  await panel.getByRole('button', { name: 'Remove' }).click();
  await expect(page).not.toHaveURL(/area2=/);

  // the season of the map is the season of the answer
  await page.getByLabel('Months').selectOption('djf');
  await expect(panel.locator('.panel-side__kicker')).toContainText('Dec–Feb');
  await expect(panel.locator('.panel-side__kicker')).toContainText('1982–2025');
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await expect(page).not.toHaveURL(/area=/);
  expect(errors).toEqual([]);
});

test('your own area: drawing can be cancelled, and a box without data says so', async ({ page }) => {
  await returning(page);
  await page.goto('/#/?var=t2m');
  await page.locator('.explore__map .maplibregl-canvas').waitFor();
  await page.getByRole('button', { name: 'Draw an area' }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByText('Drag on the map to mark your area.')).toHaveCount(0);
  await page.goto('/#/?var=soil&panel=area&area=-40,20,-30,30'); // open Atlantic: no soil
  await expect(page.getByRole('dialog', { name: 'Your area' })).toContainText('There is no complete record of soil wetness inside this area.');
  // a clear-looking result carries the "chosen before looking?" warning; precipitation is not compared with the world
  await page.goto('/#/?var=t2m&panel=area&area=-10,36,40,70');
  const europe = page.getByRole('dialog', { name: 'Your area' });
  await expect(europe.locator('.area__caution')).toBeVisible({ timeout: 15000 });
  await page.goto('/#/?var=precip&panel=area&area=-10,36,40,70');
  await expect(europe).toContainText('not compared with a world average');
});

test('a region page compares the place with the world (ADR-011)', async ({ page }) => {
  await page.goto('/#/region/c_usa?var=t2m');
  const d = page.locator('details.disclosure', { hasText: 'Compared with the world average' });
  await expect(d).toBeVisible({ timeout: 15000 });
  await d.locator('summary').click();
  await expect(d.locator('.vsworld__table tbody tr')).toHaveCount(4);
  await expect(d.locator('.series-chart .main-svg').first()).toBeVisible({ timeout: 15000 });
  await expect(d).toContainText('The world average is the area-weighted mean');
});
