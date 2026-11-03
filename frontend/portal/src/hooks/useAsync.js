import { useCallback, useEffect, useState } from 'react';

// Runs an async function on mount and exposes loading / error / reload.
export function useAsync(fn) {
  const [state, setState] = useState({ data: null, error: null, loading: true });

  const run = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await fn();
      setState({ data, error: null, loading: false });
      return data;
    } catch (err) {
      setState({ data: null, error: err.message || 'Something went wrong.', loading: false });
      throw err;
    }
  }, [fn]);

  useEffect(() => {
    let active = true;
    Promise.resolve()
      .then(() => fn())
      .then((data) => {
        if (active) setState({ data, error: null, loading: false });
      })
      .catch((err) => {
        if (active) setState({ data: null, error: err.message || 'Something went wrong.', loading: false });
      });
    return () => { active = false; };
  }, [fn]);

  return { ...state, reload: run };
}
