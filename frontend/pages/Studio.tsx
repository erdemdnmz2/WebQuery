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
import { useWorkspaces } from '../lib/workspaces';
import { isEditable, statusMeta } from '../lib/workspace-status';
import { outcomeFromError, outcomeFromResponse, type ExecutionOutcome } from '../lib/execution';
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
          toast.error('Bağlantı listesi alınamadı', errorMessage(caught));
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
        toast.error('Çalışma alanı açılamadı', errorMessage(caught));
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
      toast.error('Hedef seçilmedi', 'Çalıştırmadan önce bir sunucu ve veritabanı seçin.');
      return;
    }
    if (!query.trim()) {
      toast.error('Sorgu boş', 'Çalıştırılacak bir SQL ifadesi yazın.');
      return;
    }

    setRunning(true);
    setOutcome(null);
    runTimer.current = performance.now();
    try {
      const response = await api.executeQuery({
        db_uuid: dbUuid,
        query,
        ad_hoc_mask_columns: adHocMasked.length > 0 ? adHocMasked : undefined,
      });
      setOutcome(outcomeFromResponse(response));
    } catch (caught) {
      if (caught instanceof UnauthorizedError) return;
      const failure = outcomeFromError(caught);
      setOutcome(failure);
      if (failure.sentForApproval) {
        /* The analyzer saved the statement as a workspace of its own. */
        toast.warning('Sorgu onaya gönderildi', 'Risk analizi bu ifadeyi yönetici incelemesine yönlendirdi.');
        void reload();
      }
    } finally {
      setDurationMs(performance.now() - runTimer.current);
      setRunning(false);
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
      toast.success('Sorgu güncellendi', current.name);
    } catch (caught) {
      if (caught instanceof UnauthorizedError) return;
      toast.error('Kaydedilemedi', errorMessage(caught));
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
      toast.success('Çalışma alanı kaydedildi', saveName.trim());
      if (created?.workspace_id) navigate(`/editor/${created.workspace_id}`);
    } catch (caught) {
      if (caught instanceof UnauthorizedError) return;
      toast.error('Kaydedilemedi', errorMessage(caught));
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
        meta: `${servers[name].databases.length} veritabanı`,
        trailing: servers[name].technology ? (
          <Badge tone="neutral" mono>
            {servers[name].technology}
          </Badge>
        ) : undefined,
      })),
    [servers],
  );

  const databaseItems = useMemo<PickerItem[]>(
    () => databasesOf(servers, server).map((entry) => ({ value: entry.uuid, label: entry.name })),
    [server, servers],
  );

  const statusInfo = current ? statusMeta(current.status) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Picker
          label="Çalışma alanı seçin"
          placeholder="Kaydedilmemiş sorgu"
          value={current ? String(current.id) : null}
          onChange={(value) => navigate(`/editor/${value}`)}
          items={workspaceItems}
          triggerClassName="w-[220px]"
          emptyMessage="Kayıtlı çalışma alanı yok"
          searchPlaceholder="Çalışma alanı ara"
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
              Yeni sorgu
            </button>
          )}
        />

        <Picker
          label="Sunucu seçin"
          placeholder="Sunucu"
          value={server || null}
          onChange={chooseServer}
          items={serverItems}
          triggerClassName="w-[210px]"
          emptyMessage="Yetkili olduğunuz sunucu yok"
          searchPlaceholder="Sunucu ara"
          leading={<HardDrivesIcon size={14} className="shrink-0 text-subtle" />}
        />

        <Picker
          label="Veritabanı seçin"
          placeholder="Veritabanı"
          value={dbUuid || null}
          onChange={setDbUuid}
          items={databaseItems}
          disabled={!server}
          triggerClassName="w-[190px]"
          emptyMessage="Bu sunucuda yetkili olduğunuz veritabanı yok"
          searchPlaceholder="Veritabanı ara"
          leading={<DatabaseIcon size={14} className="shrink-0 text-subtle" />}
        />

        <div className="ml-auto flex items-center gap-2">
          <Button icon={<LockKeyIcon size={14} />} disabled={!dbUuid} onClick={() => setMaskingOpen(true)}>
            Maskeleme
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
            {current ? 'Kaydet' : 'Farklı kaydet'}
            {dirty && <span aria-label="Kaydedilmemiş değişiklik" className="ml-0.5 size-1.5 rounded-full bg-warning" />}
          </Button>

          <Tooltip content={<span>{isMac ? '⌘' : 'Ctrl'} + Enter</span>}>
            <Button
              variant="primary"
              icon={<PlayIcon size={13} weight="fill" />}
              loading={running}
              disabled={!dbUuid}
              onClick={() => void runQuery()}
            >
              Çalıştır
            </Button>
          </Tooltip>
        </div>
      </div>

      {noGrants && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-md border border-warning-line bg-warning-soft px-3.5 py-2.5 text-[12.5px] text-warning"
        >
          <WarningCircleIcon size={15} weight="fill" className="shrink-0" />
          <span>
            Hiçbir veritabanına erişim yetkiniz yok. Sorgu çalıştırabilmek için bir yöneticinin sizi bir
            veritabanına yetkilendirmesi gerekir.
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
            Bu çalışma alanının hedefi (<span className="font-mono">{current?.servername}</span> /{' '}
            <span className="font-mono">{current?.database_name}</span>) erişebildiğiniz veritabanları arasında
            değil. Çalıştırmadan önce yetkili bir hedef seçin.
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
        firstLabel="Düzenleyici"
        secondLabel="Sonuçlar"
        className="min-h-0 flex-1"
        first={
          <section className="flex min-h-0 w-full flex-col overflow-hidden rounded-md border border-line bg-surface">
            <PanelHeader
              dense
              title={current?.name ?? 'Kaydedilmemiş sorgu'}
              description={
                server && database ? (
                  <span className="flex items-center gap-1.5">
                    <Identifier>{server}</Identifier>
                    <span aria-hidden>/</span>
                    <Identifier>{database}</Identifier>
                  </span>
                ) : (
                  'Hedef seçilmedi'
                )
              }
              actions={
                <>
                  <span className="mr-1 hidden items-center gap-1 text-[11.5px] text-subtle sm:flex">
                    <Kbd>{isMac ? '⌘' : 'Ctrl'}</Kbd>
                    <Kbd>↵</Kbd>
                    çalıştır
                  </span>
                  <IconButton
                    label="Düzenleyiciyi temizle"
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
            exportBaseName={current?.name ?? 'webquery-sonuc'}
            emptyTitle="Henüz sorgu çalıştırılmadı"
            emptyDescription={`Sorgunuzu yazın ve ${isMac ? '⌘' : 'Ctrl'} + Enter ile çalıştırın. Sonuçlar burada görünür.`}
          />
        }
      />

      {/* --------------------------------------------------------- masking */}
      <Dialog
        open={maskingOpen}
        onOpenChange={setMaskingOpen}
        title="Veri maskeleme"
        description={`${server} / ${database} üzerinde bu çalıştırma için geçerli kurallar.`}
        footer={
          <Button variant="primary" onClick={() => setMaskingOpen(false)}>
            Tamam
          </Button>
        }
      >
        <div className="flex flex-col gap-6">
          <section>
            <h3 className="text-[12.5px] font-medium text-muted">Yönetici kuralları</h3>
            <p className="mt-1 text-[12.5px] leading-relaxed text-subtle">
              Bu kolonlar sunucu tarafında maskelenir ve kaldırılamaz.
            </p>
            {persistentMasked.length === 0 ? (
              <p className="mt-2.5 rounded-sm border border-line bg-sunken px-3 py-2.5 text-[12.5px] text-subtle">
                Bu veritabanı için tanımlı kalıcı kural yok.
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
            <h3 className="text-[12.5px] font-medium text-muted">Geçici kurallar</h3>
            <p className="mt-1 text-[12.5px] leading-relaxed text-subtle">
              Yalnızca bu oturumdaki çalıştırmalara uygulanır, kaydedilmez.
            </p>

            <form
              className="mt-2.5 flex items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                addAdHocColumn();
              }}
            >
              <Field label="Kolon adı" className="flex-1 [&>div:first-child]:sr-only">
                <Input
                  value={newMaskColumn}
                  onChange={(event) => setNewMaskColumn(event.target.value)}
                  placeholder="email, tckn, iban"
                  className="font-mono"
                />
              </Field>
              <Button type="submit" disabled={!newMaskColumn.trim()}>
                Ekle
              </Button>
            </form>

            {adHocMasked.length > 0 && (
              <ul className="mt-2.5 flex flex-wrap gap-1.5">
                {adHocMasked.map((column) => (
                  <li key={column}>
                    <span className="inline-flex h-[22px] items-center gap-1 rounded-[var(--r-pill)] border border-warning-line bg-warning-soft pl-2 pr-1 font-mono text-[11px] text-warning">
                      {column}
                      <IconButton
                        label={`${column} kuralını kaldır`}
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
        title="Çalışma alanı olarak kaydet"
        description="Kaydedilen sorgular listenizde görünür ve onay akışına dahil olur."
        size="md"
        busy={saving}
        footer={
          <>
            <Button variant="secondary" onClick={() => setSaveOpen(false)} disabled={saving}>
              Vazgeç
            </Button>
            <Button
              variant="primary"
              loading={saving}
              disabled={!saveName.trim() || !dbUuid}
              onClick={() => void createWorkspace()}
            >
              Kaydet
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Ad" required>
            <Input
              value={saveName}
              onChange={(event) => setSaveName(event.target.value)}
              autoFocus
              placeholder="Aylık satış özeti"
            />
          </Field>
          <Field
            label="Açıklama"
            hint="Sorguyu inceleyen yöneticinin neden çalıştırıldığını anlaması için bir cümle yeterli."
          >
            <Textarea
              value={saveDescription}
              onChange={(event) => setSaveDescription(event.target.value)}
              rows={3}
              placeholder="Kapanış raporu için ürün kırılımında ciro."
            />
          </Field>
          <div className="rounded-sm border border-line bg-sunken px-3 py-2.5 text-[12.5px] text-subtle">
            Hedef: <span className="font-mono text-fg">{server || 'seçilmedi'}</span> /{' '}
            <span className="font-mono text-fg">{database || 'seçilmedi'}</span>
          </div>
        </div>
      </Dialog>
    </div>
  );
};

export default Studio;
