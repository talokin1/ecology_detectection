/** Export helpers. They copy values from the JSON as they are; nothing is recomputed. */
import type { AnalysisResult } from '../data/types.gen';

export function seriesCsv(a: AnalysisResult, variableName: string, regionName: string): string {
  const head = [
    `# ${variableName}, ${regionName}, ${a.period.start} to ${a.period.end}`,
    `# source: ${a.provenance.dataset}${a.provenance.synthetic ? ' (SYNTHETIC DEMO DATA, not a result)' : ''}`,
    `# anomaly: ${a.series.baseline}`,
    `# trend: ${a.trend.display.annotation}; verdict: ${a.verdict.headline}`,
    'month,value,anomaly',
  ];
  const rows = a.series.dates.map((d, i) => `${d},${a.series.raw[i] ?? ''},${a.series.anomaly[i] ?? ''}`);
  return head.concat(rows).join('\n') + '\n';
}

export function download(filename: string, text: string, type = 'text/csv'): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyLink(): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(window.location.href);
    return true;
  } catch {
    return false;
  }
}
