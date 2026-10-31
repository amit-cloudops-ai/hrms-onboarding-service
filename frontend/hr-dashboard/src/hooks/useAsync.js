import { useCallback, useEffect, useState } from 'react';

// Runs an async function on mount and exposes loading / error / reload.
export function useAsync(fn) {
  const [state, setState] = useState({ data: null, error: null, loading: true });

  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fn();
      setState({ data, error: null, loading: false });
    } catch (err) {
      setState({ data: null, error: err.message || 'Something went wrong.', loading: false });
    }
  }, [fn]);

  useEffect(() => { run(); }, [run]);

  return { ...state, reload: run };
}
