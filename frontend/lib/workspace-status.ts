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
    label: "Draft",
    tone: 'neutral',
    hint: "Editable. Risky statements are sent for approval when run.",
  },
  waiting_for_approval: {
    label: "Awaiting approval",
    tone: 'warning',
    hint: "Cannot be edited until administrator review is complete.",
  },
  approved_and_executed: {
    label: "Approved",
    tone: 'success',
    hint: "An administrator executed the query. Results were not shared.",
  },
  approved_with_results: {
    label: "Ready to run",
    tone: 'success',
    hint: "You can execute the query and export its results.",
  },
  rejected: {
    label: "Rejected",
    tone: 'danger',
    hint: "An administrator rejected this query. You can edit and resubmit it.",
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
