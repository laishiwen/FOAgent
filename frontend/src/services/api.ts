import type {
  TaskMeta,
  PlanResult,
  ExecutionResult,
  RollbackResult,
  TaskStatus,
} from "../types";

const BASE = "/api";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { error?: string }).error || `HTTP ${res.status}`
    );
  }
  return res.json();
}

export const api = {
  createTask(rootPath: string, dryRun: boolean): Promise<TaskMeta> {
    return request<TaskMeta>("/tasks", {
      method: "POST",
      body: JSON.stringify({ root_path: rootPath, dry_run: dryRun }),
    });
  },

  runPlanning(taskId: string): Promise<PlanResult> {
    return request<PlanResult>(`/tasks/${taskId}/plan`, { method: "POST" });
  },

  getTask(taskId: string): Promise<TaskStatus> {
    return request<TaskStatus>(`/tasks/${taskId}`);
  },

  submitReview(
    taskId: string,
    action: "approve" | "adjust" | "reject",
    plan?: unknown
  ): Promise<{ task_id: string; status: string }> {
    return request(`/tasks/${taskId}/review`, {
      method: "POST",
      body: JSON.stringify({ action, plan }),
    });
  },

  executeTask(taskId: string): Promise<ExecutionResult> {
    return request<ExecutionResult>(`/tasks/${taskId}/execute`, {
      method: "POST",
    });
  },

  rollbackTask(taskId: string): Promise<RollbackResult> {
    return request<RollbackResult>(`/tasks/${taskId}/rollback`, {
      method: "POST",
    });
  },
};
