export interface User {
  username: string;
  email: string;
  is_admin: boolean;
}

export interface Workspace {
  id: number;
  name: string;
  description?: string;
  status: 'saved_in_workspace' | 'waiting_for_approval' | 'approved_and_executed' | 'approved_with_results' | 'rejected';
  query: string;
  servername: string;
  database_name: string;
  show_results?: boolean;
}

export interface QueryResult {
  message?: string;
  error?: string;
  data?: any[];
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

export interface MultipleQueryResultItem {
  data?: any[];
  error?: string;
}

export interface MultipleQueryResponse {
  results: MultipleQueryResultItem[];
  error?: string;
}
