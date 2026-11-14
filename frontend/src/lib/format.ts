/**
 * Display-only formatting of values that are ALREADY rounded in the JSON (no statistics, no
 * rounding decisions here): fixed decimals as declared by the file, a real minus sign, a plus sign
 * for positive values.
 */
const cache = new Map<number, Intl.NumberFormat>();

export function formatCell(value: number, decimals: number): string {
  let f = cache.get(decimals);
  if (!f) {
    f = new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals, signDisplay: 'exceptZero' });
    cache.set(decimals, f);
  }
  return f.format(value).replace('-', '−');
}
