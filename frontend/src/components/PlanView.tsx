import type { PlanResult } from "../types";

interface Props {
  plan: PlanResult;
  dryRun: boolean;
  onExecute: () => void;
  onRollback: () => void;
  executing: boolean;
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    planned: "badge-green",
    review_required: "badge-yellow",
    approved: "badge-green",
    failed: "badge-red",
  };
  return <span className={`badge ${map[status] || "badge-gray"}`}>{status}</span>;
}

export default function PlanView({ plan, dryRun, onExecute, onRollback, executing }: Props) {
  const categories = plan.target_structure?.categories ?? [];
  const moves = plan.plan?.moves ?? [];
  const conflicts = plan.plan?.conflicts ?? [];
  const needsReview = plan.needs_review;

  return (
    <div className="card">
      <h2>
        2. 分类方案 {statusBadge(plan.status)}
      </h2>

      {/* Files */}
      <section className="section">
        <h3>当前文件（{plan.current_files.length} 个）</h3>
        <ul className="file-list">
          {plan.current_files.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </section>

      {/* Categories */}
      <section className="section">
        <h3>目标分类结构</h3>
        {categories.length === 0 ? (
          <p className="muted">无分类</p>
        ) : (
          categories.map((cat) => (
            <div key={cat.name} className="category-group">
              <h4>{cat.name}</h4>
              <ul className="file-list">
                {cat.members.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          ))
        )}
      </section>

      {/* Moves */}
      <section className="section">
        <h3>移动计划（{moves.length} 条）</h3>
        <div className="table-wrap">
          <table className="moves-table">
            <thead>
              <tr>
                <th>源路径</th>
                <th>目标路径</th>
                <th>分类</th>
                <th>置信度</th>
              </tr>
            </thead>
            <tbody>
              {moves.map((m, i) => (
                <tr key={i}>
                  <td className="mono">{m.source_path}</td>
                  <td className="mono green">{m.target_path}</td>
                  <td>{m.category || "-"}</td>
                  <td>{(m.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Conflicts */}
      {conflicts.length > 0 && (
        <div className="alert alert-error">
          冲突项：{JSON.stringify(conflicts)}
        </div>
      )}

      {/* Notes */}
      {plan.notes && plan.notes.length > 0 && (
        <div className="notes">
          备注：{plan.notes.join("；")}
        </div>
      )}

      {/* Actions */}
      <div className="actions">
        {!dryRun && (
          <button
            className="btn btn-success"
            onClick={onExecute}
            disabled={executing}
          >
            {executing ? (
              <><span className="spinner" /> 执行中...</>
            ) : needsReview ? (
              "需人工审核，确认后执行"
            ) : (
              "确认执行"
            )}
          </button>
        )}
        <button className="btn btn-danger" onClick={onRollback}>
          回滚
        </button>
      </div>
    </div>
  );
}
