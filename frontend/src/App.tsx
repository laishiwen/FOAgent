import { useState } from "react";
import FolderInput from "./components/FolderInput";
import PlanView from "./components/PlanView";
import ExecutionView from "./components/ExecutionView";
import { api } from "./services/api";
import type { PlanResult, ExecutionResult, Adjustments } from "./types";

export default function App() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [execResult, setExecResult] = useState<ExecutionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adjustments, setAdjustments] = useState<Adjustments>({});

  const handleStart = async (rootPath: string, dry: boolean) => {
    setError(null); setPlan(null); setExecResult(null);
    setAdjustments({});
    setLoading(true); setDryRun(dry);
    try {
      const task = await api.createTask(rootPath, dry);
      setTaskId(task.task_id);
      const planResult = await api.runPlanning(task.task_id);
      setPlan(planResult);
      if (planResult.status === "failed") setError("规划失败");
    } catch (e) {
      setError(e instanceof Error ? e.message : "未知错误");
    } finally { setLoading(false); }
  };

  const handleAdjustMove = (fileId: string, newCategory: string) => {
    setAdjustments(prev => {
      const moves = (prev.moves || []).filter(m => m.file_id !== fileId);
      moves.push({ file_id: fileId, category: newCategory });
      return { ...prev, moves };
    });
  };

  const handleAdjustCategory = (oldName: string, newName: string) => {
    setAdjustments(prev => {
      const cats = (prev.categories || []).filter(c => c.old_name !== oldName);
      if (newName !== oldName) cats.push({ old_name: oldName, new_name: newName });
      return { ...prev, categories: cats };
    });
  };

  const handleConfirm = async () => {
    if (!taskId) return;
    // Submit adjustments first
    if ((adjustments.moves?.length || 0) > 0 ||
        (adjustments.categories?.length || 0) > 0) {
      await api.submitReview(taskId, "adjust", adjustments);
    } else {
      await api.submitReview(taskId, "approve");
    }

    if (dryRun) {
      alert("Dry-run 模式，不执行实际移动。取消勾选后可执行。");
      return;
    }
    setExecuting(true);
    try {
      const result = await api.executeTask(taskId);
      setExecResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "执行失败");
    } finally { setExecuting(false); }
  };

  const handleRollback = async () => {
    if (!taskId) return;
    if (!confirm("确认回滚？")) return;
    try { await api.rollbackTask(taskId); alert("回滚完成"); }
    catch (e) { alert("回滚失败：" + (e instanceof Error ? e.message : "?")); }
  };

  return (
    <div className="container">
      <header className="header">
        <h1>文件分类整理系统</h1>
        <span className="header-sub">Agent A → Agent B → Harness</span>
      </header>

      {error && <div className="alert alert-error" onClick={() => setError(null)}>{error}</div>}

      <FolderInput onStart={handleStart} loading={loading} />

      {plan && (
        <PlanView
          plan={plan} dryRun={dryRun} executing={executing}
          adjustments={adjustments}
          onAdjustMove={handleAdjustMove}
          onAdjustCategory={handleAdjustCategory}
          onConfirm={handleConfirm}
          onRollback={handleRollback}
        />
      )}

      {execResult && <ExecutionView result={execResult} />}
    </div>
  );
}
