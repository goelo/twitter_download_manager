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

export type RunStatus = {
  status: string;
  started_at: number | null;
  ended_at: number | null;
  running_for: number | null;
  return_code: number | null;
  summary: {
    elapsed: number | null;
    api_calls: number;
    downloads: number;
  };
  output_path: string;
  message: string;
  log_version: number;
  logs: string[];
};

export type RunConfig = {
  save_path: string;
  user_lst: string;
  cookie: string;
  time_range: string;
  has_retweet: boolean;
  high_lights: boolean;
  likes: boolean;
  down_log: boolean;
  autoSync: boolean;
  image_format: string;
  has_video: boolean;
  log_output: boolean;
  max_concurrent_requests: number;
  proxy: string;
  md_output: boolean;
  media_count_limit: number;
  project_path?: string;
};
