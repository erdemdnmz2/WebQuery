import React, { useCallback, useEffect, useState } from 'react';
import { ArrowClockwiseIcon, CrownIcon, LockKeyIcon, ShieldCheckIcon } from '@phosphor-icons/react';
import { api, errorMessage, UnauthorizedError } from '../services/api';
import { cn } from '../lib/cn';
import { usePersistentState } from '../lib/hooks';
import { useSession } from '../lib/session';
import { ApprovalsTab } from '../components/app/admin/ApprovalsTab';
import { MaskingTab } from '../components/app/admin/MaskingTab';
import { OwnerTab } from '../components/app/owner/OwnerTab';
import { IconButton } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { SegmentedControl } from '../components/ui/SegmentedControl';
import type { PendingQuery } from '../types';

type Tab = 'approvals' | 'masking' | 'owner';

const Admin: React.FC = () => {
  const { user, status } = useSession();
  const [tab, setTab] = usePersistentState<Tab>('webquery.admin.tab', 'approvals');
  const [requests, setRequests] = useState<PendingQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const visibleTab: Tab = user?.is_platform_owner && !user.is_admin
    ? 'owner'
    : tab === 'owner' && !user?.is_platform_owner
      ? 'approvals'
      : tab;

  const loadRequests = useCallback(async () => {
    if (!user?.is_admin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setRequests(await api.pendingQueries());
    } catch (caught) {
      if (!(caught instanceof UnauthorizedError)) setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [user?.is_admin]);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  if (status === 'authenticated' && user && !user.is_admin && !user.is_platform_owner) {
    return (
      <EmptyState
        className="my-auto"
        icon={<LockKeyIcon size={18} />}
        title="Bu bölüme erişiminiz yok"
        description="Yönetim paneli yalnızca yönetici hesapları için açıktır."
      />
    );
  }

  return (
    <div className="flex flex-col gap-5 animate-enter">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1>Yönetim</h1>
          <p className="mt-1 max-w-[62ch] text-[13px] text-subtle">
            Veritabanı yönetişimi, riskli sorgu talepleri ve kolon bazlı maskeleme kuralları.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {user?.is_admin && (
            <IconButton label="Bekleyen talepleri yenile" onClick={() => void loadRequests()}>
              <ArrowClockwiseIcon size={15} className={cn(loading && 'animate-spin-slow')} />
            </IconButton>
          )}
          <SegmentedControl<Tab>
            label="Yönetim bölümü"
            value={visibleTab}
            onChange={setTab}
            segments={[
              ...(user?.is_admin
                ? [
                    {
                      value: 'approvals' as const,
                      label: 'Onaylar',
                      icon: <ShieldCheckIcon size={14} />,
                      count: requests.length,
                    },
                    {
                      value: 'masking' as const,
                      label: 'Maskeleme',
                      icon: <LockKeyIcon size={14} />,
                    },
                  ]
                : []),
              ...(user?.is_platform_owner
                ? [{ value: 'owner' as const, label: 'Platform OWNER', icon: <CrownIcon size={14} /> }]
                : []),
            ]}
          />
        </div>
      </header>

      {visibleTab === 'approvals' ? (
        <ApprovalsTab requests={requests} loading={loading} error={error} reload={() => void loadRequests()} />
      ) : visibleTab === 'masking' ? (
        <MaskingTab />
      ) : (
        <OwnerTab />
      )}
    </div>
  );
};

export default Admin;
