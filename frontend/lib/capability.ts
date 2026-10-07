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
    label: 'Salt-okuma',
    tone: 'neutral',
    hint: 'Kayıtta yalnız RO hesabı var. Bu veritabanında veri değiştirilemez.',
  },
  ro_rw: {
    label: 'Okuma ve yazma',
    tone: 'warning',
    hint: 'Kayıtta RO ve RW hesapları var. Şema değiştiren sorgular reddedilir.',
  },
  ro_rw_ddl: {
    label: 'Gelişmiş / DDL',
    tone: 'danger',
    hint: 'Kayıtta RO, RW ve DDL hesapları var. Şema değişikliği mümkündür.',
  },
};

/** SQL editor: what this user may actually execute on this database. */
export const CAPABILITY: Record<ConnectionMode, ModeMeta> = {
  ro: {
    label: 'Salt-okuma',
    tone: 'neutral',
    hint: 'Bu veritabanında veri okuyabilirsiniz. Veri değiştiren sorgular reddedilir.',
  },
  ro_rw: {
    label: 'Okuma + yazma',
    tone: 'warning',
    hint: 'Veri okuyabilir ve değiştirebilirsiniz. Şema değiştiren sorgular reddedilir.',
  },
  ro_rw_ddl: {
    label: 'Şema değişikliği',
    tone: 'danger',
    hint: 'Veri ve şema değişikliği yapabilirsiniz. Riskli ifadeler onaya düşer.',
  },
};

/**
 * The fallback for a null value, which is a real state rather than an error:
 * a registration made before per-tier credentials existed, or a grant whose
 * role carries no data access. Both need to read as "unknown", never as
 * "read-only" — that would understate what a legacy record can still run.
 */
const UNKNOWN_CONNECTION_MODE: ModeMeta = {
  label: 'Kademe tanımsız',
  tone: 'neutral',
  hint: 'Bu kayıtta rol bazlı hesap tanımlı değil. Yöneticinin kaydı güncellemesi gerekir.',
};

const UNKNOWN_CAPABILITY: ModeMeta = {
  label: 'Yetki tanımsız',
  tone: 'neutral',
  hint: 'Bu veritabanındaki erişim kademeniz belirlenemedi. Yöneticinize başvurun.',
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
  ro: 'Salt-okuma sorguları',
  rw: 'Veri değiştiren sorgular',
  ddl: 'Şema değiştiren sorgular',
};
