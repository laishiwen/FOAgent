# Contributing to Agent File Organizer

首先，感谢你对本项目的兴趣！🎉 我们欢迎各种形式的贡献，包括代码、文档、测试和反馈。

## 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
- [开发设置](#开发设置)
- [提交流程](#提交流程)
- [代码风格指南](#代码风格指南)
- [测试指南](#测试指南)
- [文档贡献](#文档贡献)
- [提交问题](#提交问题)
- [社区](#社区)

## 行为准则

本项目采纳了贡献者公约。参与本项目即表示你同意遵守其条款。请参阅 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 了解详情。

## 如何贡献

### 报告Bug

在报告Bug之前，请先检查[问题列表](../../issues)，确保该问题未被报告过。

**提交Bug报告时，请包含以下信息：**

- 清晰的标题和描述
- 详细的复现步骤
- 实际行为和预期行为的对比
- 屏幕截图或日志输出（如果适用）
- 环境信息：操作系统、Python版本、Node.js版本等
- 任何额外的相关信息

### 建议功能

我们欢迎新功能的建议！提交功能请求时：

- 使用清晰的标题
- 提供功能的详细描述
- 列举一些使用场景
- 列出类似的功能（如果存在）

### 改进文档

文档总是可以改进的。你可以：

- 修复文档中的错别字和语法错误
- 改进或澄清现有文档
- 添加新的使用示例
- 翻译文档到其他语言

## 开发设置

### 克隆仓库

```bash
git clone https://github.com/yourusername/agent-file-organizer.git
cd agent-file-organizer
```

### 后端开发环境

```bash
# 进入app目录
cd app

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # 在Windows上使用: .venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 安装pre-commit hooks（可选但推荐）
pre-commit install
```

### 前端开发环境

```bash
# 进入frontend目录
cd frontend

# 使用pnpm（推荐）
pnpm install

# 或使用npm
npm install

# 启动开发服务器
pnpm dev
```

### LLM设置

```bash
# 安装Ollama
# macOS: brew install ollama
# Linux: 见 https://ollama.ai
# Windows: 见 https://ollama.ai

# 启动Ollama服务
ollama serve

# 在另一个终端中拉取模型
ollama pull qwen3.5:9b

# 设置环境变量
export LLM_BASE_URL="http://localhost:4141/v1"
export LLM_API_KEY="11111"
export MODEL_NAME="qwen3.5:9b"
```

## 提交流程

### 1. Fork仓库

点击GitHub上的"Fork"按钮创建仓库的个人副本。

### 2. 创建功能分支

```bash
git checkout -b feature/your-feature-name
# 或用于bug修复
git checkout -b fix/issue-number-description
```

分支命名约定：

- `feature/` - 新功能
- `fix/` - Bug修复
- `docs/` - 文档更新
- `test/` - 测试添加/改进
- `refactor/` - 代码重构（无功能改变）

### 3. 提交更改

```bash
# 查看改动
git status

# 添加文件到暂存区
git add .

# 提交更改
git commit -m "feat: add amazing new feature"
```

提交消息格式遵循 [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - 新功能
- `fix:` - Bug修复
- `docs:` - 文档更改
- `style:` - 格式、缺少分号等（无代码逻辑改变）
- `refactor:` - 重构现有代码
- `perf:` - 性能改进
- `test:` - 添加或更新测试
- `chore:` - 构建流程、依赖管理等

**提交消息示例：**

```
feat: add file association analysis for Agent A

- Implement semantic analysis of file names
- Add support for time-based association detection
- Add comprehensive test coverage

Closes #123
```

### 4. 保持分支最新

```bash
# 从上游主分支获取最新更改
git fetch upstream
git rebase upstream/main
```

### 5. 推送到你的Fork

```bash
git push origin feature/your-feature-name
```

### 6. 创建Pull Request

1. 进入GitHub上的你的fork仓库
2. 点击"Compare & pull request"按钮
3. 填写PR模板中的所有信息
4. 点击"Create pull request"

**PR描述应包含：**

- 变更的简要描述
- 解决的问题（使用 `Closes #issue-number`）
- 测试覆盖情况
- 文档更新情况
- 任何有用的背景或上下文

### 7. 代码审查

维护者会审查你的PR。你可能被要求进行更改。这很正常！请：

- 及时回应反馈
- 进行请求的修改
- 不需要创建新PR，只需更新现有分支

### 8. 合并

一旦PR获得批准，维护者将合并你的代码。祝贺！🎉

## 代码风格指南

### Python代码

遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/)：

```bash
# 使用Black格式化代码
black app/

# 使用Flake8进行linting
flake8 app/

# 使用Pylint进行深入分析
pylint app/
```

**Python风格示例：**

```python
"""
Module docstring explaining the module's purpose.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class FileInfo:
    """Data class for file information."""

    name: str
    path: str
    size_bytes: int

    def get_extension(self) -> str:
        """
        Extract file extension.

        Returns:
            str: File extension including the dot (e.g., '.txt')
        """
        if '.' in self.name:
            return '.' + self.name.split('.')[-1]
        return ''


def analyze_files(root_path: str) -> List[FileInfo]:
    """
    Analyze files in a directory.

    Args:
        root_path: Root directory path

    Returns:
        List of FileInfo objects

    Raises:
        FileNotFoundError: If root_path doesn't exist
    """
    # Implementation here
    pass
```

### TypeScript/React代码

遵循ESLint配置和以下约定：

```bash
# 运行linter
cd frontend
pnpm lint

# 修复自动可修复的问题
pnpm lint --fix
```

**TypeScript风格示例：**

```typescript
import React, { useState, useCallback } from 'react';

interface FileItem {
  name: string;
  path: string;
  sizeBytes: number;
}

interface FolderInputProps {
  onFolderSelect: (path: string) => Promise<void>;
  isLoading?: boolean;
}

export const FolderInput: React.FC<FolderInputProps> = ({
  onFolderSelect,
  isLoading = false,
}) => {
  const [selectedPath, setSelectedPath] = useState<string>('');

  const handleSelect = useCallback(async () => {
    try {
      await onFolderSelect(selectedPath);
    } catch (error) {
      console.error('Failed to select folder:', error);
    }
  }, [selectedPath, onFolderSelect]);

  return (
    <div>
      {/* Component JSX */}
    </div>
  );
};
```

### Bash脚本代码

遵循以下约定：

```bash
#!/bin/bash
# Script description

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="${SCRIPT_DIR}/execution.log"

# Functions
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

main() {
    log "Starting script"
    # Implementation
    log "Script completed"
}

main "$@"
```

## 测试指南

### 添加测试

为新功能添加测试至关重要。使用以下约定：

```bash
# 后端测试（pytest）
cd app
pytest tests/

# 前端测试（vitest或Jest）
cd frontend
pnpm test
```

**Python测试示例：**

```python
import pytest
from app.services.task_service import TaskService


class TestTaskService:
    """Tests for TaskService."""

    @pytest.fixture
    def service(self):
        """Create TaskService instance for testing."""
        return TaskService()

    def test_create_task(self, service):
        """Test task creation."""
        task = service.create_task('/path/to/folder')
        assert task.id is not None
        assert task.root_path == '/path/to/folder'

    def test_invalid_path_raises_error(self, service):
        """Test that invalid path raises error."""
        with pytest.raises(FileNotFoundError):
            service.create_task('/nonexistent/path')
```

**TypeScript测试示例：**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { FolderInput } from './FolderInput';

describe('FolderInput Component', () => {
  let onFolderSelect: jest.Mock;

  beforeEach(() => {
    onFolderSelect = jest.fn();
  });

  it('should render the component', () => {
    const { container } = render(
      <FolderInput onFolderSelect={onFolderSelect} />
    );
    expect(container).toBeInTheDocument();
  });

  it('should call onFolderSelect when button is clicked', async () => {
    const { getByRole } = render(
      <FolderInput onFolderSelect={onFolderSelect} />
    );
    const button = getByRole('button');
    await userEvent.click(button);
    expect(onFolderSelect).toHaveBeenCalled();
  });
});
```

### 运行测试

```bash
# 后端 - 运行所有测试
cd app
pytest

# 后端 - 运行带覆盖率的测试
pytest --cov=app

# 后端 - 运行特定测试
pytest tests/test_agents.py::TestAgentA::test_association_analysis

# 前端
cd frontend
pnpm test

# 前端 - 带覆盖率
pnpm test:coverage
```

## 文档贡献

### 编辑现有文档

1. 找到要编辑的.md文件
2. 进行更改
3. 遵循现有风格和格式
4. 测试Markdown渲染（在VS Code中使用Markdown预览）
5. 提交PR

### 创建新文档

使用以下模板：

```markdown
# Document Title

Brief introduction of what this document covers.

## Table of Contents

- [Section 1](#section-1)
- [Section 2](#section-2)

## Section 1

Content here.

### Subsection 1.1

More content.

## Section 2

Additional information.

## Related Documents

- [Related Doc 1](./related-doc-1.md)
- [Related Doc 2](./related-doc-2.md)
```

## 提交问题

### 使用Issue模板

提交Issue时，GitHub会自动显示相应的模板。请完整填写所有部分。

### Issue标签

帮助我们分类问题，请添加相关标签：

- `bug` - 报告的问题
- `enhancement` - 功能请求
- `documentation` - 文档改进
- `good first issue` - 适合新手贡献者
- `help wanted` - 需要社区帮助
- `question` - 问题或讨论

## 社区

### 获取帮助

- **讨论**: 使用GitHub Discussions提问
- **聊天**: 加入我们的Discord服务器（如有）
- **文档**: 查看[README.md](./README.md)和其他文档

### 保持联系

- ⭐ 给仓库Star以示支持
- 📢 分享你的使用案例
- 🔗 在社交媒体上分享项目链接
- 💬 在讨论中提供反馈

## 常见问题

### PR被拒的原因有哪些？

- 不遵循代码风格指南
- 缺少或不充分的测试
- 文档未更新
- 提交消息不清楚
- 与现有PR重复
- 不符合项目目标

### 如何加快PR审查？

- 保持PR规模小而专注
- 清楚解释改动原因
- 包含充分的测试
- 更新相关文档
- 及时回应反馈

### 我可以同时处理多个PR吗？

可以！但建议：

- 每个功能/修复用单独的分支
- 完成一个PR再开始下一个
- 避免PR之间的依赖

## 许可证

通过贡献代码到本项目，你同意你的代码在MIT License下发布。

---

感谢你的贡献！如有疑问，请提交Issue或参与讨论。💪
