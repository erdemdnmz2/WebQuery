export interface User {
  username: string;
  email: string;
  is_admin: boolean;
}

export type WorkspaceStatus =
  | 'saved_in_workspace'
  | 'waiting_for_approval'
  | 'approved_and_executed'
  | 'approved_with_results'
  | 'rejected';

export interface Workspace {
  id: number;
  name: string;
  description?: string;
  status: WorkspaceStatus;
  query: string;
  servername: string;
  database_name: string;
  show_results?: boolean;
}

export type ResultRow = Record<string, unknown>;

export interface QueryResult {
  message?: string;
  error?: string;
  data?: ResultRow[];
  servername?: string;
  database?: string;
  row_count?: number;
  truncated?: boolean;
  query?: string;
}

export interface ServerInfo {
  databases: string[];
  technology?: string;
}

export interface DatabaseInfo {
  [serverName: string]: ServerInfo;
}

export interface PendingQuery {
  workspace_id: number;
  username: string;
  servername: string;
  database: string;
  query: string;
  status: string;
  risk_type?: string;
}

export interface RegisteredDatabase {
  id: number;
  servername: string;
  database_name: string;
  technology: string;
  db_username?: string;
}

export interface MaskingRule {
  table_name: string;
  column_name: string;
  masking_type: string;
  is_active: boolean;
}

export interface GeneratedCredentials {
  username: string;
  password: string;
}

export type DatabaseSchema = Record<string, string[]>;
