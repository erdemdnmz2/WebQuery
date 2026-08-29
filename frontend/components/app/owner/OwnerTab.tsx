import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowClockwiseIcon,
  CheckCircleIcon,
  DatabaseIcon,
  PlusIcon,
  ShieldCheckIcon,
  UserCircleIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react';
import { api, errorMessage } from '../../../services/api';
import { cn } from '../../../lib/cn';
import { CONNECTION_MODE } from '../../../lib/capability';
import { formatCount } from '../../../lib/format';
import type { ConnectionMode, DatabaseAdmin, OwnerUser, RegisteredDatabase } from '../../../types';
import { Badge, type Tone } from '../../ui/Badge';
import { Button, IconButton } from '../../ui/Button';
import { ConfirmDialog } from '../../ui/Dialog';
import { EmptyState } from '../../ui/EmptyState';
import { Field } from '../../ui/Field';
import { Input } from '../../ui/Input';
import { Panel, PanelHeader } from '../../ui/Panel';
import { Select } from '../../ui/Select';
import { SegmentedControl } from '../../ui/SegmentedControl';
import { Skeleton } from '../../ui/Skeleton';
import { useToast } from '../../ui/Toast';

const NONE = '__none__';
const TECHNOLOGIES = [
  { value: 'mssql', label: 'Microsoft SQL Server' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
];
const CONNECTION_MODES = (['ro', 'ro_rw', 'ro_rw_ddl'] as const).map((value) => ({
  value,
  label: CONNECTION_MODE[value].label,
}));
const statusLabel: Record<OwnerUser['status'], string> = {
  pending: 'Aktivasyon bekliyor',
  active: 'Aktif',
  disabled: 'Devre dışı',
};
const statusTone: Record<OwnerUser['status'], Tone> = {
  pending: 'warning',
  active: 'success',
  disabled: 'danger',
};

const EMPTY_FORM = {
  servername: '',
  database_name: '',
  technology: 'mssql',
  connection_mode: 'ro' as ConnectionMode,
  initial_admin_user_id: NONE,
  username_ro: '',
  password_ro: '',
  username_rw: '',
  password_rw: '',
  username_ddl: '',
  password_ddl: '',
};

export const OwnerTab: React.FC = () => {
  const toast = useToast();
  const [users, setUsers] = useState<OwnerUser[]>([]);
  const [databases, setDatabases] = useState<RegisteredDatabase[]>([]);
  const [admins, setAdmins] = useState<DatabaseAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyUser, setBusyUser] = useState<number | null>(null);
  const [disableTarget, setDisableTarget] = useState<OwnerUser | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<DatabaseAdmin | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [adding, setAdding] = useState(false);
  const [grantDatabaseId, setGrantDatabaseId] = useState(NONE);
  const [grantUserId, setGrantUserId] = useState(NONE);
  const [changingAdmin, setChangingAdmin] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextUsers, nextDatabases, nextAdmins] = await Promise.all([
        api.ownerUsers(),
        api.ownerDatabases(),
        api.databaseAdmins(),
      ]);
      setUsers(nextUsers);
      setDatabases(nextDatabases);
      setAdmins(nextAdmins);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const activeUsers = useMemo(() => users.filter((user) => user.is_active), [users]);
  const userOptions = useMemo(
    () => [
      { value: NONE, label: 'Kullanıcı seçin', disabled: true },
      ...activeUsers.map((user) => ({ value: String(user.id), label: `${user.username} · ${user.email}` })),
    ],
    [activeUsers],
  );
  const databaseOptions = useMemo(
    () => [
      { value: NONE, label: 'Veritabanı seçin', disabled: true },
      ...databases.map((database) => ({
        value: String(database.id),
        label: `${database.database_name} · ${database.servername}`,
      })),
    ],
    [databases],
  );

  const enableUser = async (user: OwnerUser) => {
    setBusyUser(user.id);
    try {
      await api.enableOwnerUser(user.id);
      toast.success('Kullanıcı etkinleştirildi', `${user.username} artık giriş yapabilir`);
      await load();
    } catch (caught) {
      toast.error('Kullanıcı etkinleştirilemedi', errorMessage(caught));
    } finally {
      setBusyUser(null);
    }
  };

  const disableUser = async () => {
    if (!disableTarget) return;
    setBusyUser(disableTarget.id);
    try {
      await api.disableOwnerUser(disableTarget.id);
      toast.success('Kullanıcı devre dışı bırakıldı', `${disableTarget.username} oturumları sonlandırıldı`);
      setDisableTarget(null);
      await load();
    } catch (caught) {
      toast.error('Kullanıcı devre dışı bırakılamadı', errorMessage(caught));
    } finally {
      setBusyUser(null);
    }
  };

  const addDatabase = async (event: React.FormEvent) => {
    event.preventDefault();
    if (form.initial_admin_user_id === NONE) return;
    setAdding(true);
    try {
      const created = await api.createOwnerDatabase({
        servername: form.servername.trim(),
        database_name: form.database_name.trim(),
        tech_name: form.technology,
        connection_mode: form.connection_mode,
        initial_admin_user_id: Number(form.initial_admin_user_id),
        username_ro: form.username_ro.trim(),
        password_ro: form.password_ro,
        ...(form.connection_mode !== 'ro'
          ? { username_rw: form.username_rw.trim(), password_rw: form.password_rw }
          : {}),
        ...(form.connection_mode === 'ro_rw_ddl'
          ? { username_ddl: form.username_ddl.trim(), password_ddl: form.password_ddl }
          : {}),
      });
      setForm(EMPTY_FORM);
      toast.success('Veritabanı kaydedildi', `Kayıt kimliği: ${created.db_uuid}`);
      await load();
    } catch (caught) {
      toast.error('Veritabanı kaydedilemedi', errorMessage(caught));
    } finally {
      setAdding(false);
    }
  };

  const grantAdmin = async () => {
    if (grantDatabaseId === NONE || grantUserId === NONE) return;
    setChangingAdmin(true);
    try {
      await api.grantDatabaseAdmin(Number(grantDatabaseId), Number(grantUserId));
      toast.success('DB ADMIN atandı', 'Kullanıcının mevcut veri rolleri korundu.');
      setGrantUserId(NONE);
      await load();
    } catch (caught) {
      toast.error('DB ADMIN atanamadı', errorMessage(caught));
    } finally {
      setChangingAdmin(false);
    }
  };

  const revokeAdmin = async () => {
    if (!revokeTarget) return;
    setChangingAdmin(true);
    try {
      await api.revokeDatabaseAdmin(revokeTarget.database_id, revokeTarget.user_id);
      toast.success('DB ADMIN kaldırıldı', `${revokeTarget.username} · ${revokeTarget.database_name}`);
      setRevokeTarget(null);
      await load();
    } catch (caught) {
      toast.error('DB ADMIN kaldırılamadı', errorMessage(caught));
    } finally {
      setChangingAdmin(false);
    }
  };

  const formComplete =
    Boolean(form.servername.trim() && form.database_name.trim()) &&
    form.initial_admin_user_id !== NONE &&
    Boolean(form.username_ro.trim() && form.password_ro) &&
    (form.connection_mode === 'ro' || Boolean(form.username_rw.trim() && form.password_rw)) &&
    (form.connection_mode !== 'ro_rw_ddl' || Boolean(form.username_ddl.trim() && form.password_ddl));

  if (loading && users.length === 0 && databases.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-16 w-full rounded-sm" />)}
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={<WarningCircleIcon size={18} />}
        title="OWNER verileri alınamadı"
        description={error}
        action={<Button onClick={() => void load()}>Yeniden dene</Button>}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Panel flush as="section">
        <PanelHeader
          title="Platform kullanıcıları"
          description="Hesap yaşam döngüsünü yönetin. OWNER yetkisi yalnız sunucu bootstrap komutuyla verilir."
          actions={
            <IconButton label="OWNER verilerini yenile" size="sm" onClick={() => void load()}>
              <ArrowClockwiseIcon size={14} className={cn(loading && 'animate-spin-slow')} />
            </IconButton>
          }
        />
        {users.length === 0 ? (
          <EmptyState
            size="sm"
            icon={<UserCircleIcon size={18} />}
            title="Kayıtlı kullanıcı yok"
            description="İzinli şirket domaininden gelen ilk başvuru burada görünür."
          />
        ) : (
          <ul className="divide-y divide-line">
            {users.map((user) => (
              <li key={user.id} className="grid grid-cols-1 items-center gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_auto_auto]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-[13px] font-medium text-fg">{user.username}</span>
                    <Badge tone={statusTone[user.status]} dot>{statusLabel[user.status]}</Badge>
                    {user.is_platform_owner && <Badge tone="accent">OWNER</Badge>}
                  </div>
                  <p className="truncate font-mono text-[11.5px] text-subtle">{user.email}</p>
                </div>
                <span className="text-[12px] text-subtle">
                  {user.is_platform_owner ? 'Platform yönetişim yetkisi' : 'DB erişimi ayrıca atanır'}
                </span>
                {user.is_active ? (
                  <Button size="sm" variant="danger" onClick={() => setDisableTarget(user)}>
                    Devre dışı bırak
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    icon={<CheckCircleIcon size={14} />}
                    loading={busyUser === user.id}
                    onClick={() => void enableUser(user)}
                  >
                    Etkinleştir
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel flush as="section">
          <PanelHeader
            title="Veritabanı kaydet"
            description="Kayıt ve ilk aktif DB ADMIN ataması tek işlemde tamamlanır."
          />
          <form onSubmit={addDatabase} className="flex flex-col gap-3.5 p-4">
            <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
              <Field label="Sunucu adresi" required>
                <Input value={form.servername} onChange={(event) => setForm({ ...form, servername: event.target.value })} required className="font-mono" placeholder="sql-prod-01.sirket.local" />
              </Field>
              <Field label="Veritabanı adı" required>
                <Input value={form.database_name} onChange={(event) => setForm({ ...form, database_name: event.target.value })} required className="font-mono" placeholder="Satis" />
              </Field>
              <Field label="Teknoloji">
                <Select value={form.technology} onValueChange={(technology) => setForm({ ...form, technology })} options={TECHNOLOGIES} />
              </Field>
              <Field label="İlk DB ADMIN" required hint="Yalnız aktif kullanıcılar listelenir.">
                <Select value={form.initial_admin_user_id} onValueChange={(initial_admin_user_id) => setForm({ ...form, initial_admin_user_id })} options={userOptions} />
              </Field>
            </div>
            <Field label="Bağlantı modu" required hint="Seçilmeyen kademedeki sorgular reddedilir.">
              <SegmentedControl value={form.connection_mode} onChange={(connection_mode) => setForm({ ...form, connection_mode })} segments={CONNECTION_MODES} label="Bağlantı modu" className="w-full overflow-x-auto" />
            </Field>
            <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
              <Field label="RO kullanıcı adı" required><Input value={form.username_ro} onChange={(event) => setForm({ ...form, username_ro: event.target.value })} required autoComplete="off" /></Field>
              <Field label="RO şifre" required><Input type="password" value={form.password_ro} onChange={(event) => setForm({ ...form, password_ro: event.target.value })} required autoComplete="new-password" /></Field>
              {form.connection_mode !== 'ro' && (
                <>
                  <Field label="RW kullanıcı adı" required><Input value={form.username_rw} onChange={(event) => setForm({ ...form, username_rw: event.target.value })} required autoComplete="off" /></Field>
                  <Field label="RW şifre" required><Input type="password" value={form.password_rw} onChange={(event) => setForm({ ...form, password_rw: event.target.value })} required autoComplete="new-password" /></Field>
                </>
              )}
              {form.connection_mode === 'ro_rw_ddl' && (
                <>
                  <Field label="DDL kullanıcı adı" required><Input value={form.username_ddl} onChange={(event) => setForm({ ...form, username_ddl: event.target.value })} required autoComplete="off" /></Field>
                  <Field label="DDL şifre" required><Input type="password" value={form.password_ddl} onChange={(event) => setForm({ ...form, password_ddl: event.target.value })} required autoComplete="new-password" /></Field>
                </>
              )}
            </div>
            <Button type="submit" variant="primary" icon={<PlusIcon size={14} />} loading={adding} disabled={!formComplete} className="self-start">
              Veritabanını ve ilk ADMIN’i kaydet
            </Button>
          </form>
        </Panel>

        <Panel flush as="section">
          <PanelHeader
            title="DB ADMIN atamaları"
            description={`${formatCount(databases.length)} veritabanı · ${formatCount(admins.length)} ADMIN ataması`}
          />
          <div className="grid grid-cols-1 gap-3 border-b border-line p-4 sm:grid-cols-[1fr_1fr_auto]">
            <Field label="Veritabanı"><Select value={grantDatabaseId} onValueChange={setGrantDatabaseId} options={databaseOptions} /></Field>
            <Field label="Aktif kullanıcı"><Select value={grantUserId} onValueChange={setGrantUserId} options={userOptions} /></Field>
            <Button className="self-end" icon={<ShieldCheckIcon size={14} />} loading={changingAdmin} disabled={grantDatabaseId === NONE || grantUserId === NONE} onClick={() => void grantAdmin()}>
              ADMIN ata
            </Button>
          </div>
          {admins.length === 0 ? (
            <EmptyState size="sm" icon={<DatabaseIcon size={18} />} title="DB ADMIN ataması yok" description="Her kayıtlı veritabanında en az bir ADMIN bulunmalıdır." />
          ) : (
            <ul className="max-h-[420px] divide-y divide-line overflow-y-auto">
              {admins.map((admin) => (
                <li key={`${admin.database_id}:${admin.user_id}`} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <DatabaseIcon size={15} className="text-subtle" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-[12.5px] text-fg">{admin.database_name}</span>
                    <span className="block truncate text-[12px] text-subtle">{admin.username}</span>
                  </span>
                  <Badge tone="accent">ADMIN</Badge>
                  <Button size="sm" variant="danger" onClick={() => setRevokeTarget(admin)}>Kaldır</Button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <ConfirmDialog
        open={disableTarget !== null}
        onOpenChange={(open) => !open && setDisableTarget(null)}
        title="Kullanıcı devre dışı bırakılsın mı?"
        description="Tüm aktif oturumları iptal edilir. Son aktif OWNER koruması sunucuda ayrıca uygulanır."
        confirmLabel="Devre dışı bırak"
        destructive
        busy={disableTarget !== null && busyUser === disableTarget.id}
        onConfirm={() => void disableUser()}
      >
        {disableTarget && <p className="font-mono text-[12px] text-fg">{disableTarget.username} · {disableTarget.email}</p>}
      </ConfirmDialog>

      <ConfirmDialog
        open={revokeTarget !== null}
        onOpenChange={(open) => !open && setRevokeTarget(null)}
        title="DB ADMIN yetkisi kaldırılsın mı?"
        description="Kullanıcının diğer veri rolleri korunur. Son DB ADMIN sunucu tarafından kaldırılamaz."
        confirmLabel="ADMIN yetkisini kaldır"
        destructive
        busy={changingAdmin}
        onConfirm={() => void revokeAdmin()}
      >
        {revokeTarget && <p className="font-mono text-[12px] text-fg">{revokeTarget.database_name} · {revokeTarget.username}</p>}
      </ConfirmDialog>
    </div>
  );
};
