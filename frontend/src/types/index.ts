export interface TaskMeta {
  task_id: string;
  root_path: string;
  dry_run: boolean;
  status: string;
  created_at: string;
}

export interface SourceSchema {
  [fileId: string]: {
    name: string;
    path: string;
    extension: string;
    kind: string;
    size_bytes: number;
    modified_at: string;
  };
}

export interface CategoryItem {
  name: string;
  members: string[];
  member_ids: string[];
  confidence: number;
}

export interface MoveItem {
  file_id: string;
  source_path: string;
  target_path: string;
  category: string;
  confidence: number;
}

export interface PlanResult {
  status: string;
  task_id: string;
  current_files: string[];
  source_schema: SourceSchema;
  target_structure: {
    root_path: string;
    categories: CategoryItem[];
  };
  plan: {
    directories_to_create: string[];
    moves: MoveItem[];
    conflicts: unknown[];
    needs_review_items: MoveItem[];
  };
  needs_review: boolean;
  notes: string[];
}

export interface Adjustments {
  moves?: { file_id: string; category: string }[];
  categories?: { old_name: string; new_name: string }[];
}

export interface ExecutionStep {
  step_id: string;
  step_type: string;
  status: string;
  command: string;
  source_path: string | null;
  target_path: string;
  error?: string;
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
  } | null;
  harness_report: HarnessReport | null;
  summary?: { verdict: string; pipeline: unknown[] };
}

export interface RollbackResult {
  status: string;
  task_id: string;
  rollback_log: { steps: unknown[]; cleaned_dirs: string[] };
}

export interface TaskStatus {
  task_id: string;
  status: string;
  root_path: string;
  dry_run: boolean;
  created_at: string;
  state?: { step: string; status: string; input: unknown; output: unknown }[];
  summary?: { verdict: string };
  harness_report?: HarnessReport;
}