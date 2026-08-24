import type {
  DatabaseInfo,
  DatabaseSchema,
  MaskingRule,
  PendingQuery,
  QueryResult,
  RegisteredDatabase,
  ResultRow,
  User,
  Workspace,
} from '../types';

/** Thrown for any non-2xx response so callers can render one inline message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** Raised when the session expired; the shell redirects instead of rendering. */
export class UnauthorizedError extends ApiError {
  constructor() {
    super('Oturum süresi doldu.', 401);
    this.name = 'UnauthorizedError';
  }
}

function redirectToLogin() {
  const hash = window.location.hash;
  if (!hash.includes('/login') && !hash.includes('/register')) {
    window.location.hash = '/login';
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail ?? body?.error ?? body?.message;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first?.msg === 'string') return first.msg;
    }
  } catch {
    /* Non-JSON error bodies fall through to the status-based message. */
  }
  if (response.status >= 500) return 'Sunucu bu isteği tamamlayamadı.';
  return 'İstek tamamlanamadı.';
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** Login and register handle 401 themselves instead of redirecting. */
  skipAuthRedirect?: boolean;
}

async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
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
    if (!skipAuthRedirect) redirectToLogin();
    throw new UnauthorizedError();
  }

  if (!response.ok) throw new ApiError(await readError(response), response.status);

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export const api = {
  /* Session */
  me: () => request<User>('/api/me'),
  login: (email: string, password: string) =>
    request<unknown>('/api/login', { method: 'POST', body: { email, password }, skipAuthRedirect: true }),
  register: (username: string, email: string, password: string) =>
    request<unknown>('/api/register', {
      method: 'POST',
      body: { username, email, password },
      skipAuthRedirect: true,
    }),
  logout: () => request<unknown>('/api/logout', { method: 'POST' }),

  /* Connections */
  databaseInformation: () =>
    request<{ db_info?: DatabaseInfo }>('/api/database_information').then((data) => data.db_info ?? {}),

  /* Workspaces */
  workspaces: () =>
    request<{ workspaces?: Workspace[] }>('/api/workspaces').then((data) => data.workspaces ?? []),
  workspace: (id: number) => request<Workspace>(`/api/get_workspace_by_id/${id}`),
  createWorkspace: (payload: {
    name: string;
    description: string;
    query: string;
    servername: string;
    database_name: string;
  }) => request<Workspace>('/api/workspaces', { method: 'POST', body: payload }),
  updateWorkspace: (
    id: number,
    payload: {
      name: string;
      description?: string;
      query: string;
      servername: string;
      database_name: string;
    },
  ) => request<Workspace>(`/api/workspaces/${id}`, { method: 'PUT', body: payload }),
  deleteWorkspace: (id: number) => request<unknown>(`/api/workspaces/${id}`, { method: 'DELETE' }),

  /* Execution */
  executeQuery: (payload: {
    query: string;
    servername: string;
    database_name: string;
    ad_hoc_mask_columns: string[];
  }) => request<QueryResult>('/api/execute_query', { method: 'POST', body: payload }),
  executeWorkspace: (id: number) =>
    request<QueryResult>(`/api/execute_workspace/${id}`, { method: 'POST', body: {} }),

  /* Masking, user scope */
  maskingRules: (servername: string, databaseName: string) =>
    request<string[]>(
      `/api/masking_rules?servername=${encodeURIComponent(servername)}&database_name=${encodeURIComponent(databaseName)}`,
    ),

  /* Admin */
  pendingQueries: () =>
    request<{ waiting_approvals?: PendingQuery[] }>('/api/admin/queries_to_approve').then(
      (data) => data.waiting_approvals ?? [],
    ),
  previewQuery: (workspaceId: number) =>
    request<{ data?: ResultRow[] }>(`/api/admin/execute_for_preview/${workspaceId}`, { method: 'POST' }).then(
      (data) => data.data ?? [],
    ),
  approveQuery: (workspaceId: number, showResults: boolean) =>
    request<unknown>(`/api/admin/approve_query/${workspaceId}`, {
      method: 'POST',
      body: { show_results: showResults },
    }),
  rejectQuery: (workspaceId: number) =>
    request<unknown>(`/api/admin/reject_query/${workspaceId}`, { method: 'POST' }),

  registeredDatabases: () =>
    request<{ databases?: RegisteredDatabase[] }>('/api/admin/databases').then((data) => data.databases ?? []),
  addDatabase: (payload: { servername: string; database_name: string; tech_name: string }) =>
    request<{ db_username: string; db_password: string }>('/api/admin/add_database', {
      method: 'POST',
      body: payload,
    }),
  discoverSchema: (databaseId: number) =>
    request<DatabaseSchema>(`/api/admin/databases/${databaseId}/discover_schema`),
  databaseMaskingRules: (databaseId: number) =>
    request<MaskingRule[]>(`/api/admin/databases/${databaseId}/masking_rules`),
  saveMaskingRules: (databaseId: number, rules: MaskingRule[]) =>
    request<unknown>(`/api/admin/databases/${databaseId}/masking_rules`, { method: 'POST', body: { rules } }),
};

/** Normalises any thrown value into a message that is safe to show a user. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return 'Beklenmeyen bir hata oluştu.';
}
