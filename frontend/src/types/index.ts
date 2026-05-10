export interface TaskMeta {
  task_id: string;
  root_path: string;
  dry_run: boolean;
  status: string;
  created_at: string;
}

export interface FileInfo {
  name: string;
  path: string;
  extension: string;
  size_bytes: number;
  modified_at: string;
  is_hidden: boolean;
  is_symlink: boolean;
  kind?: string;
  mime_type?: string;
}

export interface ScanResult {
  success: boolean;
  error: string | null;
  root_path: string;
  files: FileInfo[];
  subdirs: string[];
  stats: {
    file_count: number;
    subdir_count: number;
    by_extension: Record<string, number>;
  };
}

export interface CategoryItem {
  name: string;
  members: string[];
}

export interface MoveItem {
  source_path: string;
  target_path: string;
  category: string;
  confidence: number;
}

export interface PlanResult {
  status: string;
  task_id: string;
  current_files: string[];
  target_structure: {
    root_path: string;
    categories: CategoryItem[];
  };
  plan: {
    directories_to_create: string[];
    moves: MoveItem[];
    conflicts: unknown[];
    needs_review_items: { source_path: string; target_path: string }[];
  };
  needs_review: boolean;
  notes: string[];
}

export interface ExecutionStep {
  step_id: string;
  step_type: string;
  sequence?: number;
  status: string;
  command: string;
  source_path: string | null;
  target_path: string;
  stdout?: string;
  stderr?: string;
  error?: string;
  started_at?: string;
  finished_at?: string;
}

export interface ExecutionLog {
  task_id: string;
  root_path: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  steps: ExecutionStep[];
  summary: {
    created_directories: number;
    moved_files: number;
    failed_steps: number;
    rolled_back_steps: number;
  };
}

export interface HarnessCheckItem {
  passed: boolean;
  detail: string;
  [key: string]: unknown;
}

export interface HarnessReport {
  verdict: "pass" | "warn" | "fail";
  overall_assessment: string;
  checks: {
    completeness: HarnessCheckItem;
    association_spot_check: HarnessCheckItem;
    naming_spot_check: HarnessCheckItem;
    execution_consistency: HarnessCheckItem;
  };
  issues: string[];
  suggestions: string[];
}

export interface ExecutionResult {
  status: string;
  task_id: string;
  execution_log: ExecutionLog;
  verify_result: {
    success: boolean;
    original_count: number;
    moved_count: number;
    missing: string[];
    extra: string[];
  } | null;
  harness_report: HarnessReport | null;
}

export interface RollbackResult {
  status: string;
  task_id: string;
  rollback_log: {
    success: boolean;
    error: string | null;
    steps: unknown[];
    cleaned_dirs: string[];
  };
}

export interface TaskStatus {
  task_id: string;
  status: string;
  root_path: string;
  dry_run: boolean;
  created_at: string;
  scan?: { file_count: number; files: string[] };
  plan_summary?: {
    categories: number;
    moves: number;
    directories_to_create: number;
  };
  harness_report?: HarnessReport;
}
