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
  is_platform_owner: boolean;
}

export interface OwnerUser {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_platform_owner: boolean;
  status: 'pending' | 'active' | 'disabled';
  created_at?: string | null;
}

export interface DatabaseAdmin {
  database_id: number;
  database_name: string;
  user_id: number;
  username: string;
  role: string;
}

export type WorkspaceStatus =
  | 'saved_in_workspace'
  | 'waiting_for_approval'
  | 'approved_and_executed'
  | 'approved_with_results'
  | 'rejected';

/** The credential tiers a registration provisions, always hierarchical. */
export type ConnectionMode = 'ro' | 'ro_rw' | 'ro_rw_ddl';

/**
 * One database a user may target. The uuid is what every execution endpoint
 * accepts; servername and database_name exist for display only.
 *
 * `capability` is the registration's connection mode already narrowed by this
 * user's role, so it states what they can run here rather than what the
 * database could serve someone else. It is null for a registration that
 * predates per-tier credentials. Credential values never appear in this
 * payload; see SPEC-0002 §7.
 */
export interface TargetDatabase {
  name: string;
  uuid: string;
  capability?: ConnectionMode | null;
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
  connection_mode?: ConnectionMode | null;
  /** Absent (older responses) is treated the same as active. */
  is_active?: boolean;
}

/** A user who currently holds a role on a database. */
export interface DatabaseMember {
  user_id: number;
  username: string;
  email: string;
  role: string;
  is_admin: boolean;
  is_active: boolean;
}

/** An active user who could be granted access; name only, nothing else. */
export interface DatabaseCandidate {
  user_id: number;
  username: string;
  email: string;
}

/** GET /api/admin/databases/{id}/users */
export interface DatabaseUsers {
  database_id: number;
  connection_mode?: ConnectionMode | null;
  members: DatabaseMember[];
  candidates: DatabaseCandidate[];
}

/** A user whose granted role the narrowed connection mode could not serve. */
export interface ConnectionModeConflict {
  user_id: number;
  username: string;
  role: string;
  unsupported_tier: string;
}

/**
 * A rule applies to its own table only: the engine scopes rules to the tables a
 * query actually reads, so a rule on `Customers.email` no longer blanks
 * `Suppliers.email`.
 *
 * `masking_type` is the single strategy the engine implements. It used to be
 * free text that nothing ever read, so the screen appeared to offer a choice
 * that had no effect; the server now rejects anything else.
 */
export type MaskingType = 'full';

export interface MaskingRule {
  table_name: string;
  column_name: string;
  masking_type: MaskingType;
  is_active: boolean;
}

export interface CreatedDatabase {
  message?: string;
  db_uuid: string;
}

/** GET /api/admin/databases/{id}/discover_schema: table name to column names. */
export type DatabaseSchema = Record<string, string[]>;
