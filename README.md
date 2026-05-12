# Agent File Organizer

A AI-powered intelligent file classification and organization system using multi-agent architecture. This project automatically scans local directories, identifies file relationships, generates classification schemes, and organizes files with full auditability and rollback support.

[English](#english) | [中文](#中文)

---

## English

### Overview

**Agent File Organizer** is a sophisticated automation system that intelligently categorizes and organizes files in local directories using a chained multi-agent architecture. Unlike simple rule-based systems, it employs three specialized AI agents working in tandem to understand file relationships, generate semantic classifications, and execute file organization with human control at each step.

**Key Innovation**: A three-stage agent pipeline that separates concerns:

- **Agent A** (Association Analyzer) - Identifies relationships between files
- **Agent B** (Classification Namer) - Generates semantic category names
- **Harness Agent** (Verifier) - Independent final validation and quality checks

### Core Features

✨ **Intelligent Classification**

- Analyzes file associations and relationships
- Generates semantic classification names
- Supports unlimited file types (documents, media, code, archives, etc.)

🔄 **Full Execution Control**

- Preview file organization plans before execution (dry-run)
- Execute file moves with transaction support
- Rollback functionality for all executed operations
- Complete execution logging and audit trails

🛡️ **Reliability & Safety**

- Multi-stage validation before file operations
- Independent quality verification (Harness Agent)
- No direct model control over file operations
- Structured JSON contracts between all layers

📊 **Transparent Operations**

- Detailed audit logs for all operations
- Task tracking and status management
- Error handling and recovery mechanisms

### Architecture

The system is organized in five layers:

```
┌─────────────────────┐
│ Frontend UI Layer   │ (React + TypeScript)
│ (Path Selection)    │
└──────────┬──────────┘
           │
┌──────────▼──────────────────┐
│ Local API Bridge            │ (Flask + CORS)
│ (Task Management)           │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────────────┐
│ Agent Workflow Orchestration        │ (LangGraph/State Machine)
│ - Scan → Analyze → Plan → Execute   │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────┐
│ Bash Shell Tool Layer           │ (Execution)
│ - scan_parent_dir               │
│ - dry_run_moves                 │
│ - create_dirs / move_files      │
│ - rollback                      │
└──────────┬──────────────────────┘
           │
┌──────────▼──────────────────────┐
│ Local Storage & Audit           │ (JSON Logs)
│ - execution_log.json            │
│ - rollback_log.json             │
└─────────────────────────────────┘
```

### System Workflow

```
1. [User] Selects folder in frontend
                    ↓
2. [Frontend] Sends root_path to backend
                    ↓
3. [scan_parent_dir] Collects file metadata
                    ↓
4. [Agent A] Analyzes file associations
                    ↓
5. [Agent B] Generates classification plan
                    ↓
6. [Frontend] Displays plan (dry-run preview)
                    ↓
7. [User] Confirms or modifies plan
                    ↓
8. [create_dirs] Creates target directories
                    ↓
9. [move_files] Executes file moves with logging
                    ↓
10. [Harness Agent] Validates results
                    ↓
11. [Frontend] Shows completion report
```

### Project Structure

```
File_grouping_agents/
├── app/                          # Backend Python application
│   ├── agents/                   # Agent implementations
│   │   ├── agent_a_association.py   # File association analysis
│   │   ├── agent_b_naming.py        # Classification naming
│   │   ├── harness_agent.py         # Final verification
│   │   └── llm_client.py            # LLM interface
│   ├── graph/                    # Workflow state machine
│   │   └── state.py              # Workflow state definition
│   ├── services/                 # Business logic
│   │   ├── task_service.py       # Task management
│   │   └── audit_service.py      # Audit logging
│   ├── storage/                  # Local storage layer
│   │   └── task_store.py         # Task persistence
│   ├── tools/                    # Bash shell tools
│   │   ├── scan_parent_dir.sh    # Directory scanning
│   │   ├── bash_dry_run_moves.sh # Preview moves
│   │   ├── bash_create_dirs.sh   # Directory creation
│   │   ├── bash_move_files.sh    # File moving
│   │   └── bash_rollback.sh      # Rollback operations
│   ├── core/                     # Core configuration
│   │   ├── config.py             # LLM & app config
│   │   └── logging.py            # Logging setup
│   ├── server.py                 # Flask API server
│   ├── cli.py                    # CLI entry point
│   └── pyproject.toml            # Python dependencies
│
├── frontend/                     # React frontend application
│   ├── src/
│   │   ├── components/
│   │   │   └── FolderInput.tsx   # Folder selection
│   │   ├── services/
│   │   │   └── api.ts            # API client
│   │   ├── types/
│   │   │   └── index.ts          # TypeScript types
│   │   ├── App.tsx               # Main app component
│   │   └── main.tsx              # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── index.html
│
├── TECH_DESIGN_AGENT_FILE_ORGANIZER.md     # Technical design
├── BASH_TOOL_AND_EXECUTION_SCHEMA.md       # Bash tools spec
└── README.md                                 # This file
```

### Demo & Screenshots

🎥 **Video Demo** (Coming Soon)

- [YouTube - Agent File Organizer Demo](https://youtube.com/your-demo-link)
- [Full Tutorial Playlist](https://youtube.com/your-playlist-link)

📸 **Screenshots**

**1. Folder Selection**

```
User selects a folder with mixed file types:
  ├── report_v1.docx
  ├── report_v1.pdf
  ├── project_notes.txt
  ├── meeting_2026-05.mp4
  ├── photo_team.jpg
  └── budget.xlsx
```

**2. Analysis in Progress**

```
Agent A analyzing relationships:
  ✓ Identified: report_v1.docx ↔ report_v1.pdf (related documents)
  ✓ Identified: meeting_2026-05.mp4 (media content)
  ✓ Identified: photo_team.jpg (image asset)
  ✓ Processing: project_notes.txt (text document)
  ✓ Processing: budget.xlsx (spreadsheet data)
```

**3. Classification Generated by Agent B**

```
📁 Project Reports
  ├── report_v1.docx
  ├── report_v1.pdf
  └── project_notes.txt

📁 Media & Assets
  ├── meeting_2026-05.mp4
  └── photo_team.jpg

📁 Financial Documents
  └── budget.xlsx
```

**4. Preview (Dry-run)**

- Frontend displays the proposed structure
- User can review and adjust classifications
- Shows confidence scores for each grouping

**5. After Execution**

```
✅ All files organized successfully!

Generated Directories:
  /folder/Project Reports/      (3 files, 2.4 MB)
  /folder/Media & Assets/       (2 files, 156 MB)
  /folder/Financial Documents/  (1 file, 45 KB)

Total Time: 2.3s
Files Moved: 6
Rollback Available: ✓
```

### Quick Start

#### Prerequisites

- Python 3.10+
- Node.js 18+
- Ollama with Qwen3.5 (9b) model
- macOS/Linux (Windows support via WSL)

#### Setup Backend

```bash
# Navigate to app directory
cd app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Configure LLM (set environment variables)
export LLM_BASE_URL="http://localhost:4141/v1"
export LLM_API_KEY="11111"
export MODEL_NAME="qwen3.5:9b"

# Run the backend server
python server.py
```

The API server will start at `http://localhost:5000`

#### Setup Frontend

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

The frontend will be available at `http://localhost:5173`

#### Running with CLI

```bash
# After activating venv
agent-organizer --help

# Organize files in a directory
agent-organizer organize /path/to/target/folder
```

### Configuration

#### LLM Configuration

Set these environment variables before running:

```bash
export LLM_BASE_URL="http://localhost:4141/v1"      # Ollama endpoint
export LLM_API_KEY="11111"                           # API key
export MODEL_NAME="qwen3.5:9b"                       # Model name
```

Or edit `app/core/config.py`:

```python
LLM_CONFIG = {
    "base_url": "http://localhost:4141/v1",
    "api_key": "11111",
    "model_name": "qwen3.5:9b"
}
```

#### Application Configuration

Edit `app/core/config.py` for other settings:

```python
APP_CONFIG = {
    "debug": False,
    "log_level": "INFO",
    "task_storage_path": "./tasks"
}
```

### API Endpoints

#### Health Check

```
GET /health
```

#### Scan Directory

```
POST /api/scan
{
  "root_path": "/target/folder"
}
```

Response:

```json
{
  "task_id": "uuid",
  "files": [...],
  "subdirs": [...],
  "stats": {...}
}
```

#### Analyze & Plan Classification

```
POST /api/classify
{
  "task_id": "uuid",
  "root_path": "/target/folder"
}
```

#### Dry Run (Preview Moves)

```
POST /api/dry-run
{
  "task_id": "uuid",
  "plan": {...}
}
```

#### Execute Organization

```
POST /api/execute
{
  "task_id": "uuid",
  "plan": {...}
}
```

#### Rollback

```
POST /api/rollback
{
  "task_id": "uuid"
}
```

### Key Concepts

#### File Association Analysis

Agent A examines files to identify relationships:

- Files with related names (e.g., `report.docx` and `report.pdf`)
- Files sharing common prefixes or suffixes
- Files created around the same time
- Files with complementary types (e.g., `.psd` and `.png`)

#### Classification Generation

Agent B creates meaningful category names based on:

- Identified file relationships
- File types and purposes
- Semantic analysis of file names
- Content patterns (when applicable)

#### Harness Verification

The Harness Agent performs:

- Cross-validation of Agent B's classification
- Quality scoring of category names
- Detection of potential issues
- Confidence assessment

#### Execution Log

All operations produce detailed logs:

```json
{
  "timestamp": "2026-05-09T10:00:00Z",
  "task_id": "abc123",
  "operation": "move_file",
  "source": "/target/folder/file.txt",
  "destination": "/target/folder/Category/file.txt",
  "status": "success",
  "duration_ms": 45
}
```

### Business Rules

1. **Scope**: Only processes direct files in the target directory (no recursive subdirectory traversal)
2. **File Types**: No restrictions - all file types participate in classification
3. **Relationships**: Files with associations are grouped; unrelated files get individual classifications
4. **Hidden Files**: System files (starting with `.`) are excluded by default
5. **Symlinks**: Symbolic links are not processed
6. **Conflicts**: Target path conflicts prevent overwriting without explicit confirmation
7. **Confidence**: Low-confidence results enter manual review queue
8. **Planning**: All moves must be planned before execution
9. **Auditing**: Every operation generates audit logs
10. **Recovery**: Failed operations support rollback based on logs

### Troubleshooting

#### "connection refused" to LLM

Ensure Ollama is running:

```bash
ollama serve
```

In another terminal:

```bash
ollama pull qwen3.5:9b
```

#### Files not organizing as expected

Check the audit log:

```bash
cat /path/to/tasks/{task_id}/execution_log.json
```

Review Agent B's classification reasoning:

```bash
cat /path/to/tasks/{task_id}/classification_plan.json
```

#### Rollback failed

Verify rollback log:

```bash
cat /path/to/tasks/{task_id}/rollback_log.json
```

### Development

#### Running Tests

```bash
cd app
pytest tests/
```

#### Building Frontend

```bash
cd frontend
pnpm build
```

Output: `frontend/dist/`

#### Code Style

- Python: Follow PEP 8 with Black formatter
- TypeScript: Use ESLint configuration in `frontend/eslint.config.js`

### Performance Considerations

- **Directory Scanning**: O(n) where n = number of direct files
- **Association Analysis**: O(n²) comparisons, but uses intelligent pruning
- **Classification Generation**: Single LLM call per grouping
- **File Operations**: Sequential moves with fsync for safety

For directories with 1000+ files, expect 5-15 minutes for the full workflow.

### Security Notes

- **Path Validation**: All paths are canonicalized and validated against root boundaries
- **No Remote Execution**: This tool runs entirely locally
- **File Permissions**: Respects system file permissions; won't move files without read/write access
- **No Model Access**: Model receives only file metadata, not content
- **Audit Trail**: Complete logging of all operations for accountability

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure:

- Code follows project style guidelines
- Tests pass and new tests are added
- Documentation is updated
- Commit messages are clear and descriptive

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Documentation & Resources

- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines and development setup
- **[TECH_DESIGN_AGENT_FILE_ORGANIZER.md](TECH_DESIGN_AGENT_FILE_ORGANIZER.md)** - Technical architecture and design decisions
- **[BASH_TOOL_AND_EXECUTION_SCHEMA.md](BASH_TOOL_AND_EXECUTION_SCHEMA.md)** - Bash tools interface specification
- **[.github/workflows/](/.github/workflows/)** - CI/CD pipeline configuration
  - `tests.yml` - Automated testing on Python 3.10-3.12
  - `lint.yml` - Code style and linting checks
  - `build.yml` - Build and release automation

### Acknowledgments

- Built with [LangChain](https://python.langchain.com/)
- LLM powered by [Ollama](https://ollama.ai/)
- Frontend built with [React](https://react.dev/) and [Vite](https://vitejs.dev/)
- CLI powered by [Flask](https://flask.palletsprojects.com/)

---

## 中文

### 项目概述

**Agent File Organizer** 是一个使用多Agent链式架构的智能文件分类整理系统。与传统的规则引擎不同，它采用三个专业化的AI Agent协作工作，理解文件关系、生成语义分类、执行文件整理，并在每个步骤提供人工控制。

**核心创新**: 三阶段Agent管道，职责分明：

- **Agent A** (关联分析器) - 识别文件之间的关系
- **Agent B** (分类命名器) - 生成语义化分类名称
- **Harness Agent** (终检器) - 独立的最终验证和质量检查

### 主要特性

✨ **智能分类**

- 分析文件关联和依赖关系
- 生成语义化的分类名称
- 支持无限制的文件类型（文档、媒体、代码、压缩包等）

🔄 **完整的执行控制**

- 执行前预览整理方案（Dry-run）
- 支持文件移动的事务性执行
- 完整的回滚功能
- 详细的执行日志和审计追踪

🛡️ **可靠性与安全性**

- 文件操作前的多阶段验证
- 独立的质量验证（Harness Agent）
- 模型无法直接控制文件操作
- 各层之间的结构化JSON契约

📊 **操作透明**

- 所有操作的详细审计日志
- 任务跟踪和状态管理
- 完整的错误处理和恢复机制

### 系统架构

系统分为五层：

```
┌─────────────────────┐
│ 前端交互层          │ (React + TypeScript)
│ (路径选择)          │
└──────────┬──────────┘
           │
┌──────────▼──────────────────┐
│ 本地API网关                 │ (Flask + CORS)
│ (任务管理)                  │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────────────┐
│ Agent工作流编排                      │ (LangGraph/状态机)
│ - 扫描 → 分析 → 规划 → 执行          │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────┐
│ Bash Shell工具执行层            │ (执行)
│ - scan_parent_dir               │
│ - dry_run_moves                 │
│ - create_dirs / move_files      │
│ - rollback                      │
└──────────┬──────────────────────┘
           │
┌──────────▼──────────────────────┐
│ 本地存储与审计                   │ (JSON日志)
│ - execution_log.json            │
│ - rollback_log.json             │
└─────────────────────────────────┘
```

### 工作流程

```
1. [用户] 在前端选择文件夹
                    ↓
2. [前端] 发送root_path到后端
                    ↓
3. [scan_parent_dir] 收集文件元数据
                    ↓
4. [Agent A] 分析文件关联
                    ↓
5. [Agent B] 生成分类方案
                    ↓
6. [前端] 显示方案预览(Dry-run)
                    ↓
7. [用户] 确认或修改方案
                    ↓
8. [create_dirs] 创建目标目录
                    ↓
9. [move_files] 执行文件移动并记录日志
                    ↓
10. [Harness Agent] 验证结果
                    ↓
11. [前端] 显示完成报告
```

### 演示和截图

🎥 **视频演示** (敬请期待)

- [YouTube - Agent File Organizer 演示](https://youtube.com/your-demo-link)
- [完整教程播放列表](https://youtube.com/your-playlist-link)

📸 **截图示例**

**1. 选择文件夹**

```
用户选择一个包含混合文件类型的文件夹：
  ├── report_v1.docx
  ├── report_v1.pdf
  ├── project_notes.txt
  ├── meeting_2026-05.mp4
  ├── photo_team.jpg
  └── budget.xlsx
```

**2. 分析进行中**

```
Agent A 正在分析关联关系：
  ✓ 已识别: report_v1.docx ↔ report_v1.pdf (相关文档)
  ✓ 已识别: meeting_2026-05.mp4 (媒体内容)
  ✓ 已识别: photo_team.jpg (图片资产)
  ✓ 处理中: project_notes.txt (文本文档)
  ✓ 处理中: budget.xlsx (电子表格)
```

**3. Agent B 生成的分类**

```
📁 项目报告
  ├── report_v1.docx
  ├── report_v1.pdf
  └── project_notes.txt

📁 媒体和资产
  ├── meeting_2026-05.mp4
  └── photo_team.jpg

📁 财务文件
  └── budget.xlsx
```

**4. 预览（Dry-run）**

- 前端显示建议的文件结构
- 用户可以查看并调整分类
- 显示每个分组的置信度评分

**5. 执行完成**

```
✅ 所有文件整理完成！

生成的目录结构：
  /folder/项目报告/        (3个文件，2.4 MB)
  /folder/媒体和资产/       (2个文件，156 MB)
  /folder/财务文件/       (1个文件，45 KB)

总耗时: 2.3秒
已移动文件: 6个
支持回滚: ✓
```

### 快速开始

#### 前置要求

- Python 3.10+
- Node.js 18+
- Ollama with Qwen3.5 (9b)
- macOS/Linux (Windows通过WSL)

#### 后端设置

```bash
# 进入app目录
cd app

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .

# 配置LLM（设置环境变量）
export LLM_BASE_URL="http://localhost:4141/v1"
export LLM_API_KEY="11111"
export MODEL_NAME="qwen3.5:9b"

# 运行后端服务器
python server.py
```

API服务器将在 `http://localhost:5000` 启动

#### 前端设置

```bash
# 进入frontend目录
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

前端将在 `http://localhost:5173` 可用

#### 使用CLI

```bash
# 激活虚拟环境后
agent-organizer --help

# 整理指定文件夹
agent-organizer organize /path/to/target/folder
```

### 配置

#### LLM配置

在运行前设置环境变量：

```bash
export LLM_BASE_URL="http://localhost:4141/v1"      # Ollama端点
export LLM_API_KEY="11111"                          # API密钥
export MODEL_NAME="qwen3.5:9b"                      # 模型名称
```

或编辑 `app/core/config.py`：

```python
LLM_CONFIG = {
    "base_url": "http://localhost:4141/v1",
    "api_key": "11111",
    "model_name": "qwen3.5:9b"
}
```

#### 应用程序配置

编辑 `app/core/config.py` 其他设置：

```python
APP_CONFIG = {
    "debug": False,
    "log_level": "INFO",
    "task_storage_path": "./tasks"
}
```

### API端点

#### 健康检查

```
GET /health
```

#### 扫描目录

```
POST /api/scan
{
  "root_path": "/target/folder"
}
```

#### 分析和规划分类

```
POST /api/classify
{
  "task_id": "uuid",
  "root_path": "/target/folder"
}
```

#### 干运行（预览移动）

```
POST /api/dry-run
{
  "task_id": "uuid",
  "plan": {...}
}
```

#### 执行整理

```
POST /api/execute
{
  "task_id": "uuid",
  "plan": {...}
}
```

#### 回滚

```
POST /api/rollback
{
  "task_id": "uuid"
}
```

### 故障排查

#### "无法连接"到LLM

确保Ollama正在运行：

```bash
ollama serve
```

在另一个终端：

```bash
ollama pull qwen3.5:9b
```

#### 文件未按预期整理

检查审计日志：

```bash
cat /path/to/tasks/{task_id}/execution_log.json
```

审查Agent B的分类理由：

```bash
cat /path/to/tasks/{task_id}/classification_plan.json
```

### 许可证

本项目采用 MIT License - 详见 [LICENSE](LICENSE) 文件

### 文档与资源

- **[CONTRIBUTING.md](CONTRIBUTING.md)** - 贡献指南和开发设置
- **[TECH_DESIGN_AGENT_FILE_ORGANIZER.md](TECH_DESIGN_AGENT_FILE_ORGANIZER.md)** - 技术架构和设计决策
- **[BASH_TOOL_AND_EXECUTION_SCHEMA.md](BASH_TOOL_AND_EXECUTION_SCHEMA.md)** - Bash工具接口规范
- **[.github/workflows/](/.github/workflows/)** - CI/CD管道配置
  - `tests.yml` - 在Python 3.10-3.12上的自动化测试
  - `lint.yml` - 代码风格和Lint检查
  - `build.yml` - 构建和发布自动化

### 致谢

- 基于 [LangChain](https://python.langchain.com/)
- 由 [Ollama](https://ollama.ai/) 提供LLM支持
- 前端使用 [React](https://react.dev/) 和 [Vite](https://vitejs.dev/)
- CLI使用 [Flask](https://flask.palletsprojects.com/)
