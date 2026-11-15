import { S } from '../strings/en';

/** Play/pause, a year slider and the current year (keyboard: the slider takes arrow keys). */
export function TimePlayer({ years, index, playing, onToggle, onIndex, label }: {
  years: number[]; index: number; playing: boolean; onToggle: () => void; onIndex: (i: number) => void; label: string;
}) {
  const year = years[index];
  return (
    <div className="time-player" role="group" aria-label={label}>
      <button type="button" className="btn btn--primary time-player__play" onClick={onToggle}
        aria-label={playing ? S.time.pause : S.time.play} title={playing ? S.time.pause : S.time.play}>
        {playing ? '❚❚' : '▶'}
      </button>
      <input type="range" className="time-player__slider" min={0} max={years.length - 1} step={1} value={index}
        aria-label={S.time.year} aria-valuetext={String(year)}
        onChange={(e) => onIndex(Number(e.target.value))} />
      <span className="time-player__year" aria-live="off">{year}</span>
    </div>
  );
}
