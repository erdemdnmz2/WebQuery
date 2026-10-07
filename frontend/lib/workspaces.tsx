import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, errorMessage } from '../services/api';
import { UnauthorizedError } from '../services/api';
import { useSession } from './session';
import type { Workspace } from '../types';

interface WorkspacesContextValue {
  workspaces: Workspace[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  /** Applies a local change immediately so lists do not flash while refetching. */
  replace: (next: Workspace[]) => void;
}

const WorkspacesContext = createContext<WorkspacesContextValue | null>(null);

/**
 * A single shared workspace list. The overview, the studio switcher and the
 * command palette all read it, so opening the palette never triggers a
 * duplicate request.
 */
export const WorkspacesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { status } = useSession();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setWorkspaces(await api.workspaces());
    } catch (caught) {
      if (!(caught instanceof UnauthorizedError)) setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (status === 'authenticated') void reload();
    else if (status === 'anonymous') {
      setWorkspaces([]);
      setLoading(false);
    }
  }, [status, reload]);

  const value = useMemo(
    () => ({ workspaces, loading, error, reload, replace: setWorkspaces }),
    [workspaces, loading, error, reload],
  );

  return <WorkspacesContext.Provider value={value}>{children}</WorkspacesContext.Provider>;
};

export function useWorkspaces(): WorkspacesContextValue {
  const ctx = useContext(WorkspacesContext);
  if (!ctx) throw new Error('useWorkspaces must be used inside WorkspacesProvider');
  return ctx;
}
