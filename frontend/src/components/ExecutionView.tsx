import type { ExecutionResult } from "../types";

interface Props {
  result: ExecutionResult;
}

function verdictBadge(v: string) {
  const map: Record<string, string> = {
    pass: "verdict-pass",
    warn: "verdict-warn",
    fail: "verdict-fail",
  };
  return <span className={`verdict ${map[v] || ""}`}>{v.toUpperCase()}</span>;
}

function checkItem(label: string, item: { passed: boolean; detail: string }) {
  return (
    <div className={`check-item ${item.passed ? "check-pass" : "check-fail"}`}>
      <strong>{label}</strong>：{item.passed ? "PASS" : "FAIL"}
      <div className="detail">{item.detail}</div>
    </div>
  );
}

export default function ExecutionView({ result }: Props) {
  const log = result.execution_log;
  const summary = log?.summary ?? {};
  const verify = result.verify_result;
  const harness = result.harness_report;

  return (
    <div className="card">
      <h2>3. 执行结果 &amp; Harness 检测</h2>

      {/* Summary */}
      <section className="section">
        <div className="exec-summary">
          <div className="stat">
            <span className="stat-value">{summary.created_directories ?? 0}</span>
            <span className="stat-label">创建目录</span>
          </div>
          <div className="stat">
            <span className="stat-value">{summary.moved_files ?? 0}</span>
            <span className="stat-label">移动文件</span>
          </div>
          <div className="stat">
            <span className="stat-value">{summary.failed_steps ?? 0}</span>
            <span className="stat-label">失败步骤</span>
          </div>
        </div>
        {verify && (
          <p className="muted" style={{ marginTop: 8 }}>
            文件校验：{verify.moved_count}/{verify.original_count} 已移动
            {verify.missing.length > 0 && (
              <span className="red"> | 遗漏：{verify.missing.join(", ")}</span>
            )}
          </p>
        )}
      </section>

      {/* Steps */}
      <section className="section">
        <h3>执行步骤</h3>
        <div className="table-wrap">
          <table className="moves-table">
            <thead>
              <tr>
                <th>步骤ID</th>
                <th>类型</th>
                <th>状态</th>
                <th>命令</th>
              </tr>
            </thead>
            <tbody>
              {(log?.steps ?? []).map((s) => (
                <tr key={s.step_id}>
                  <td className="mono">{s.step_id}</td>
                  <td>{s.step_type}</td>
                  <td>
                    <span
                      className={`badge ${
                        s.status === "completed" ? "badge-green" : "badge-red"
                      }`}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {s.command}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Harness Report */}
      {harness && (
        <section className="section">
          <h3>Harness Agent 终检报告</h3>
          <div className="verdict-row">
            {verdictBadge(harness.verdict)}
            <span className="muted" style={{ marginLeft: 8 }}>
              {harness.overall_assessment}
            </span>
          </div>
          <div className="checks-grid">
            {checkItem("完整性", harness.checks.completeness)}
            {checkItem("关联合理性", harness.checks.association_spot_check)}
            {checkItem("命名恰当性", harness.checks.naming_spot_check)}
            {checkItem("执行一致性", harness.checks.execution_consistency)}
          </div>
          {harness.issues.length > 0 && (
            <div className="alert alert-error" style={{ marginTop: 8 }}>
              问题：{harness.issues.join("；")}
            </div>
          )}
          {harness.suggestions.length > 0 && (
            <div className="alert alert-info" style={{ marginTop: 4 }}>
              建议：{harness.suggestions.join("；")}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
