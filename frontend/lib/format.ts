const NUMBER_FORMAT = new Intl.NumberFormat('tr-TR');

/** Groups digits so a 1.2 million row count is readable at a glance. */
export function formatCount(value: number): string {
  return NUMBER_FORMAT.format(value);
}

/** Approximate byte size of a result payload, for the export affordance. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Milliseconds rendered the way an engineer reads a query timing. */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} sn`;
}

/**
 * Renders one result-grid cell. Null is a distinct value from an empty string
 * and the grid must never let the two look identical.
 */
export function formatCell(value: unknown): { text: string; kind: 'null' | 'empty' | 'value' } {
  if (value === null || value === undefined) return { text: 'NULL', kind: 'null' };
  if (typeof value === 'string' && value.length === 0) return { text: 'boş', kind: 'empty' };
  if (typeof value === 'object') return { text: JSON.stringify(value), kind: 'value' };
  return { text: String(value), kind: 'value' };
}

/** True when a column should be right-aligned in the result grid. */
export function isNumericColumn(rows: Record<string, unknown>[], column: string): boolean {
  let seen = 0;
  for (const row of rows.slice(0, 40)) {
    const v = row[column];
    if (v === null || v === undefined || v === '') continue;
    if (typeof v !== 'number' && !(typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v))) return false;
    seen += 1;
  }
  return seen > 0;
}
