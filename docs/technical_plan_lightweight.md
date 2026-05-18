# 轻量版技术方案：品牌合作视频脚本编辑系统

## 1. 方案目标

本方案基于 `prd.md`，面向一个轻量化 MVP 实现。目标不是一次性搭建完整平台，而是优先完成核心产品闭环：

1. 用户输入自定义 `user_id` 进入系统。
2. 用户上传或输入品牌 brief。
3. 用户在表格化 Script Editor 中编辑视频脚本。
4. 用户通过品牌方 Agent、观众 Agent、专家 Agent 获取反馈。
5. 专家 Agent 生成可预览的 cell-level 修改建议。
6. 用户确认后，系统将选中的 hunk 写回脚本。

核心原则：

1. 系统保持轻量，避免过早引入复杂工作流和过多数据表。
2. AI 不直接覆盖脚本，只生成分析、建议和可确认的修改。
3. 保留 Agent 输出质量所需的结构化数据。
4. 使用缓存、摘要和局部上下文降低 LLM 调用成本。

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

1. 维护 Script Editor 的交互状态。
2. 维护 Agent 面板、quote、diff overlay 等 UI 状态。
3. 通过 SSE 展示 Agent 流式回复。
4. 将用户编辑 debounce 后同步到后端。

### 2.2 后端

建议使用：

```text
FastAPI
MongoDB
Redis
SiliconFlow OpenAI-compatible LLM API
```

后端职责：

1. 管理项目、脚本、brief、persona、Agent 输出。
2. 构建轻量上下文并调用 SiliconFlow Chat Completions API。
3. 通过 SSE 向前端流式返回 Agent 回复。
4. 使用 Redis 缓存上下文和流式任务状态。
5. 应用专家 hunk 并生成必要的脚本快照。

### 2.3 暂不引入 LangGraph

MVP 阶段不使用 LangGraph。三类 Agent 先实现为普通 service：

```text
BrandAgentService
AudienceAgentService
ExpertAgentService
```

每次调用时，service 从 MongoDB 读取当前 project、script、brief、persona 和必要的结构化结果，构建上下文后调用 SiliconFlow LLM。

后续如果出现复杂工作流、任务恢复、多 Agent 自动编排，再考虑接入 LangGraph。

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
agent_messages
script_snapshots
```

如专家方案后续增长较大，可再拆出：

```text
expert_suggestions
```

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
    "rows": []
  },
  "brand_insights": [],
  "personas": [],
  "active_persona_id": "persona_id",
  "audience_analysis": {},
  "expert_suggestions": [],
  "stale": {
    "brand": false,
    "audience": false,
    "expert": false
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

### 4.4 BrandInsight

品牌方 Agent 的价值依赖可追溯依据，因此保留完整结构。

```json
{
  "id": "insight_id",
  "category": "explicit_requirement | implicit_requirement | brand_feedback",
  "content": "需求或反馈内容",
  "reason": "为什么这样判断",
  "evidence": [
    {
      "source_type": "brief | script | chat",
      "quote": "证据原文",
      "row_id": "row_id",
      "column_id": "column_id"
    }
  ],
  "confidence": "high | medium | low",
  "status": "new | confirmed | pending | ignored",
  "created_by": "agent | user",
  "updated_by": "agent | user",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

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

### 4.6 AudienceAnalysis

轻量版只保留当前 persona 的最近一次分析，不做历史分析列表。

```json
{
  "persona_id": "persona_id",
  "summary": "分析摘要",
  "naturalness_score": 3,
  "credibility_score": 3,
  "ad_sensitivity_score": 4,
  "key_risks": ["string"],
  "liked_parts": [
    {
      "row_id": "row_id",
      "reason": "string"
    }
  ],
  "rejected_parts": [
    {
      "row_id": "row_id",
      "reason": "string"
    }
  ],
  "suggestions": ["string"],
  "updated_at": "datetime"
}
```

### 4.7 ExpertSuggestion

专家方案保留 hunk，但字段减半。

```json
{
  "id": "suggestion_id",
  "title": "修改方案标题",
  "direction": "brand_first | audience_natural | balanced | creator_expression | custom",
  "description": "方案描述",
  "reason": "综合理由、取舍和风险说明",
  "hunks": [
    {
      "hunk_id": "hunk_id",
      "row_id": "row_id",
      "column_id": "column_id",
      "old": "原文",
      "new": "修改后文本",
      "reason": "为什么这样改"
    }
  ],
  "status": "draft | applied | dismissed",
  "created_at": "datetime"
}
```

应用 hunk 时必须检查：

1. 当前 cell 的值是否仍等于 `old`。
2. 如果不一致，说明脚本已变化，应拒绝应用该 hunk 或提示用户重新生成方案。
3. 成功应用前后写入 `script_snapshots`。

### 4.8 AgentMessage

Agent 对话消息独立保存，避免 project 文档无限膨胀。

```json
{
  "_id": "message_id",
  "project_id": "project_id",
  "user_id": "custom_user_id",
  "agent_type": "brand | audience | expert",
  "role": "user | assistant",
  "content": "消息内容",
  "quotes": [
    {
      "text": "引用文本快照",
      "row_id": "row_id",
      "column_id": "column_id",
      "selection_start": 0,
      "selection_end": 10
    }
  ],
  "created_at": "datetime"
}
```

## 5. Stale 状态设计

`AgentStaleness` 不做独立 collection，直接放在 `project.stale`。

基础版：

```json
{
  "stale": {
    "brand": false,
    "audience": true,
    "expert": true
  }
}
```

如需展示原因，可扩展为：

```json
{
  "stale": {
    "brand": {
      "value": false,
      "reason": null
    },
    "audience": {
      "value": true,
      "reason": "script_changed"
    },
    "expert": {
      "value": true,
      "reason": "audience_changed"
    }
  }
}
```

MVP 推荐先用基础版。

更新规则：

1. 脚本变更后：`brand = true`，`audience = true`，`expert = true`。
2. persona 切换或编辑后：`audience = true`，`expert = true`。
3. BrandInsight 更新后：`expert = true`。
4. AudienceAnalysis 更新后：`expert = true`。
5. Expert 重新生成方案后：`expert = false`。

## 6. LLM 上下文优化

为了避免每次调用 LLM 都重新传入完整 brief、完整脚本和完整聊天历史，采用“分层上下文 + 摘要 + Redis 缓存”的策略。

### 6.1 上下文分层

```text
固定上下文：brief 摘要、品牌要求、当前 persona
动态上下文：用户本轮问题、quote、相关脚本行
历史上下文：最近 N 轮消息 + 长历史摘要
结构化上下文：brand_insights、audience_analysis、expert_suggestions
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

Agent 调用优先使用 `brief.summary`。只有当用户追问具体 brief 原文依据时，再补充相关原文片段。

### 6.3 Script 上下文

不默认传完整脚本。根据触发方式选择上下文：

1. 用户选中 quote：传 quote 所在行、前后 1-2 行、当前脚本概要。
2. 用户问整体问题：传脚本概要和关键行摘要。
3. Expert 生成方案：传 BrandInsight、AudienceAnalysis、相关脚本行和必要的全局结构。

### 6.4 聊天历史

每次 Agent 调用只传最近 5-10 轮消息。更早历史压缩为摘要：

```json
{
  "conversation_summary": "用户主要关心广告感过强、品牌露出自然度和观众信任感。"
}
```

### 6.5 Redis 缓存

Redis 用于缓存上下文构建结果和部分 LLM 结果。

建议 key：

```text
context:{project_id}:{agent_type}:{context_hash}
llm_cache:{prompt_hash}
stream:{request_id}
```

`context_hash` 可由以下内容生成：

```text
project_id
agent_type
script.updated_at
brief.uploaded_at
active_persona_id
persona.updated_at
brand_insights.updated_at
audience_analysis.updated_at
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
2. `Qwen/Qwen3-32B`：复杂任务模型，处理 brief 深度拆解、完整 BrandInsight 生成、AudienceAnalysis 生成、ExpertSuggestion 多方案生成、hunk 生成和结构化 JSON 输出。

### 7.3 模型路由规则

后端增加 `ModelRouter`，根据任务类型选择模型。

```python
def select_model(task_type: str, estimated_complexity: str) -> str:
    if task_type in {
        "brand_analyze_brief",
        "brand_generate_insights",
        "audience_analyze_script",
        "expert_generate_suggestions",
        "expert_generate_hunks",
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
| BrandInsight 结构化生成 | `Qwen/Qwen3-32B` |
| AudienceAnalysis 结构化生成 | `Qwen/Qwen3-32B` |
| Expert 多方案生成 | `Qwen/Qwen3-32B` |
| cell-level hunk 生成 | `Qwen/Qwen3-32B` |
| JSON 修复和格式校验重试 | `Qwen/Qwen3-8B` |

### 7.4 Thinking 配置

SiliconFlow Chat Completions 支持 `enable_thinking` 字段，且 Qwen3-8B 与 Qwen3-32B 均在支持列表中。

建议策略：

1. 普通聊天、局部点评、简单改写：`enable_thinking = false`。
2. Brief 深度拆解、AudienceAnalysis、ExpertSuggestion：`enable_thinking = true`。
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

BrandInsight、AudienceAnalysis、ExpertSuggestion 需要结构化落库，因此 LLM 输出必须经过校验。

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
5. Expert Agent 只读取 `brand_insights` 和最近一次 `audience_analysis`，不读取完整聊天历史。

## 8. Agent 调用设计

### 8.1 Brand Agent

输入：

```text
brief summary
brand_insights
user message
quotes
related script rows
recent brand messages
conversation summary
```

输出：

```text
streaming assistant text
updated brand_insights
```

写入：

1. `agent_messages`
2. `project.brand_insights`
3. `project.stale.expert = true`

### 8.2 Audience Agent

输入：

```text
active persona
user message
quotes
related script rows
recent audience messages
conversation summary
```

输出：

```text
streaming assistant text
latest audience_analysis
```

写入：

1. `agent_messages`
2. `project.audience_analysis`
3. `project.stale.expert = true`

### 8.3 Expert Agent

输入：

```text
brand_insights
latest audience_analysis
user message
quotes
related script rows
recent expert messages
```

Expert Agent 不读取 Brand/Audience 的完整聊天历史，只读取结构化结果。

输出：

```text
streaming assistant text
expert_suggestions with hunks
```

写入：

1. `agent_messages`
2. `project.expert_suggestions`
3. `project.stale.expert = false`

## 9. SSE 流式响应

使用 SSE，而不是 WebSocket。SSE 对单向流式文本足够轻量。

接口示例：

```http
POST /api/projects/{project_id}/agents/{agent_type}/stream
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
data: {"brand_insights":[...]}

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

### 9.6 Agent

```http
POST /api/projects/{project_id}/agents/{agent_type}/stream
GET /api/projects/{project_id}/agents/{agent_type}/messages
```

### 9.7 Persona

```http
POST /api/projects/{project_id}/personas
PATCH /api/projects/{project_id}/personas/{persona_id}
DELETE /api/projects/{project_id}/personas/{persona_id}
PATCH /api/projects/{project_id}/active-persona
```

### 9.8 Expert Suggestion

```http
GET /api/projects/{project_id}/expert-suggestions
POST /api/projects/{project_id}/expert-suggestions/{suggestion_id}/apply
PATCH /api/projects/{project_id}/expert-suggestions/{suggestion_id}
```

应用 hunk 请求：

```json
{
  "accepted_hunk_ids": ["hunk_001"],
  "rejected_hunk_ids": ["hunk_002"]
}
```

## 11. 前端状态管理

Zustand store 建议拆成：

```ts
type AppState = {
  user: {
    userId?: string;
  };
  project: Project | null;
  script: Script | null;
  editor: {
    selectedRowId?: string;
    selectedColumnId?: string;
    selectedText?: string;
    saveStatus: 'saved' | 'editing' | 'saving' | 'failed';
  };
  layout: {
    activePanel: 'brand' | 'audience' | 'expert' | null;
    agentsColWidth: number;
  };
  brand: {
    activePinnedTab: 'explicit_requirement' | 'implicit_requirement' | 'brand_feedback';
    streaming: boolean;
  };
  audience: {
    activePersonaId?: string;
    modalMode: 'create' | 'edit' | null;
    streaming: boolean;
  };
  expert: {
    activeSuggestionId?: string;
    diffOverlayOpen: boolean;
    hunkState: Record<string, true | false | null>;
    streaming: boolean;
  };
};
```

## 12. MVP 开发阶段

### P0：基础工程与数据闭环

1. 创建 Next.js 前端项目。
2. 创建 FastAPI 后端项目。
3. 接入 MongoDB。
4. 接入 Redis。
5. 接入 SiliconFlow OpenAI 兼容 Chat Completions API。
6. 实现统一 `LLMClient` 和 `ModelRouter`。
7. 实现 user_id 进入系统。
8. 实现项目创建和读取。
9. 实现 current_script 的读取与保存。

### P1：Script Editor

1. 表格编辑。
2. 行插入、删除。
3. 列插入、删除。
4. 列名重命名。
5. 时长校验。
6. 时间轴与重叠提示。
7. 文本选择 quote。

### P2：Agent 基础能力

1. Brief 上传或输入。
2. Brief 摘要缓存。
3. Brand Agent 流式响应。
4. BrandInsight 结构化输出。
5. Persona CRUD。
6. Audience Agent 最近一次分析。
7. AgentMessage 持久化。
8. Qwen3-8B / Qwen3-32B 按任务复杂度自动切换。

### P3：专家方案闭环

1. Expert Agent 生成多个方案。
2. 方案包含轻量 hunk。
3. diff overlay 预览。
4. 用户逐段接受或拒绝。
5. 应用前校验 cell 当前值。
6. 应用前后生成 script snapshot。
7. 写回 current_script。

## 13. 暂缓实现项

以下能力暂缓，避免 MVP 过重：

1. LangGraph 编排。
2. PostgreSQL checkpointer。
3. 独立 AgentStaleness 表。
4. 每次编辑生成 ScriptVersion。
5. 独立 BriefFile collection。
6. AudienceAnalysis 历史列表。
7. 多 persona 对比分析。
8. 正式登录注册和权限系统。
9. 复杂后台任务队列。
10. 多人协作。

## 14. 风险与约束

### 14.1 MongoDB 文档膨胀

`projects` 嵌入较多数据，后续如果消息、专家方案或脚本变大，需要拆 collection。

MVP 规避方式：

1. `agent_messages` 独立 collection。
2. `script_snapshots` 独立 collection。
3. 必要时将 `expert_suggestions` 拆出。

### 14.2 Hunk 应用冲突

如果用户在专家方案生成后手动改了对应 cell，旧 hunk 可能不再适用。

规避方式：

1. hunk 保存 `old`。
2. 应用前检查当前 cell 是否等于 `old`。
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

本方案保留：

1. MongoDB。
2. Redis。
3. SSE 流式响应。
4. SiliconFlow OpenAI 兼容接口。
5. Qwen/Qwen3-8B 与 Qwen/Qwen3-32B 模型路由。
6. BrandInsight 完整 evidence / confidence / status。
7. 当前 persona 的最近一次 AudienceAnalysis。
8. 轻量 ExpertSuggestion + cell-level hunk。
9. 自定义 user_id。
10. LLM 上下文缓存与摘要。

本方案简化：

1. 不使用 PostgreSQL。
2. 暂不使用 LangGraph。
3. 不做独立 AgentStaleness 表。
4. 不做每次编辑版本化。
5. 不做独立 BriefFile collection。
6. 不做正式鉴权。
7. 不做多 persona 历史分析。

这版设计可以支撑完整 MVP，同时保留后续扩展空间。
