# 轻量版技术方案：Coordinator 驱动的品牌合作视频脚本编辑系统

## 1. 方案目标

本方案基于 `docs/prd_new.md`，面向轻量化 MVP。目标不是一次性实现 PRD 中的 PostgreSQL + LangGraph 全栈，而是优先完成核心闭环：

1. 用户输入自定义 `user_id` 进入系统。
2. 用户上传或输入品牌 brief（MVP：MD/TXT/粘贴）。
3. 用户在 **Script Editor** 与 **IBIS Node Graph** 中编辑脚本并追踪推理结构。
4. 用户通过统一的 **Coordinator Agent Chat** 提问（可选品牌/观众/专家/综合视角）。
5. Coordinator 生成 **Revision Proposal**（cell-level hunk）与 **RationaleNode**，不直接覆盖脚本。
6. 用户在 Output Panel 查看 **Negotiation Preparation** 与 **References**；确认 hunk 后写回脚本。

核心原则（与 PRD 一致）：

1. 前台只有 Coordinator Chat；品牌/观众/专家为内部视角能力。
2. AI 不直接覆盖脚本，只生成分析、节点、方案与可确认修改。
3. 重要推理沉淀到 Node Graph（IBIS），而非仅停留在聊天。
4. 系统保持轻量：MongoDB 嵌入 + 必要 collection 拆分；LangGraph 可二期接入。
5. 使用缓存、摘要和局部上下文降低 LLM 成本。

## 2. 技术栈

### 2.1 前端

建议使用：

```text
Next.js
React
TypeScript
Zustand
SSE client
```

前端职责：

1. 维护 Script Editor、Node Graph（React Flow）、Coordinator Chat、Output Panel 状态。
2. 维护 layout（主视图切换、Output tab、Persona 面板）、quote、Revision Diff overlay。
3. 通过 SSE 展示 Coordinator 流式回复与 `artifact` 事件。
4. 将脚本编辑 debounce 后同步到后端。

### 2.2 后端

建议使用：

```text
FastAPI
MongoDB
Redis
SiliconFlow OpenAI-compatible LLM API
```

后端职责：

1. 管理项目、脚本、brief、persona、Coordinator 消息、Rationale Graph、Revision Proposal、Output 数据。
2. 实现 **CoordinatorService**：按任务路由调用内部 Brand / Audience / Expert **Perspective** 逻辑（可先同文件内函数，后拆节点）。
3. 通过 SSE 流式返回 Coordinator 自然语言与结构化 artifact。
4. Redis 缓存上下文与流式任务状态。
5. 应用 Revision Proposal hunk 并生成 script snapshot。

### 2.3 LangGraph（MVP 与演进）

**MVP：** 不强制 LangGraph。`CoordinatorService` 内按 `task_type` 顺序调用 perspective 函数并落库，语义对齐 `data_structures.md` 中的 `CoordinatorState` / 推荐节点列表。

**二期：** 接入 LangGraph，`thread_id = project_id`，checkpointer 仅用于运行恢复；业务数据仍写 MongoDB（或迁移 PostgreSQL 时见 PRD §18）。

```text
CoordinatorService          # MVP 编排入口
  ├─ BrandPerspective       # brief、品牌需求、PR 风险
  ├─ AudiencePerspective    # active persona、广告感、信任
  ├─ ExpertPerspective      # 综合 trade-off、方案方向
  ├─ RationaleGraphWriter   # Issue / Position / Argument / Reference
  ├─ RevisionProposalWriter # cell-level hunks
  └─ NegotiationWriter      # NegotiationPreparation + ReferenceItem
```

## 3. 用户与鉴权

MVP 不做正式登录注册。用户进入系统时输入一个不重复的自定义 `user_id`。

前端流程：

```text
首次进入系统
-> 输入 user_id
-> 保存到 localStorage
-> 后续请求自动携带 user_id
```

后端逻辑：

1. 如果 `user_id` 不存在，则创建用户记录。
2. 如果 `user_id` 已存在，则进入该用户项目列表。
3. 所有项目通过 `user_id` 做简单隔离。

`users` collection：

```json
{
  "_id": "custom_user_id",
  "created_at": "datetime"
}
```

## 4. MongoDB 数据设计

轻量版优先减少 collection 数量。建议 MVP 使用：

```text
users
projects
coordinator_messages
script_snapshots
```

如图谱或方案体积增大，再拆出：

```text
rationale_nodes
rationale_edges
revision_proposals
```

（亦可短期嵌入 `projects`，见 §14.1。）

### 4.1 Project 文档

大部分项目级数据直接嵌入 `projects`。

```json
{
  "_id": "project_id",
  "user_id": "custom_user_id",
  "title": "项目名称",
  "brief": {
    "filename": "brand.pdf",
    "text": "brief 原文",
    "summary": "brief 摘要",
    "parse_status": "pending | parsing | parsed | failed",
    "uploaded_at": "datetime"
  },
  "current_script": {
    "columns": [],
    "rows": [],
    "updated_at": "datetime"
  },
  "current_script_version_id": "string",
  "personas": [],
  "active_persona_id": "persona_id",
  "rationale_nodes": [],
  "rationale_edges": [],
  "revision_proposals": [],
  "negotiation_preparations": [],
  "references": [],
  "stale": {
    "rationale_graph": "up_to_date",
    "revision_proposals": "up_to_date",
    "negotiation_preparation": "up_to_date",
    "references": "up_to_date"
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4.2 Script 结构

普通编辑直接更新 `project.current_script`，不为每次编辑生成版本。

```json
{
  "columns": [
    {
      "column_id": "col_duration",
      "key": "duration",
      "label": "时长",
      "type": "duration | text | textarea | tag",
      "multiline": false,
      "order": 0
    }
  ],
  "rows": [
    {
      "row_id": "row_001",
      "order": 0,
      "cells": [
        {
          "column_id": "col_duration",
          "value": "0-5"
        }
      ]
    }
  ],
  "updated_at": "datetime"
}
```

规则：

1. 序号列不进入 `columns`，只由前端渲染层生成。
2. 单元格通过 `row_id + column_id` 定位。
3. 动态列通过 `columns` 管理。
4. 删除列时，同步删除所有 row 中对应 cell。

### 4.3 Script Snapshot

不需要每次编辑生成版本。只在关键时刻生成快照：

1. 专家 hunk 应用前后。
2. 用户点击“保存版本”。
3. 重要导入或批量修改。

`script_snapshots` collection：

```json
{
  "_id": "snapshot_id",
  "project_id": "project_id",
  "user_id": "custom_user_id",
  "reason": "manual_save | before_expert_apply | after_expert_apply | import",
  "script": {
    "columns": [],
    "rows": []
  },
  "created_at": "datetime"
}
```

### 4.4 RationaleNode / RationaleEdge（轻量嵌入）

IBIS 图节点与边；完整字段见 `data_structures.md` §5–6。MVP 可只持久化核心字段：

```json
{
  "node_id": "string",
  "node_type": "issue | position | argument | reference",
  "title": "string",
  "content": "string",
  "source_type": "brand_brief | audience_persona | ...",
  "status": "open | in_review | resolved | needs_negotiation | deferred | dismissed",
  "linked_script_refs": [],
  "based_on_script_version_id": "string",
  "created_by": "agent | user",
  "updated_at": "datetime"
}
```

```json
{
  "edge_id": "string",
  "from_node_id": "string",
  "to_node_id": "string",
  "relation_type": "responds_to | supports | opposes | evidenced_by | ..."
}
```

旧版 `brand_insights` 不再作为一级前台实体；品牌需求表达为 `node_type=issue` 且 `source_type` 含 `brand_*` 的节点。

### 4.5 Persona

`age_range` 保持自由文本，不做枚举限制，符合 PRD 中“大学生”“年轻职场人”“30+新手妈妈”等表达方式。

```json
{
  "persona_id": "persona_id",
  "name": "年轻职场人",
  "icon": "string",
  "gender": "string",
  "age_range": "string",
  "preferences": "string",
  "behavior": "string",
  "platform_context": "string",
  "ad_sensitivity": "low | medium | high",
  "trust_trigger": ["string"],
  "reject_trigger": ["string"],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4.6 RevisionProposal（轻量）

替代 `expert_suggestions`；字段对齐 PRD §9.3，`hunks` 使用 `removed` / `added`（与 `data_structures.md` 一致）。

```json
{
  "proposal_id": "string",
  "title": "string",
  "direction": "brand_first | audience_natural | balanced | creator_expression | custom",
  "target_issue_ids": [],
  "rationale": "string",
  "brand_tradeoff": "string",
  "audience_tradeoff": "string",
  "creator_tradeoff": "string",
  "risk": "string",
  "explanation_to_brand": "string",
  "hunks": [
    {
      "hunk_id": "string",
      "row_id": "string",
      "column_id": "string",
      "context": "string",
      "removed": "string",
      "added": "string"
    }
  ],
  "related_node_ids": [],
  "based_on_script_version_id": "string",
  "status": "draft | previewed | partially_applied | applied | dismissed",
  "created_at": "datetime"
}
```

应用 hunk 时：

1. 校验当前 cell 值是否仍等于 `removed`。
2. 不一致则拒绝或提示重新生成。
3. apply 前后写入 `script_snapshots`，更新 `current_script_version_id`。

### 4.7 NegotiationPreparation / ReferenceItem（轻量）

嵌入 `projects` 或独立 collection；结构见 `data_structures.md` §8–9。Output Panel 通过 tab 读取列表。

### 4.8 CoordinatorMessage

统一 Chat 消息；**无** `agent_type`。

```json
{
  "_id": "message_id",
  "project_id": "project_id",
  "user_id": "custom_user_id",
  "role": "user | assistant | system",
  "content": "string",
  "requested_perspectives": ["brand", "audience", "expert", "comprehensive"],
  "active_persona_id": "string",
  "quotes": [
    {
      "text": "string",
      "row_id": "string",
      "column_id": "string",
      "selection_start": 0,
      "selection_end": 10,
      "script_version_id": "string"
    }
  ],
  "related_node_ids": [],
  "generated_artifact_ids": [],
  "created_at": "datetime"
}
```

Collection 名：`coordinator_messages`（替代 `agent_messages`）。

## 5. Stale 状态设计（ArtifactStaleness）

不做独立 collection，放在 `project.stale`。完整枚举见 `data_structures.md` §11。

```json
{
  "stale": {
    "rationale_graph": "up_to_date | stale_script_changed | stale_brief_changed | stale_persona_changed",
    "revision_proposals": "up_to_date | stale_script_changed | stale_graph_changed | stale_persona_changed",
    "negotiation_preparation": "up_to_date | stale_script_changed | stale_graph_changed",
    "references": "up_to_date | stale_brief_changed | stale_external_source_changed"
  }
}
```

MVP 可暂用 `stale_*: true` + `reason` 字符串，前端展示「可能过期」badge 即可。

更新规则（PRD §14）：

1. **脚本 cell 变更：** `rationale_graph`、`revision_proposals`、`negotiation_preparation` → `stale_script_changed`。
2. **Brief 重新上传/解析：** `rationale_graph`、`references` → brief 相关；`revision_proposals`、`negotiation_preparation` → `stale_graph_changed`。
3. **active persona 变更/编辑：** `rationale_graph`、`revision_proposals` → `stale_persona_changed`。
4. **Node Graph 用户编辑：** `revision_proposals`、`negotiation_preparation` → `stale_graph_changed`。
5. **Coordinator persist 新 artifact 后：** 在 `based_on_script_version_id` 匹配当前版本时，将该 artifact 置为 `up_to_date`。

## 6. LLM 上下文优化

为了避免每次调用 LLM 都重新传入完整 brief、完整脚本和完整聊天历史，采用“分层上下文 + 摘要 + Redis 缓存”的策略。

### 6.1 上下文分层

```text
固定上下文：brief 摘要、active persona、平台语境
动态上下文：用户本轮问题、quote、相关脚本行、target_node_ids
历史上下文：最近 N 轮 coordinator_messages + 长历史摘要
结构化上下文：rationale_nodes（子图摘要）、revision_proposals 摘要、references 摘要
内部上下文（不拼进用户可见 prompt）：brand/audience/expert perspective 中间结果
```

### 6.2 Brief 上下文

Brief 上传或输入后，做一次解析和摘要，保存到 project：

```json
{
  "brief": {
    "text": "完整 brief",
    "summary": "摘要",
    "parse_status": "parsed"
  }
}
```

Coordinator / Brand Perspective 调用优先使用 `brief.summary`；追问依据时再补 brief 原文片段。

### 6.3 Script 上下文

不默认传完整脚本。根据触发方式选择上下文：

1. 用户选中 quote：传 quote 所在行、前后 1-2 行、当前脚本概要。
2. 用户问整体问题：传脚本概要和关键行摘要。
3. 生成 Revision Proposal：传相关 Issue/Position/Argument 子图、内部 perspective 结果、相关脚本行。

### 6.4 聊天历史

每次 Coordinator 调用只传最近 5–10 轮 `coordinator_messages`。更早历史压缩为摘要：

```json
{
  "conversation_summary": "用户主要关心广告感过强、品牌露出自然度和观众信任感。"
}
```

### 6.5 Redis 缓存

Redis 用于缓存上下文构建结果和部分 LLM 结果。

建议 key：

```text
context:{project_id}:{task_type}:{context_hash}
llm_cache:{prompt_hash}
stream:{request_id}
```

`context_hash` 可由以下内容生成：

```text
project_id
task_type
script.updated_at
brief.uploaded_at
active_persona_id
persona.updated_at
rationale_graph.updated_at
revision_proposals.updated_at
```

缓存策略：

1. brief 摘要可长期缓存。
2. 脚本概要在脚本变更后失效。
3. persona 上下文在 persona 更新后失效。
4. LLM 完整结果缓存只用于完全相同 prompt 的重复请求。

## 7. 大模型服务与模型路由

MVP 使用 SiliconFlow 提供的大模型 API。接口采用 OpenAI 兼容格式：

```text
POST https://api.siliconflow.cn/v1/chat/completions
Authorization: Bearer {SILICONFLOW_API_KEY}
Content-Type: application/json
```

官方文档：

```text
https://docs.siliconflow.cn/cn/api-reference/chat-completions/chat-completions
```

### 7.1 环境变量

后端使用环境变量保存配置：

```text
SILICONFLOW_API_KEY=your_api_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_DEFAULT_MODEL=Qwen/Qwen3-8B
SILICONFLOW_ADVANCED_MODEL=Qwen/Qwen3-32B
```

### 7.2 候选模型

MVP 使用两个模型，根据任务复杂程度切换：

```text
Qwen/Qwen3-8B
Qwen/Qwen3-32B
```

建议定位：

1. `Qwen/Qwen3-8B`：默认模型，处理轻量对话、局部脚本点评、普通 persona 问答、简单改写。
2. `Qwen/Qwen3-32B`：复杂任务模型，处理 brief 深度拆解、IBIS 节点批量生成、Revision Proposal 多方案、hunk 生成、Negotiation Preparation 与结构化 JSON 输出。

### 7.3 模型路由规则

后端增加 `ModelRouter`，根据任务类型选择模型。

```python
def select_model(task_type: str, estimated_complexity: str) -> str:
    if task_type in {
        "initialize_project",
        "brand_perspective",
        "audience_perspective",
        "expert_perspective",
        "write_rationale_graph",
        "generate_revision_proposals",
        "generate_negotiation_preparation",
    }:
        return "Qwen/Qwen3-32B"

    if estimated_complexity == "high":
        return "Qwen/Qwen3-32B"

    return "Qwen/Qwen3-8B"
```

推荐路由表：

| 场景 | 模型 |
|---|---|
| 普通聊天追问 | `Qwen/Qwen3-8B` |
| quote 局部点评 | `Qwen/Qwen3-8B` |
| 简单文案改写 | `Qwen/Qwen3-8B` |
| Brief 摘要 | `Qwen/Qwen3-8B` |
| Brief 深度需求拆解 | `Qwen/Qwen3-32B` |
| IBIS 节点 / 边批量生成 | `Qwen/Qwen3-32B` |
| 观众视角结构化分析（内部） | `Qwen/Qwen3-32B` |
| Revision Proposal 多方案 | `Qwen/Qwen3-32B` |
| cell-level hunk 生成 | `Qwen/Qwen3-32B` |
| Negotiation Preparation | `Qwen/Qwen3-32B` |
| JSON 修复和格式校验重试 | `Qwen/Qwen3-8B` |

### 7.4 Thinking 配置

SiliconFlow Chat Completions 支持 `enable_thinking` 字段，且 Qwen3-8B 与 Qwen3-32B 均在支持列表中。

建议策略：

1. 普通聊天、局部点评、简单改写：`enable_thinking = false`。
2. Brief 深度拆解、图谱写入、Revision Proposal、Negotiation：`enable_thinking = true`。
3. 需要稳定 JSON 输出时，优先降低 temperature，并使用结构化输出约束；如果 thinking 内容影响解析，只解析最终 `content`。

默认参数建议：

```json
{
  "temperature": 0.4,
  "top_p": 0.7,
  "max_tokens": 2048
}
```

复杂任务建议：

```json
{
  "temperature": 0.3,
  "top_p": 0.7,
  "max_tokens": 4096,
  "enable_thinking": true,
  "thinking_budget": 2048
}
```

### 7.5 OpenAI 兼容调用封装

后端不要在业务代码中直接调用 SiliconFlow。建议封装统一 client：

```python
class LLMClient:
    async def chat(
        self,
        *,
        messages: list[dict],
        task_type: str,
        stream: bool = False,
        response_format: dict | None = None,
        complexity: str = "normal",
    ):
        model = select_model(task_type, complexity)
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.4,
            "top_p": 0.7,
        }
        if response_format:
            payload["response_format"] = response_format
        return await self._post("/chat/completions", payload)
```

调用示例：

```json
{
  "model": "Qwen/Qwen3-32B",
  "messages": [
    {
      "role": "system",
      "content": "你是品牌合作视频脚本顾问。"
    },
    {
      "role": "user",
      "content": "请分析这份 brief 的显式和隐式需求。"
    }
  ],
  "stream": true,
  "enable_thinking": true,
  "thinking_budget": 2048
}
```

### 7.6 结构化输出策略

`RationaleNode`、`RationaleEdge`、`RevisionProposal`、`NegotiationPreparation`、`ReferenceItem` 等 artifact 需要结构化落库，LLM 输出必须经过校验。

推荐流程：

```text
LLM streaming text
-> 前端展示自然语言回复
-> 后端累积完整 content
-> 解析 JSON artifact
-> Pydantic 校验
-> 校验失败时触发 JSON 修复重试
-> 写入 MongoDB
```

JSON 修复重试可以使用 `Qwen/Qwen3-8B`，因为任务只是格式修复，不需要复杂推理。

### 7.7 成本控制

模型路由与上下文缓存一起使用：

1. 默认走 `Qwen/Qwen3-8B`。
2. 只有结构化分析和专家方案生成走 `Qwen/Qwen3-32B`。
3. 复杂模型调用前先检查 Redis 是否存在相同 `prompt_hash` 的可复用结果。
4. 脚本编辑后只失效相关上下文缓存，不清空所有缓存。
5. Expert Perspective 只读取 rationale 子图摘要与内部 brand/audience perspective 结果，不读取完整 coordinator 聊天历史。

## 8. Coordinator 调用设计

### 8.1 入口：`POST /api/projects/{id}/coordinator/stream`

请求体示例：

```json
{
  "message": "用户问题",
  "requested_perspectives": ["comprehensive"],
  "quotes": [],
  "target_node_ids": [],
  "task_type": "user_message"
}
```

`CoordinatorService` 根据 `task_type` 与 `requested_perspectives` 决定调用哪些内部步骤（见 §2.3）。

### 8.2 用户可见输出

```text
streaming Coordinator 自然语言（event: token）
结构化 artifact（event: artifact）
  - rationale_nodes / rationale_edges
  - revision_proposals
  - negotiation_preparation
  - references
完成（event: done，含 message_id、generated_artifact_ids）
```

写入：

1. `coordinator_messages`（user + assistant）
2. `project.rationale_*` / `revision_proposals` / `negotiation_preparations` / `references`（或独立 collection）
3. `project.stale` 按 §5 更新

### 8.3 内部 Perspective（不直接暴露前台）

| 步骤 | 输入要点 | 输出要点 |
|------|----------|----------|
| Brand Perspective | brief summary、相关脚本、PR 反馈 | 品牌需求、审片风险（中间结构） |
| Audience Perspective | active persona、脚本、quote | 自然度/广告感/风险（中间结构） |
| Expert Perspective | 子图 + 上述中间结果 | 方案方向、trade-off |
| RationaleGraphWriter | 上述结果 | Issue/Position/Argument/Reference |
| RevisionProposalWriter | target issues + script cells | proposals + hunks |
| NegotiationWriter | issues + positions | NegotiationPreparation sections |

上下文隔离见 `data_structures.md` §二、`prd_new.md` §13.5。

## 9. SSE 流式响应

使用 SSE，而不是 WebSocket。SSE 对单向流式文本足够轻量。

接口示例：

```http
POST /api/projects/{project_id}/coordinator/stream
```

响应类型：

```http
Content-Type: text/event-stream
```

事件格式：

```text
event: token
data: {"content":"这段脚本"}

event: artifact
data: {"rationale_nodes":[...],"revision_proposals":[...]}

event: done
data: {"message_id":"msg_001"}

event: error
data: {"message":"LLM 调用失败"}
```

前端处理流程：

1. 用户发送消息。
2. 立即把 user message 写入 UI。
3. 创建 assistant message placeholder。
4. 接收 `token`，持续追加文本。
5. 接收 `artifact`，更新结构化区域。
6. 接收 `done`，标记完成并刷新必要数据。
7. 接收 `error`，展示失败状态并允许重试。

Redis 中可保存临时流状态：

```text
stream:{request_id}
```

## 10. API 草案

### 9.1 User

```http
POST /api/users/enter
```

请求：

```json
{
  "user_id": "custom_user_id"
}
```

### 9.2 Project

```http
GET /api/projects?user_id={user_id}
POST /api/projects
GET /api/projects/{project_id}
PATCH /api/projects/{project_id}
DELETE /api/projects/{project_id}
```

### 9.3 Brief

```http
POST /api/projects/{project_id}/brief
PATCH /api/projects/{project_id}/brief
```

### 9.4 Script

```http
GET /api/projects/{project_id}/script
PATCH /api/projects/{project_id}/script/cells
POST /api/projects/{project_id}/script/rows
DELETE /api/projects/{project_id}/script/rows/{row_id}
POST /api/projects/{project_id}/script/columns
PATCH /api/projects/{project_id}/script/columns/{column_id}
DELETE /api/projects/{project_id}/script/columns/{column_id}
```

### 9.5 Snapshots

```http
GET /api/projects/{project_id}/script/snapshots
POST /api/projects/{project_id}/script/snapshots
POST /api/projects/{project_id}/script/snapshots/{snapshot_id}/restore
```

### 9.6 Coordinator Chat

```http
POST /api/projects/{project_id}/coordinator/stream
GET /api/projects/{project_id}/coordinator/messages
```

### 9.7 Persona

```http
GET /api/projects/{project_id}/personas
POST /api/projects/{project_id}/personas
PATCH /api/projects/{project_id}/personas/{persona_id}
DELETE /api/projects/{project_id}/personas/{persona_id}
PATCH /api/projects/{project_id}/active-persona
```

### 9.8 Rationale Graph

```http
GET /api/projects/{project_id}/graph/nodes
POST /api/projects/{project_id}/graph/nodes
PATCH /api/projects/{project_id}/graph/nodes/{node_id}
DELETE /api/projects/{project_id}/graph/nodes/{node_id}
GET /api/projects/{project_id}/graph/edges
POST /api/projects/{project_id}/graph/edges
DELETE /api/projects/{project_id}/graph/edges/{edge_id}
```

### 9.9 Revision Proposal

```http
GET /api/projects/{project_id}/revision-proposals
POST /api/projects/{project_id}/revision-proposals/{proposal_id}/apply
PATCH /api/projects/{project_id}/revision-proposals/{proposal_id}
```

应用 hunk 请求：

```json
{
  "accepted_hunk_ids": ["hunk_001"],
  "rejected_hunk_ids": ["hunk_002"]
}
```

### 9.10 Output Panel

```http
GET /api/projects/{project_id}/outputs/negotiation
POST /api/projects/{project_id}/outputs/negotiation
GET /api/projects/{project_id}/outputs/references
POST /api/projects/{project_id}/outputs/references
```

完整路径命名以 `prd_new.md` §11 为准；实现时可合并路由。

## 11. 前端状态管理

对齐 `prd_new.md` §12；Zustand 可按域拆分 slice。

```ts
type AppState = {
  user: { userId?: string };
  project: Project | null;
  script: ScriptVersion | null;

  layout: {
    mainView: 'script' | 'graph';
    coordinatorWidth: number;
    outputPanelOpen: boolean;
    outputPanelTab: 'negotiation' | 'references';
    personaPanelOpen: boolean;
    nodeDetailOpen: boolean;
    versionHistoryOpen: boolean;
  };

  editor: {
    selectedRowId?: string;
    selectedColumnId?: string;
    selectedText?: string;
    saveStatus: 'saved' | 'editing' | 'saving' | 'failed';
    durationErrors: Record<string, string>;
  };

  coordinator: {
    messages: CoordinatorMessage[];
    input: string;
    quotes: QuoteRef[];
    requestedPerspectives: Array<'brand' | 'audience' | 'expert' | 'comprehensive'>;
    isStreaming: boolean;
  };

  personas: {
    items: Persona[];
    activePersonaId?: string;
    modalMode: 'create' | 'edit' | null;
  };

  graph: {
    nodes: RationaleNode[];
    edges: RationaleEdge[];
    selectedNodeId?: string;
    filterSourceTypes: string[];
    filterNodeTypes: Array<'issue' | 'position' | 'argument' | 'reference'>;
  };

  revision: {
    proposals: RevisionProposal[];
    activeProposalId?: string;
    diffOverlayOpen: boolean;
    hunkState: Record<string, true | false | null>;
  };

  output: {
    negotiationPreparations: NegotiationPreparation[];
    references: ReferenceItem[];
  };

  stale: {
    rationaleGraph: string;
    revisionProposals: string;
    negotiationPreparation: string;
    references: string;
  };
};
```

## 12. MVP 开发阶段

与 `development_plan_P0.md`、`prd_new.md` §15 对齐；以下为技术侧摘要。

### P0：界面结构重构 + 工程底座

1. 移除三 Agent 前台面板；Coordinator Chat + Output Panel + 主工作区切换。
2. Next.js / FastAPI / MongoDB / Redis / SiliconFlow 骨架。
3. `user_id`、Project CRUD、`current_script` 读写与 debounce 保存。

### P1：Script Editor 稳定化

1. 默认四列（无 feedback）；表格行/列 CRUD、时长与时间轴。
2. 选中文本 → Coordinator quote；脚本变更触发 `stale`。

### P2：Persona + Coordinator Chat

1. Persona CRUD；`coordinator/stream` SSE；`coordinator_messages`。
2. `requested_perspectives`；8B/32B 路由。

### P3：IBIS Node Graph

1. `rationale_nodes` / `rationale_edges` API + React Flow。
2. Brief（MD/TXT）→ 初始 Issue/Reference。

### P4：Revision Proposal + Output Panel

1. Revision Proposal + cell-level diff apply。
2. Negotiation Preparation / References tab 与 API。

### P5：整合

1. 版本历史、证据链、LangGraph 可选接入、全量验收。

## 13. 暂缓实现项

1. PostgreSQL 迁移与 LangGraph checkpointer（PRD 推荐终态）。
2. Brief：PDF、DOC、DOCX、PPT 解析。
3. 独立 BriefFile collection（可先嵌入 `project.brief`）。
4. 每次 cell 编辑自动生成 ScriptVersion（用 snapshot 关键时刻代替）。
5. 节点合并、重复检测、多 persona 对比（PRD P5）。
6. 正式登录、`owner_id` 权限、多人协作。
7. 复杂后台任务队列。

## 14. 风险与约束

### 14.1 MongoDB 文档膨胀

`projects` 嵌入较多数据，后续如果消息、专家方案或脚本变大，需要拆 collection。

MVP 规避方式：

1. `coordinator_messages` 独立 collection。
2. `script_snapshots` 独立 collection。
3. 必要时将 `rationale_nodes`、`revision_proposals` 拆出。

### 14.2 Hunk 应用冲突

如果用户在专家方案生成后手动改了对应 cell，旧 hunk 可能不再适用。

规避方式：

1. hunk 保存 `removed`（应用前与当前 cell 比对）。
2. 应用前检查当前 cell 是否等于 `removed`。
3. 不一致则提示用户重新生成或手动处理。

### 14.3 LLM 成本

如果每次都传完整上下文，成本会偏高。

规避方式：

1. Brief 摘要。
2. 脚本局部上下文。
3. 最近 N 轮消息。
4. 长历史摘要。
5. Redis 上下文缓存。

### 14.4 SSE 中断

网络中断可能导致前端只收到部分回复。

规避方式：

1. 后端在完成后才写入最终 assistant message。
2. 前端中断时显示“生成中断，可重试”。
3. Redis 暂存 `request_id` 状态，便于排查。

## 15. 最终取舍总结

本方案保留（产品语义对齐 `prd_new.md`）：

1. Coordinator 统一 Chat + 内部多视角。
2. Script Editor + IBIS Node Graph + Output Panel（Negotiation / References）。
3. RevisionProposal + cell-level hunk；ArtifactStaleness。
4. MongoDB + Redis + SSE + SiliconFlow（8B/32B 路由）。
5. 自定义 `user_id`；LLM 上下文缓存与摘要。

本方案相对 PRD 的 MVP 简化：

1. 数据库先用 MongoDB 嵌入，而非 PostgreSQL 全表规范化。
2. LangGraph 二期接入，MVP 用 `CoordinatorService` 顺序编排。
3. Brief 文件类型先 MD/TXT/粘贴。
4. 不做每次编辑自动 ScriptVersion；用 snapshot 关键时刻。
5. 不做正式鉴权与多人协作。

演进路径：MVP 验证交互与数据结构后，按 `data_structures.md` 迁移 PostgreSQL，并将 `CoordinatorService` 节点化接入 LangGraph。

---

## 16. 相关文档

- 产品需求：`docs/prd_new.md`
- 数据结构：`docs/data_structures.md`
- 开发计划：`docs/development_plan_P0.md`
