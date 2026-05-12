# Bash Shell 工具接口与执行日志 Schema

## 1. 文档目标

本文档定义本地 Agent Runner 在执行文件整理时所使用的 bash shell 工具接口、命令构造约束、执行日志格式与回滚日志格式。目标是让执行层可以直接开发，并与上层 Agent 工作流层（Agent A / Agent B / Harness Agent）保持稳定契约。

核心要点：

1. 所有工具底层均为 bash shell 脚本（.sh 文件）
2. Agent 工作流层通过 subprocess 调用脚本，传入 JSON stdin，读取 JSON stdout
3. 只处理父级目录内直接文件，不做子目录层级遍历
4. 不限制文件类型
5. Harness Agent 终检报告为 JSON 文件，由 Agent 工作流中的 harness_check 节点生成

## 2. 设计原则

1. Agent 不直接输出可执行 shell 文本，只输出结构化规划
2. 所有 bash 命令都由工具脚本内部渲染执行，不接受自由文本
3. 所有真实写操作都必须附带 task_id
4. 所有路径都必须先做 canonicalize 和 root_path 边界校验
5. 所有操作都必须写入 execution_log.json
6. 任一移动失败后停止后续执行，并转入回滚
7. 工具脚本只接受 stdin JSON 参数，输出 stdout JSON 结果
8. 只扫描 root_path 的直接子项（find -maxdepth 1）

## 3. 工具清单

### 3.1 scan_parent_dir.sh

职责：扫描父级目录，列出直接文件与子目录名称（不递归）。

脚本路径：`agent_runner/app/tools/scan_parent_dir.sh`

输入（stdin JSON）：

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder"
}
```

输出（stdout JSON）：

```json
{
  "success": true,
  "error": null,
  "root_path": "/target/folder",
  "files": [
    {
      "name": "a.docx",
      "path": "/target/folder/a.docx",
      "extension": ".docx",
      "size_bytes": 123456,
      "modified_at": "2026-05-09T10:00:00Z",
      "is_hidden": false,
      "is_symlink": false
    }
  ],
  "subdirs": ["existing_subdir_1", "existing_subdir_2"],
  "stats": {
    "file_count": 15,
    "subdir_count": 3,
    "by_extension": {".docx": 3, ".pdf": 5, ".jpg": 7}
  }
}
```

底层 bash 实现逻辑：

```bash
#!/bin/bash
# 读取 stdin JSON
INPUT=$(cat)
ROOT_PATH=$(echo "$INPUT" | jq -r '.root_path')
TASK_ID=$(echo "$INPUT" | jq -r '.task_id')

# 校验 root_path 存在且为目录
if [ ! -d "$ROOT_PATH" ]; then
  echo '{"success":false,"error":"root_path not found or not a directory"}'
  exit 1
fi

# 扫描直接文件（不递归，排除隐藏文件）
FILES_JSON=$(find "$ROOT_PATH" -maxdepth 1 -type f ! -name '.*' \
  -exec stat -f '{"name":"%N","path":"%N","size_bytes":%z,"modified_at":"%Sm"}' {} \; \
  | jq -s '.')

# 列出子目录名称（仅名称，不展开）
SUBDIRS_JSON=$(find "$ROOT_PATH" -maxdepth 1 -type d ! -path "$ROOT_PATH" ! -name '.*' \
  -exec basename {} \; | jq -R -s 'split("\n") | map(select(length > 0))')

# 输出组合结果
jq -n --arg root "$ROOT_PATH" --arg task_id "$TASK_ID" \
  --argjson files "$FILES_JSON" --argjson subdirs "$SUBDIRS_JSON" \
  '{
    success: true,
    error: null,
    root_path: $root,
    files: $files,
    subdirs: $subdirs,
    stats: {
      file_count: ($files | length),
      subdir_count: ($subdirs | length)
    }
  }'
```

约束：

1. 必须使用 `find -maxdepth 1`，禁止递归
2. 过滤 `.` 开头的隐藏文件
3. 标记符号链接（`-type l` 单独处理）
4. 子目录只返回名称列表，不返回内容

---

### 3.2 get_file_info.sh

职责：获取单个文件的详细属性（MIME 类型、文件大类等）。

脚本路径：`agent_runner/app/tools/get_file_info.sh`

输入（stdin JSON）：

```json
{
  "task_id": "uuid",
  "file_path": "/target/folder/a.docx"
}
```

输出（stdout JSON）：

```json
{
  "success": true,
  "error": null,
  "file_path": "/target/folder/a.docx",
  "name": "a.docx",
  "extension": ".docx",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "kind": "document",
  "size_bytes": 123456,
  "modified_at": "2026-05-09T10:00:00Z"
}
```

底层 bash 实现逻辑：

```bash
#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.file_path')
TASK_ID=$(echo "$INPUT" | jq -r '.task_id')

if [ ! -f "$FILE_PATH" ]; then
  echo '{"success":false,"error":"file not found"}'
  exit 1
fi

NAME=$(basename "$FILE_PATH")
EXT="${NAME##*.}"
MIME=$(file --mime-type -b "$FILE_PATH")
SIZE=$(stat -f "%z" "$FILE_PATH")
MTIME=$(stat -f "%Sm" -t "%Y-%m-%dT%H:%M:%SZ" "$FILE_PATH")

# MIME 类型到大类的映射
case "$MIME" in
  text/*|application/json|application/xml|application/javascript|application/pdf)
    KIND="document" ;;
  image/*) KIND="image" ;;
  video/*) KIND="video" ;;
  audio/*) KIND="audio" ;;
  application/zip|application/gzip|application/x-tar|application/x-7z-compressed)
    KIND="archive" ;;
  application/vnd.openxmlformats-officedocument.*) KIND="document" ;;
  *) KIND="other" ;;
esac

jq -n \
  --arg path "$FILE_PATH" \
  --arg name "$NAME" \
  --arg ext ".$EXT" \
  --arg mime "$MIME" \
  --arg kind "$KIND" \
  --argjson size "$SIZE" \
  --arg mtime "$MTIME" \
  '{
    success: true,
    error: null,
    file_path: $path,
    name: $name,
    extension: $ext,
    mime_type: $mime,
    kind: $kind,
    size_bytes: $size,
    modified_at: $mtime
  }'
```

约束：

1. 不限制文件类型，所有类型均返回结果
2. MIME 类型通过 `file --mime-type` 获取
3. kind 字段为大类映射，用于辅助关联判断

---

### 3.3 bash_create_dirs.sh

职责：在 root_path 下创建分类子目录。

脚本路径：`agent_runner/app/tools/bash_create_dirs.sh`

输入（stdin JSON）：

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder",
  "dry_run": true,
  "directories": ["工作文档", "图片素材", "代码项目"]
}
```

输出（stdout JSON）：

```json
{
  "success": true,
  "error": null,
  "steps": [
    {
      "step_id": "mkdir-001",
      "status": "planned",
      "command": "mkdir -p -- '/target/folder/工作文档'",
      "target_path": "/target/folder/工作文档"
    },
    {
      "step_id": "mkdir-002",
      "status": "completed",
      "command": "mkdir -p -- '/target/folder/图片素材'",
      "target_path": "/target/folder/图片素材"
    }
  ]
}
```

底层 bash 实现逻辑：

```bash
#!/bin/bash
INPUT=$(cat)
ROOT_PATH=$(echo "$INPUT" | jq -r '.root_path')
TASK_ID=$(echo "$INPUT" | jq -r '.task_id')
DRY_RUN=$(echo "$INPUT" | jq -r '.dry_run')
DIRS=$(echo "$INPUT" | jq -r '.directories[]')

STEPS="["
I=1
while IFS= read -r DIR; do
  TARGET_PATH="${ROOT_PATH}/${DIR}"

  # 路径逃逸检查：目标路径必须在 root_path 下
  CANON_TARGET=$(realpath "$TARGET_PATH" 2>/dev/null || echo "")
  CANON_ROOT=$(realpath "$ROOT_PATH")
  if [[ "$CANON_TARGET" != "$CANON_ROOT"/* ]] && [ -n "$CANON_TARGET" ]; then
    echo "{\"success\":false,\"error\":\"path escape detected: $TARGET_PATH\"}"
    exit 1
  fi

  STEP_ID=$(printf "mkdir-%03d" "$I")
  CMD="mkdir -p -- '$TARGET_PATH'"

  if [ "$DRY_RUN" = "true" ]; then
    STATUS="planned"
  else
    mkdir -p -- "$TARGET_PATH" 2>/dev/null
    if [ $? -eq 0 ]; then
      STATUS="completed"
    else
      STATUS="failed"
    fi
  fi

  STEPS="${STEPS}{\"step_id\":\"$STEP_ID\",\"status\":\"$STATUS\",\"command\":\"$CMD\",\"target_path\":\"$TARGET_PATH\"},"
  I=$((I+1))
done <<< "$DIRS"

STEPS="${STEPS%,}]"

echo "{\"success\":true,\"error\":null,\"steps\":$STEPS}"
```

约束：

1. 目录名使用相对路径拼接（root_path + dirname），防止路径逃逸
2. 执行前 canonicalize 校验目标路径在 root_path 范围内
3. dry_run=true 时不执行实际创建
4. 使用 `mkdir -p` 创建父级目录

---

### 3.4 bash_dry_run_moves.sh

职责：在不执行 mv 的前提下，检查移动计划是否可安全执行。

脚本路径：`agent_runner/app/tools/bash_dry_run_moves.sh`

输入（stdin JSON）：

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder",
  "moves": [
    {
      "source_path": "/target/folder/a.docx",
      "target_path": "/target/folder/工作文档/a.docx"
    }
  ]
}
```

输出（stdout JSON）：

```json
{
  "success": true,
  "error": null,
  "can_execute": true,
  "conflicts": [],
  "checks": [
    {
      "source_path": "/target/folder/a.docx",
      "target_path": "/target/folder/工作文档/a.docx",
      "source_exists": true,
      "target_absent": true,
      "within_root": true
    }
  ]
}
```

底层 bash 实现逻辑：

```bash
#!/bin/bash
INPUT=$(cat)
ROOT_PATH=$(echo "$INPUT" | jq -r '.root_path')
TASK_ID=$(echo "$INPUT" | jq -r '.task_id')
MOVE_COUNT=$(echo "$INPUT" | jq '.moves | length')

CANON_ROOT=$(realpath "$ROOT_PATH")
CHECKS="["
CONFLICTS="["
ALL_OK=true

for (( i=0; i<MOVE_COUNT; i++ )); do
  SOURCE=$(echo "$INPUT" | jq -r ".moves[$i].source_path")
  TARGET=$(echo "$INPUT" | jq -r ".moves[$i].target_path")

  SOURCE_EXISTS=false
  TARGET_ABSENT=false
  WITHIN_ROOT=false

  # 检查源文件存在
  test -f "$SOURCE" && SOURCE_EXISTS=true

  # 检查目标不存在（不覆盖）
  test ! -e "$TARGET" && TARGET_ABSENT=true

  # 检查目标在 root_path 范围内
  CANON_TARGET=$(realpath "$TARGET" 2>/dev/null || echo "")
  [[ "$CANON_TARGET" == "$CANON_ROOT"/* ]] && WITHIN_ROOT=true

  if [ "$SOURCE_EXISTS" != "true" ] || [ "$TARGET_ABSENT" != "true" ] || [ "$WITHIN_ROOT" != "true" ]; then
    ALL_OK=false
    CONFLICTS="${CONFLICTS}{\"source\":\"$SOURCE\",\"target\":\"$TARGET\",\"source_exists\":$SOURCE_EXISTS,\"target_absent\":$TARGET_ABSENT,\"within_root\":$WITHIN_ROOT},"
  fi

  CHECKS="${CHECKS}{\"source_path\":\"$SOURCE\",\"target_path\":\"$TARGET\",\"source_exists\":$SOURCE_EXISTS,\"target_absent\":$TARGET_ABSENT,\"within_root\":$WITHIN_ROOT},"
done

CHECKS="${CHECKS%,}]"
CONFLICTS="${CONFLICTS%,}]"

echo "{\"success\":true,\"error\":null,\"can_execute\":$ALL_OK,\"conflicts\":$CONFLICTS,\"checks\":$CHECKS}"
```

约束：

1. 逐条检查，不执行实际 mv
2. `test -f` 检查源存在
3. `test ! -e` 检查目标不存在（禁止覆盖）
4. realpath 校验目标在 root_path 范围内

---

### 3.5 bash_move_files.sh

职责：按计划执行真实的文件移动。

脚本路径：`agent_runner/app/tools/bash_move_files.sh`

输入（stdin JSON）：

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder",
  "moves": [
    {
      "source_path": "/target/folder/a.docx",
      "target_path": "/target/folder/工作文档/a.docx"
    }
  ]
}
```

输出（stdout JSON）：

```json
{
  "success": true,
  "error": null,
  "steps": [
    {
      "step_id": "move-001",
      "status": "completed",
      "command": "mv -- '/target/folder/a.docx' '/target/folder/工作文档/a.docx'",
      "source_path": "/target/folder/a.docx",
      "target_path": "/target/folder/工作文档/a.docx"
    }
  ],
  "summary": {
    "total": 1,
    "completed": 1,
    "failed": 0
  }
}
```

底层 bash 实现逻辑：

```bash
#!/bin/bash
INPUT=$(cat)
ROOT_PATH=$(echo "$INPUT" | jq -r '.root_path')
TASK_ID=$(echo "$INPUT" | jq -r '.task_id')
MOVE_COUNT=$(echo "$INPUT" | jq '.moves | length')

CANON_ROOT=$(realpath "$ROOT_PATH")
STEPS="["
COMPLETED=0
FAILED=0

for (( i=0; i<MOVE_COUNT; i++ )); do
  SOURCE=$(echo "$INPUT" | jq -r ".moves[$i].source_path")
  TARGET=$(echo "$INPUT" | jq -r ".moves[$i].target_path")
  STEP_ID=$(printf "move-%03d" $((i+1)))
  CMD="mv -- '$SOURCE' '$TARGET'"

  # 执行前检查
  if [ ! -f "$SOURCE" ]; then
    STATUS="failed"
    FAILED=$((FAILED+1))
    STEPS="${STEPS}{\"step_id\":\"$STEP_ID\",\"status\":\"$STATUS\",\"command\":\"$CMD\",\"source_path\":\"$SOURCE\",\"target_path\":\"$TARGET\",\"error\":\"source not found\"},"
    break
  fi

  CANON_TARGET=$(realpath "$TARGET" 2>/dev/null || echo "")
  if [[ "$CANON_TARGET" != "$CANON_ROOT"/* ]]; then
    STATUS="failed"
    FAILED=$((FAILED+1))
    STEPS="${STEPS}{\"step_id\":\"$STEP_ID\",\"status\":\"$STATUS\",\"command\":\"$CMD\",\"source_path\":\"$SOURCE\",\"target_path\":\"$TARGET\",\"error\":\"target outside root_path\"},"
    break
  fi

  # 执行移动
  mv -- "$SOURCE" "$TARGET" 2>/dev/null
  if [ $? -eq 0 ]; then
    STATUS="completed"
    COMPLETED=$((COMPLETED+1))
  else
    STATUS="failed"
    FAILED=$((FAILED+1))
    STEPS="${STEPS}{\"step_id\":\"$STEP_ID\",\"status\":\"$STATUS\",\"command\":\"$CMD\",\"source_path\":\"$SOURCE\",\"target_path\":\"$TARGET\",\"error\":\"mv command failed\"},"
    break
  fi

  STEPS="${STEPS}{\"step_id\":\"$STEP_ID\",\"status\":\"$STATUS\",\"command\":\"$CMD\",\"source_path\":\"$SOURCE\",\"target_path\":\"$TARGET\"},"
done

STEPS="${STEPS%,}]"
SUCCESS=$([ "$FAILED" -eq 0 ] && echo "true" || echo "false")

echo "{\"success\":$SUCCESS,\"error\":null,\"steps\":$STEPS,\"summary\":{\"total\":$MOVE_COUNT,\"completed\":$COMPLETED,\"failed\":$FAILED}}"
```

执行规则：

1. 逐条执行 mv，禁止批量拼接
2. 每条执行前再次校验 source_path 存在性与 target_path 边界
3. 任一条失败立即停止后续执行（break），保留失败位置
4. 失败后调用方应转入回滚流程

---

### 3.6 bash_rollback.sh

职责：根据 execution_log.json 将本次任务产生的移动按逆序撤销。

脚本路径：`agent_runner/app/tools/bash_rollback.sh`

输入（stdin JSON）：

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder",
  "execution_log_path": ".agent-file-organizer/tasks/{task_id}/execution_log.json"
}
```

输出（stdout JSON）：

```json
{
  "success": true,
  "error": null,
  "steps": [
    {
      "step_id": "rollback-001",
      "original_step_id": "move-001",
      "status": "completed",
      "command": "mv -- '/target/folder/工作文档/a.docx' '/target/folder/a.docx'",
      "source_path": "/target/folder/工作文档/a.docx",
      "target_path": "/target/folder/a.docx"
    }
  ],
  "cleaned_dirs": ["/target/folder/工作文档"]
}
```

底层 bash 实现逻辑：

```bash
#!/bin/bash
INPUT=$(cat)
TASK_ID=$(echo "$INPUT" | jq -r '.task_id')
ROOT_PATH=$(echo "$INPUT" | jq -r '.root_path')
LOG_PATH=$(echo "$INPUT" | jq -r '.execution_log_path')

if [ ! -f "$LOG_PATH" ]; then
  echo '{"success":false,"error":"execution_log not found"}'
  exit 1
fi

# 逆序提取 move_file 类型的已完成步骤
STEPS_TO_ROLLBACK=$(jq '[.steps[] | select(.step_type=="move_file" and .status=="completed")] | reverse' "$LOG_PATH")

STEP_COUNT=$(echo "$STEPS_TO_ROLLBACK" | jq 'length')
ROLLBACK_STEPS="["
CLEANED_DIRS="["
declare -A DIRS_CREATED

for (( i=0; i<STEP_COUNT; i++ )); do
  ORIG_STEP_ID=$(echo "$STEPS_TO_ROLLBACK" | jq -r ".[$i].step_id")
  SRC=$(echo "$STEPS_TO_ROLLBACK" | jq -r ".[$i].source_path")
  TGT=$(echo "$STEPS_TO_ROLLBACK" | jq -r ".[$i].target_path")

  RB_ID=$(printf "rollback-%03d" $((i+1)))
  CMD="mv -- '$TGT' '$SRC'"

  # 反向移动
  mv -- "$TGT" "$SRC" 2>/dev/null
  if [ $? -eq 0 ]; then
    STATUS="completed"
    # 记录目标目录以便后续清理
    TGT_DIR=$(dirname "$TGT")
    DIRS_CREATED["$TGT_DIR"]=1
  else
    STATUS="failed"
  fi

  ROLLBACK_STEPS="${ROLLBACK_STEPS}{\"step_id\":\"$RB_ID\",\"original_step_id\":\"$ORIG_STEP_ID\",\"status\":\"$STATUS\",\"command\":\"$CMD\",\"source_path\":\"$TGT\",\"target_path\":\"$SRC\"},"
done

# 清理已空的目录
for DIR in "${!DIRS_CREATED[@]}"; do
  if [ -d "$DIR" ] && [ -z "$(ls -A "$DIR" 2>/dev/null)" ]; then
    rmdir -- "$DIR" 2>/dev/null
    CLEANED_DIRS="${CLEANED_DIRS}\"$DIR\","
  fi
done

ROLLBACK_STEPS="${ROLLBACK_STEPS%,}]"
CLEANED_DIRS="${CLEANED_DIRS%,}]"

echo "{\"success\":true,\"error\":null,\"steps\":$ROLLBACK_STEPS,\"cleaned_dirs\":$CLEANED_DIRS}"
```

约束：

1. 逆序读取 execution_log 中的 move_file 步骤
2. 反向执行 mv（target → source）
3. 回滚完成后删除本次创建且已空的目录（rmdir）
4. 只回滚当前 task_id 产生的动作
5. rmdir 只删除空目录，非空目录保留

---

## 4. 执行日志 Schema

`execution_log.json` 覆盖目录创建、文件移动、失败和回滚触发点。

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder",
  "started_at": "2026-05-09T10:00:00Z",
  "finished_at": null,
  "status": "running",
  "steps": [
    {
      "step_id": "mkdir-001",
      "step_type": "create_directory",
      "sequence": 1,
      "status": "completed",
      "command": "mkdir -p -- '/target/folder/工作文档'",
      "source_path": null,
      "target_path": "/target/folder/工作文档",
      "stdout": "",
      "stderr": "",
      "started_at": "2026-05-09T10:00:00Z",
      "finished_at": "2026-05-09T10:00:00Z"
    },
    {
      "step_id": "move-001",
      "step_type": "move_file",
      "sequence": 2,
      "status": "completed",
      "command": "mv -- '/target/folder/a.docx' '/target/folder/工作文档/a.docx'",
      "source_path": "/target/folder/a.docx",
      "target_path": "/target/folder/工作文档/a.docx",
      "stdout": "",
      "stderr": "",
      "started_at": "2026-05-09T10:00:01Z",
      "finished_at": "2026-05-09T10:00:01Z"
    }
  ],
  "summary": {
    "created_directories": 1,
    "moved_files": 3,
    "failed_steps": 0,
    "rolled_back_steps": 0
  }
}
```

---

## 5. 回滚日志 Schema

```json
{
  "task_id": "uuid",
  "triggered_by": "execution_failure",
  "started_at": "2026-05-09T10:00:03Z",
  "finished_at": "2026-05-09T10:00:04Z",
  "status": "completed",
  "steps": [
    {
      "step_id": "rollback-001",
      "original_step_id": "move-001",
      "step_type": "rollback_move_file",
      "status": "completed",
      "command": "mv -- '/target/folder/工作文档/a.docx' '/target/folder/a.docx'",
      "source_path": "/target/folder/工作文档/a.docx",
      "target_path": "/target/folder/a.docx",
      "stderr": ""
    }
  ],
  "cleaned_directories": ["/target/folder/工作文档"]
}
```

---

## 6. Harness 检测报告 Schema

Harness Agent 在执行完成后输出 `harness_report.json`，由 Agent 工作流层的 `harness_check` 节点生成并落盘。bash 工具层不参与此报告的生成，但报告中的 `execution_consistency` 维度依赖 execution_log.json。

```json
{
  "task_id": "uuid",
  "generated_at": "2026-05-09T10:00:05Z",
  "verdict": "pass",
  "overall_assessment": "分类方案合理，无遗漏文件，关联判断基本正确",
  "checks": {
    "completeness": {
      "passed": true,
      "total_files": 15,
      "classified_files": 15,
      "unclassified_files": 0,
      "detail": "所有文件均已分类，无遗漏"
    },
    "association_spot_check": {
      "passed": true,
      "samples_checked": 3,
      "issues_found": 0,
      "detail": "抽查 group_001、group_002、group_003，关联判断合理"
    },
    "naming_spot_check": {
      "passed": true,
      "samples_checked": 3,
      "issues_found": 0,
      "detail": "抽查 3 个分类名称，命名恰当"
    },
    "execution_consistency": {
      "passed": true,
      "planned_moves": 15,
      "actual_moves": 15,
      "mismatches": 0,
      "detail": "计划与执行一致"
    }
  },
  "issues": [],
  "suggestions": []
}
```

verdict 枚举与后续动作：

| verdict | 含义 | 后续动作 |
|---------|------|---------|
| pass | 所有检查通过 | 进入 Complete |
| warn | 存在可疑项但不确定为错误 | 问题项回传 HumanReview，由用户决定 |
| fail | 存在明确错误（遗漏、误分类） | 建议回滚或重新规划 |

---

## 7. 状态枚举

任务主状态：

| 状态 | 说明 |
|------|------|
| created | 任务已创建 |
| scanning | 正在扫描父级目录 |
| planned | 计划已生成，等待确认 |
| review_required | 存在需人工审核的项 |
| approved | 人工审核通过 |
| executing | 正在执行 |
| completed | 执行完成 |
| failed | 执行失败 |
| rolled_back | 已回滚 |

步骤子状态：

| 状态 | 说明 |
|------|------|
| planned | 已规划，待执行（dry_run 模式） |
| running | 正在执行 |
| completed | 执行成功 |
| failed | 执行失败 |
| skipped | 已跳过 |

---

## 8. 本地任务目录结构

```text
.agent-file-organizer/
  tasks/
    {task_id}/
      request.json          # 任务请求（仅 root_path + dry_run）
      scan_result.json      # 扫描结果（父级文件清单）
      associations.json     # Agent A 输出：文件关联分组结果
      plan.json             # Agent B 输出：分类方案与移动计划
      execution_log.json    # 执行日志
      harness_report.json   # Harness Agent 输出：检测报告
      rollback_log.json     # 回滚日志
```

---

## 9. 开发约束

1. 所有执行与回滚步骤都必须能映射到唯一 step_id
2. 目录创建与文件移动必须记录原始 command 文本，便于排障
3. 日志必须能够独立支撑回滚，不依赖内存态
4. 不允许把多个 mv 合并进一条无法拆分审计的命令
5. 所有工具脚本必须是独立的 .sh 文件，可单独测试
6. 工具脚本只接受 stdin JSON，只输出 stdout JSON（stderr 用于调试日志）
7. 扫描必须使用 `find -maxdepth 1`，禁止递归遍历子目录
8. 不限制文件类型，所有文件均参与分类
9. Harness Agent 的 execution_consistency 检查必须使用 execution_log.json 中的实际数据
10. Agent A、Agent B、Harness Agent 的输入输出文件由工作流层管理，不在 bash 工具层处理
