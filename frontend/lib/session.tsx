import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import type { User } from '../types';

type SessionStatus = 'loading' | 'authenticated' | 'anonymous';

interface SessionContextValue {
  user: User | null;
  status: SessionStatus;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

/**
 * Holds the signed-in user for the whole app so every screen does not repeat
 * the /api/me round trip, and so a 401 anywhere resolves to one redirect.
 */
export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<SessionStatus>('loading');

  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
      setStatus('authenticated');
    } catch {
      setUser(null);
      setStatus('anonymous');
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* The cookie may already be gone; clear local state either way. */
    }
    setUser(null);
    setStatus('anonymous');
  }, []);

  const value = useMemo(() => ({ user, status, refresh, signOut }), [user, status, refresh, signOut]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}
