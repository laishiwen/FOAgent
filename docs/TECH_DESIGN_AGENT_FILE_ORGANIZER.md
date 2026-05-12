# Agent 文件分类整理项目技术设计文档

## 1. 文档信息

- 项目名称：Agent 文件分类整理系统
- 文档版本：v3.0
- 文档日期：2026-05-09
- 适用阶段：第一版可开发实现
- 目标形态：前端仅提供源文件夹路径，3 个串联 Agent（关联分析 → 分类命名 → 终检）按工作流调用 bash shell 工具完成文件理解、关联识别、分类规划、创建目录、执行移动与最终检测

## 2. 背景与目标

当前目标是构建一个可控的文件整理 Agent 系统。用户在前端只提供源文件夹路径后，Agent 需要在本地完成以下动作：

1. 扫描父级目录下的文件（不做层级遍历）
2. 识别文件之间的关联关系
3. 将有关联的文件归入相同分类，无关联的文件各自独立分类
4. 输出分类方案与目标文件结构
5. 新建分类文件夹
6. 按规划结果移动文件

本项目的核心难点在于：

1. 文件关联判断必须稳定且可解释
2. 文件移动必须可预览、可确认、可回滚
3. 模型只能负责决策，不应直接控制高风险文件操作
4. 分类依据来自文件名、类型、大小、修改时间等可直接获取的属性
5. 不限制文件类型，所有类型文件均参与分类

因此，系统采用"前端只提供路径 + 3 个串联 Agent（关联分析 → 分类命名 → 终检）+ 本地 bash shell 工具负责执行"的架构。三个 Agent 职责边界清晰：Agent A 判断文件关联、Agent B 生成分类方案、Harness Agent 在最终做语义层独立复检。

## 3. 范围定义

### 3.1 本期目标

第一版必须支持：

1. 扫描父级目录并输出文件清单（仅父级，不遍历子目录）
2. 获取文件基础属性（名称、扩展名、大小、修改时间、MIME 类型）
3. Agent A 识别文件之间的关联关系，决定归组
4. Agent B 根据关联结果为每组文件生成分类名称
5. 生成目标文件结构（父级目录下的分类子目录）
6. 支持 dry-run 预览
7. 支持创建目录与实际移动文件
8. 支持执行日志和回滚
9. Harness Agent 在最终做语义层独立复检，输出检测报告
10. 提供前端可消费的最小调用协议
11. 不限制文件类型，所有类型均参与分类

### 3.2 非目标

第一版暂不处理：

1. 跨磁盘移动优化
2. 多用户并发整理同一目录
3. 云端对象存储整理
4. 子目录遍历与层级重组
5. 文件内容深度语义分析
6. 图片高级视觉理解
7. 自动覆盖同名目标文件

## 4. 关键业务规则

系统必须固化以下规则，不能依赖模型临时理解：

1. 只处理父级目录内的直接文件，不做子目录层级遍历
2. 不限制文件类型，所有类型文件均参与分类
3. 识别文件之间的关联关系：有关联的文件归入相同分类，无关联的文件各自独立分类
4. 隐藏系统文件（. 开头）默认不移动
5. 符号链接默认不处理
6. 目标路径若冲突，不允许直接覆盖
7. 低置信度结果必须进入人工确认队列
8. 所有文件移动必须先经过计划生成，再执行
9. 所有执行步骤必须产生审计日志
10. 执行失败必须支持基于日志回滚

## 5. 方案选型

### 5.1 模型配置

```text
MODEL_NAME = "qwen3.5:9b"
BASE_URL = "http://localhost:4141/v1"
API_KEY = "11111"
```

模型调用约束：

1. 关闭思维链（thinking / chain-of-thought），禁止模型输出推理过程
2. 输出必须是结构化 JSON
3. 模型只负责决策与规划，不直接执行文件操作

### 5.2 Agent 架构：串联 3 Agent

本项目采用 **3 个串联 Agent**，而非单 Agent 或多 Agent 协作框架。原因：

1. **Agent A（关联分析器）** 与 **Agent B（分类命名器）** 任务性质不同 —— 一个是关系判断，一个是语义命名。拆分后每个 Agent 的提示词高度聚焦，qwen3.5:9b 小模型也能胜任。
2. **Harness Agent（终检器）** 在执行完成后独立复查 —— 小模型出错概率不低，用同一个模型带不同视角做一次只读检查，能拦截相当一部分错误。代价仅是一次额外调用。
3. 拆分后错误不会传播：关联判断出错时，分类命名阶段可发现异常并回传修正；分类完成后 Harness 再做独立抽检。

Agent 拓扑：

```text
Agent A (关联分析) → Agent B (分类命名) → 执行 → Harness Agent (终检)
```

### 5.3 推荐工作流框架

推荐使用轻量级工作流状态机（如 LangGraph 或自建状态机）作为 Agent 调度框架。

选择原因：

1. 任务是强状态流转，不是自由对话
2. 每个阶段都需要明确输入输出
3. 需要支持中断、确认、恢复、重试
4. 需要在执行前插入人工审核节点
5. Agent 按照工作流逐步调用 bash shell 工具

### 5.4 不优先采用的方案

不建议第一版使用多 Agent 协作框架（AutoGen、CrewAI 等）。原因：

1. 当前问题是流程控制，不是角色协作
2. 多 Agent 会增加决策漂移和调试成本
3. 文件整理任务更适合单 Agent 加确定性工具层

### 5.5 推荐技术栈

- Agent 工作流：轻量状态机 / LangGraph
- 模型接入：OpenAI 兼容接口（qwen3.5:9b @ localhost:4141）
- 本地运行时：Python CLI 或 Node.js 桌面宿主
- 文件系统操作：bash shell 脚本工具为主（.sh），Python/Node 负责工作流调度与工具调用封装
- 本地状态存储：JSON 文件
- 前端：React / Electron / Tauri，负责目录选择、预览、确认、执行结果展示
- 日志与审计：本地 JSON 日志

## 6. 总体架构

### 6.1 架构原则

1. 模型只负责判断和规划，不直接执行文件操作
2. 文件创建与移动必须通过 bash shell 工具统一执行
3. 工作流显式持有任务状态
4. 所有中间结果都应结构化存储
5. 执行动作必须支持 dry-run 和 rollback
6. Agent 按工作流节点逐步调用工具，工具底层为 bash shell 脚本

### 6.2 架构分层

系统划分为五层：

1. 前端交互层
2. 本地调用桥接层
3. Agent 工作流层
4. bash shell 工具执行层
5. 本地存储与审计层

### 6.3 模块职责

#### 前端交互层

职责：

1. 选择源文件夹
2. 触发扫描与分类
3. 展示当前文件列表
4. 展示分类方案与移动计划
5. 展示低置信度项供人工调整
6. 确认执行或回滚

前端仅向接口提供源文件夹路径，不传递规则配置或分类体系。

#### 本地调用桥接层

职责：

1. 从前端接收 root_path
2. 校验路径是否存在且可访问
3. 创建本地任务记录
4. 调用 Agent 工作流
5. 向前端返回计划、执行状态和结果

桥接方式二选一：

1. Electron / Tauri IPC
2. 本地 CLI 进程调用

#### Agent 工作流层

职责：

1. 按工作流节点调度扫描、关联检测、分类、规划、审核、执行、校验、回滚
2. 聚合上下文
3. 控制状态流转与异常处理
4. 在每个节点按需调用对应的 bash shell 工具

#### bash shell 工具执行层

职责：

1. 通过 bash 脚本扫描父级目录文件列表
2. 通过 bash 脚本获取文件属性
3. 通过 bash 创建分类目录（mkdir -p）
4. 通过 bash 移动文件（mv）
5. 通过 bash 回滚移动（逆序 mv）

所有工具底层均为 bash shell 脚本，由 Agent 工作流层通过结构化参数调用。

#### 本地存储与审计层

职责：

1. 保存任务元数据
2. 保存扫描结果
3. 保存分类结果
4. 保存移动计划
5. 保存执行日志和回滚日志

## 7. 工作流设计

### 7.1 状态机概览

工作流定义如下节点（标注各节点由谁执行）：

| 序号 | 节点 | 执行者 | 说明 |
|------|------|--------|------|
| 1 | ScanParentLevel | bash 工具 | 扫描父级目录文件 |
| 2 | AnalyzeFileAttributes | bash 工具 | 获取文件基础属性 |
| 3 | DetectFileAssociations | **Agent A** | 识别文件关联关系 |
| 4 | BuildCategories | **Agent B** | 根据关联生成分类 |
| 5 | GeneratePlan | 确定性逻辑 | 生成目标结构与移动计划 |
| 6 | ValidatePlan | bash 工具 | 校验计划 |
| 7 | HumanReview | 人工 | 审核低置信度项 |
| 8 | ExecutePlan | bash 工具 | 执行计划 |
| 9 | VerifyExecution | bash 工具 | 校验执行结果 |
| 10 | HarnessCheck | **Harness Agent** | 语义层独立复检 |
| 11 | Rollback | bash 工具 | 回滚 |
| 12 | Complete | — | 完成 |

执行路径：

1. 前端只提交 root_path
2. bash 工具扫描父级文件并获取属性
3. Agent A 分析文件关联，输出关联分组
4. Agent B 根据关联分组生成分类方案
5. 确定性逻辑将分类方案转为移动计划
6. 计划校验通过后（含人工审核），bash 工具执行目录创建和文件移动
7. 执行完成后 Harness Agent 独立复检，输出检测报告
8. 检测通过则完成，检测发现问题则回人工审核或回滚

### 7.2 节点说明

#### 7.2.1 ScanParentLevel

输入：root_path

输出：

1. 父级目录下直接文件清单（不含子目录内容）
2. 文件基础元数据（名称、扩展名、大小、修改时间）
3. 子目录列表（仅列出名称，不展开内部）

说明：

1. 只扫描 root_path 的直接子项，不做递归
2. 过滤 . 开头的隐藏文件
3. 标记符号链接

#### 7.2.2 AnalyzeFileAttributes

输入：文件清单

输出：每个文件的属性信息

说明：

1. 获取 MIME 类型
2. 判断是否为文本文件
3. 识别文件大类（文档、图片、代码、压缩包、音视频等）

#### 7.2.3 DetectFileAssociations（Agent A：关联分析器）

输入：文件属性列表

输出：文件关联关系

说明：

1. 由 **Agent A（关联分析器）** 负责，调用模型进行关联判断
2. 基于文件名、扩展名、类型、大小、修改时间等判断关联
3. 关联判断依据：
   - 同名不同扩展名（如 report.docx 与 report.xlsx）
   - 文件名前缀一致（如 project-a-v1.pdf、project-a-v2.pdf）
   - 同类文件修改时间相近
   - 文件名包含相同关键词
4. 输出关联组，每组包含关联文件列表及置信度
5. 无关联的文件各自独立成组
6. Agent A 只做关联判断，不做分类命名

#### 7.2.4 BuildCategories（Agent B：分类命名器）

输入：关联组列表

输出：分类方案

说明：

1. 由 **Agent B（分类命名器）** 负责，调用模型进行语义命名
2. 为每个关联组生成分类名称
3. 若组内文件可推断共同主题，则以主题命名
4. 若无法推断，则以文件共性特征命名（如"文档类"、"图片类"）
5. 独立文件各自分配分类
6. 低置信度的分类标记 needs_review
7. Agent B 若发现 Agent A 的关联分组明显不合理，可标记 needs_review 回传

#### 7.2.5 GeneratePlan

输入：分类方案

输出：

1. 目标目录列表（需在 root_path 下创建的分类子目录）
2. 移动计划（每个文件的源路径 → 目标路径）
3. 计划理由

#### 7.2.6 ValidatePlan

输入：移动计划

输出：校验结果

校验项：

1. 目标路径冲突
2. 非法路径
3. 重复目标文件
4. 禁止覆盖风险
5. 计划完整性

#### 7.2.7 HumanReview

输入：计划结果与待审核项

输出：

1. 用户确认通过
2. 用户局部修改
3. 用户拒绝执行

说明：

1. 仅当存在低置信度项、冲突项或用户开启人工确认时进入
2. 第一版可做同步确认接口

#### 7.2.8 ExecutePlan

输入：最终确认的移动计划

输出：执行结果和操作日志

执行顺序：

1. 调用 bash 工具创建缺失目录
2. 调用 bash 工具按计划逐条移动文件
3. 记录每一步操作

#### 7.2.9 VerifyExecution

输入：执行日志、目标目录状态

输出：校验结果

校验项：

1. 所有源文件是否已移动
2. 所有目标文件是否存在
3. 是否存在漏移或误移

说明：此节点为 bash 层校验（文件级），不做语义判断。

#### 7.2.10 HarnessCheck（Harness Agent：终检器）

输入：原始文件清单、关联分组结果、最终分类方案、执行结果

输出：检测报告

说明：

1. 由 **Harness Agent（终检器）** 负责，在所有 bash 执行完成后运行
2. 只读操作，不修改任何文件
3. 检测项：
   - 是否有文件未被分类（遗漏检测）
   - 抽查关联判断是否合理（抽 2-3 组）
   - 抽查分类命名是否恰当（抽 2-3 个分类）
   - 分类结果与计划是否一致
4. 输出检测报告，包含：
   - 整体评估（pass / warn / fail）
   - 发现的问题列表
   - 建议修正项
5. pass → 进入 Complete
6. warn → 问题项回传 HumanReview，由用户决定
7. fail → 建议回滚或重新规划

#### 7.2.11 Rollback

输入：执行日志

输出：回滚结果

说明：

1. 调用 bash 工具按逆序回退移动
2. 删除本次创建且已空的目录
3. 记录回滚明细

## 8. Agent 设计

### 8.1 总体架构

系统使用 **3 个串联 Agent**，共享同一模型实例但各自持有独立的提示词和输入输出 Schema：

```text
Agent A (关联分析器) → Agent B (分类命名器) → [执行] → Harness Agent (终检器)
```

三个 Agent 均使用 qwen3.5:9b，调用参数一致，仅提示词和输入输出不同。

### 8.2 模型调用配置（三个 Agent 共用）

```python
MODEL_NAME = "qwen3.5:9b"
BASE_URL = "http://localhost:4141/v1"
API_KEY = "11111"
```

调用参数：

- temperature: 0（确保结果稳定）
- 关闭 thinking / chain-of-thought
- response_format: json_object（强制 JSON 输出）

### 8.3 通用约束（三个 Agent 均遵守）

1. 只能根据工具返回的数据或上一 Agent 输出进行判断
2. 不允许编造文件内容或虚构文件属性
3. 输出必须是结构化 JSON
4. 对低置信度项必须显式标记
5. 只处理父级目录内文件，不考虑子目录

---

### 8.4 Agent A：关联分析器

**职责**：识别文件之间的关联关系，输出关联分组。不做分类命名。

**输入上下文**：

1. 任务上下文（task_id、root_path）
2. 业务规则（仅父级文件、不限制类型、关联归组规则）
3. 文件属性清单（由 scan_parent_dir.sh + get_file_info.sh 返回）

**输出 Schema**：

```json
{
  "groups": [
    {
      "group_id": "group_001",
      "members": [
        "/target/folder/project-a-report.docx",
        "/target/folder/project-a-data.xlsx"
      ],
      "association_type": "same_prefix",
      "reason": "文件名前缀一致(project-a-)，类型互补",
      "confidence": 0.92,
      "needs_review": false
    }
  ],
  "ungrouped_files": [
    {
      "path": "/target/folder/notes.txt",
      "reason": "无关联文件",
      "confidence": 0.70,
      "needs_review": true
    }
  ]
}
```

**核心提示词要点**：

1. 你是文件关联分析器，只判断文件间是否存在关联，不负责命名分类
2. 基于文件名、扩展名、MIME 类型、大小、修改时间判断关联
3. 关联判断优先级：同名不同后缀 > 共同前缀 > 共同关键词 > 时间聚集 > 类型互补
4. 无关联的文件放入 ungrouped_files
5. 低置信度关联标记 needs_review=true
6. 禁止输出思维链

---

### 8.5 Agent B：分类命名器

**职责**：根据 Agent A 的关联分组结果，为每组生成分类名称和最终分类方案。

**输入上下文**：

1. 任务上下文（task_id、root_path）
2. Agent A 的输出（关联分组 + 独立文件）
3. 文件属性清单（用于辅助命名参考）

**输出 Schema**：

```json
{
  "categories": [
    {
      "category_name": "项目A文档",
      "group_id": "group_001",
      "members": [
        "/target/folder/project-a-report.docx",
        "/target/folder/project-a-data.xlsx"
      ],
      "reason": "同属 project-a 项目，办公文档组合",
      "confidence": 0.90,
      "needs_review": false
    }
  ],
  "category_order": ["项目A文档", "临时图片", "杂项"],
  "notes": []
}
```

**核心提示词要点**：

1. 你是文件分类命名器，根据关联分组为每组生成中文分类名称
2. 若能推断共同主题，以主题命名（如"项目A文档"、"财务资料"）
3. 若为同类文件聚集，以类型+特征命名（如"会议照片"）
4. 独立文件归入"未分类"或单独命名
5. 若发现 Agent A 的关联分组明显不合理，在 notes 中标明并标记 needs_review
6. 禁止输出思维链

---

### 8.6 Harness Agent：终检器

**职责**：在所有 bash 执行完成后，独立对最终结果做语义层复检。只读不写，输出检测报告。

**输入上下文**：

1. 任务上下文（task_id、root_path）
2. 原始文件清单（scan_result.json）
3. Agent A 关联分组结果（associations.json）
4. Agent B 分类方案（plan.json）
5. 执行结果（execution_log.json）

**输出 Schema**：

```json
{
  "verdict": "pass",
  "overall_assessment": "分类方案合理，无遗漏文件，关联判断基本正确",
  "checks": {
    "completeness": {
      "passed": true,
      "total_files": 15,
      "classified_files": 15,
      "unclassified_files": 0,
      "detail": "所有文件均已分类"
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

**verdict 判定规则**：

| 判决 | 条件 | 后续动作 |
|------|------|---------|
| pass | 所有检查通过 | 进入 Complete |
| warn | 存在可疑项但不确定为错误 | 问题项回传 HumanReview |
| fail | 存在明确错误（遗漏、误分类） | 建议回滚或重新规划 |

**核心提示词要点**：

1. 你是文件分类终检器，独立复查已完成分类的结果
2. 只读操作，只输出检测报告，不修改任何文件或计划
3. 检测四个维度：完整性、关联合理性、命名恰当性、执行一致性
4. 抽查而非全量检查（每个维度抽 2-3 项）
5. 明确给出 pass / warn / fail 判决
6. 发现问题时给出具体修正建议
7. 禁止输出思维链

## 9. 工具设计

### 9.1 设计原则

1. 所有工具底层均为 bash shell 脚本（.sh 文件）
2. Agent 工作流层通过结构化参数调用这些脚本
3. 脚本接收 JSON 参数（通过 stdin 或命令行参数），输出 JSON 结果
4. 所有工具必须返回 success 字段和 error 字段
5. 文件操作工具必须幂等或可检测重复执行
6. 任何真实修改动作都必须带 task_id
7. bash 工具必须只接受结构化参数，不接受自由文本命令
8. bash 工具必须内置路径白名单校验

### 9.2 工具清单

#### 9.2.1 scan_parent_dir.sh

功能：扫描父级目录，列出直接文件（不递归子目录）

输入（stdin JSON）：

```json
{
  "root_path": "/target/folder",
  "task_id": "uuid"
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
  "subdirs": ["existing_folder_1", "existing_folder_2"],
  "stats": {
    "file_count": 15,
    "subdir_count": 3,
    "by_extension": {".docx": 3, ".pdf": 5, ".jpg": 7}
  }
}
```

底层实现：

```bash
# 使用 ls、find（maxdepth 1）、stat 等命令
find "$root_path" -maxdepth 1 -type f ! -name '.*'
```

#### 9.2.2 get_file_info.sh

功能：获取单个文件的详细属性（MIME 类型等）

输入（stdin JSON）：

```json
{
  "file_path": "/target/folder/a.docx",
  "task_id": "uuid"
}
```

输出（stdout JSON）：

```json
{
  "success": true,
  "error": null,
  "file_path": "/target/folder/a.docx",
  "extension": ".docx",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "kind": "document",
  "size_bytes": 123456,
  "modified_at": "2026-05-09T10:00:00Z"
}
```

底层实现：

```bash
# 使用 file 命令获取 MIME 类型
file --mime-type -b "$file_path"
# 使用 stat 获取文件属性
stat -f "%z %m" "$file_path"
```

#### 9.2.3 bash_create_dirs.sh

功能：在 root_path 下创建分类子目录

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
    }
  ]
}
```

底层实现：

```bash
# 逐条执行 mkdir -p
mkdir -p -- "$root_path/$dirname"
```

约束：

1. 统一使用 mkdir -p
2. 所有路径必须校验在 root_path 范围内
3. 目录名使用相对路径拼接，防止路径逃逸

#### 9.2.4 bash_dry_run_moves.sh

功能：模拟执行移动计划，不实际改动文件

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
      "source_exists": true,
      "target_absent": true,
      "within_root": true
    }
  ]
}
```

底层实现：

```bash
# 逐条检查，不执行 mv
test -f "$source_path"   # 源存在
test ! -e "$target_path" # 目标不存在
```

#### 9.2.5 bash_move_files.sh

功能：执行真实文件移动

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
  ]
}
```

底层实现：

```bash
# 逐条执行 mv
mv -- "$source_path" "$target_path"
```

执行规则：

1. 逐条执行，禁止一次性拼接大批量命令
2. 每条执行前再次校验 source_path 与 target_path
3. 任一条失败立即停止并返回失败位置

#### 9.2.6 bash_rollback.sh

功能：基于执行日志按逆序撤销文件移动

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
      "status": "completed",
      "command": "mv -- '/target/folder/工作文档/a.docx' '/target/folder/a.docx'"
    }
  ]
}
```

底层实现：

```bash
# 逆序读取执行日志，逐条反向 mv
mv -- "$target_path" "$source_path"
# 删除本次创建且为空的目录
rmdir -- "$empty_dir" 2>/dev/null
```

### 9.3 工具设计约束

1. 所有工具必须返回 JSON
2. 所有工具必须返回 success 字段和 error 字段
3. 文件操作工具必须幂等或可检测重复执行
4. 任何真实修改动作都必须带 task_id
5. bash 工具必须只接受结构化参数，不接受自由文本命令
6. bash 工具必须内置 root_path 白名单校验
7. 工具底层均为 bash shell 脚本，工作流层通过 subprocess 调用

## 10. 上下文 Schema 设计

### 10.1 任务请求 Schema

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder",
  "mode": "local_plan_and_execute",
  "dry_run": true
}
```

前端仅传入 root_path 和 dry_run 标志，不传规则配置与分类体系。

### 10.2 文件关联结果 Schema

```json
{
  "groups": [
    {
      "group_id": "group_001",
      "category_name": "项目A文档",
      "members": [
        "/target/folder/project-a-report.docx",
        "/target/folder/project-a-data.xlsx",
        "/target/folder/project-a-slides.pptx"
      ],
      "reason": "相同前缀 project-a，类型互补，属于同一项目",
      "confidence": 0.92,
      "needs_review": false
    },
    {
      "group_id": "group_002",
      "category_name": "临时图片",
      "members": [
        "/target/folder/IMG_001.jpg",
        "/target/folder/IMG_002.jpg"
      ],
      "reason": "相同前缀 IMG_，修改时间相近，同类文件",
      "confidence": 0.85,
      "needs_review": false
    },
    {
      "group_id": "group_003",
      "category_name": "杂项",
      "members": [
        "/target/folder/notes.txt"
      ],
      "reason": "独立文件，无关联文件",
      "confidence": 0.70,
      "needs_review": true
    }
  ]
}
```

### 10.3 目标结构 Schema

```json
{
  "target_tree": {
    "root_path": "/target/folder",
    "categories": [
      {
        "name": "项目A文档",
        "members": ["project-a-report.docx", "project-a-data.xlsx", "project-a-slides.pptx"]
      },
      {
        "name": "临时图片",
        "members": ["IMG_001.jpg", "IMG_002.jpg"]
      },
      {
        "name": "杂项",
        "members": ["notes.txt"]
      }
    ]
  }
}
```

### 10.4 移动计划 Schema

```json
{
  "task_id": "uuid",
  "root_path": "/target/folder",
  "directories_to_create": [
    "/target/folder/项目A文档",
    "/target/folder/临时图片",
    "/target/folder/杂项"
  ],
  "moves": [
    {
      "source_path": "/target/folder/project-a-report.docx",
      "target_path": "/target/folder/项目A文档/project-a-report.docx",
      "category": "项目A文档",
      "confidence": 0.92
    }
  ],
  "conflicts": [],
  "needs_review_items": []
}
```

## 11. 分类策略设计

### 11.1 文件关联识别策略

判断文件是否关联的依据（按优先级排列）：

1. **同名不同扩展名**：文件名主体相同，扩展名不同（如 report.docx、report.pdf、report.xlsx）→ 高度关联
2. **共同前缀**：文件名包含相同前缀（如 project-a-xxx）→ 高度关联
3. **共同关键词**：文件名包含相同主题词（如 财务-xxx、财务-xxx）→ 中度关联
4. **修改时间聚集**：同类文件修改时间在同一时段内 → 中度关联
5. **类型互补**：文档+表格+演示文稿等常见办公组合 → 低度关联（需结合其他条件）

### 11.2 分类命名策略

1. 若能推断关联组的共同主题，以主题命名（如"项目A文档"、"财务资料"）
2. 若为同类文件聚集，以类型+特征命名（如"会议照片"、"技术PDF"）
3. 若无法确定主题，以主要文件类型命名（如"文档类"、"图片类"）
4. 单个独立文件归入"未分类"或根据其特征单独命名

### 11.3 不适用场景

以下场景不在第一版处理范围内：

1. 子目录内部文件的重组与分类
2. 跨父级目录的文件整理
3. 深层目录树的层级调整

## 12. API 设计

### 12.1 创建任务

接口：前端调用本地 Agent Runner，仅提供文件夹路径

请求体：

```json
{
  "root_path": "/target/folder",
  "dry_run": true
}
```

响应体：

```json
{
  "task_id": "uuid",
  "status": "created"
}
```

实现方式：

1. Electron / Tauri 通过 IPC 调用本地 Agent Runner
2. 前端直接调用本地 CLI，CLI 返回 JSON

### 12.2 扫描并生成计划

接口语义：run_task(root_path, dry_run)

响应体：

```json
{
  "task_id": "uuid",
  "status": "planned",
  "current_files": [],
  "target_structure": {},
  "plan": {},
  "needs_review": true
}
```

### 12.3 获取任务详情

接口语义：get_task(task_id)

返回：当前状态、扫描结果、关联分组、分类方案、移动计划、执行记录

### 12.4 提交人工审核结果

接口语义：submit_review(task_id, review_payload)

用途：

1. 用户确认全部通过
2. 用户调整部分目标路径或分类名称
3. 用户拒绝执行

### 12.5 执行计划

接口语义：execute_task(task_id)

说明：

1. 仅允许在 planned 或 reviewed 状态下调用
2. 默认再次进行 conflict check

### 12.6 回滚任务

接口语义：rollback_task(task_id)

说明：

1. 仅允许对已执行任务调用
2. 依赖完整执行日志

### 12.7 获取 Harness 检测报告

接口语义：get_harness_report(task_id)

返回：Harness Agent 的检测报告（verdict、各维度检查结果、问题列表、建议）

说明：

1. 仅在任务执行完成后可调用
2. Harness Agent 在 VerifyExecution 之后自动运行

## 13. 本地状态存储设计

第一版使用本地 JSON 文件存储，不引入远程数据库。

### 13.1 本地文件落盘结构

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

### 13.2 任务状态枚举

1. created
2. scanning
3. planned
4. review_required
5. approved
6. executing
7. completed
8. failed
9. rolled_back

## 14. 提示词设计原则

三个 Agent 各自持有独立的系统提示词，按职责聚焦。

### 14.1 Agent A（关联分析器）提示词要点

1. 你是文件关联分析器，只判断文件间是否存在关联
2. 不负责命名分类，不负责执行操作
3. 只依据文件属性信息（名称、扩展名、MIME 类型、大小、修改时间）判断
4. 关联判断优先级：同名不同后缀 > 共同前缀 > 共同关键词 > 时间聚集 > 类型互补
5. 无关联的文件放入 ungrouped_files
6. 低置信度关联标记 needs_review=true
7. 只处理父级目录内文件，不考虑子目录
8. 不限制文件类型
9. 输出必须符合既定 JSON Schema
10. 禁止输出思维链或推理过程

### 14.2 Agent B（分类命名器）提示词要点

1. 你是文件分类命名器，根据关联分组生成分类方案
2. 不负责判断关联（关联结果由上游提供），不负责执行操作
3. 分类名称必须使用中文
4. 命名优先级：主题推断 > 类型+特征 > 泛指类别
5. 若发现上游关联分组明显不合理，在 notes 中标注
6. 低置信度分类标记 needs_review=true
7. 输出必须符合既定 JSON Schema
8. 禁止输出思维链或推理过程

### 14.3 Harness Agent（终检器）提示词要点

1. 你是文件分类终检器，只读检测，不修改任何文件或计划
2. 检测四个维度：完整性（是否有遗漏）、关联合理性（抽查）、命名恰当性（抽查）、执行一致性（计划 vs 实际）
3. 每个维度抽查 2-3 项，不做全量检查
4. 明确给出 pass / warn / fail 判决
5. 发现问题时给出具体修正建议
6. 输出必须符合既定 JSON Schema
7. 禁止输出思维链或推理过程

## 15. bash 执行设计

### 15.1 设计原则

1. 所有工具底层均为 bash shell 脚本（.sh 文件）
2. Agent 工作流层通过 subprocess 调用这些脚本
3. 脚本接收 JSON stdin 参数，输出 JSON stdout 结果
4. Agent 不直接产出可执行 bash 文本
5. 所有路径都必须进行 shell 转义与 root_path 边界校验

### 15.2 建议命令模板

创建目录：

```bash
mkdir -p -- "${root_path}/${dirname}"
```

移动文件：

```bash
mv -- "$source_path" "$target_path"
```

检查目标冲突：

```bash
test ! -e "$target_path"
```

扫描父级文件（仅直接子项）：

```bash
find "$root_path" -maxdepth 1 -type f ! -name '.*'
```

获取 MIME 类型：

```bash
file --mime-type -b "$file_path"
```

### 15.3 禁止事项

1. 禁止使用 rm -rf 参与主流程整理
2. 禁止使用未经校验的 find -exec 做批量移动
3. 禁止将用户原始输入直接拼接进 shell 命令
4. 禁止跨 root_path 操作路径
5. 禁止递归遍历子目录（find 必须使用 -maxdepth 1）

## 16. 安全与风险控制

### 16.1 必做控制

1. 正式执行前必须 dry-run
2. 禁止覆盖已有文件
3. 禁止跳出 root_path 进行移动
4. 所有路径必须 canonicalize 后再比较
5. 日志中必须记录每次移动的前后路径
6. bash 执行前必须逐条做路径与冲突校验

### 16.2 主要风险

1. 模型误判文件关联关系
2. 路径冲突导致执行失败
3. 局部执行成功、局部失败造成中间态
4. 无关文件被错误归组
5. shell 注入或路径逃逸

### 16.3 缓解策略

1. 引入低置信度审核机制
2. 执行前统一冲突检查
3. 记录逐步日志，支持失败回滚
4. 对高风险关联判断启用人工确认
5. bash 命令统一由受控脚本执行并严格转义

## 17. 开发拆分建议

### 17.1 第一阶段

目标：跑通扫描、Agent A 关联检测、Agent B 分类规划、计划预览

交付内容：

1. 本地 Agent Runner 基础骨架（含工作流状态机）
2. 父级目录扫描工具（scan_parent_dir.sh）
3. 文件属性获取工具（get_file_info.sh）
4. Agent A（关联分析器）提示词与调用逻辑
5. Agent B（分类命名器）提示词与调用逻辑
6. Agent A → Agent B 串联流程
7. 目标结构与移动计划输出
8. dry-run 预览输出

### 17.2 第二阶段

目标：支持实际执行、回滚、Harness Agent 终检

交付内容：

1. bash 创建目录工具（bash_create_dirs.sh）
2. bash 移动文件工具（bash_move_files.sh）
3. bash 回滚工具（bash_rollback.sh）
4. 执行日志与审计
5. Harness Agent（终检器）提示词与调用逻辑
6. Harness 检测报告输出

### 17.3 第三阶段

目标：增强可用性与准确性

交付内容：

1. 人工审核界面
2. 文件关联策略增强
3. 更多文件类型属性识别增强
4. 规则配置化

## 18. 推荐目录结构

```text
agent_runner/
  app/
    core/
      config.py              # 模型配置、路径配置
      logging.py             # 日志工具
    agents/
      agent_a_association.py # Agent A：关联分析器（提示词 + 调用逻辑）
      agent_b_naming.py      # Agent B：分类命名器（提示词 + 调用逻辑）
      harness_agent.py       # Harness Agent：终检器（提示词 + 调用逻辑）
    graph/
      state.py               # 工作流状态定义
      nodes/
        scan.py              # ScanParentLevel
        analyze.py           # AnalyzeFileAttributes
        detect_assoc.py      # DetectFileAssociations（调用 Agent A）
        build_cat.py         # BuildCategories（调用 Agent B）
        generate_plan.py     # GeneratePlan
        validate.py          # ValidatePlan
        execute.py           # ExecutePlan（调用 bash 工具）
        verify.py            # VerifyExecution
        harness_check.py     # HarnessCheck（调用 Harness Agent）
        rollback.py          # Rollback
    tools/
      scan_parent_dir.sh     # bash：扫描父级目录
      get_file_info.sh       # bash：获取文件属性
      bash_create_dirs.sh    # bash：创建目录
      bash_dry_run_moves.sh  # bash：dry-run 检查
      bash_move_files.sh     # bash：移动文件
      bash_rollback.sh       # bash：回滚
    schemas/
      task.py
      plan.py
      association.py
      harness_report.py
    services/
      task_service.py
      audit_service.py
    storage/
      task_store.py
    cli.py
frontend/
  src/
    pages/
    components/
    services/
```

## 19. 最小可行实现建议

MVP 范围：

1. 仅支持本地目录父级文件整理
2. 不限制文件类型，所有类型均可处理
3. 只做单次任务，不做复杂调度
4. 默认先开启 dry-run，执行需二次确认
5. 所有低置信度项直接进入人工审核
6. 前端第一版只传入 root_path，不承担文件处理逻辑
7. 模型使用 qwen3.5:9b，关闭思维链
8. Agent A + Agent B 串联完成关联与分类
9. Harness Agent 执行后自动运行终检

## 20. 验收标准

第一版完成后，至少应满足以下验收条件：

1. 输入一个目标目录，系统可输出父级文件清单
2. Agent A 可识别文件之间的关联关系并输出分组结果
3. Agent B 可根据关联生成分类方案和目标目录结构
4. 系统可识别需要人工审核的项
5. 系统可创建新分类目录
6. 系统可按计划移动文件
7. 系统可生成执行日志
8. 系统在执行失败时可基于日志回滚
9. 系统不会遍历或修改子目录内容
10. 前端只传入目标文件夹路径，也能完成端到端整理流程
11. 真实文件操作通过本地 bash 脚本执行，且不存在越界路径写入
12. 所有文件类型均参与分类，无类型限制
13. Harness Agent 自动运行终检，输出 pass / warn / fail 检测报告
14. Agent A 与 Agent B 的输出可独立检查与调试

## 21. 结论

本项目应采用"前端只提供 root_path + 3 个串联 Agent（关联分析 → 分类命名 → 终检）+ 本地 bash shell 工具执行 + dry-run / 审核 / 回滚机制"的方案。

三个 Agent 职责边界清晰，均使用 qwen3.5:9b + 关闭思维链：
- **Agent A（关联分析器）**：判断文件间关联关系
- **Agent B（分类命名器）**：根据关联分组生成分类方案
- **Harness Agent（终检器）**：执行后独立语义复检

该方案聚焦于父级目录文件的关联分类整理，不遍历子目录、不限制文件类型，兼顾了小模型的稳定性（拆开职责）、执行安全性和工程可控性，适合作为第一版直接开发落地的技术路线。

从实施优先级看，应先完成父级扫描 + Agent A/B 串联的分类规划与预览，再接入 bash 脚本真实移动与回滚，最后接入 Harness Agent 终检。这样可以在不牺牲工程安全边界的前提下，逐步验证 Agent 对文件整理场景的有效性。
