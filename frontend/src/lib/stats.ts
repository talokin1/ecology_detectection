/**
 * Trend test for one value per year, used only by the "your own area" tool (an area the visitor
 * draws cannot be precomputed). It is a line-by-line port of the project's reference code,
 * `.claude/skills/trend-stats/scripts/trend_stats.py` (sens_slope, mann_kendall with the Yue-Wang
 * correction, ols_trend with the lag-1 effective sample size), combined exactly as
 * `yearly_level` in `scripts/make_app_data.py`. `stats.test.ts` checks it against values produced
 * by that Python code (`scripts/area_stats.py --fixture`). Do not change one without the other.
 */

export type Level = 'strong' | 'moderate' | 'weak' | 'none' | 'insufficient';
const RANK: Record<Level, number> = { insufficient: -1, none: 0, weak: 1, moderate: 2, strong: 3 };
export const weaker = (a: Level, b: Level): Level => (RANK[a] <= RANK[b] ? a : b);

/** Two-sided normal quantiles for alpha = 0.10, 0.05, 0.01 (scipy.stats.norm.ppf(1 - alpha / 2)). */
const Z = { 90: 1.6448536269514722, 95: 1.959963984540054, 99: 2.5758293035489004 };

// --------------------------------------------------------------------------- special functions
function lgamma(x: number): number {
  // Lanczos approximation (g = 7, n = 9), accurate to about 1e-15 for x > 0
  const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
    12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  if (x < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * x)) - lgamma(1 - x);
  const y = x - 1;
  let a = c[0];
  const t = y + 7.5;
  for (let i = 1; i < 9; i++) a += c[i] / (y + i);
  return 0.5 * Math.log(2 * Math.PI) + (y + 0.5) * Math.log(t) - t + Math.log(a);
}

/** Regularised upper incomplete gamma function Q(a, x). */
function gammaQ(a: number, x: number): number {
  if (x <= 0) return 1;
  const lead = Math.exp(-x + a * Math.log(x) - lgamma(a));
  if (x < a + 1) {
    let sum = 1 / a;
    let term = sum;
    for (let n = 1; n < 500; n++) {
      term *= x / (a + n);
      sum += term;
      if (Math.abs(term) < Math.abs(sum) * 1e-16) break;
    }
    return 1 - sum * lead;
  }
  const tiny = 1e-300;
  let b = x + 1 - a;
  let c = 1 / tiny;
  let d = 1 / b;
  let h = d;
  for (let i = 1; i < 500; i++) {
    const an = -i * (i - a);
    b += 2;
    d = an * d + b;
    if (Math.abs(d) < tiny) d = tiny;
    c = b + an / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < 1e-16) break;
  }
  return lead * h;
}

/** Two-sided normal p-value: 2 * norm.sf(|z|) = erfc(|z| / sqrt 2). */
export function normalTwoSided(z: number): number {
  return gammaQ(0.5, (z * z) / 2);
}

/** Regularised incomplete beta function I_x(a, b) (continued fraction, modified Lentz). */
function betaInc(a: number, b: number, x: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const front = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  if (x > (a + 1) / (a + b + 2)) return 1 - betaInc(b, a, 1 - x);
  const tiny = 1e-300;
  let c = 1;
  let d = 1 - ((a + b) * x) / (a + 1);
  if (Math.abs(d) < tiny) d = tiny;
  d = 1 / d;
  let h = d;
  for (let m = 1; m < 500; m++) {
    const m2 = 2 * m;
    let aa = (m * (b - m) * x) / ((a + m2 - 1) * (a + m2));
    d = 1 + aa * d;
    if (Math.abs(d) < tiny) d = tiny;
    c = 1 + aa / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1 / d;
    h *= d * c;
    aa = (-(a + m) * (a + b + m) * x) / ((a + m2) * (a + m2 + 1));
    d = 1 + aa * d;
    if (Math.abs(d) < tiny) d = tiny;
    c = 1 + aa / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < 1e-16) break;
  }
  return (front * h) / a;
}

/** Two-sided Student-t p-value: 2 * t.sf(|t|, dof), dof may be fractional. */
export function studentTwoSided(t: number, dof: number): number {
  if (!Number.isFinite(t)) return 0;
  return betaInc(dof / 2, 0.5, dof / (dof + t * t));
}

// --------------------------------------------------------------------------- building blocks
const mean = (a: number[]) => a.reduce((s, v) => s + v, 0) / a.length;

function median(sorted: number[]): number {
  const n = sorted.length;
  return n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
}

/** Lag-1 autocorrelation (trend_stats.lag1_autocorr). */
export function lag1(x: number[]): number {
  if (x.length < 3) return NaN;
  const m = mean(x);
  let num = 0;
  let den = 0;
  for (let i = 0; i < x.length; i++) {
    const a = x[i] - m;
    den += a * a;
    if (i < x.length - 1) num += a * (x[i + 1] - m);
  }
  return den > 0 ? num / den : NaN;
}

function mkS(y: number[]): number {
  let s = 0;
  for (let i = 0; i < y.length - 1; i++) for (let j = i + 1; j < y.length; j++) s += Math.sign(y[j] - y[i]);
  return s;
}

/** Variance of S with the tie term (trend_stats._mk_var). */
function mkVar(y: number[]): number {
  const n = y.length;
  const counts = new Map<number, number>();
  y.forEach((v) => counts.set(v, (counts.get(v) ?? 0) + 1));
  let ties = 0;
  counts.forEach((c) => {
    if (c > 1) ties += c * (c - 1) * (2 * c + 5);
  });
  return (n * (n - 1) * (2 * n + 5) - ties) / 18;
}

function sortedSlopes(t: number[], y: number[]): number[] {
  const out: number[] = [];
  for (let i = 0; i < t.length - 1; i++) {
    for (let j = i + 1; j < t.length; j++) {
      const dt = t[j] - t[i];
      if (dt !== 0) out.push((y[j] - y[i]) / dt);
    }
  }
  return out.sort((a, b) => a - b);
}

/** np.interp(rank, 1..N, slopes): linear between ranks, clamped at both ends. */
function atRank(slopes: number[], rank: number): number {
  const n = slopes.length;
  if (rank <= 1) return slopes[0];
  if (rank >= n) return slopes[n - 1];
  const lo = Math.floor(rank);
  return slopes[lo - 1] + (rank - lo) * (slopes[lo] - slopes[lo - 1]);
}

type Sen = { slope: number; intercept: number; slopes: number[] };
function sen(t: number[], y: number[]): Sen {
  const slopes = sortedSlopes(t, y);
  const slope = median(slopes);
  const intercept = median(y.map((v, i) => v - slope * t[i]).sort((a, b) => a - b));
  return { slope, intercept, slopes };
}

function senCi(s: Sen, z: number, varS: number): [number, number] {
  const c = z * Math.sqrt(varS);
  const N = s.slopes.length;
  return [atRank(s.slopes, (N - c) / 2), atRank(s.slopes, (N + c) / 2 + 1)];
}

/** Mann-Kendall with the Yue-Wang variance correction (trend_stats.mann_kendall, method="yue_wang"). */
function mannKendall(t: number[], y: number[], s0: Sen) {
  const n = y.length;
  const s = mkS(y);
  let r1 = lag1(y.map((v, i) => v - s0.slope * t[i]));
  r1 = Number.isFinite(r1) ? Math.max(0, r1) : 0;
  let sum = 0;
  for (let k = 1; k < n; k++) sum += (1 - k / n) * r1 ** k;
  const correction = 1 + 2 * sum;
  const varS = mkVar(y) * correction;
  const z = s > 0 ? (s - 1) / Math.sqrt(varS) : s < 0 ? (s + 1) / Math.sqrt(varS) : 0;
  return { s, varS, z, p: normalTwoSided(z), correction };
}

/** OLS slope and t-test with the lag-1 effective sample size (trend_stats.ols_trend). */
function ols(t: number[], y: number[]) {
  const n = t.length;
  const tm = mean(t);
  const ym = mean(y);
  let sxx = 0;
  let sxy = 0;
  for (let i = 0; i < n; i++) {
    sxx += (t[i] - tm) ** 2;
    sxy += (t[i] - tm) * (y[i] - ym);
  }
  const b = sxy / sxx;
  const a = ym - b * tm;
  const resid = y.map((v, i) => v - (a + b * t[i]));
  const r1 = lag1(resid);
  let nEff = n;
  if (Number.isFinite(r1) && r1 > 0) nEff = Math.max(3, (n * (1 - r1)) / (1 + r1));
  const dof = nEff - 2;
  const se = Math.sqrt(resid.reduce((s, v) => s + v * v, 0) / dof) / Math.sqrt(sxx);
  const tStat = se > 0 ? b / se : Infinity;
  return { slope: b, p: studentTwoSided(tStat, dof), nEff, r1 };
}

const excludesZero = (ci: [number, number]) => (ci[0] > 0 && ci[1] > 0) || (ci[0] < 0 && ci[1] < 0);
const levelFromP = (p: number): Level => (p < 0.01 ? 'strong' : p < 0.05 ? 'moderate' : p < 0.1 ? 'weak' : 'none');
const isLeap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
/** Decimal year of 1 July, as trend_stats.decimal_years gives for the yearly values. */
const midYear = (y: number) => y + (isLeap(y) ? 182 / 366 : 181 / 365);

export type YearlyTrend = {
  n: number;
  /** Sen's slope per decade and its ranges (Mann-Kendall variance with the Yue-Wang correction). */
  perDecade: number;
  ci90: [number, number];
  ci95: [number, number];
  ci99: [number, number];
  /** Sen line: value = intercept + slopePerYear * year. */
  intercept: number;
  slopePerYear: number;
  pMk: number;
  pOls: number;
  olsPerDecade: number;
  /** The app's verdict rule for yearly values: the weaker of the two tests. */
  level: Level;
};

export const MIN_YEARS = 10;

/** Trend of one value per year. `years` must be whole years in ascending order. */
export function yearlyTrend(years: number[], values: number[]): YearlyTrend | null {
  const n = years.length;
  if (n < 4 || values.some((v) => !Number.isFinite(v)) || values.every((v) => v === values[0])) return null;
  const s0 = sen(years, values);
  const mk = mannKendall(years, values, s0);
  const ci = (z: number) => senCi(s0, z, mk.varS).map((c) => c * 10) as [number, number];
  const ci90 = ci(Z[90]);
  const ci95 = ci(Z[95]);
  const ci99 = ci(Z[99]);
  const o = ols(years.map(midYear), values);
  const fromCi: Level = excludesZero(ci99) ? 'strong' : excludesZero(ci95) ? 'moderate' : excludesZero(ci90) ? 'weak' : 'none';
  const level = n < MIN_YEARS ? 'insufficient' : weaker(fromCi, levelFromP(o.p));
  return {
    n, perDecade: s0.slope * 10, ci90, ci95, ci99, intercept: s0.intercept, slopePerYear: s0.slope,
    pMk: mk.p, pOls: o.p, olsPerDecade: o.slope * 10, level,
  };
}
