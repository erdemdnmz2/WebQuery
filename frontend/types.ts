/*
 * The wire contract of the WebQuery API.
 *
 * Field names mirror the backend Pydantic schemas exactly (snake_case) so a
 * mismatch is visible here rather than at runtime. Anything reshaped for the
 * UI lives in lib/ instead, next to the code that does the reshaping.
 */

/** GET /api/me. The backend derives is_admin from database associations. */
export interface User {
  username: string;
  is_admin: boolean;
}

export type WorkspaceStatus =
  | 'saved_in_workspace'
  | 'waiting_for_approval'
  | 'approved_and_executed'
  | 'approved_with_results'
  | 'rejected';

/**
 * One database a user may target. The uuid is what every execution endpoint
 * accepts; servername and database_name exist for display only.
 */
export interface TargetDatabase {
  name: string;
  uuid: string;
}

export interface ServerInfo {
  databases: TargetDatabase[];
  technology?: string;
}

/** GET /api/database_information, already narrowed to the user's grants. */
export type DatabaseInfo = Record<string, ServerInfo>;

export interface Workspace {
  id: number;
  name: string;
  description?: string | null;
  query: string;
  servername: string;
  database_name: string;
  db_uuid: string;
  status: WorkspaceStatus;
  show_results?: boolean | null;
  owner_id: number;
  is_owner?: boolean | null;
}

/** POST /api/workspaces returns an envelope, not the created workspace. */
export interface WorkspaceCreated {
  success: boolean;
  workspace_id: number;
}

export type ResultRow = Record<string, unknown>;

/** POST /api/execute_query and POST /api/execute_workspace/{id}. */
export interface SqlResponse {
  response_type: 'data' | 'error';
  data: ResultRow[];
  message?: string | null;
  error?: string | null;
  /**
   * Columns the server actually redacted in `data`, spelled as they appear in
   * the rows. Empty when nothing was masked - including when the caller is a
   * database admin and masking is deliberately bypassed. Never infer masking
   * from what was requested; see SPEC-0012 BR-04.
   */
  masked_columns?: string[] | null;
}

/** POST /api/admin/execute_for_preview/{id} carries a little more. */
export interface PreviewResponse extends SqlResponse {
  columns?: string[] | null;
  row_count?: number | null;
}

export interface PendingQuery {
  user_id: number;
  workspace_id: number;
  username: string;
  query: string;
  database: string;
  status: string;
  risk_type?: string | null;
  servername?: string | null;
}

export interface RegisteredDatabase {
  id: number;
  servername: string;
  database_name: string;
  technology: string;
  db_username?: string | null;
}

export interface MaskingRule {
  table_name: string;
  column_name: string;
  masking_type: string;
  is_active: boolean;
}

export interface GeneratedCredentials {
  message?: string;
  db_username: string;
  db_password: string;
}

/** GET /api/admin/databases/{id}/discover_schema: table name to column names. */
export type DatabaseSchema = Record<string, string[]>;
