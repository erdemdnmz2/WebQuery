import React from 'react';
import {
  DownloadSimpleIcon,
  FileCsvIcon,
  FileXlsIcon,
  ShieldCheckIcon,
  TableIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react';
import { cn } from '../../lib/cn';
import { formatCount, formatDuration } from '../../lib/format';
import { exportToCsv, exportToXlsx } from '../../lib/export';
import { summarise, type ExecutionOutcome } from '../../lib/execution';
import { Button } from '../ui/Button';
import { DataGrid } from '../ui/DataGrid';
import { EmptyState } from '../ui/EmptyState';
import { PanelHeader } from '../ui/Panel';
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../ui/Menu';
import { Skeleton } from '../ui/Skeleton';

export interface ResultPanelProps {
  outcome: ExecutionOutcome | null;
  running: boolean;
  /** Wall-clock time of the last completed run. */
  durationMs: number | null;
  exportBaseName: string;
  emptyTitle: string;
  emptyDescription: string;
  className?: string;
  title?: string;
}

/**
 * Renders every outcome a query can have: running, sent for approval, failed,
 * succeeded with no rows, succeeded with rows. The panel never shows a blank
 * area without saying why it is blank.
 */
export const ResultPanel: React.FC<ResultPanelProps> = ({
  outcome,
  running,
  durationMs,
  exportBaseName,
  emptyTitle,
  emptyDescription,
  className,
  title = 'Sonuçlar',
}) => {
  const rows = outcome?.rows ?? [];
  const hasRows = rows.length > 0;
  const summary = outcome ? summarise(outcome, formatCount) : null;

  const description = running
    ? 'Sorgu çalışıyor'
    : summary
      ? `${summary}${durationMs !== null ? ` · ${formatDuration(durationMs)}` : ''}`
      : undefined;

  return (
    <section
      className={cn('flex min-h-0 min-w-0 flex-1 flex-col rounded-md border border-line bg-surface', className)}
      aria-busy={running || undefined}
    >
      <PanelHeader
        dense
        title={title}
        description={description}
        actions={
          hasRows ? (
            <Menu>
              <MenuTrigger asChild>
                <Button size="sm" icon={<DownloadSimpleIcon size={13} />}>
                  Dışa aktar
                </Button>
              </MenuTrigger>
              <MenuContent>
                <MenuItem icon={<FileXlsIcon size={15} />} onSelect={() => void exportToXlsx(rows, exportBaseName)}>
                  Excel (.xlsx)
                </MenuItem>
                <MenuItem icon={<FileCsvIcon size={15} />} onSelect={() => exportToCsv(rows, exportBaseName)}>
                  CSV (.csv)
                </MenuItem>
              </MenuContent>
            </Menu>
          ) : undefined
        }
      />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-b-md bg-sunken">
        {running ? (
          <div className="flex flex-col gap-2 p-4" aria-live="polite">
            <span className="sr-only">Sorgu çalışıyor</span>
            <Skeleton className="h-6 w-full" />
            {['w-full', 'w-[92%]', 'w-full', 'w-[78%]', 'w-[95%]', 'w-[64%]', 'w-[86%]'].map((width, index) => (
              <Skeleton key={index} className={cn('h-4', width)} />
            ))}
          </div>
        ) : outcome?.sentForApproval ? (
          /*
           * Not a failure. The analyzer flagged the statement, saved it as a
           * workspace and routed it to an administrator, so this reads as a
           * pending state rather than an error.
           */
          <div className="overflow-auto p-4" role="status">
            <div className="rounded-sm border border-warning-line bg-warning-soft p-3.5">
              <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-warning">
                <ShieldCheckIcon size={14} weight="fill" />
                Sorgu onaya gönderildi
              </p>
              <p className="mt-2 text-[12.5px] leading-relaxed text-warning">
                Risk analizi bu ifadeyi doğrudan çalıştırmadı. Sorgu çalışma alanlarınıza kaydedildi ve
                yönetici incelemesine düştü. Karar verildiğinde listede durumu değişecek.
              </p>
              {outcome.error && (
                <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-warning">
                  {outcome.error}
                </pre>
              )}
            </div>
          </div>
        ) : outcome?.error ? (
          <div className="overflow-auto p-4" role="alert">
            <div className="rounded-sm border border-danger-line bg-danger-soft p-3.5">
              <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-danger">
                <WarningCircleIcon size={14} weight="fill" />
                Sorgu çalıştırılamadı
              </p>
              <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-danger">
                {outcome.error}
              </pre>
              {outcome.traceId && (
                <p className="mt-2 font-mono text-[11.5px] text-danger">İz kaydı: {outcome.traceId}</p>
              )}
            </div>
          </div>
        ) : hasRows ? (
          <DataGrid
            rows={rows}
            maskedColumns={outcome?.maskedColumns}
            truncated={outcome?.truncated}
            truncationNote={
              outcome?.truncated && outcome.limit !== null
                ? `Sunucu ilk ${formatCount(outcome.limit)} satırı döndürdü. Tamamı için sorguyu daraltın.`
                : undefined
            }
            className="flex-1"
          />
        ) : outcome?.affectedRows !== null && outcome?.affectedRows !== undefined ? (
          <EmptyState
            icon={<TableIcon size={18} />}
            title="Sorgu tamamlandı"
            description={`${formatCount(outcome.affectedRows)} satır etkilendi. Bu ifade sonuç kümesi döndürmez.`}
          />
        ) : outcome ? (
          <EmptyState
            icon={<TableIcon size={18} />}
            title="Sonuç kümesi boş"
            description="Sorgu başarıyla çalıştı ancak koşullara uyan satır bulunamadı."
          />
        ) : (
          <EmptyState icon={<TableIcon size={18} />} title={emptyTitle} description={emptyDescription} />
        )}
      </div>
    </section>
  );
};
