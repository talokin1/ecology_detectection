import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * A year player: index into a list of years, play/pause, stepping, speed. Starts paused; playback
 * never starts by itself (accessibility: prefers-reduced-motion users only move it by hand).
 */
export function usePlayer(count: number, msPerStep = 450) {
  const [index, setIndex] = useState(Math.max(0, count - 1));
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    setIndex((i) => Math.min(Math.max(0, count - 1), i));
  }, [count]);

  useEffect(() => {
    if (!playing || count < 2) return;
    timer.current = window.setInterval(() => {
      setIndex((i) => {
        if (i >= count - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, msPerStep);
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current);
    };
  }, [playing, count, msPerStep]);

  const toggle = useCallback(() => {
    setPlaying((p) => {
      if (!p) setIndex((i) => (i >= count - 1 ? 0 : i)); // replay from the start at the end
      return !p;
    });
  }, [count]);

  return { index, setIndex, playing, setPlaying, toggle };
}
