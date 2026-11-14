import { useEffect, useState } from 'react';

export type Loadable<T> = { data: T | undefined; error: Error | undefined; loading: boolean };

/**
 * Runs an async loader whenever `key` changes. Keeps the previous data while the next one
 * loads, so screens do not flash empty between investigations.
 */
export function useData<T>(loader: () => Promise<T>, key: string): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>({ data: undefined, error: undefined, loading: true });
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    loader().then(
      (data) => alive && setState({ data, error: undefined, loading: false }),
      (error: Error) => alive && setState({ data: undefined, error, loading: false }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
