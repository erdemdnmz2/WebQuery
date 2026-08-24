import type { ResultRow } from '../types';

function safeFileName(name: string): string {
  return (
    name
      .trim()
      .replace(/[^\p{L}\p{N}._-]+/gu, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 60) || 'sonuc'
  );
}

/**
 * Downloads the result set as a single-sheet workbook. The spreadsheet
 * library is pulled in on demand so it never lands in the initial bundle.
 */
export async function exportToXlsx(rows: ResultRow[], baseName: string): Promise<void> {
  const XLSX = await import('xlsx');
  const sheet = XLSX.utils.json_to_sheet(rows);
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, sheet, 'Sonuclar');
  XLSX.writeFile(book, `${safeFileName(baseName)}.xlsx`);
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
