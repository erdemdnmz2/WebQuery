import type { ResultRow } from '../types';

function safeFileName(name: string): string {
  return (
    name
      .trim()
      .replace(/[^\p{L}\p{N}._-]+/gu, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 60) || "results"
  );
}

/**
 * Downloads the result set as a single-sheet workbook. The spreadsheet
 * library is pulled in on demand so it never lands in the initial bundle.
 */
export async function exportToXlsx(rows: ResultRow[], baseName: string): Promise<void> {
  const columns = Object.keys(rows[0] ?? {});
  const toCellValue = (value: unknown): string | number | boolean | Date | null => {
    if (value === null || value === undefined) return null;
    if (value instanceof Date || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return value;
    }
    return String(value);
  };
  const writeXlsxFile = (await import('write-excel-file/browser')).default;

  await writeXlsxFile([
    columns,
    ...rows.map((row) => columns.map((column) => toCellValue(row[column]))),
  ]).toFile(`${safeFileName(baseName)}.xlsx`);
}

/** Downloads the result set as RFC 4180 CSV with a UTF-8 BOM for Excel. */
export function exportToCsv(rows: ResultRow[], baseName: string): void {
  if (rows.length === 0) return;
  const columns = Object.keys(rows[0]);
  const escape = (value: unknown) => {
    if (value === null || value === undefined) return '';
    return `"${String(value).replace(/"/g, '""')}"`;
  };

  const lines = [columns.map(escape).join(',')];
  for (const row of rows) lines.push(columns.map((column) => escape(row[column])).join(','));

  const blob = new Blob([`﻿${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${safeFileName(baseName)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
