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
const TEST_LABEL: Record<string, string> = {
  'MK Yue-Wang (default)': 'Mann-Kendall + Yue-Wang (ours)',
  'OLS n_eff': 'Regression, effective n (ours, second test)',
  'MK original': 'Mann-Kendall, no correction',
  'MK Hamed-Rao': 'Mann-Kendall + Hamed-Rao',
};

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
      // draw the grey references first and our test last, on top
      const order = ['MK original', 'MK Hamed-Rao', 'OLS n_eff', OURS].filter((t) => present.has(t));
      const data = order.map((t) => {
        const rows = v.rows.filter((r) => r.test === t && r.n_months === n).sort((p, q) => p.phi - q.phi);
        const ours = t === OURS;
        const second = t === 'OLS n_eff';
        const color = ours ? c.ink : second ? c.text2 : c.lineStrong;
        return {
          type: 'scatter', mode: 'lines+markers', name: TEST_LABEL[t] ?? t,
          x: rows.map((r) => r.phi), y: rows.map((r) => r.false_alarm_rate * 100),
          line: { color, width: ours ? 3 : 2 }, marker: { color, size: ours ? 9 : 7, line: { color: c.bg, width: 2 } },
          hovertemplate: `${TEST_LABEL[t] ?? t}<br>memory φ = %{x}: %{y:.1f}% false alarms<extra></extra>`,
        };
      });
      // direct labels at the line ends, nudged apart so they never overlap
      const ends = order.map((t) => {
        const r = v.rows.filter((x) => x.test === t && x.n_months === n).sort((p, q) => p.phi - q.phi);
        return { t, y: r[r.length - 1].false_alarm_rate * 100, x: r[r.length - 1].phi };
      }).sort((p, q) => p.y - q.y);
      const yMax = Math.max(...v.rows.filter((r) => r.n_months === n).map((r) => r.false_alarm_rate * 100)) * 1.1;
      const gap = yMax / 11;
      ends.forEach((e, i) => { if (i > 0 && e.y - ends[i - 1].y < gap) e.y = ends[i - 1].y + gap; });
      const labels = ends.map((e) => ({
        x: e.x, y: e.y, xanchor: 'left', xshift: 12, showarrow: false, text: e.t === OURS ? `<b>${TEST_LABEL[e.t]}</b>` : TEST_LABEL[e.t] ?? e.t,
        font: { size: 12.5, color: e.t === OURS ? c.text : c.text2 },
      }));
      P.react(node, data, {
        height: 340, margin: { l: 56, r: 280, t: 10, b: 48 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', showlegend: false,
        font: { family: FONT, size: 12, color: c.text2 },
        hoverlabel: { bgcolor: c.bg, bordercolor: c.lineStrong, font: { family: FONT, color: c.text } },
        xaxis: { title: { text: 'How much each month "remembers" the previous one (φ)' }, tickvals: [0, 0.3, 0.6], range: [-0.05, 0.68], showgrid: false, zeroline: false, linecolor: c.lineStrong, ticks: 'outside', tickcolor: c.lineStrong, fixedrange: true },
        yaxis: { title: { text: 'False alarms (%)' }, range: [0, yMax], gridcolor: c.line, zeroline: false, fixedrange: true, ticksuffix: '%' },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 5, y1: 5, line: { color: c.ink, width: 1 } }],
        annotations: [...labels, { x: 0.45, y: 5, yanchor: 'top', yshift: -4, xanchor: 'center', showarrow: false, text: '5%: what an honest test should give', font: { size: 12, color: c.text } }],
      }, { displayModeBar: false, responsive: true });
    });
    return () => {
      alive = false;
    };
  }, [v, n, theme]);
  return <div ref={el} role="img" aria-label={`False-alarm rate of four trend tests for ${n}-month series as month-to-month memory grows.`} />;
}

function Audit({ index }: { index: Index }) {
  const [rows, setRows] = useState<{ id: string; title: string; a: AnalysisResult }[]>([]);
  useEffect(() => {
    Promise.all(index.cases.map((c) => api.analysis(c.region_id, c.variable_id).then((a) => ({ id: c.id, title: c.title, a })))).then(setRows, () => setRows([]));
  }, [index]);
  return (
    <table className="table">
      <thead><tr><th>Case</th><th>Main verdict</th><th className="num">Checks run</th><th className="num">Held up</th><th className="num">Shown as findings</th></tr></thead>
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

const STEPS = [
  ['Average the region', 'We average every grid square inside the outline. Squares near the poles are smaller, so they count less (cos-latitude weights).'],
  ['Remove the seasons', 'January is compared with January, July with July. What is left is the change from normal, called the anomaly.'],
  ['Measure the slope', "Sen's slope: the middle value of the slopes between all pairs of months. A few odd months cannot pull it around."],
  ['Test it, honestly', 'Mann-Kendall test with a correction for month-to-month memory, plus a second, independent regression test.'],
  ['Say it in words', 'The verdict and every finding are written from fixed templates. A finding never sounds stronger than the test behind it.'],
];

const GLOSSARY: [string, string][] = [
  ['Anomaly', 'How much a month differs from its normal: January is compared with January, not with July.'],
  ['Trend', 'A steady, long drift in one direction.'],
  ["Sen's slope", 'The middle value of the slopes between all pairs of points. A few odd months do not shift it.'],
  ['Mann-Kendall test', 'Counts whether later values are larger than earlier ones more often than chance would allow. It looks only at the order, not the sizes.'],
  ['Memory (autocorrelation)', 'Neighbouring months are alike: a dry July often has a dry August. Without correcting for it, a test finds false trends far too often.'],
  ['p-value', 'If there were really no trend, the chance of seeing one this strong or stronger. It is not the chance that the trend is real.'],
  ['Likely range', 'The 95% confidence interval: the range in which the true rate of change most likely lies.'],
  ['False discovery rate', 'Run many tests and a few will look significant by chance. This correction keeps the share of such false findings small.'],
  ['Reanalysis', 'A weather model that is continuously corrected with observations. It has no gaps, but it is not a direct measurement.'],
];

export function MethodsPage() {
  const index = useData(api.index, 'index');
  const val = useData(api.validation, 'validation');
  const [params] = useSearchParams();
  const [n, setN] = useState(240);
  const focus = params.get('s');
  useScreenContext({ variable: 'Methods' }, []);

  useEffect(() => {
    if (!focus || !index.data) return;
    const el = document.getElementById(focus);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        <h1>{S.methods.title}</h1>
        <p className="lead">Every number on this site comes from one open-source analysis pipeline. Here is what it does, why, and how we checked that it does not cry wolf.</p>
      </header>

      <nav className="toc" aria-label="On this page">
        {[['pipeline', 'The five steps'], ['trend-test', 'The trend test'], ['false-alarms', 'Why the correction'], ['verdict-levels', 'Verdict levels'], ['fdr', 'Many checks'], ['limitations', 'Limits'], ['data', 'Data'], ['glossary', 'Glossary']].map(([id, t]) => (
          <a key={id} href={`#/methods?s=${id}`}>{t}</a>
        ))}
      </nav>

      <section id="pipeline" className="msec">
        <h2>The five steps</h2>
        <ol className="steps">
          {STEPS.map(([t, d], i) => (
            <li key={t}><span className="steps__n">{i + 1}</span><strong>{t}</strong><p>{d}</p></li>
          ))}
        </ol>
      </section>

      <section id="trend-test" className="msec">
        <h2>The trend test</h2>
        <p>We measure the rate of change with <strong>Sen's slope</strong> (Sen, 1968) and test it with the <strong>Mann-Kendall test</strong> (Mann, 1945; Kendall, 1975), corrected for month-to-month memory with the <strong>Yue-Wang</strong> method (Yue &amp; Wang, 2004). The slope is reported per decade with a 95% likely range.</p>
        <div className="formula">
          <div>anomaly<sub>t</sub> = value<sub>t</sub> − mean of the same calendar month</div>
          <div>slope = median of (a<sub>j</sub> − a<sub>i</sub>) / (t<sub>j</sub> − t<sub>i</sub>) over all pairs i &lt; j</div>
          <div>Var*(S) = η · Var(S), with η = 1 + 2 Σ<sub>k</sub> (1 − k/n) r<sub>1</sub><sup>k</sup></div>
        </div>
      </section>

      <section id="two-tests" className="msec">
        <h2>Two independent tests</h2>
        <p>As a second opinion we fit an ordinary regression line and judge it with an <strong>effective sample size</strong>, n<sub>eff</sub> = n (1 − r<sub>1</sub>) / (1 + r<sub>1</sub>): 528 similar months can carry as little information as 150 independent ones. If the two tests reach different levels, the card says so and shows the <strong>weaker</strong> verdict.</p>
      </section>

      <section id="false-alarms" className="msec">
        <div className="msec__head">
          <h2>Why the correction matters</h2>
          <div className="segmented" role="tablist" aria-label="Series length">
            {[120, 240, 480].map((m) => (
              <button key={m} type="button" role="tab" aria-selected={n === m} className={n === m ? 'is-active' : ''} onClick={() => setN(m)}>{m / 12} years</button>
            ))}
          </div>
        </div>
        <p>We generated thousands of series that have <strong>no trend at all</strong> but do have month-to-month memory, and counted how often each test still shouted “trend”. An honest test should do so 5% of the time. The classic test does it up to a third of the time; ours stays near 5%.</p>
        {val.data ? <FalseAlarmChart v={val.data} n={n} /> : val.error ? <p className="muted">{val.error.message}</p> : <Loading />}
        {val.data && (
          <details className="table-twin">
            <summary>Show the numbers as a table</summary>
            <table className="table">
              <thead><tr><th>Test</th><th className="num">φ</th><th className="num">False alarms</th><th className="num">Power</th></tr></thead>
              <tbody>
                {val.data.rows.filter((r) => r.n_months === n).map((r) => (
                  <tr key={`${r.test}${r.phi}`}><td>{TEST_LABEL[r.test] ?? r.test}</td><td className="num">{r.phi}</td><td className="num">{(r.false_alarm_rate * 100).toFixed(1)}%</td><td className="num">{(r.power * 100).toFixed(0)}%</td></tr>
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
            {[
              ['strong', 'Strong evidence', 'The 99% likely range of the slope excludes zero (p < 0.01).'],
              ['moderate', 'Evidence', 'The 95% range excludes zero (p < 0.05).'],
              ['weak', 'A hint, not proof', 'The 90% range excludes zero (p < 0.10).'],
              ['none', 'No clear trend yet', 'Otherwise. We still show the slope and how many more years would be needed.'],
              ['insufficient', 'Not enough data to judge', 'Less than 10 years, or less than 80% of months with data.'],
            ].map(([lvl, h, d]) => (
              <tr key={lvl}><td className="levels__scale"><EvidenceScale level={lvl} compact /></td><td><strong>{h}</strong></td><td>{d}</td></tr>
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
        <p>Each season is a series of one value per year (winter = December to February). It gets the same Sen + Mann-Kendall test. We say “winters change twice as fast” only if the fastest season passes the false-discovery filter and its likely range does not overlap the slowest season’s.</p>
      </section>

      <section id="months" className="msec">
        <h2>Months</h2>
        <p>Same idea for each of the 12 calendar months (Hirsch, Slack &amp; Smith, 1982). Twelve tests are many, so each month must pass the false-discovery filter before it can appear in a finding.</p>
      </section>

      <section id="extremes" className="msec">
        <h2>Extreme months</h2>
        <p>A month is “very dry” (or “very hot”) if it is beyond the 10th (or 90th) percentile of 1981–2010. We count such months per year and test the counts for a trend. The threshold is fixed in advance and never tuned.</p>
      </section>

      <section id="fdr" className="msec">
        <h2>Many checks, few findings</h2>
        <p>For each case we run 12 monthly, 4 seasonal and 1 extremes check. Run enough tests and some will look significant by luck, so we apply the Benjamini-Hochberg false-discovery-rate correction (q = 0.10) to the whole family and show only what holds up. The main verdict is not filtered: it is the one question we declared in advance.</p>
        <Audit index={index.data} />
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
        <p>Two trends that look different may still differ by chance. We take the month-by-month difference between the regions and test whether that difference has a trend of its own. Only then do we say “the trends really differ”.</p>
      </section>

      <section id="limitations" className="msec">
        <h2>What this cannot tell you</h2>
        <ul className="bullets">
          <li>It describes change; it does not say what caused it. Words like “because of climate change” are attribution, which we do not do.</li>
          <li>NASA POWER is based on the MERRA-2 reanalysis: a weather model corrected by observations, about 50 km per grid square. It cannot see frost in a valley or a single field.</li>
          <li>The start and end of the period are always the whole record. We never pick a start year that makes a trend look stronger.</li>
          <li>The map uses one value per year per square; regional investigations use monthly data.</li>
        </ul>
      </section>

      <section id="data" className="msec">
        <h2>Data</h2>
        {index.data.synthetic ? (
          <p className="callout"><strong>The numbers currently on this site are synthetic.</strong> They were generated to look like NASA POWER monthly data so that we could build and test the design. The statistics are computed from them with the real pipeline, but they describe no real place. The real NASA data replace them file by file; each file says in its provenance whether it is synthetic.</p>
        ) : null}
        <p>Planned sources: NASA POWER (MERRA-2 meteorology), with satellite records from GES DISC and LP DAAC. Basemap: Natural Earth (public domain), Ukrainian point of view for borders. Statistics: <code>trend_stats.py</code>, open in our repository.</p>
      </section>

      <section id="glossary" className="msec">
        <h2>Glossary</h2>
        <dl className="glossary">
          {GLOSSARY.map(([t, d]) => (
            <div key={t}><dt>{t}</dt><dd>{d}</dd></div>
          ))}
        </dl>
      </section>
    </div>
  );
}
