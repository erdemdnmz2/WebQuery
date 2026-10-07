import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  DatabaseIcon,
  EraserIcon,
  FloppyDiskIcon,
  HardDrivesIcon,
  LockKeyIcon,
  PlayIcon,
  PlusIcon,
  WarningCircleIcon,
  XIcon,
} from '@phosphor-icons/react';
import { api, errorMessage, UnauthorizedError } from '../services/api';
import { cn } from '../lib/cn';
import { useHotkey, useIsMac } from '../lib/hooks';
import { useQueryCancellation } from '../lib/query-cancellation';
import { QueryCancelControl } from '../components/app/QueryCancelControl';
import { useWorkspaces } from '../lib/workspaces';
import { isEditable, statusMeta } from '../lib/workspace-status';
import { outcomeFromError, outcomeFromResponse, type ExecutionOutcome } from '../lib/execution';
import { capabilityMeta } from '../lib/capability';
import { databasesOf, findTarget, listTargets, resolveUuid, serverNames, technologyOf } from '../lib/targets';
import { CodeEditor } from '../components/app/CodeEditor';
import { ResultPanel } from '../components/app/ResultPanel';
import { SplitPane } from '../components/app/SplitPane';
import { Badge, Identifier } from '../components/ui/Badge';
import { Button, IconButton } from '../components/ui/Button';
import { Dialog } from '../components/ui/Dialog';
import { Field } from '../components/ui/Field';
import { Input, Textarea } from '../components/ui/Input';
import { Kbd } from '../components/ui/Kbd';
import { PanelHeader } from '../components/ui/Panel';
import { Picker, type PickerItem } from '../components/ui/Picker';
import { Tooltip } from '../components/ui/Tooltip';
import { useToast } from '../components/ui/Toast';
import type { DatabaseInfo, Workspace } from '../types';

const STARTER_QUERY = 'SELECT TOP 100 *\nFROM ';

const Studio: React.FC = () => {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const isMac = useIsMac();
  const { workspaces, reload } = useWorkspaces();

  const [query, setQuery] = useState(STARTER_QUERY);
  const [servers, setServers] = useState<DatabaseInfo>({});
  const [targetsLoaded, setTargetsLoaded] = useState(false);
  const [server, setServer] = useState('');
  /* The API addresses a database by uuid; the names are for the reader. */
  const [dbUuid, setDbUuid] = useState('');

  const [current, setCurrent] = useState<Workspace | null>(null);
  const [savedQuery, setSavedQuery] = useState<string | null>(null);

  const [outcome, setOutcome] = useState<ExecutionOutcome | null>(null);
  const [running, setRunning] = useState(false);
  const cancellation = useQueryCancellation();
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);

  const [persistentMasked, setPersistentMasked] = useState<string[]>([]);
  const [adHocMasked, setAdHocMasked] = useState<string[]>([]);
  const [maskingOpen, setMaskingOpen] = useState(false);
  const [newMaskColumn, setNewMaskColumn] = useState('');

  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDescription, setSaveDescription] = useState('');
  const [saving, setSaving] = useState(false);

  const runTimer = useRef<number>(0);

  const target = useMemo(() => findTarget(servers, dbUuid), [servers, dbUuid]);
  const database = target?.databaseName ?? '';
  const technology = technologyOf(servers, server);
  const editable = current === null || isEditable(current.status);
  const maskedCount = persistentMasked.length + adHocMasked.length;
  const dirty = current !== null && savedQuery !== null && savedQuery !== query;
  const noGrants = targetsLoaded && listTargets(servers).length === 0;
  /* A saved workspace can point at a database the user no longer holds. */
  const targetUnavailable = targetsLoaded && current !== null && dbUuid === '';

  /* ---------------------------------------------------------------- data */

  useEffect(() => {
    let cancelled = false;
    api
      .databaseInformation()
      .then((info) => {
        if (cancelled) return;
        setServers(info);
        setTargetsLoaded(true);
      })
      .catch((caught) => {
        if (cancelled) return;
        setTargetsLoaded(true);
        if (!(caught instanceof UnauthorizedError)) {
          toast.error("Could not load connections", errorMessage(caught));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [toast]);

  useEffect(() => {
    if (!workspaceId) {
      setCurrent(null);
      setSavedQuery(null);
      return;
    }
    let cancelled = false;
    setLoadingWorkspace(true);
    api
      .workspace(Number(workspaceId))
      .then((workspace) => {
        if (cancelled) return;
        setCurrent(workspace);
        setQuery(workspace.query);
        setSavedQuery(workspace.query);
        setServer(workspace.servername);
        setOutcome(null);
      })
      .catch((caught) => {
        if (cancelled || caught instanceof UnauthorizedError) return;
        toast.error("Could not open workspace", errorMessage(caught));
        navigate('/');
      })
      .finally(() => {
        if (!cancelled) setLoadingWorkspace(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, navigate, toast]);

  /*
   * Point the editor at the workspace's own database. The backend resolves
   * db_uuid by name and returns an empty string when the registration moved,
   * so the names are the fallback. The target is never silently swapped for a
   * different one: an unresolvable target stays empty and is reported.
   */
  useEffect(() => {
    if (!current) return;
    setDbUuid(current.db_uuid || resolveUuid(servers, current.servername, current.database_name));
  }, [current, servers]);

  /* A fresh query starts on the first grant the user actually holds. */
  useEffect(() => {
    if (workspaceId || server || dbUuid) return;
    const first = listTargets(servers)[0];
    if (!first) return;
    setServer(first.servername);
    setDbUuid(first.uuid);
  }, [servers, workspaceId, server, dbUuid]);

  useEffect(() => {
    setAdHocMasked([]);
    if (!dbUuid) {
      setPersistentMasked([]);
      return;
    }
    let cancelled = false;
    api
      .maskingRules(dbUuid)
      .then((rules) => {
        if (!cancelled) setPersistentMasked(rules ?? []);
      })
      .catch(() => {
        if (!cancelled) setPersistentMasked([]);
      });
    return () => {
      cancelled = true;
    };
  }, [dbUuid]);

  /* -------------------------------------------------------------- actions */

  const chooseServer = (name: string) => {
    setServer(name);
    setDbUuid(databasesOf(servers, name)[0]?.uuid ?? '');
  };

  const runQuery = useCallback(async () => {
    if (!dbUuid) {
      toast.error("No target selected", "Select a server and database before running the query.");
      return;
    }
    if (!query.trim()) {
      toast.error("Empty query", "Enter an SQL statement to execute.");
      return;
    }

    const executionId = cancellation.begin();
    if (!executionId) return;
    setRunning(true);
    setOutcome(null);
    runTimer.current = performance.now();
    try {
      const response = await api.executeQuery({
        db_uuid: dbUuid,
        query,
        execution_id: executionId,
        ad_hoc_mask_columns: adHocMasked.length > 0 ? adHocMasked : undefined,
      });
      setOutcome(outcomeFromResponse(response));
    } catch (caught) {
      if (caught instanceof UnauthorizedError) return;
      const failure = outcomeFromError(caught);
      setOutcome(failure);
      if (failure.sentForApproval) {
        /* The analyzer saved the statement as a workspace of its own. */
        toast.warning("Query sent for approval", "Risk analysis sent this statement for administrator review.");
        void reload();
      }
    } finally {
      setDurationMs(performance.now() - runTimer.current);
      setRunning(false);
      cancellation.finish(executionId);
    }
  }, [dbUuid, query, adHocMasked, reload, toast]);

  const saveWorkspace = useCallback(async () => {
    if (!current) {
      setSaveName('');
      setSaveDescription('');
      setSaveOpen(true);
      return;
    }
    setSaving(true);
    try {
      // The update endpoint accepts the SQL and status only.
      await api.updateWorkspace(current.id, { query });
      setSavedQuery(query);
      void reload();
      toast.success("Query updated", current.name);
    } catch (caught) {
      if (caught instanceof UnauthorizedError) return;
      toast.error("Could not save", errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }, [current, query, reload, toast]);

  const createWorkspace = async () => {
    if (!saveName.trim() || !dbUuid) return;
    setSaving(true);
    try {
      const created = await api.createWorkspace({
        name: saveName.trim(),
        description: saveDescription.trim() || undefined,
        query,
        db_uuid: dbUuid,
      });
      setSaveOpen(false);
      void reload();
      toast.success("Workspace saved", saveName.trim());
      if (created?.workspace_id) navigate(`/editor/${created.workspace_id}`);
    } catch (caught) {
      if (caught instanceof UnauthorizedError) return;
      toast.error("Could not save", errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const addAdHocColumn = () => {
    const value = newMaskColumn.trim().toLocaleLowerCase('tr');
    if (!value) return;
    if (persistentMasked.includes(value) || adHocMasked.includes(value)) {
      setNewMaskColumn('');
      return;
    }
    setAdHocMasked((columns) => [...columns, value]);
    setNewMaskColumn('');
  };

  // The editor binds Mod+Enter itself, so this only covers focus outside it.
  useHotkey('mod+enter', () => void runQuery(), { enabled: !running });
  useHotkey(
    'mod+s',
    (event) => {
      event.preventDefault();
      if (editable) void saveWorkspace();
    },
    { allowInEditable: true },
  );

  /* --------------------------------------------------------------- render */

  const workspaceItems = useMemo<PickerItem[]>(
    () =>
      workspaces.map((workspace) => ({
        value: String(workspace.id),
        label: workspace.name,
        meta: `${workspace.servername} / ${workspace.database_name}`,
        trailing: <Badge tone={statusMeta(workspace.status).tone}>{statusMeta(workspace.status).label}</Badge>,
      })),
    [workspaces],
  );

  const serverItems = useMemo<PickerItem[]>(
    () =>
      serverNames(servers).map((name) => ({
        value: name,
        label: name,
        meta: `${servers[name].databases.length} databases`,
        trailing: servers[name].technology ? (
          <Badge tone="neutral" mono>
            {servers[name].technology}
          </Badge>
        ) : undefined,
      })),
    [servers],
  );

  const databaseItems = useMemo<PickerItem[]>(
    () =>
      databasesOf(servers, server).map((entry) => {
        const meta = capabilityMeta(entry.capability);
        return {
          value: entry.uuid,
          label: entry.name,
          trailing: <Badge tone={meta.tone}>{meta.label}</Badge>,
        };
      }),
    [server, servers],
  );

  // One database is one row. The tier it connects with is chosen by the
  // backend from the query itself, so this badge reports the ceiling rather
  // than offering a choice.
  const capability = capabilityMeta(target?.capability);

  const statusInfo = current ? statusMeta(current.status) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Picker
          label="Select a workspace"
          placeholder="Unsaved query"
          value={current ? String(current.id) : null}
          onChange={(value) => navigate(`/editor/${value}`)}
          items={workspaceItems}
          triggerClassName="w-[220px]"
          emptyMessage="No saved workspaces"
          searchPlaceholder="Search workspaces"
          header={(close) => (
            <button
              type="button"
              onClick={() => {
                close();
                setCurrent(null);
                setSavedQuery(null);
                setQuery(STARTER_QUERY);
                setOutcome(null);
                navigate('/editor');
              }}
              className="flex w-full items-center gap-2 border-b border-line px-3 py-2 text-left text-[13px] text-accent hover:bg-hover"
            >
              <PlusIcon size={14} weight="bold" />
              New query
            </button>
          )}
        />

        <Picker
          label="Select a server"
          placeholder="Server"
          value={server || null}
          onChange={chooseServer}
          items={serverItems}
          triggerClassName="w-[210px]"
          emptyMessage="No accessible servers"
          searchPlaceholder="Search servers"
          leading={<HardDrivesIcon size={14} className="shrink-0 text-subtle" />}
        />

        <Picker
          label="Select a database"
          placeholder="Database"
          value={dbUuid || null}
          onChange={setDbUuid}
          items={databaseItems}
          disabled={!server}
          triggerClassName="w-[190px]"
          emptyMessage="No accessible databases on this server"
          searchPlaceholder="Search databases"
          leading={<DatabaseIcon size={14} className="shrink-0 text-subtle" />}
        />

        {target && (
          <Tooltip content={<span>{capability.hint}</span>}>
            <Badge tone={capability.tone}>{capability.label}</Badge>
          </Tooltip>
        )}

        <div className="ml-auto flex items-center gap-2">
          <Button icon={<LockKeyIcon size={14} />} disabled={!dbUuid} onClick={() => setMaskingOpen(true)}>
            Masking
            {maskedCount > 0 && (
              <span className="ml-0.5 rounded-[var(--r-pill)] bg-warning-soft px-1.5 text-[10.5px] font-medium leading-[16px] text-warning">
                {maskedCount}
              </span>
            )}
          </Button>

          <Button
            icon={<FloppyDiskIcon size={14} />}
            loading={saving}
            disabled={!editable || !dbUuid}
            onClick={() => void saveWorkspace()}
          >
            {current ? "Save" : "Save as"}
            {dirty && <span aria-label="Unsaved changes" className="ml-0.5 size-1.5 rounded-full bg-warning" />}
          </Button>

          <Tooltip content={<span>{isMac ? '⌘' : 'Ctrl'} + Enter</span>}>
            <Button
              variant="primary"
              icon={<PlayIcon size={13} weight="fill" />}
              loading={running}
              disabled={!dbUuid}
              onClick={() => void runQuery()}
            >
              Run
            </Button>
          </Tooltip>
          {running && <QueryCancelControl cancellation={cancellation} />}
        </div>
      </div>

      {noGrants && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-md border border-warning-line bg-warning-soft px-3.5 py-2.5 text-[12.5px] text-warning"
        >
          <WarningCircleIcon size={15} weight="fill" className="shrink-0" />
          <span>
            You do not have access to any databases. An administrator needs to grant you database access before you can run queries.
          </span>
        </div>
      )}

      {targetUnavailable && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-md border border-danger-line bg-danger-soft px-3.5 py-2.5 text-[12.5px] text-danger"
        >
          <WarningCircleIcon size={15} weight="fill" className="shrink-0" />
          <span>
            This workspace's target (<span className="font-mono">{current?.servername}</span> /{' '}
            <span className="font-mono">{current?.database_name}</span>) is not among your accessible databases. Select an authorized target before running the query.
          </span>
        </div>
      )}

      {statusInfo && !editable && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-md border border-warning-line bg-warning-soft px-3.5 py-2.5 text-[12.5px] text-warning"
        >
          <Badge tone={statusInfo.tone}>{statusInfo.label}</Badge>
          <span>{statusInfo.hint}</span>
        </div>
      )}

      <SplitPane
        storageKey="webquery.studio.split"
        firstLabel="Editor"
        secondLabel="Results"
        className="min-h-0 flex-1"
        first={
          <section className="flex min-h-0 w-full flex-col overflow-hidden rounded-md border border-line bg-surface">
            <PanelHeader
              dense
              title={current?.name ?? "Unsaved query"}
              description={
                server && database ? (
                  <span className="flex items-center gap-1.5">
                    <Identifier>{server}</Identifier>
                    <span aria-hidden>/</span>
                    <Identifier>{database}</Identifier>
                  </span>
                ) : (
                  "No target selected"
                )
              }
              actions={
                <>
                  <span className="mr-1 hidden items-center gap-1 text-[11.5px] text-subtle sm:flex">
                    <Kbd>{isMac ? '⌘' : 'Ctrl'}</Kbd>
                    <Kbd>↵</Kbd>
                    run
                  </span>
                  <IconButton
                    label="Clear editor"
                    size="sm"
                    disabled={!editable || query.length === 0}
                    onClick={() => setQuery('')}
                  >
                    <EraserIcon size={15} />
                  </IconButton>
                </>
              }
            />
            <div className={cn('min-h-0 flex-1 overflow-hidden rounded-b-md', loadingWorkspace && 'opacity-50')}>
              <CodeEditor
                value={query}
                onChange={setQuery}
                onRun={() => void runQuery()}
                readOnly={!editable}
                technology={technology}
                placeholder="SELECT ..."
              />
            </div>
          </section>
        }
        second={
          <ResultPanel
            outcome={outcome}
            running={running}
            durationMs={durationMs}
            exportBaseName={current?.name ?? "webquery-results"}
            emptyTitle="No query run yet"
            emptyDescription={`Write your query and press ${isMac ? '⌘' : 'Ctrl'} + Enter to run it. Results will appear here.`}
          />
        }
      />

      {/* --------------------------------------------------------- masking */}
      <Dialog
        open={maskingOpen}
        onOpenChange={setMaskingOpen}
        title="Data masking"
        description={`${server} / ${database} — rules configured for this execution.`}
        footer={
          <Button variant="primary" onClick={() => setMaskingOpen(false)}>
            Done
          </Button>
        }
      >
        <div className="flex flex-col gap-6">
          <section>
            <h3 className="text-[12.5px] font-medium text-muted">Administrator rules</h3>
            <p className="mt-1 text-[12.5px] leading-relaxed text-subtle">
              These columns are masked server-side and the rules cannot be removed here.
            </p>
            {persistentMasked.length === 0 ? (
              <p className="mt-2.5 rounded-sm border border-line bg-sunken px-3 py-2.5 text-[12.5px] text-subtle">
                No permanent rules are configured for this database.
              </p>
            ) : (
              <ul className="mt-2.5 flex flex-wrap gap-1.5">
                {persistentMasked.map((column) => (
                  <li key={column}>
                    <Badge tone="danger" mono>
                      <LockKeyIcon size={11} weight="fill" />
                      {column}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="text-[12.5px] font-medium text-muted">Temporary rules</h3>
            <p className="mt-1 text-[12.5px] leading-relaxed text-subtle">
              Apply only to executions in this session and are not saved.
            </p>

            <form
              className="mt-2.5 flex items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                addAdHocColumn();
              }}
            >
              <Field label="Column name" className="flex-1 [&>div:first-child]:sr-only">
                <Input
                  value={newMaskColumn}
                  onChange={(event) => setNewMaskColumn(event.target.value)}
                  placeholder="email, phone, account_number"
                  className="font-mono"
                />
              </Field>
              <Button type="submit" disabled={!newMaskColumn.trim()}>
                Add
              </Button>
            </form>

            {adHocMasked.length > 0 && (
              <ul className="mt-2.5 flex flex-wrap gap-1.5">
                {adHocMasked.map((column) => (
                  <li key={column}>
                    <span className="inline-flex h-[22px] items-center gap-1 rounded-[var(--r-pill)] border border-warning-line bg-warning-soft pl-2 pr-1 font-mono text-[11px] text-warning">
                      {column}
                      <IconButton
                        label={`${column} — remove rule`}
                        size="sm"
                        className="size-4 text-warning hover:bg-transparent hover:text-fg"
                        onClick={() => setAdHocMasked((columns) => columns.filter((item) => item !== column))}
                      >
                        <XIcon size={10} weight="bold" />
                      </IconButton>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </Dialog>

      {/* ------------------------------------------------------------ save */}
      <Dialog
        open={saveOpen}
        onOpenChange={setSaveOpen}
        title="Save as workspace"
        description="Saved queries appear in your workspace list and participate in the approval workflow."
        size="md"
        busy={saving}
        footer={
          <>
            <Button variant="secondary" onClick={() => setSaveOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={saving}
              disabled={!saveName.trim() || !dbUuid}
              onClick={() => void createWorkspace()}
            >
              Save
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Name" required>
            <Input
              value={saveName}
              onChange={(event) => setSaveName(event.target.value)}
              autoFocus
              placeholder="Monthly sales summary"
            />
          </Field>
          <Field
            label="Description"
            hint="A brief description helps the reviewing administrator understand why this query is needed."
          >
            <Textarea
              value={saveDescription}
              onChange={(event) => setSaveDescription(event.target.value)}
              rows={3}
              placeholder="Revenue by product for the month-end report."
            />
          </Field>
          <div className="rounded-sm border border-line bg-sunken px-3 py-2.5 text-[12.5px] text-subtle">
            Target: <span className="font-mono text-fg">{server || "not selected"}</span> /{' '}
            <span className="font-mono text-fg">{database || "not selected"}</span>
          </div>
        </div>
      </Dialog>
    </div>
  );
};

export default Studio;
