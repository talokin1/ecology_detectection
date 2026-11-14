import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { AnalysisResult, Index, Validation } from '../data/types.gen';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { EvidenceScale } from '../components/VerdictCard';
import { FONT, loadPlotly, themeColors } from '../lib/plotly';
import { useTheme } from '../state/theme';
import { S } from '../strings/en';

const OURS = 'MK Yue-Wang (default)';
const M = S.methods;

function FalseAlarmChart({ v, n }: { v: Validation; n: number }) {
  const el = useRef<HTMLDivElement>(null);
  const theme = useTheme();
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    let alive = true;
    loadPlotly().then((P) => {
      if (!alive) return;
      const c = themeColors();
      const present = new Set(v.rows.map((r) => r.test));
      // grey references first, our test last (on top)
      const order = ['MK original', 'MK Hamed-Rao', 'OLS n_eff', OURS].filter((t) => present.has(t));
      const rowsOf = (t: string) => v.rows.filter((r) => r.test === t && r.n_months === n).sort((p, q) => p.phi - q.phi);
      const data = order.map((t) => {
        const rows = rowsOf(t);
        const ours = t === OURS;
        const color = ours ? c.ink : t === 'OLS n_eff' ? c.text2 : c.lineStrong;
        return {
          type: 'scatter', mode: 'lines+markers', name: M.tests[t] ?? t,
          x: rows.map((r) => r.phi), y: rows.map((r) => r.false_alarm_rate * 100),
          line: { color, width: ours ? 3 : 2 }, marker: { color, size: ours ? 9 : 7, line: { color: c.bg, width: 2 } },
          hovertemplate: rows.map((r) => `${M.tests[t] ?? t}<br>φ = ${r.phi}: ${r.false_alarm_text} false alarms<extra></extra>`),
        };
      });
      // direct labels at the line ends, nudged apart so they never overlap
      const yMax = Math.max(...v.rows.filter((r) => r.n_months === n).map((r) => r.false_alarm_rate * 100)) * 1.1;
      const ends = order.map((t) => {
        const r = rowsOf(t);
        return { t, x: r[r.length - 1].phi, y: r[r.length - 1].false_alarm_rate * 100 };
      }).sort((p, q) => p.y - q.y);
      ends.forEach((e, i) => { if (i > 0 && e.y - ends[i - 1].y < yMax / 11) e.y = ends[i - 1].y + yMax / 11; });
      const labels = ends.map((e) => ({
        x: e.x, y: e.y, xanchor: 'left', xshift: 12, showarrow: false, text: e.t === OURS ? `<b>${M.tests[e.t]}</b>` : M.tests[e.t] ?? e.t,
        font: { size: 12.5, color: e.t === OURS ? c.text : c.text2 },
      }));
      const narrow = node.clientWidth < 640;
      P.react(node, data, {
        height: narrow ? 420 : 340, margin: { l: 56, r: narrow ? 16 : 290, t: 10, b: narrow ? 130 : 48 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', showlegend: narrow,
        legend: { orientation: 'h', y: -0.35, font: { size: 12 } },
        font: { family: FONT, size: 12, color: c.text2 },
        hoverlabel: { bgcolor: c.bg, bordercolor: c.lineStrong, font: { family: FONT, color: c.text } },
        xaxis: { title: { text: M.xTitle }, tickvals: [0, 0.3, 0.6], range: [-0.05, 0.68], showgrid: false, zeroline: false, linecolor: c.lineStrong, ticks: 'outside', tickcolor: c.lineStrong, fixedrange: true },
        yaxis: { title: { text: M.yTitle }, range: [0, yMax], gridcolor: c.line, zeroline: false, fixedrange: true, ticksuffix: '%' },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 5, y1: 5, line: { color: c.ink, width: 1 } }],
        annotations: [...(narrow ? [] : labels), { x: 0.45, y: 5, yanchor: 'top', yshift: -4, xanchor: 'center', showarrow: false, text: M.honest, font: { size: 12, color: c.text } }],
      }, { displayModeBar: false, responsive: true });
    });
    return () => {
      alive = false;
    };
  }, [v, n, theme]);
  return <div ref={el} role="img" aria-label={`False-alarm rate of four trend tests for ${n}-month series as month-to-month memory grows. ${v.summary}`} />;
}

function Audit({ index }: { index: Index }) {
  const [rows, setRows] = useState<{ id: string; title: string; a: AnalysisResult }[]>([]);
  useEffect(() => {
    Promise.all(index.cases.map((c) => api.analysis(c.region_id, c.variable_id).then((a) => ({ id: c.id, title: c.title, a })))).then(setRows, () => setRows([]));
  }, [index]);
  return (
    <table className="table">
      <thead><tr>{M.auditHead.map((h, i) => <th key={h} className={i > 1 ? 'num' : ''}>{h}</th>)}</tr></thead>
      <tbody>
        {rows.map(({ id, title, a }) => (
          <tr key={id}>
            <td><Link to={`/case/${id}`}>{id} · {title}</Link></td>
            <td>{a.verdict.headline}</td>
            <td className="num">{a.insights_audit.tested}</td>
            <td className="num">{a.insights_audit.passed}</td>
            <td className="num">{a.insights_audit.shown}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MethodsPage() {
  const index = useData(api.index, 'index');
  const val = useData(api.validation, 'validation');
  const [params] = useSearchParams();
  const [n, setN] = useState(240);
  const focus = params.get('s');
  useScreenContext({ variable: S.nav.methods }, []);

  useEffect(() => {
    if (!focus || !index.data) return;
    const el = document.getElementById(focus);
    if (el) {
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      el.classList.add('is-focus');
      const t = setTimeout(() => el.classList.remove('is-focus'), 2200);
      return () => clearTimeout(t);
    }
  }, [focus, index.data]);

  if (index.error) return <ErrorState error={index.error} />;
  if (!index.data) return <Loading />;

  return (
    <div className="page methods">
      <header className="page__header">
        <h1>{M.title}</h1>
        <p className="lead">{M.lead}</p>
      </header>

      <nav className="toc" aria-label="On this page">
        {M.toc.map(([id, t]) => <Link key={id} to={`/methods?s=${id}`}>{t}</Link>)}
      </nav>

      <section id="pipeline" className="msec">
        <h2>The five steps</h2>
        <ol className="steps">
          {M.steps.map(([t, d], i) => (
            <li key={t}><span className="steps__n">{String(i + 1).padStart(2, '0')}</span><strong>{t}</strong><p>{d}</p></li>
          ))}
        </ol>
      </section>

      <section id="trend-test" className="msec">
        <h2>The trend test</h2>
        <p>We measure the rate of change with <strong>Sen's slope</strong> (Sen, 1968) and test it with the <strong>Mann-Kendall test</strong> (Mann, 1945; Kendall, 1975), corrected for month-to-month memory with the <strong>Yue-Wang</strong> method (Yue &amp; Wang, 2004). The slope is reported per decade with its 95% range.</p>
        <div className="formula">
          <div>anomaly<sub>t</sub> = value<sub>t</sub> − mean of the same calendar month</div>
          <div>slope = median of (a<sub>j</sub> − a<sub>i</sub>) / (t<sub>j</sub> − t<sub>i</sub>) over all pairs i &lt; j</div>
          <div>Var*(S) = η · Var(S), with η = 1 + 2 Σ<sub>k</sub> (1 − k/n) r<sub>1</sub><sup>k</sup></div>
        </div>
      </section>

      <section id="two-tests" className="msec">
        <h2>Two independent tests</h2>
        <p>As a second opinion we fit an ordinary regression line and judge it with an <strong>effective sample size</strong>, n<sub>eff</sub> = n (1 − r<sub>1</sub>) / (1 + r<sub>1</sub>): hundreds of similar months can carry the information of far fewer independent ones (for soil wetness, often fewer than 50). If the two tests reach different levels, the page shows both p-values and reports the <strong>weaker</strong> verdict.</p>
        <p><strong>Is the verdict borderline?</strong> For every region and variable we repeat the verdict rule three more ways, chosen in advance: without the first two years, without the last two years, and on one average per year (fewer, more independent points). The headline verdict never changes, but if any of the three disagrees, the “How sure?” line says “Borderline” and names it.</p>
        <p><strong>Rounding.</strong> Ranges are rounded outwards (the lower bound down, the upper bound up), so a printed range is never narrower than the computed one. The exact values are in the downloadable files.</p>
      </section>

      <section id="false-alarms" className="msec">
        <div className="msec__head">
          <h2>{M.falseAlarmsTitle}</h2>
          <div className="segmented" role="group" aria-label="Series length">
            {[120, 240, 480].map((m) => (
              <button key={m} type="button" aria-pressed={n === m} className={n === m ? 'is-active' : ''} onClick={() => setN(m)}>{M.years(m)}</button>
            ))}
          </div>
        </div>
        <p>{M.falseAlarmsBody} {val.data?.summary}</p>
        {val.data ? <FalseAlarmChart v={val.data} n={n} /> : val.error ? <p className="muted">{val.error.message}</p> : <Loading />}
        {val.data && (
          <details className="table-twin">
            <summary>{M.tableToggle}</summary>
            <table className="table">
              <thead><tr>{M.tableHead.map((h, i) => <th key={h} className={i ? 'num' : ''}>{h}</th>)}</tr></thead>
              <tbody>
                {val.data.rows.filter((r) => r.n_months === n).map((r) => (
                  <tr key={`${r.test}${r.phi}`}><td>{M.tests[r.test] ?? r.test}</td><td className="num">{r.phi}</td><td className="num">{r.false_alarm_text}</td><td className="num">{r.power_text}</td></tr>
                ))}
              </tbody>
            </table>
            <p className="help">{val.data.runs} simulated series per cell, α = {val.data.alpha}. Power: how often the test finds a real trend of 0.06 noise-units per year. Source: {val.data.source}.</p>
          </details>
        )}
      </section>

      <section id="verdict-levels" className="msec">
        <h2>Verdict levels</h2>
        <table className="table levels">
          <tbody>
            {M.levels.map(([lvl, h, d]) => (
              <tr key={lvl}><td className="levels__scale"><EvidenceScale level={lvl} /></td><td><strong>{h}</strong></td><td>{d}</td></tr>
            ))}
          </tbody>
        </table>
      </section>

      <section id="years-to-detect" className="msec">
        <h2>“How many more years?”</h2>
        <p>When there is no clear trend yet, we estimate how many years of data a trend of this size would need to be detected 9 times out of 10, given the noise and memory of the series (Weatherhead et al., 1998). The estimate is rough, so we round it to 5 years and say “if the current rate held”.</p>
      </section>

      <section id="signal-noise" className="msec">
        <h2>Bigger than a normal swing</h2>
        <p>We compare the total change along the trend with the typical year-to-year swing (the spread of yearly averages around the trend). The year from which the change stays bigger than that swing is the <em>time of emergence</em> (Hawkins &amp; Sutton, 2012). Shown only when the verdict is at least “Evidence”.</p>
      </section>

      <section id="seasons" className="msec">
        <h2>Seasons</h2>
        <p>Each season is a series of one value per year (winter = December to February) and gets the same Sen and Mann-Kendall test. We say one season changes faster only if it passes the false-discovery filter and its 95% range does not overlap the slowest season’s. Otherwise we name the fastest season and say plainly that we cannot yet tell it apart.</p>
      </section>

      <section id="months" className="msec">
        <h2>Months</h2>
        <p>Same idea for each of the 12 calendar months (Hirsch, Slack &amp; Smith, 1982). Twelve tests are many, so each month must pass the false-discovery filter before it can appear in a finding. The bars show 95% ranges, matching the filter level.</p>
      </section>

      <section id="extremes" className="msec">
        <h2>Extreme months</h2>
        <p>A month is “very dry” (or “very hot”) if it is beyond the 10th (or 90th) percentile of 1981–2010. We count such months per year and test the counts for a trend. The threshold is fixed in advance and never tuned.</p>
      </section>

      <section id="fdr" className="msec">
        <h2>Many checks, few findings</h2>
        <p>Besides the main test, each investigation runs 17 follow-up checks: 12 months, 4 seasons and extreme months. Run enough tests and some will look significant by luck, so we apply the Benjamini-Hochberg false-discovery-rate correction (q = 0.05, the same level as the maps) to the whole family. Only findings marked “Follow-up check” come from this family. The main verdict is not filtered: it is the one question we declared in advance.</p>
        <Audit index={index.data} />
      </section>

      <section id="deeper" className="msec">
        <h2>Deeper checks</h2>
        <p>Each investigation also shows results from the team's second statistics pipeline (<code>trend_detective.climate_stats</code>), run on the same NASA POWER record. From daily highs, lows and rain it counts events people notice: summer days above 25 °C, frost nights, the hottest day and coldest night of the year, the growing season, the last spring frost, the wettest day and the longest dry spell. It also computes two drought indices for the summer (June–August and March–August): SPI uses rain only, SPEI uses rain minus the water warm air can draw from the ground (Hargreaves evaporative demand). If SPEI falls while SPI does not, heat rather than missing rain is drying the land.</p>
        <p>Four checks test the main trend in other ways: a block bootstrap of the rate (whole years resampled 999 times), a comparison of the two halves of the record (split fixed in advance at the calendar midpoint), a comparison of year-to-year swings in the two halves, and the Pettitt test for a single sudden jump.</p>
        <p>The rows to show were chosen by what each variable is about, before looking at the results, and every row is shown whether or not it changed. A row says “Clear change” only if both of the pipeline's tests (Mann-Kendall with memory correction and regression with effective sample size) pass after the Benjamini-Hochberg correction over every test run for that region (q = 0.05). Daily data are in our frozen copy only for the four European regions, so some rows are not available for the Sahel. The full output of the pipeline for each region can be downloaded as JSON from the investigation page.</p>
      </section>

      <section id="neighbour" className="msec">
        <h2>The neighbour hint</h2>
        <p>For each investigation we look for the nearest prepared region (within 3,000 km) where the same variable has at least “Evidence” of a trend in the other direction.</p>
      </section>

      <section id="sign-split" className="msec">
        <h2>When the average hides a contrast</h2>
        <p>If at least 15% of a region’s area has a significant trend of the opposite sign on the map, we warn that the regional average hides a contrast.</p>
      </section>

      <section id="compare" className="msec">
        <h2>Comparing two regions</h2>
        <p>{S.compare.explain}</p>
      </section>

      <section id="limitations" className="msec">
        <h2>What this cannot tell you</h2>
        <ul className="bullets">
          <li>It describes change; it does not say what caused it. Words like “because of climate change” are attribution, which we do not do.</li>
          <li>NASA POWER is based on the MERRA-2 reanalysis: a weather model corrected by observations, about 50 km per grid square. It cannot see frost in a valley or a single field. The world map averages it into 2° squares (about 220 km).</li>
          <li>The trend is a straight line through the whole record. We never pick a start year that makes a trend look stronger.</li>
          <li>The map uses one value per year per square; regional investigations use monthly data.</li>
          <li>The world map uses Web Mercator, which enlarges areas near the poles.</li>
          <li>GRACE water storage has a real resolution of about 300 km (3°). Two ways of cutting a region out of it (cells chosen by their centre with JPL’s land mask, or cells weighted by how much of them overlaps the region) give regional trends about 4% apart. That is within the product’s own uncertainty; we use the first and keep the second as a cross-check. GRACE also has an 11-month gap between missions (July 2017 to May 2018), which every GRACE file states.</li>
        </ul>
      </section>

      <section id="data" className="msec">
        <h2>Data</h2>
        <p>All numbers on this site come from NASA POWER, version 10 (MERRA-2 reanalysis): monthly air temperature at 2 m (T2M), precipitation (PRECTOTCORR) and root-zone soil wetness (GWETROOT), and daily highs, lows and precipitation for the deeper checks. We read them from the POWER archive on AWS Open Data on 14–15 November 2026 and keep a frozen copy in our repository; every file has a checksum and a provenance record, and a check refuses any change. Regional values are averages of the land grid squares (about 50 km) whose centre lies inside the region, weighted by cos(latitude). The European regions follow real borders from Natural Earth: Ukraine with Crimea; southern Ukraine as the Odesa, Mykolaiv, Kherson and Zaporizhzhia oblasts, Crimea and Sevastopol; northern Europe as Norway, Sweden, Finland, Denmark and the Baltic states; southern Europe as Portugal, Spain, Italy, Malta, Greece, the western Balkans (Kosovo as part of Serbia in our border file) and Bulgaria. The Sahel is a climate belt, not a country, so it is a box (10–18°N, 15°W–35°E). Every investigation uses whole calendar years, from January 1981 to the last year complete in every file. Basemap: Natural Earth (public domain), Ukrainian point of view for borders. Statistics: <code>trend_stats.py</code> and <code>trend_detective.climate_stats</code>, open in our repository.</p>
      </section>

      <section id="glossary" className="msec">
        <h2>Glossary</h2>
        <dl className="glossary">
          {M.glossary.map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}
        </dl>
      </section>
    </div>
  );
}
