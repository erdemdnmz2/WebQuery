import type { Tone } from '../components/ui/Badge';
import type { ConnectionMode } from '../types';

/**
 * A registration provisions a hierarchical set of target accounts (ro, ro+rw,
 * ro+rw+ddl). The same enum is read two ways, and the two must not be mixed up:
 *
 * - In the admin panel it is the *registration mode*: which DBA-provided
 *   accounts this database record holds. It is a configuration fact.
 * - In the SQL editor it is the *capability*: that mode narrowed by the
 *   viewer's own role. It is a per-user fact, and the backend computes it.
 *
 * Labelling them from one file keeps a badge from meaning two things.
 */

export interface ModeMeta {
  label: string;
  tone: Tone;
  /** One line saying what this level allows, for a tooltip or hint row. */
  hint: string;
}

/** Admin panel: the credential tiers stored on the registration. */
export const CONNECTION_MODE: Record<ConnectionMode, ModeMeta> = {
  ro: {
    label: "Read only",
    tone: 'neutral',
    hint: "Only an RO account is configured. Data cannot be changed on this database.",
  },
  ro_rw: {
    label: "Read and write",
    tone: 'warning',
    hint: "RO and RW accounts are configured. Schema-changing queries are rejected.",
  },
  ro_rw_ddl: {
    label: "Advanced / DDL",
    tone: 'danger',
    hint: "RO, RW and DDL accounts are configured. Schema changes are supported.",
  },
};

/** SQL editor: what this user may actually execute on this database. */
export const CAPABILITY: Record<ConnectionMode, ModeMeta> = {
  ro: {
    label: "Read only",
    tone: 'neutral',
    hint: "You can read data on this database. Data-changing queries are rejected.",
  },
  ro_rw: {
    label: "Read + write",
    tone: 'warning',
    hint: "You can read and change data. Schema-changing queries are rejected.",
  },
  ro_rw_ddl: {
    label: "Schema changes",
    tone: 'danger',
    hint: "You can change data and schema. Risky statements require approval.",
  },
};

/**
 * The fallback for a null value, which is a real state rather than an error:
 * a registration made before per-tier credentials existed, or a grant whose
 * role carries no data access. Both need to read as "unknown", never as
 * "read-only" — that would understate what a legacy record can still run.
 */
const UNKNOWN_CONNECTION_MODE: ModeMeta = {
  label: "Tier not configured",
  tone: 'neutral',
  hint: "Role-based accounts are not configured. An administrator needs to update this registration.",
};

const UNKNOWN_CAPABILITY: ModeMeta = {
  label: "Capability unknown",
  tone: 'neutral',
  hint: "Your access tier on this database could not be determined. Contact your administrator.",
};

export function connectionModeMeta(mode: ConnectionMode | null | undefined): ModeMeta {
  return mode ? CONNECTION_MODE[mode] : UNKNOWN_CONNECTION_MODE;
}

export function capabilityMeta(capability: ConnectionMode | null | undefined): ModeMeta {
  return capability ? CAPABILITY[capability] : UNKNOWN_CAPABILITY;
}

/** The tiers a mode provisions, for the admin panel's per-tier breakdown. */
export function tiersOf(mode: ConnectionMode | null | undefined): Array<'ro' | 'rw' | 'ddl'> {
  if (mode === 'ro_rw_ddl') return ['ro', 'rw', 'ddl'];
  if (mode === 'ro_rw') return ['ro', 'rw'];
  if (mode === 'ro') return ['ro'];
  return [];
}

export const TIER_LABEL: Record<'ro' | 'rw' | 'ddl', string> = {
  ro: "Read-only queries",
  rw: "Data-changing queries",
  ddl: "Schema-changing queries",
};
