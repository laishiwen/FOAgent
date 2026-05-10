import { useState } from "react";

interface Props {
  onStart: (rootPath: string) => void;
  loading: boolean;
}

export default function FolderInput({ onStart, loading }: Props) {
  const [path, setPath] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (path.trim()) onStart(path.trim());
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
                扫描分类中...
              </>
            ) : (
              "扫描并分类"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
