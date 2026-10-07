import React, { useState } from 'react';
import { CheckCircleIcon, MagnifyingGlassIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { cn } from '../../../lib/cn';
import { Badge, Identifier } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { EmptyState } from '../../ui/EmptyState';
import { Panel } from '../../ui/Panel';
import { SkeletonRows } from '../../ui/Skeleton';
import { ReviewDialog } from './ReviewDialog';
import type { PendingQuery } from '../../../types';

export interface ApprovalsTabProps {
  requests: PendingQuery[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export const ApprovalsTab: React.FC<ApprovalsTabProps> = ({ requests, loading, error, reload }) => {
  const [selected, setSelected] = useState<PendingQuery | null>(null);

  return (
    <>
      <Panel flush>
        {loading && requests.length === 0 ? (
          <SkeletonRows rows={3} />
        ) : error ? (
          <EmptyState
            icon={<WarningCircleIcon size={18} />}
            title="Bekleyen talepler yüklenemedi"
            description={error}
            action={<Button onClick={reload}>Yeniden dene</Button>}
          />
        ) : requests.length === 0 ? (
          <EmptyState
            icon={<CheckCircleIcon size={18} />}
            title="Bekleyen talep yok"
            description="Riskli olarak sınıflandırılan her sorgu burada listelenir ve karar verilene kadar çalıştırılamaz."
          />
        ) : (
          <ul>
            {requests.map((request, index) => (
              <li
                key={request.workspace_id}
                className={cn(
                  'flex flex-wrap items-start gap-x-4 gap-y-3 px-4 py-3.5',
                  'transition-colors duration-[var(--dur-fast)] hover:bg-hover',
                  index > 0 && 'border-t border-line',
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13.5px] font-medium text-fg">{request.username}</span>
                    {request.risk_type ? (
                      <Badge tone="danger">{request.risk_type}</Badge>
                    ) : (
                      <Badge tone="warning">Onay bekliyor</Badge>
                    )}
                    <Identifier>{request.servername}</Identifier>
                    <span aria-hidden className="text-faint">
                      /
                    </span>
                    <Identifier>{request.database}</Identifier>
                  </div>

                  <pre className="mt-2 max-w-full overflow-hidden truncate rounded-sm border border-line bg-sunken px-3 py-2 font-mono text-[12px] text-muted">
                    {request.query}
                  </pre>
                </div>

                <Button
                  icon={<MagnifyingGlassIcon size={13} />}
                  className="mt-0.5"
                  onClick={() => setSelected(request)}
                >
                  İncele
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <ReviewDialog
        request={selected}
        onClose={() => setSelected(null)}
        onDecided={() => {
          setSelected(null);
          reload();
        }}
      />
    </>
  );
};
