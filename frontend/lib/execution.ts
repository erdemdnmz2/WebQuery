import {
  ApiError,
  DATABASE_ACCESS_DENIED,
  QUERY_BLOCKED,
  QUERY_CANCELLED,
  QUERY_ROLE_DENIED,
  QUERY_SENT_FOR_APPROVAL,
  QUERY_SYNTAX_ERROR,
  errorMessage,
} from '../services/api';
import type { ResultRow, SqlResponse } from '../types';

/**
 * What the UI needs to know about one execution.
 *
 * The API reports row counts and truncation only inside an English message
 * string, so that text is parsed once, here, rather than in every screen that
 * shows a result.
 */
export interface ExecutionOutcome {
  rows: ResultRow[];
  /** Rows actually returned to the client. */
  rowCount: number;
  /** Set for statements that changed rows instead of returning them. */
  affectedRows: number | null;
  /** The server stopped reading at its row cap; more rows exist. */
  truncated: boolean;
  /** The cap the server reported, when it reported one. */
  limit: number | null;
  error: string | null;
  /** Support reference for a failed run. */
  traceId?: string;
  /** The analyzer refused the query and routed it to an administrator. */
  sentForApproval: boolean;
  cancelled: boolean;
  /** Columns the server reported as redacted in these rows. */
  maskedColumns: string[];
}

const TRUNCATED = /^Truncated to MAX_ROW_COUNT_LIMIT \((\d+)\)/i;
const AFFECTED = /^(\d+) rows? affected/i;

function emptyOutcome(): ExecutionOutcome {
  return {
    rows: [],
    rowCount: 0,
    affectedRows: null,
    truncated: false,
    limit: null,
    error: null,
    sentForApproval: false,
    cancelled: false,
    maskedColumns: [],
  };
}

export function outcomeFromResponse(response: SqlResponse): ExecutionOutcome {
  const outcome = emptyOutcome();
  const message = response.message ?? '';

  if (response.response_type === 'error' || response.error) {
    outcome.error = response.error || "Could not execute the query.";
    return outcome;
  }

  outcome.rows = response.data ?? [];
  outcome.rowCount = outcome.rows.length;
  outcome.maskedColumns = response.masked_columns ?? [];

  const truncated = TRUNCATED.exec(message);
  if (truncated) {
    outcome.truncated = true;
    outcome.limit = Number(truncated[1]);
  }

  const affected = AFFECTED.exec(message);
  if (affected) outcome.affectedRows = Number(affected[1]);

  return outcome;
}

export function outcomeFromError(error: unknown): ExecutionOutcome {
  const outcome = emptyOutcome();
  outcome.error = errorMessage(error);
  if (error instanceof ApiError) {
    outcome.traceId = error.traceId;
    if (error.code === QUERY_CANCELLED) {
      outcome.cancelled = true;
      outcome.error = null;
      return outcome;
    }
    // Only this code means an approval request now exists. The refusals below
    // create none, and drawing a waiting state over them made users wait on an
    // administrator who had never been asked.
    outcome.sentForApproval = error.code === QUERY_SENT_FOR_APPROVAL;
    if (error.code === QUERY_SYNTAX_ERROR) {
      // The analyzer could not parse the statement, so it never reached a role
      // decision and no approval request was created. Saying so keeps the user
      // on their own SQL instead of waiting on an administrator.
      outcome.error = "Could not parse the query. Check the SQL syntax and try again.";
    } else if (error.code === QUERY_ROLE_DENIED) {
      outcome.error =
        "Your role cannot execute this statement. Contact your database administrator for access.";
    } else if (error.code === DATABASE_ACCESS_DENIED) {
      outcome.error =
        "You do not have access to this database. Contact your database administrator for access.";
    } else if (error.code === QUERY_BLOCKED) {
      // A hard-blocked risk class. No approval can lift it, so the user must
      // not be told to wait for one.
      outcome.error = errorMessage(error);
    }
  }
  return outcome;
}

/** One line summarising a completed run, in the language of the interface. */
export function summarise(outcome: ExecutionOutcome, format: (value: number) => string): string | null {
  if (outcome.error || outcome.cancelled) return null;
  if (outcome.affectedRows !== null) return `${format(outcome.affectedRows)} rows affected`;
  if (outcome.truncated && outcome.limit !== null) {
    return `First ${format(outcome.limit)} rows (truncated)`;
  }
  return `${format(outcome.rowCount)} rows`;
}
