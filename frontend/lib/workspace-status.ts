import type { Tone } from '../components/ui/Badge';
import type { WorkspaceStatus } from '../types';

export interface StatusMeta {
  label: string;
  tone: Tone;
  /** One line explaining what the user can do next in this state. */
  hint: string;
}

/**
 * The lifecycle of a saved query, in one place. Every screen reads its labels
 * and colours from here so a status never means two different things.
 */
export const WORKSPACE_STATUS: Record<WorkspaceStatus, StatusMeta> = {
  saved_in_workspace: {
    label: 'Taslak',
    tone: 'neutral',
    hint: 'Düzenlenebilir. Riskli bir ifade içeriyorsa çalıştırıldığında onaya düşer.',
  },
  waiting_for_approval: {
    label: 'Onay bekliyor',
    tone: 'warning',
    hint: 'Yönetici incelemesi tamamlanana kadar düzenlenemez.',
  },
  approved_and_executed: {
    label: 'Onaylandı',
    tone: 'success',
    hint: 'Yönetici sorguyu çalıştırdı. Sonuçlar paylaşıma açılmadı.',
  },
  approved_with_results: {
    label: 'Çalıştırılabilir',
    tone: 'success',
    hint: 'Sorguyu çalıştırıp sonuçları dışa aktarabilirsiniz.',
  },
  rejected: {
    label: 'Reddedildi',
    tone: 'danger',
    hint: 'Yönetici bu sorguyu reddetti. Düzenleyip yeniden gönderebilirsiniz.',
  },
};

export function statusMeta(status: string): StatusMeta {
  return (
    WORKSPACE_STATUS[status as WorkspaceStatus] ?? {
      label: status,
      tone: 'neutral' as Tone,
      hint: '',
    }
  );
}

/**
 * A workspace is editable only while no approval decision depends on its text.
 *
 * This mirrors `WORKSPACE_EDITABLE_STATUSES` on the server, which answers 409
 * for anything else. Approved states are excluded on purpose: rewriting the SQL
 * of an approved query would carry a single approval onto unlimited different
 * statements. A rejected query stays editable so it can be fixed and resubmitted.
 */
export function isEditable(status: string): boolean {
  return status === 'saved_in_workspace' || status === 'rejected';
}

/** Only an explicitly shared result set can be run from the execute screen. */
export function isRunnable(status: string, showResults?: boolean | null): boolean {
  return status === 'approved_with_results' && Boolean(showResults);
}
