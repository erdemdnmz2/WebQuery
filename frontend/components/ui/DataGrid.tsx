import React, { useEffect, useMemo, useState } from 'react';
import { ArrowsOutSimpleIcon } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';
import { formatCell, formatCount, isNumericColumn } from '../../lib/format';
import { Button } from './Button';

const PAGE = 200;

export interface DataGridProps {
  rows: Record<string, unknown>[];
  className?: string;
  /** Marks columns the backend masked, so the reader knows the value is hidden. */
  maskedColumns?: string[];
  /** Shown when the backend capped the result set. */
  truncated?: boolean;
}

/**
 * Result grid for query output. Columns are typed from the first rows so
 * numbers align right on tabular figures, NULL is visually distinct from an
 * empty string, and long results render incrementally instead of putting
 * tens of thousands of cells into the DOM at once.
 */
export const DataGrid: React.FC<DataGridProps> = ({ rows, className, maskedColumns = [], truncated }) => {
  const [visible, setVisible] = useState(PAGE);

  // A fresh result set starts at the first page rather than inheriting the
  // expansion of the previous one.
  useEffect(() => setVisible(PAGE), [rows]);

  const columns = useMemo(() => (rows.length > 0 ? Object.keys(rows[0]) : []), [rows]);
  const numericColumns = useMemo(() => {
    const set = new Set<string>();
    for (const column of columns) if (isNumericColumn(rows, column)) set.add(column);
    return set;
  }, [columns, rows]);

  const maskedSet = useMemo(
    () => new Set(maskedColumns.map((column) => column.toLocaleLowerCase('tr'))),
    [maskedColumns],
  );

  const shown = rows.slice(0, visible);

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <div
        tabIndex={0}
        role="region"
        aria-label="Sorgu sonuçları"
        className="min-h-0 flex-1 overflow-auto focus-visible:outline-none"
      >
        <table className="w-full border-separate border-spacing-0 text-left">
          <thead>
            <tr>
              <th
                scope="col"
                className="grid-head-cell w-12 px-3 py-2 text-right font-mono text-[11px] font-normal text-subtle"
              >
                #
              </th>
              {columns.map((column) => {
                const masked = maskedSet.has(column.toLocaleLowerCase('tr'));
                return (
                  <th
                    key={column}
                    scope="col"
                    className={cn(
                      'grid-head-cell whitespace-nowrap px-3 py-2 font-mono text-[11.5px] font-medium text-muted',
                      numericColumns.has(column) && 'text-right',
                    )}
                  >
                    {column}
                    {masked && (
                      <span className="ml-1.5 rounded-xs bg-warning-soft px-1 text-[9.5px] font-medium text-warning">
                        maskeli
                      </span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, rowIndex) => (
              <tr key={rowIndex} className="group">
                <td className="border-b border-line px-3 py-1.5 text-right align-top font-mono text-[11px] text-subtle group-hover:bg-hover">
                  {rowIndex + 1}
                </td>
                {columns.map((column) => {
                  const { text, kind } = formatCell(row[column]);
                  return (
                    <td
                      key={column}
                      title={kind === 'value' ? text : undefined}
                      className={cn(
                        'max-w-[380px] truncate border-b border-line px-3 py-1.5 align-top text-[12.5px] group-hover:bg-hover',
                        numericColumns.has(column) && 'text-right font-mono',
                        kind === 'value' ? 'text-fg' : 'text-subtle italic',
                      )}
                    >
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(visible < rows.length || truncated) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface px-3 py-2">
          <p className="text-[12px] text-subtle">
            {formatCount(shown.length)} / {formatCount(rows.length)} satır gösteriliyor
            {truncated && ' · sonuç sunucu tarafında kırpıldı'}
          </p>
          {visible < rows.length && (
            <Button size="sm" icon={<ArrowsOutSimpleIcon size={13} />} onClick={() => setVisible((v) => v + PAGE)}>
              {formatCount(Math.min(PAGE, rows.length - visible))} satır daha
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
