import React, { useCallback, useEffect, useState } from 'react';
import { ArrowClockwiseIcon, CheckCircleIcon, UserCircleIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { api, errorMessage } from '../../../services/api';
import { cn } from '../../../lib/cn';
import { Badge, type Tone } from '../../ui/Badge';
import { Button, IconButton } from '../../ui/Button';
import { EmptyState } from '../../ui/EmptyState';
import { Panel, PanelHeader } from '../../ui/Panel';
import { Skeleton } from '../../ui/Skeleton';
import { useToast } from '../../ui/Toast';
import type { AdminUser } from '../../../types';

const statusLabel: Record<AdminUser['status'], string> = {
  pending: 'Aktivasyon bekliyor',
  active: 'Aktif',
  disabled: 'Devre dışı',
};

const statusTone: Record<AdminUser['status'], Tone> = {
  pending: 'warning',
  active: 'success',
  disabled: 'danger',
};

export const UsersTab: React.FC = () => {
  const toast = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enabling, setEnabling] = useState<number | null>(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await api.platformUsers());
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const enableUser = async (user: AdminUser) => {
    setEnabling(user.id);
    try {
      await api.enableUser(user.id);
      toast.success('Kullanıcı etkinleştirildi', `${user.username} artık giriş yapabilir`);
      await loadUsers();
    } catch (caught) {
      toast.error('Kullanıcı etkinleştirilemedi', errorMessage(caught));
    } finally {
      setEnabling(null);
    }
  };

  return (
    <Panel flush as="section">
      <PanelHeader
        title="Kullanıcılar"
        description="Şirket domainiyle gelen hesapları etkinleştirin. Veritabanı erişimi ayrıca verilir."
        actions={
          <IconButton label="Kullanıcı listesini yenile" size="sm" onClick={() => void loadUsers()}>
            <ArrowClockwiseIcon size={14} className={cn(loading && 'animate-spin-slow')} />
          </IconButton>
        }
      />

      {loading && users.length === 0 ? (
        <div className="flex flex-col gap-2 p-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full rounded-sm" />
          ))}
        </div>
      ) : error ? (
        <EmptyState
          className="m-4"
          icon={<WarningCircleIcon size={18} />}
          title="Kullanıcılar alınamadı"
          description={error}
          action={<Button onClick={() => void loadUsers()}>Yeniden dene</Button>}
        />
      ) : users.length === 0 ? (
        <EmptyState
          className="m-4"
          icon={<UserCircleIcon size={18} />}
          title="Kayıtlı kullanıcı yok"
          description="İzinli şirket domainindeki ilk kayıt başvurusu burada görünür."
        />
      ) : (
        <ul className="divide-y divide-line">
          {users.map((user) => (
            <li key={user.id} className="grid grid-cols-1 items-center gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_15rem_auto]">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[13px] font-medium text-fg">{user.username}</span>
                  <Badge tone={statusTone[user.status]} dot>{statusLabel[user.status]}</Badge>
                </div>
                <p className="truncate font-mono text-[11.5px] text-subtle">{user.email}</p>
              </div>
              <span className="text-[12px] text-subtle">
                {user.status === 'pending'
                  ? 'Aktivasyon sonrası erişim rolü ayrıca atanır.'
                  : user.status === 'active'
                    ? 'Giriş yapabilir; DB erişimi ayrı politikadır.'
                    : 'Hesap yeniden etkinleştirilebilir.'}
              </span>
              {user.status !== 'active' ? (
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<CheckCircleIcon size={14} />}
                  loading={enabling === user.id}
                  onClick={() => void enableUser(user)}
                >
                  Etkinleştir
                </Button>
              ) : (
                <span className="text-right text-[12px] text-subtle">Hazır</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
};
