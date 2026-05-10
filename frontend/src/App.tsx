import { useState } from "react";
import FolderInput from "./components/FolderInput";
import type { ClassifyResult, ProgressEvent } from "./types";
import { classifyStream } from "./services/api";
import type { SSEClassifyResult } from "./services/api";

const PHASE_LABELS: Record<string, string> = {
  scanning: "正在扫描",
  classifying: "正在分类",
  merging: "正在合并类别",
  done: "完成",
};

export default function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);

  const handleStart = async (rootPath: string) => {
    setError(null);
    setResult(null);
    setProgress(null);
    setLoading(true);

    try {
      for await (const event of classifyStream(rootPath)) {
        if ("result" in event || "error" in event) {
          const final = event as SSEClassifyResult;
          if (final.error) {
            setError(final.error);
          } else if (final.result) {
            setResult(final.result);
          }
          break;
        }
        setProgress(event as ProgressEvent);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "error");
    } finally {
      setLoading(false);
      setProgress(null);
    }
  };

  const phase = progress?.phase || "";
  const pct = progress && progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0;

  return (
    <div className="container">
      <header className="header">
        <h1>file organizer</h1>
        <span className="header-sub">deep scan / classify</span>
      </header>

      {error && (
        <div className="alert alert-error" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <FolderInput onStart={handleStart} loading={loading} />

      {loading && (
        <div className="card">
          <h2>progress</h2>
          <div className="progress-section">
            <div className="progress-phase">
              {PHASE_LABELS[phase] || "connecting..."}
              {progress && progress.total > 0 && (
                <span className="progress-stats">
                  {progress.current}/{progress.total}
                </span>
              )}
            </div>
            {progress && progress.total > 0 && (
              <div className="progress-bar-wrap">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${pct}%` }}
                />
              </div>
            )}
            {progress && (
              <div className="progress-msg">{progress.message}</div>
            )}
            {!progress && (
              <div className="progress-msg">
                <span className="spinner" /> connecting...
              </div>
            )}
          </div>
        </div>
      )}

      {result && (
        <div className="card">
          <h2>results</h2>
          <p className="summary">
            <strong>{result.total_files}</strong> files
            ({result.stats.dir_count} dirs)
            / <strong>{result.categories.length}</strong> categories
          </p>

          <div className="categories">
            {result.categories.map((cat) => (
              <section key={cat.category_name} className="category-group">
                <div className="cat-header">
                  <h3>{cat.category_name}</h3>
                  <span className="badge badge-green">{cat.count}</span>
                </div>
                <ul className="file-list">
                  {cat.member_names.map((name, i) => {
                    const fid = cat.member_ids[i];
                    const schema = result.source_schema[fid];
                    const ext = schema?.extension || "";
                    return (
                      <li key={fid} className="file-row">
                        <span className="file-name">{name}</span>
                        {ext && <span className="file-ext">{ext}</span>}
                        {schema?.parent_id && schema.parent_id !== "0" && (
                          <span className="file-parent">
                            {result.source_schema[schema.parent_id]?.name ||
                              schema.parent_id}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
