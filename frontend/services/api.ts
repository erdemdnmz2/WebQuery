import type {
  DatabaseInfo,
  DatabaseSchema,
  GeneratedCredentials,
  MaskingRule,
  PendingQuery,
  PreviewResponse,
  RegisteredDatabase,
  SqlResponse,
  User,
  Workspace,
  WorkspaceCreated,
} from '../types';

/**
 * Thrown for any non-2xx response.
 *
 * The backend's service-layer handler returns
 * `{success, error_code, message, error, trace_id}`, so a caller can branch on
 * a stable `code` instead of matching message text, and can show `traceId`
 * when a user needs to report the failure.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly traceId?: string;

  constructor(message: string, status: number, code?: string, traceId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.traceId = traceId;
  }
}

/** Raised when the session expired; the shell redirects instead of rendering. */
export class UnauthorizedError extends ApiError {
  constructor() {
    super('Oturum süresi doldu.', 401);
    this.name = 'UnauthorizedError';
  }
}

/** The analyzer refused the query and sent it to an administrator instead. */
export const QUERY_SENT_FOR_APPROVAL = 'QUERY_REJECTED_BY_ANALYZER';

/**
 * The statement did not parse, so no role decision was possible. Distinct from
 * QUERY_REJECTED_BY_ANALYZER: this is the user's SQL to fix, not an approval
 * to wait for.
 */
export const QUERY_SYNTAX_ERROR = 'QUERY_SYNTAX_ERROR';

/**
 * Someone decided this approval request first. The decision is atomic on the
 * server, so the loser of the race gets this instead of overwriting a settled
 * status; the only correct response is to reload the pending list.
 */
export const APPROVAL_CONFLICT = 'APPROVAL_CONFLICT';

function redirectToLogin() {
  const hash = window.location.hash;
  if (!hash.includes('/login') && !hash.includes('/register')) {
    window.location.hash = '/login';
  }
}

interface ParsedError {
  message: string;
  code?: string;
  traceId?: string;
}

async function readError(response: Response): Promise<ParsedError> {
  try {
    const body = await response.json();
    const code = typeof body?.error_code === 'string' ? body.error_code : undefined;
    const traceId = typeof body?.trace_id === 'string' && body.trace_id !== '-' ? body.trace_id : undefined;
    const detail = body?.detail ?? body?.error ?? body?.message;

    if (typeof detail === 'string' && detail.trim()) return { message: detail, code, traceId };
    if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI validation errors arrive as a list of {loc, msg, type}.
      const first = detail[0];
      if (typeof first?.msg === 'string') return { message: first.msg, code, traceId };
    }
    if (code) return { message: 'İstek tamamlanamadı.', code, traceId };
  } catch {
    /* Non-JSON error bodies fall through to the status-based message. */
  }

  if (response.status >= 500) return { message: 'Sunucu bu isteği tamamlayamadı.' };
  if (response.status === 403) return { message: 'Bu işlem için yetkiniz yok.' };
  if (response.status === 404) return { message: 'Kayıt bulunamadı.' };
  if (response.status === 429) return { message: 'Çok fazla istek gönderildi. Biraz bekleyip tekrar deneyin.' };
  return { message: 'İstek tamamlanamadı.' };
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /**
   * Login, register and the refresh call itself handle 401 on their own: they
   * neither redirect nor try to renew a session that is not established yet.
   */
  skipAuthRedirect?: boolean;
}

/**
 * The access cookie expires in ACCESS_TOKEN_EXPIRE_MINUTES (20 by default)
 * while the rotating refresh cookie lives for hours. A 401 in the middle of a
 * session therefore usually means "mint a new access token", not "sign in
 * again", so one refresh round trip is spent before giving up on the session.
 *
 * Refresh tokens are single use. Concurrent 401s must not each post their own
 * refresh, or every request but one would burn a token the next request still
 * needs, so they share one in-flight attempt.
 */
let refreshInFlight: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  const attempt = request<{ ok?: boolean }>('/api/refresh', {
    method: 'POST',
    skipAuthRedirect: true,
  })
    .then(() => true)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });

  refreshInFlight = attempt;
  return attempt;
}

async function request<T>(url: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const { body, skipAuthRedirect, headers, ...rest } = options;

  let response: Response;
  try {
    response = await fetch(url, {
      credentials: 'include',
      headers: body === undefined ? headers : { 'Content-Type': 'application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
      ...rest,
    });
  } catch {
    throw new ApiError('Sunucuya ulaşılamıyor. Ağ bağlantınızı kontrol edin.', 0);
  }

  if (response.status === 401) {
    if (!retried && !skipAuthRedirect && (await refreshSession())) {
      return request<T>(url, options, true);
    }
    if (!skipAuthRedirect) redirectToLogin();
    throw new UnauthorizedError();
  }

  if (!response.ok) {
    const { message, code, traceId } = await readError(response);
    throw new ApiError(message, response.status, code, traceId);
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

function query(params: Record<string, string>): string {
  return new URLSearchParams(params).toString();
}

export const api = {
  /* ------------------------------------------------------------- session */

  me: () => request<User>('/api/me'),
  login: (email: string, password: string) =>
    request<{ access_token: string }>('/api/login', {
      method: 'POST',
      body: { email, password },
      skipAuthRedirect: true,
    }),
  register: (username: string, email: string, password: string) =>
    request<{ message?: string }>('/api/register', {
      method: 'POST',
      body: { username, email, password },
      skipAuthRedirect: true,
    }),
  logout: () => request<{ success?: string }>('/api/logout', { method: 'POST' }),

  /* ------------------------------------------------------------- targets */

  /** Servers and databases the signed-in user has been granted access to. */
  databaseInformation: () =>
    request<{ db_info?: DatabaseInfo }>('/api/database_information').then((data) => data.db_info ?? {}),

  /** Column names an administrator masks permanently for this database. */
  maskingRules: (dbUuid: string) => request<string[]>(`/api/masking_rules?${query({ db_uuid: dbUuid })}`),

  /* ---------------------------------------------------------- workspaces */

  workspaces: () =>
    request<{ workspaces?: Workspace[] }>('/api/workspaces').then((data) => data.workspaces ?? []),
  workspace: (id: number) => request<Workspace>(`/api/get_workspace_by_id/${id}`),

  createWorkspace: (payload: { name: string; description?: string; query: string; db_uuid: string }) =>
    request<WorkspaceCreated>('/api/workspaces', { method: 'POST', body: payload }),

  /** The API updates the stored SQL and status only; other fields are fixed. */
  updateWorkspace: (id: number, payload: { query: string; status?: string }) =>
    request<void>(`/api/workspaces/${id}`, { method: 'PUT', body: payload }),

  deleteWorkspace: (id: number) => request<void>(`/api/workspaces/${id}`, { method: 'DELETE' }),

  /* ----------------------------------------------------------- execution */

  executeQuery: (payload: { db_uuid: string; query: string; ad_hoc_mask_columns?: string[] }) =>
    request<SqlResponse>('/api/execute_query', { method: 'POST', body: payload }),

  executeWorkspace: (id: number, adHocMaskColumns?: string[]) =>
    request<SqlResponse>(`/api/execute_workspace/${id}`, {
      method: 'POST',
      body: { ad_hoc_mask_columns: adHocMaskColumns ?? null },
    }),

  /* --------------------------------------------------------------- admin */

  pendingQueries: () =>
    request<{ waiting_approvals?: PendingQuery[] }>('/api/admin/queries_to_approve').then(
      (data) => data.waiting_approvals ?? [],
    ),
  previewQuery: (workspaceId: number) =>
    request<PreviewResponse>(`/api/admin/execute_for_preview/${workspaceId}`, { method: 'POST' }),
  approveQuery: (workspaceId: number, showResults: boolean) =>
    request<{ success?: boolean; message?: string }>(`/api/admin/approve_query/${workspaceId}`, {
      method: 'POST',
      body: { show_results: showResults },
    }),
  /**
   * The reviewer has to say why. The backend enforces 3-500 characters and
   * stores the reason with the decision, where the requester and the audit log
   * both read it, so an empty rejection is refused rather than defaulted.
   */
  rejectQuery: (workspaceId: number, reason: string) =>
    request<void>(`/api/admin/reject_query/${workspaceId}`, {
      method: 'POST',
      body: { reason },
    }),

  registeredDatabases: () =>
    request<{ databases?: RegisteredDatabase[] }>('/api/admin/databases').then((data) => data.databases ?? []),
  addDatabase: (payload: { servername: string; database_name: string; tech_name: string }) =>
    request<GeneratedCredentials>('/api/admin/add_database', { method: 'POST', body: payload }),
  discoverSchema: (databaseId: number) =>
    request<DatabaseSchema>(`/api/admin/databases/${databaseId}/discover_schema`),
  databaseMaskingRules: (databaseId: number) =>
    request<MaskingRule[]>(`/api/admin/databases/${databaseId}/masking_rules`),
  saveMaskingRules: (databaseId: number, rules: MaskingRule[]) =>
    request<{ success?: boolean; message?: string }>(`/api/admin/databases/${databaseId}/masking_rules`, {
      method: 'POST',
      body: { rules },
    }),
  associateUser: (payload: { user_id: number; database_id: number; role: string }) =>
    request<{ success?: boolean; message?: string }>('/api/admin/associate_user', {
      method: 'POST',
      body: payload,
    }),
};

/** Normalises any thrown value into a message that is safe to show a user. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return 'Beklenmeyen bir hata oluştu.';
}

/** The support reference the backend attaches to service-layer failures. */
export function errorTraceId(error: unknown): string | undefined {
  return error instanceof ApiError ? error.traceId : undefined;
}
