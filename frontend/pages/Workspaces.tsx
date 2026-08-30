import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowClockwiseIcon,
  DotsThreeIcon,
  MagnifyingGlassIcon,
  PlayIcon,
  PlusIcon,
  PencilSimpleIcon,
  TrashIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react';
import { api, errorMessage } from '../services/api';
import { cn } from '../lib/cn';
import { useWorkspaces } from '../lib/workspaces';
import { formatCount } from '../lib/format';
import { isEditable, isRunnable, statusMeta } from '../lib/workspace-status';
import { Badge, Identifier } from '../components/ui/Badge';
import { Button, IconButton } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/Dialog';
import { EmptyState } from '../components/ui/EmptyState';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from '../components/ui/Menu';
import { Panel } from '../components/ui/Panel';
import { SkeletonRows } from '../components/ui/Skeleton';
import { Tooltip } from '../components/ui/Tooltip';
import { useToast } from '../components/ui/Toast';
import type { Workspace, WorkspaceStatus } from '../types';

type Filter = 'all' | WorkspaceStatus;

const SUMMARY: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Tümü' },
  { key: 'saved_in_workspace', label: 'Taslak' },
  { key: 'waiting_for_approval', label: 'Onay bekleyen' },
  { key: 'approved_with_results', label: 'Çalıştırılabilir' },
  { key: 'rejected', label: 'Reddedilen' },
];

const Workspaces: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const { workspaces, loading, error, reload, replace } = useWorkspaces();
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [pendingDelete, setPendingDelete] = useState<Workspace | null>(null);
  const [deleting, setDeleting] = useState(false);

  const counts = useMemo(() => {
    const map = new Map<Filter, number>([['all', workspaces.length]]);
    for (const workspace of workspaces) {
      map.set(workspace.status, (map.get(workspace.status) ?? 0) + 1);
    }
    return map;
  }, [workspaces]);

  const visible = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('tr');
    return workspaces.filter((workspace) => {
      if (filter !== 'all' && workspace.status !== filter) return false;
      if (!needle) return true;
      return `${workspace.name} ${workspace.description ?? ''} ${workspace.servername} ${workspace.database_name}`
        .toLocaleLowerCase('tr')
        .includes(needle);
    });
  }, [workspaces, filter, search]);

  const openWorkspace = (workspace: Workspace) => {
    if (isRunnable(workspace.status, workspace.show_results)) navigate(`/execute/${workspace.id}`);
    else navigate(`/editor/${workspace.id}`);
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await api.deleteWorkspace(pendingDelete.id);
      replace(workspaces.filter((workspace) => workspace.id !== pendingDelete.id));
      toast.success('Çalışma alanı silindi', pendingDelete.name);
      setPendingDelete(null);
    } catch (caught) {
      toast.error('Silinemedi', errorMessage(caught));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 animate-enter">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1>Çalışma alanları</h1>
          <p className="mt-1 max-w-[60ch] text-[13px] text-subtle">
            Kaydettiğiniz sorgular, onay durumları ve çalıştırma yetkileri.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <IconButton label="Listeyi yenile" onClick={() => void reload()}>
            <ArrowClockwiseIcon size={15} className={cn(loading && 'animate-spin-slow')} />
          </IconButton>
          <Button variant="primary" icon={<PlusIcon size={14} weight="bold" />} onClick={() => navigate('/editor')}>
            Yeni sorgu
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <div
          role="group"
          aria-label="Duruma göre filtrele"
          className="flex w-full items-stretch overflow-x-auto rounded-md border border-line bg-surface sm:w-auto"
        >
          {SUMMARY.map((item, index) => {
            const active = filter === item.key;
            const count = counts.get(item.key) ?? 0;
            return (
              <button
                key={item.key}
                type="button"
                aria-pressed={active}
                onClick={() => setFilter(item.key)}
                className={cn(
                  'flex min-w-[104px] shrink-0 flex-col items-start gap-0.5 px-3.5 py-2 text-left',
                  'transition-colors duration-[var(--dur-fast)] ease-standard hover:bg-hover',
                  index > 0 && 'border-l border-line',
                  active && 'bg-selected hover:bg-selected',
                )}
              >
                <span
                  data-numeric
                  className={cn('font-mono text-[17px] leading-none', active ? 'text-accent' : 'text-fg')}
                >
                  {formatCount(count)}
                </span>
                <span className={cn('text-[11.5px]', active ? 'text-accent' : 'text-subtle')}>{item.label}</span>
              </button>
            );
          })}
        </div>

        <div className="ml-auto w-full sm:w-64">
          <Field label="Ara" className="[&>div:first-child]:sr-only">
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Ad, sunucu veya veritabanı"
              icon={<MagnifyingGlassIcon size={14} />}
            />
          </Field>
        </div>
      </div>

      <Panel flush>
        {loading && workspaces.length === 0 ? (
          <SkeletonRows rows={5} />
        ) : error ? (
          <EmptyState
            icon={<WarningCircleIcon size={18} />}
            title="Liste yüklenemedi"
            description={error}
            action={
              <Button icon={<ArrowClockwiseIcon size={14} />} onClick={() => void reload()}>
                Yeniden dene
              </Button>
            }
          />
        ) : workspaces.length === 0 ? (
          <EmptyState
            icon={<PlusIcon size={18} />}
            title="Henüz kayıtlı sorgunuz yok"
            description="SQL Studio'da bir sorgu yazıp kaydettiğinizde burada listelenir ve onay durumunu buradan takip edersiniz."
            action={
              <Button variant="primary" icon={<PlusIcon size={14} weight="bold" />} onClick={() => navigate('/editor')}>
                İlk sorgunuzu yazın
              </Button>
            }
          />
        ) : visible.length === 0 ? (
          <EmptyState
            size="sm"
            title="Bu filtreye uyan kayıt yok"
            description="Arama terimini kısaltmayı veya durum filtresini temizlemeyi deneyin."
            action={
              <Button
                onClick={() => {
                  setFilter('all');
                  setSearch('');
                }}
              >
                Filtreleri temizle
              </Button>
            }
          />
        ) : (
          <ul>
            {visible.map((workspace, index) => {
              const meta = statusMeta(workspace.status);
              const runnable = isRunnable(workspace.status, workspace.show_results);
              const editable = isEditable(workspace.status);

              return (
                <li
                  key={workspace.id}
                  className={cn(
                    'group grid grid-cols-1 items-center gap-x-4 gap-y-2 px-4 py-3',
                    'md:grid-cols-[minmax(0,1fr)_15rem_8.5rem_9.5rem]',
                    'transition-colors duration-[var(--dur-fast)] hover:bg-hover',
                    index > 0 && 'border-t border-line',
                  )}
                >
                  <div className="min-w-0">
                    <button
                      type="button"
                      onClick={() => openWorkspace(workspace)}
                      className="block max-w-full truncate text-left text-[13.5px] font-medium text-fg hover:text-accent"
                    >
                      {workspace.name}
                    </button>
                    <p className="mt-0.5 truncate text-[12.5px] text-subtle">
                      {workspace.description || 'Açıklama girilmedi'}
                    </p>
                  </div>

                  <div className="flex min-w-0 items-center gap-1.5">
                    <Identifier className="shrink">{workspace.servername}</Identifier>
                    <span aria-hidden className="text-faint">
                      /
                    </span>
                    <Identifier className="shrink">{workspace.database_name}</Identifier>
                  </div>

                  <Tooltip content={meta.hint} disabled={!meta.hint}>
                    <span className="justify-self-start">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </span>
                  </Tooltip>

                  <div className="flex items-center gap-1 md:justify-self-end">
                    {runnable ? (
                      <Button
                        size="sm"
                        className="w-[6.25rem]"
                        icon={<PlayIcon size={13} weight="fill" />}
                        onClick={() => navigate(`/execute/${workspace.id}`)}
                      >
                        Çalıştır
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        className="w-[6.25rem]"
                        icon={<PencilSimpleIcon size={13} />}
                        onClick={() => navigate(`/editor/${workspace.id}`)}
                      >
                        {editable ? 'Aç' : 'Görüntüle'}
                      </Button>
                    )}

                    <Menu>
                      <MenuTrigger asChild>
                        <IconButton label={`${workspace.name} için işlemler`} size="sm">
                          <DotsThreeIcon size={17} weight="bold" />
                        </IconButton>
                      </MenuTrigger>
                      <MenuContent>
                        <MenuItem
                          icon={<PencilSimpleIcon size={15} />}
                          onSelect={() => navigate(`/editor/${workspace.id}`)}
                        >
                          Studio'da aç
                        </MenuItem>
                        <MenuItem
                          icon={<PlayIcon size={15} />}
                          disabled={!runnable}
                          onSelect={() => navigate(`/execute/${workspace.id}`)}
                        >
                          Çalıştır ve dışa aktar
                        </MenuItem>
                        <MenuSeparator />
                        <MenuItem
                          destructive
                          icon={<TrashIcon size={15} />}
                          onSelect={() => setPendingDelete(workspace)}
                        >
                          Sil
                        </MenuItem>
                      </MenuContent>
                    </Menu>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="Çalışma alanını sil"
        description="Kayıtlı sorgu ve onay geçmişi kalıcı olarak kaldırılır. Bu işlem geri alınamaz."
        confirmLabel="Kalıcı olarak sil"
        destructive
        busy={deleting}
        onConfirm={() => void confirmDelete()}
      >
        {pendingDelete && (
          <div className="rounded-sm border border-line bg-sunken px-3 py-2.5">
            <p className="text-[13px] font-medium text-fg">{pendingDelete.name}</p>
            <p className="mt-1 font-mono text-[11.5px] text-subtle">
              {pendingDelete.servername} / {pendingDelete.database_name}
            </p>
          </div>
        )}
      </ConfirmDialog>
    </div>
  );
};

export default Workspaces;
