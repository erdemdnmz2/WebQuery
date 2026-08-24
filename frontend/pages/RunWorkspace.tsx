import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftIcon, PlayIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { api, errorMessage, UnauthorizedError } from '../services/api';
import { useHotkey, useIsMac } from '../lib/hooks';
import { statusMeta } from '../lib/workspace-status';
import { CodeEditor } from '../components/app/CodeEditor';
import { ResultPanel } from '../components/app/ResultPanel';
import { SplitPane } from '../components/app/SplitPane';
import { Badge, Identifier } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { PanelHeader } from '../components/ui/Panel';
import { Skeleton } from '../components/ui/Skeleton';
import { Tooltip } from '../components/ui/Tooltip';
import type { QueryResult, Workspace } from '../types';

/**
 * Read-only run screen for a query an administrator approved and shared. The
 * SQL is shown exactly as approved, so the operator can see what they are
 * about to execute against production.
 */
const RunWorkspace: React.FC = () => {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const isMac = useIsMac();

  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [running, setRunning] = useState(false);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const timer = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .workspace(Number(workspaceId))
      .then((data) => {
        if (!cancelled) setWorkspace(data);
      })
      .catch((caught) => {
        if (cancelled || caught instanceof UnauthorizedError) return;
        setLoadError(errorMessage(caught));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const execute = useCallback(async () => {
    setRunning(true);
    setResult(null);
    timer.current = performance.now();
    try {
      setResult(await api.executeWorkspace(Number(workspaceId)));
    } catch (caught) {
      if (caught instanceof UnauthorizedError) return;
      setResult({ error: errorMessage(caught) });
    } finally {
      setDurationMs(performance.now() - timer.current);
      setRunning(false);
    }
  }, [workspaceId]);

  // The editor binds Mod+Enter itself, so this only covers focus outside it.
  useHotkey('mod+enter', () => void execute(), { enabled: !running && !loading });

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-3 h-80 w-full rounded-md" />
      </div>
    );
  }

  if (!workspace) {
    return (
      <EmptyState
        icon={<WarningCircleIcon size={18} />}
        title="Çalışma alanı açılamadı"
        description={loadError ?? 'Bu kayda erişim yetkiniz olmayabilir.'}
        action={
          <Button icon={<ArrowLeftIcon size={14} />} onClick={() => navigate('/')}>
            Listeye dön
          </Button>
        }
      />
    );
  }

  const meta = statusMeta(workspace.status);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to="/"
            className="mb-1.5 inline-flex items-center gap-1 text-[12.5px] text-subtle hover:text-fg"
          >
            <ArrowLeftIcon size={13} />
            Çalışma alanları
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate">{workspace.name}</h1>
            <Badge tone={meta.tone}>{meta.label}</Badge>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Identifier>{workspace.servername}</Identifier>
            <span aria-hidden className="text-faint">
              /
            </span>
            <Identifier>{workspace.database_name}</Identifier>
            {workspace.description && (
              <span className="ml-1 truncate text-[12.5px] text-subtle">{workspace.description}</span>
            )}
          </div>
        </div>

        <Tooltip content={<span>{isMac ? '⌘' : 'Ctrl'} + Enter</span>}>
          <Button
            variant="primary"
            size="lg"
            icon={<PlayIcon size={13} weight="fill" />}
            loading={running}
            onClick={() => void execute()}
          >
            Sorguyu çalıştır
          </Button>
        </Tooltip>
      </div>

      <SplitPane
        storageKey="webquery.run.split"
        defaultRatio={0.38}
        firstLabel="Sorgu"
        secondLabel="Sonuçlar"
        className="min-h-0 flex-1"
        first={
          <section className="flex min-h-0 w-full flex-col overflow-hidden rounded-md border border-line bg-surface">
            <PanelHeader dense title="Onaylanan sorgu" description="Salt okunur" />
            <div className="min-h-0 flex-1 overflow-hidden rounded-b-md">
              <CodeEditor
                value={workspace.query ?? ''}
                readOnly
                ariaLabel="Onaylanan SQL sorgusu"
                onRun={() => void execute()}
              />
            </div>
          </section>
        }
        second={
          <ResultPanel
            result={result}
            running={running}
            durationMs={durationMs}
            exportBaseName={workspace.name}
            emptyTitle="Sonuç bekleniyor"
            emptyDescription="Onaylanan sorguyu çalıştırdığınızda sonuçlar burada listelenir ve dışa aktarılabilir."
          />
        }
      />
    </div>
  );
};

export default RunWorkspace;
