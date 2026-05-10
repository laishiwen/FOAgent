import { useState } from "react";
import type { PlanResult, Adjustments } from "../types";

interface Props {
  plan: PlanResult;
  dryRun: boolean;
  executing: boolean;
  adjustments: Adjustments;
  onAdjustMove: (fileId: string, newCategory: string) => void;
  onAdjustCategory: (oldName: string, newName: string) => void;
  onConfirm: () => void;
  onRollback: () => void;
}

function badge(s: string) {
  const m: Record<string, string> = { planned: "badge-green", review_required: "badge-yellow", approved: "badge-green", failed: "badge-red" };
  return <span className={`badge ${m[s] || "badge-gray"}`}>{s}</span>;
}

function confClass(c: number) { return c >= 0.85 ? "row-ok" : c >= 0.6 ? "row-warn" : "row-low"; }

export default function PlanView({ plan, dryRun, executing, adjustments, onAdjustMove, onAdjustCategory, onConfirm, onRollback }: Props) {
  const cats = plan.target_structure?.categories ?? [];
  const moves = plan.plan?.moves ?? [];
  const conflicts = plan.plan?.conflicts ?? [];
  const needsReview = plan.needs_review;
  const catNames = [...new Set(moves.map(m => m.category))];

  const adjMoves = new Map((adjustments.moves || []).map(a => [a.file_id, a.category]));
  const adjCats = new Map((adjustments.categories || []).map(a => [a.old_name, a.new_name]));
  const effCat = (fileId: string, orig: string) => adjMoves.get(fileId) || orig;
  const effName = (name: string) => adjCats.get(name) || name;

  const [editing, setEditing] = useState<string | null>(null);

  return (
    <div className="card">
      <h2>2. 分类方案 {badge(plan.status)}</h2>

      <section className="section">
        <h3>当前文件（{plan.current_files.length} 个）</h3>
        <ul className="file-list">{plan.current_files.map((f, i) => <li key={i}>{f}</li>)}</ul>
      </section>

      <section className="section">
        <h3>目标分类（可调整）</h3>
        {cats.map(cat => {
          const en = effName(cat.name);
          return (
            <div key={cat.name} className="category-group">
              <div className="cat-header">
                {editing === cat.name ? (
                  <input className="cat-edit-input" defaultValue={en} autoFocus
                    onBlur={e => { onAdjustCategory(cat.name, e.target.value); setEditing(null); }}
                    onKeyDown={e => { if (e.key === "Enter") onAdjustCategory(cat.name, (e.target as HTMLInputElement).value); if (e.key === "Enter" || e.key === "Escape") setEditing(null); }} />
                ) : (
                  <h4 onClick={() => setEditing(cat.name)} title="点击编辑">{en}{adjCats.has(cat.name) && " *"}</h4>
                )}
                <span className={`badge ${cat.confidence >= 0.85 ? "badge-green" : "badge-yellow"}`}>{(cat.confidence * 100).toFixed(0)}%</span>
              </div>
              <ul className="file-list">
                {cat.members.map((m, i) => {
                  const fid = cat.member_ids?.[i] || "";
                  const mv = moves.find(x => x.file_id === fid);
                  const conf = mv?.confidence ?? cat.confidence;
                  const c = mv ? effCat(mv.file_id, mv.category) : en;
                  return (
                    <li key={m} className={`move-row ${confClass(conf)}`}>
                      <span>{m}</span>
                      {adjMoves.has(fid) && <span className="adj-tag">→ {c}</span>}
                      <select className="move-select" value={c} onChange={e => onAdjustMove(fid, e.target.value)}>
                        {catNames.map(cn => <option key={cn} value={cn}>{cn}</option>)}
                      </select>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </section>

      <section className="section">
        <h3>移动计划（{moves.length} 条）</h3>
        <div className="table-wrap">
          <table className="moves-table">
            <thead><tr><th>文件</th><th>源路径</th><th>目标分类</th><th>置信度</th></tr></thead>
            <tbody>
              {moves.map(m => {
                const f = m.source_path.split("/").pop() || m.source_path;
                return (
                  <tr key={m.file_id} className={confClass(m.confidence)}>
                    <td>{f}</td><td className="mono">{m.source_path}</td>
                    <td>{effName(effCat(m.file_id, m.category))}</td>
                    <td><span className={`badge ${m.confidence >= 0.85 ? "badge-green" : m.confidence >= 0.6 ? "badge-yellow" : "badge-red"}`}>{(m.confidence * 100).toFixed(0)}%</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {conflicts.length > 0 && <div className="alert alert-error">冲突：{JSON.stringify(conflicts)}</div>}
      {plan.notes?.length > 0 && <div className="notes">备注：{plan.notes.join("；")}</div>}

      <div className="actions">
        <div className="confirm-box">
          <p className="confirm-text">{dryRun ? "预览模式" : `将创建 ${cats.length} 个目录，移动 ${moves.length} 个文件`}</p>
          <button className="btn btn-success" onClick={onConfirm} disabled={executing}>
            {executing ? <><span className="spinner" />执行中...</> : dryRun ? "预览（Dry Run）" : needsReview ? "审核后确认执行" : "确认执行"}
          </button>
          <button className="btn btn-danger" onClick={onRollback}>回滚</button>
        </div>
      </div>
    </div>
  );
}
