import type { ConnectionMode, DatabaseInfo, TargetDatabase } from '../types';

/**
 * A single addressable database, flattened out of the nested
 * /api/database_information payload.
 *
 * The API identifies a target by uuid; servername and databaseName exist so a
 * person can recognise it. Every execution call must send the uuid.
 */
export interface Target {
  uuid: string;
  servername: string;
  databaseName: string;
  technology?: string;
  /** What this user may execute here; see TargetDatabase.capability. */
  capability?: ConnectionMode | null;
}

/** Servers the user has at least one granted database on, alphabetically. */
export function serverNames(info: DatabaseInfo): string[] {
  return Object.keys(info).sort((a, b) => a.localeCompare(b, 'tr'));
}

export function databasesOf(info: DatabaseInfo, servername: string): TargetDatabase[] {
  return info[servername]?.databases ?? [];
}

export function technologyOf(info: DatabaseInfo, servername: string): string | undefined {
  return info[servername]?.technology;
}

/** Every grant as one flat list, for search surfaces such as the palette. */
export function listTargets(info: DatabaseInfo): Target[] {
  const targets: Target[] = [];
  for (const servername of serverNames(info)) {
    const server = info[servername];
    for (const database of server.databases) {
      targets.push({
        uuid: database.uuid,
        servername,
        databaseName: database.name,
        technology: server.technology,
        capability: database.capability,
      });
    }
  }
  return targets;
}

export function findTarget(info: DatabaseInfo, uuid: string): Target | null {
  if (!uuid) return null;
  return listTargets(info).find((target) => target.uuid === uuid) ?? null;
}

/**
 * Recovers a uuid from a server/database pair.
 *
 * A workspace stores both its uuid and its display names, but the backend
 * resolves the uuid by name lookup and returns an empty string when the
 * registration has since changed. Falling back to the names keeps an older
 * workspace runnable instead of failing with an unhelpful validation error.
 */
export function resolveUuid(info: DatabaseInfo, servername: string, databaseName: string): string {
  const match = databasesOf(info, servername).find((database) => database.name === databaseName);
  return match?.uuid ?? '';
}

/** True when the user has no grants at all, which needs its own empty state. */
export function hasNoTargets(info: DatabaseInfo): boolean {
  return listTargets(info).length === 0;
}
