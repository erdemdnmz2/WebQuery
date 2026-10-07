import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowClockwiseIcon,
  CaretRightIcon,
  DatabaseIcon,
  ShieldCheckIcon,
  UserCirclePlusIcon,
  UsersThreeIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react';
import { api, errorMessage } from '../../../services/api';
import { cn } from '../../../lib/cn';
import { formatCount } from '../../../lib/format';
import { connectionModeMeta } from '../../../lib/capability';
import type { DatabaseUsers, RegisteredDatabase } from '../../../types';
import { Badge } from '../../ui/Badge';
import { Button, IconButton } from '../../ui/Button';
import { ConfirmDialog } from '../../ui/Dialog';
import { EmptyState } from '../../ui/EmptyState';
import { Field } from '../../ui/Field';
import { Panel, PanelHeader } from '../../ui/Panel';
import { Select } from '../../ui/Select';
import { Skeleton } from '../../ui/Skeleton';
import { useToast } from '../../ui/Toast';

const NONE = '__none__';
const ROLE_OPTIONS = [
  { value: 'READER', label: "READER — read only" },
  { value: 'WRITER', label: "WRITER — read + write" },
  { value: 'DDL', label: "DDL — schema changes" },
];

/**
 * Grants and revokes database access, and is the reason a `user_id` is
 * discoverable at all from the interface.
 *
 * Before this existed, `associate_user` was the only route to granting query
 * access and no screen could produce the `user_id` it needs: an activated
 * user could reach no database. Revoking had no route whatsoever —
 * `AuditAction.REVOKE_DATABASE_ACCESS` was defined but never called, so the
 * only way to cut a departing employee off was to disable their account
 * everywhere at once. See P1-7 / P1-8.
 */
export const AccessTab: React.FC = () => {
  const toast = useToast();
  const [databases, setDatabases] = useState<RegisteredDatabase[]>([]);
  const [loadingDatabases, setLoadingDatabases] = useState(true);
  const [selected, setSelected] = useState<RegisteredDatabase | null>(null);

  const [detail, setDetail] = useState<DatabaseUsers | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [candidateId, setCandidateId] = useState(NONE);
  const [role, setRole] = useState('READER');
  const [granting, setGranting] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<DatabaseUsers['members'][number] | null>(null);
  const [revoking, setRevoking] = useState(false);

  const loadDatabases = async () => {
    setLoadingDatabases(true);
    try {
      setDatabases(await api.registeredDatabases());
    } catch (caught) {
      toast.error("Could not load databases", errorMessage(caught));
    } finally {
      setLoadingDatabases(false);
    }
  };

  useEffect(() => {
    void loadDatabases();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadDetail = async (database: RegisteredDatabase) => {
    setLoadingDetail(true);
    setDetailError(null);
    try {
      setDetail(await api.databaseUsers(database.id));
    } catch (caught) {
      setDetailError(errorMessage(caught));
    } finally {
      setLoadingDetail(false);
    }
  };

  const selectDatabase = (database: RegisteredDatabase) => {
    setSelected(database);
    setCandidateId(NONE);
    setRole('READER');
    void loadDetail(database);
  };

  const candidateOptions = useMemo(
    () => [
      { value: NONE, label: "Select a user", disabled: true },
      ...(detail?.candidates ?? []).map((candidate) => ({
        value: String(candidate.user_id),
        label: `${candidate.username} · ${candidate.email}`,
      })),
    ],
    [detail],
  );

  const grant = async () => {
    if (!selected || candidateId === NONE) return;
    setGranting(true);
    try {
      await api.associateUser({
        user_id: Number(candidateId),
        database_id: selected.id,
        role: role as 'READER' | 'WRITER' | 'DDL',
      });
      toast.success("Access granted", `${role} access on ${selected.database_name}`);
      setCandidateId(NONE);
      await loadDetail(selected);
    } catch (caught) {
      toast.error("Could not grant access", errorMessage(caught));
    } finally {
      setGranting(false);
    }
  };

  const revoke = async () => {
    if (!selected || !revokeTarget) return;
    setRevoking(true);
    try {
      await api.revokeDatabaseAccess(selected.id, revokeTarget.user_id);
      toast.success("Access removed", `${revokeTarget.username} · ${selected.database_name}`);
      setRevokeTarget(null);
      await loadDetail(selected);
    } catch (caught) {
      toast.error("Could not remove access", errorMessage(caught));
    } finally {
      setRevoking(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="flex flex-col gap-4 lg:col-span-5">
        <Panel flush as="section" className="flex min-h-0 flex-col">
          <PanelHeader
            title="Registered databases"
            description={loadingDatabases ? undefined : `${formatCount(databases.length)} records`}
            actions={
              <IconButton label="Refresh list" size="sm" onClick={() => void loadDatabases()}>
                <ArrowClockwiseIcon size={14} className={cn(loadingDatabases && 'animate-spin-slow')} />
              </IconButton>
            }
          />
          {loadingDatabases && databases.length === 0 ? (
            <div className="flex flex-col gap-2 p-4">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-11 w-full rounded-sm" />
              ))}
            </div>
          ) : databases.length === 0 ? (
            <EmptyState
              size="sm"
              icon={<DatabaseIcon size={18} />}
              title="No registered databases"
              description="Target databases are registered by the platform OWNER."
            />
          ) : (
            <ul className="max-h-[420px] overflow-y-auto p-1.5">
              {databases.map((database) => {
                const active = selected?.id === database.id;
                return (
                  <li key={database.id}>
                    <button
                      type="button"
                      aria-current={active}
                      onClick={() => selectDatabase(database)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-sm px-2.5 py-2 text-left',
                        'transition-colors duration-[var(--dur-fast)] hover:bg-hover',
                        active && 'bg-selected hover:bg-selected',
                      )}
                    >
                      <DatabaseIcon size={15} className={cn('shrink-0', active ? 'text-accent' : 'text-subtle')} />
                      <span className="min-w-0 flex-1">
                        <span className={cn('block truncate font-mono text-[12.5px]', active ? 'text-accent' : 'text-fg')}>
                          {database.database_name}
                        </span>
                        <span className="block truncate text-[11.5px] text-subtle">{database.servername}</span>
                      </span>
                      <Badge tone={connectionModeMeta(database.connection_mode).tone}>
                        {connectionModeMeta(database.connection_mode).label}
                      </Badge>
                      <CaretRightIcon size={13} className={cn('shrink-0', active ? 'text-accent' : 'text-faint')} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="lg:col-span-7">
        {!selected ? (
          <Panel className="flex h-full min-h-[420px] items-center justify-center">
            <EmptyState
              icon={<UsersThreeIcon size={18} />}
              title="Database access"
              description="Select a database on the left to view, grant or remove user access."
            />
          </Panel>
        ) : loadingDetail ? (
          <Panel flush className="flex min-h-[420px] flex-col gap-2 p-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-11 w-full rounded-sm" />
            ))}
          </Panel>
        ) : detailError ? (
          <Panel className="flex h-full min-h-[420px] items-center justify-center">
            <EmptyState
              icon={<WarningCircleIcon size={18} />}
              title="Could not load access list"
              description={detailError}
              action={<Button onClick={() => void loadDetail(selected)}>Try again</Button>}
            />
          </Panel>
        ) : (
          <Panel flush as="section" className="flex h-full min-h-[420px] flex-col">
            <PanelHeader
              title={
                <span className="font-mono">
                  {selected.database_name}
                  <span className="ml-2 font-sans text-[12px] font-normal text-subtle">{selected.servername}</span>
                </span>
              }
              description={`${formatCount(detail?.members.length ?? 0)} users have access`}
            />

            <div className="grid grid-cols-1 gap-3 border-b border-line p-4 sm:grid-cols-[1fr_auto_auto]">
              <Field label="Active user" hint="Users who already have access are not listed.">
                <Select value={candidateId} onValueChange={setCandidateId} options={candidateOptions} />
              </Field>
              <Field label="Role">
                <Select value={role} onValueChange={setRole} options={ROLE_OPTIONS} />
              </Field>
              <Button
                className="self-end"
                icon={<UserCirclePlusIcon size={14} />}
                loading={granting}
                disabled={candidateId === NONE}
                onClick={() => void grant()}
              >
                Grant access
              </Button>
            </div>

            {(detail?.members.length ?? 0) === 0 ? (
              <EmptyState
                size="sm"
                icon={<ShieldCheckIcon size={18} />}
                title="No access granted yet"
                description="Only you currently have access to this database."
              />
            ) : (
              <ul className="min-h-0 flex-1 divide-y divide-line overflow-y-auto">
                {detail?.members.map((member) => (
                  <li key={member.user_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="truncate text-[13px] font-medium text-fg">{member.username}</span>
                        {!member.is_active && <Badge tone="neutral">Inactive user</Badge>}
                      </span>
                      <span className="block truncate text-[11.5px] text-subtle">{member.email}</span>
                    </span>
                    <Badge tone={member.is_admin ? 'accent' : 'neutral'} mono>
                      {member.role}
                    </Badge>
                    {member.is_admin ? (
                      <span className="text-[11.5px] text-subtle" title="DB ADMIN is managed only by the platform OWNER">
                        Managed by OWNER
                      </span>
                    ) : (
                      <Button size="sm" variant="danger" onClick={() => setRevokeTarget(member)}>
                        Remove access
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        )}
      </div>

      <ConfirmDialog
        open={revokeTarget !== null}
        onOpenChange={(open) => !open && setRevokeTarget(null)}
        title="Remove database access?"
        description="The user will no longer be able to run queries on this database. Access to other databases is unaffected."
        confirmLabel="Remove access"
        destructive
        busy={revoking}
        onConfirm={() => void revoke()}
      >
        {revokeTarget && (
          <p className="font-mono text-[12px] text-fg">
            {revokeTarget.username} · {revokeTarget.role}
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
};
