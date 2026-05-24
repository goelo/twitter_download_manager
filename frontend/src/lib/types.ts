export type User = {
  id: number;
  username: string;
  role: 'admin' | 'user';
};

export type Account = {
  id: number;
  label: string;
  screen_name: string | null;
  status: string;
  last_checked_at: string | null;
  created_at: string;
};

export type Task = {
  id: number;
  user_id: number;
  username: string | null;
  account_id: number | null;
  task_type: string;
  title: string;
  status: string;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  process_id: number | null;
  config?: Record<string, unknown>;
  log?: string;
  files?: Array<{ name: string; size: number }>;
};

export type ApiError = {
  detail: string;
};
