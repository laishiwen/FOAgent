import { useState } from "react";

interface Props {
  onStart: (rootPath: string, dryRun: boolean) => void;
  loading: boolean;
}

export default function FolderInput({ onStart, loading }: Props) {
  const [path, setPath] = useState("");
  const [dryRun, setDryRun] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (path.trim()) onStart(path.trim(), dryRun);
  };

  return (
    <div className="card">
      <h2>1. 选择源文件夹</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <input
            type="text"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="输入目标文件夹路径，如 /Users/xxx/Downloads"
            disabled={loading}
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !path.trim()}>
            {loading ? (
              <>
                <span className="spinner" />
                规划中...
              </>
            ) : (
              "扫描并规划"
            )}
          </button>
        </div>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            disabled={loading}
          />
          Dry-run 模式（仅预览，不实际移动文件）
        </label>
      </form>
    </div>
  );
}
