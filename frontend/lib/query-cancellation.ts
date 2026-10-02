import { useRef, useState } from 'react';
import { api, errorMessage } from '../services/api';

/** The original execution response, not the cancel acknowledgement, ends a run. */
export function useQueryCancellation() {
  const active = useRef<string | null>(null);
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [requested, setRequested] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function begin(): string | null {
    if (active.current) return null;
    const id = crypto.randomUUID();
    active.current = id;
    inFlight.current = false;
    setPending(false);
    setRequested(false);
    setError(null);
    return id;
  }

  function finish(id: string) {
    if (active.current !== id) return;
    active.current = null;
    setPending(false);
    setRequested(false);
    setError(null);
  }

  async function cancel() {
    const id = active.current;
    if (!id || inFlight.current || requested) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    try {
      await api.cancelExecution(id);
      if (active.current === id) setRequested(true);
    } catch (caught) {
      if (active.current === id) setError(errorMessage(caught));
    } finally {
      if (active.current === id) {
        inFlight.current = false;
        setPending(false);
      }
    }
  }

  return { begin, finish, cancel, pending, requested, error };
}
