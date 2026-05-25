# 数据结构 + LangGraph State 设计

> 对齐 `docs/prd_new.md` §10、§13、§14。  
> 旧版 `BrandInsight` / `AudienceAnalysis` / `ExpertSuggestion` / 三 Agent 前台模型已废弃，见文末迁移说明。

---

## 一、业务数据结构

### 1. Project

```json
{
  "project_id": "string",
  "owner_id": "string",
  "title": "string",
  "brand_name": "string",
  "video_topic": "string",
  "platform": "xiaohongshu | douyin | bilibili | other",
  "current_brief_file_id": "string",
  "current_script_version_id": "string",
  "active_persona_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**说明：** `owner_id` 预留多用户归属；`current_script_version_id` 指向当前生效脚本版本，结构化 artifact 均绑定 `script_version_id`。

---

### 2. BriefFile

```json
{
  "brief_file_id": "string",
  "project_id": "string",
  "filename": "string",
  "file_url": "string",
  "parse_status": "pending | parsing | parsed | failed",
  "parsed_text": "string",
  "created_at": "datetime"
}
```

**说明：** Brief 解析为异步流程，需独立实体追踪 `parse_status`。PRD 支持 PDF、DOC、DOCX、TXT、MD、PPT、PPTX；MVP 实现范围见 `development_plan_P0.md`。

---

### 3. ScriptVersion

`cells` 使用 `column_id` 关联数组，支持动态列；序号列 `#` 不进入 `columns`。

```json
{
  "script_version_id": "string",
  "project_id": "string",
  "version_no": 1,
  "columns": [
    {
      "column_id": "string",
      "key": "duration",
      "label": "时长",
      "type": "duration | text | textarea | tag",
      "multiline": false,
      "editable": true,
      "deletable": true,
      "order": 0
    }
  ],
  "rows": [
    {
      "row_id": "string",
      "order": 0,
      "cells": [
        { "column_id": "col_001", "value": "0-5" },
        { "column_id": "col_002", "value": "开场画面" }
      ]
    }
  ],
  "created_reason": "manual_edit | revision_proposal_applied | import | rollback",
  "created_at": "datetime"
}
```

**默认业务列（PRD §4.1）：** `duration`、`scene`、`format`、`notes`。不包含「反馈建议」默认列。

---

### 4. CoordinatorMessage

统一 Chat 消息，替代旧版按 `agent_type` 拆分的 `AgentMessage`。

```json
{
  "message_id": "string",
  "project_id": "string",
  "role": "user | assistant | system",
  "content": "string",
  "requested_perspectives": ["brand | audience | expert | comprehensive"],
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
  "related_node_ids": ["string"],
  "generated_artifact_ids": ["string"],
  "created_at": "datetime"
}
```

**说明：** `quotes` 为数组，支持多段引用；`generated_artifact_ids` 可关联本轮生成的 node / proposal / prep / reference id。

---

### 5. RationaleNode（IBIS）

```json
{
  "node_id": "string",
  "project_id": "string",
  "node_type": "issue | position | argument | reference",
  "title": "string",
  "content": "string",
  "source_type": "brand_brief | brand_feedback | brand_inferred | audience_persona | audience_simulation | creator_input | expert_analysis | system_detected | external_reference",
  "source_perspective": "brand | audience | creator | expert | system",
  "business_tags": ["brand_requirement | audience_feedback | conflict | revision_option | negotiation_point | evidence"],
  "stance": "support | oppose | neutral | not_applicable",
  "confidence": "high | medium | low",
  "status": "open | in_review | resolved | needs_negotiation | deferred | dismissed",
  "linked_script_refs": [
    {
      "row_id": "string",
      "column_id": "string",
      "text_snapshot": "string",
      "script_version_id": "string"
    }
  ],
  "related_reference_ids": ["string"],
  "created_by": "agent | user",
  "updated_by": "agent | user",
  "based_on_script_version_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**说明：** 节点**形状/图标**表示 IBIS 类型；**颜色**表示 Issue 来源（`source_type`），见 PRD §5.4。

---

### 6. RationaleEdge

```json
{
  "edge_id": "string",
  "project_id": "string",
  "from_node_id": "string",
  "to_node_id": "string",
  "relation_type": "responds_to | supports | opposes | evidenced_by | derived_from | refines | conflicts_with | updates",
  "created_by": "agent | user",
  "created_at": "datetime"
}
```

**方向约定（PRD §5.5）：**

| relation_type   | 典型方向                    |
| --------------- | ------------------------- |
| responds_to     | Position → Issue          |
| supports        | Argument → Position       |
| opposes         | Argument → Position       |
| evidenced_by    | Argument → Reference      |
| derived_from    | Issue / Argument → Reference |
| refines         | Issue → Issue             |
| conflicts_with  | Position → Position       |
| updates         | Node → Node               |

---

### 7. Persona

```json
{
  "persona_id": "string",
  "project_id": "string",
  "name": "string",
  "icon": "string",
  "gender": "string",
  "age_range": "string",
  "preferences": "string",
  "behavior": "string",
  "platform_context": "string",
  "ad_sensitivity": "low | medium | high",
  "trust_trigger": ["string"],
  "reject_trigger": ["string"],
  "data_source": "manual | system_generated | imported_data",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**说明：** `age_range` 为**自由文本**（如「大学生」「30+新手妈妈」），不做枚举限制（PRD §7.4）。

---

### 8. ReferenceItem

```json
{
  "reference_id": "string",
  "project_id": "string",
  "source_type": "brief | pr_feedback | script | persona | brand_material | case | platform_rule | creator_note | external_knowledge",
  "title": "string",
  "content": "string",
  "quote": "string",
  "url": "string",
  "file_id": "string",
  "related_node_ids": ["string"],
  "related_script_refs": [
    {
      "row_id": "string",
      "column_id": "string",
      "text_snapshot": "string"
    }
  ],
  "created_at": "datetime"
}
```

---

### 9. NegotiationPreparation

```json
{
  "prep_id": "string",
  "project_id": "string",
  "title": "string",
  "based_on_script_version_id": "string",
  "related_issue_ids": ["string"],
  "sections": [
    {
      "section_type": "likely_brand_question | creator_explanation | negotiable_point | confirm_with_brand | external_message",
      "title": "string",
      "content": "string",
      "related_node_ids": ["string"],
      "related_script_refs": [
        {
          "row_id": "string",
          "column_id": "string",
          "text_snapshot": "string"
        }
      ]
    }
  ],
  "status": "draft | reviewed | exported",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### 10. RevisionProposal

替代旧版 `ExpertSuggestion`；由 Coordinator / 内部 Expert Perspective 生成。

```json
{
  "proposal_id": "string",
  "project_id": "string",
  "title": "string",
  "direction": "brand_first | audience_natural | balanced | creator_expression | custom",
  "target_issue_ids": ["string"],
  "description": "string",
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
  "related_node_ids": ["string"],
  "related_reference_ids": ["string"],
  "based_on_script_version_id": "string",
  "status": "draft | previewed | partially_applied | applied | dismissed",
  "created_at": "datetime"
}
```

**Diff 规则：** hunk 绑定 `row_id` + `column_id`；禁止全文字符串重解析写回表格（PRD §9.4）。

**Hunk 用户决策状态：** `null`（未决定）| `true`（应用）| `false`（不应用）。

---

### 11. ArtifactStaleness

按前台 **artifact** 标记过期，不再按 brand / audience / expert 三 Agent 面板。

```json
{
  "project_id": "string",
  "rationale_graph": "up_to_date | stale_script_changed | stale_brief_changed | stale_persona_changed | generating | failed",
  "revision_proposals": "up_to_date | stale_script_changed | stale_graph_changed | stale_persona_changed | generating | failed",
  "negotiation_preparation": "up_to_date | stale_script_changed | stale_graph_changed | generating | failed",
  "references": "up_to_date | stale_brief_changed | stale_external_source_changed | generating | failed",
  "updated_at": "datetime"
}
```

**更新规则摘要（PRD §14）：**

| 触发事件       | 影响字段 |
| ------------ | ---- |
| 脚本 cell 变更   | `rationale_graph`、`revision_proposals`、`negotiation_preparation` → `stale_script_changed` |
| Brief 重新上传/解析 | `rationale_graph`、`references` → brief 相关；`revision_proposals`、`negotiation_preparation` → `stale_graph_changed` |
| active persona 变更/编辑 | `rationale_graph`、`revision_proposals` → `stale_persona_changed` |
| Node Graph 用户编辑 | `revision_proposals`、`negotiation_preparation` → `stale_graph_changed`；Reference 节点变更可能使 `references` stale |

---

## 二、LangGraph State 设计（Coordinator）

### 设计原则（PRD §13.1）

1. 前台只有 **Coordinator Chat**；Brand / Audience / Expert 为**内部视角节点**。
2. 内部节点通过**结构化 artifacts** 传递，不互传大段自然语言。
3. 每个内部节点只读必要上下文，避免污染。
4. 重要结果写入**业务数据库**；LangGraph State 是一次运行上下文，不替代业务表。
5. `thread_id` 使用 `project_id`。

---

### CoordinatorState

```python
from typing import Annotated, Literal, Optional
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


class ScriptSnapshot(BaseModel):
    script_version_id: str
    columns: list[dict]
    rows: list[dict]


class QuoteItem(BaseModel):
    text: str
    row_id: str
    column_id: str
    script_version_id: str


class TriggerSignal(BaseModel):
    task_type: Literal[
        "initialize_project",
        "user_message",
        "script_changed",
        "persona_changed",
        "generate_issue",
        "generate_positions",
        "generate_arguments",
        "generate_revision_proposals",
        "generate_negotiation_preparation",
        "retrieve_references",
    ]
    user_message: Optional[str] = None
    requested_perspectives: list[Literal["brand", "audience", "expert", "comprehensive"]] = Field(default_factory=list)
    quotes: list[QuoteItem] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    active_persona_id: Optional[str] = None


class CoordinatorState(BaseModel):
    project_id: str
    brief_text: Optional[str] = None
    script: Optional[ScriptSnapshot] = None
    active_persona: Optional[dict] = None

    trigger: Optional[TriggerSignal] = None

    # User-facing chat
    coordinator_messages: Annotated[list, add_messages] = Field(default_factory=list)

    # Structured artifacts（运行中累积，persist 节点写入 DB）
    rationale_nodes: list[dict] = Field(default_factory=list)
    rationale_edges: list[dict] = Field(default_factory=list)
    references: list[dict] = Field(default_factory=list)
    revision_proposals: list[dict] = Field(default_factory=list)
    negotiation_preparation: Optional[dict] = None

    # Internal perspective outputs（不直接暴露给前台）
    brand_perspective_result: Optional[dict] = None
    audience_perspective_result: Optional[dict] = None
    expert_perspective_result: Optional[dict] = None

    errors: list[str] = Field(default_factory=list)
```

---

### State 字段职责

| 字段 | 写入方 | 读取方 | 说明 |
|------|--------|--------|------|
| `script` | `entry_node` | 各 perspective / proposal 节点 | 执行开始时从 DB 拉取快照，只读 |
| `brief_text` | `entry_node` | `brand_perspective_node` | Brief 全文或解析文本 |
| `trigger` | 入口 | `task_router_node` | 决定任务类型与调用的内部视角 |
| `brand_perspective_result` | `brand_perspective_node` | `expert_perspective_node`、`rationale_graph_writer_node` | 品牌需求、审片风险等结构化结论 |
| `audience_perspective_result` | `audience_perspective_node` | `expert_perspective_node` | 基于 active persona 的模拟反馈 |
| `expert_perspective_result` | `expert_perspective_node` | `revision_proposal_node` | 综合方案与 trade-off |
| `rationale_nodes` / `rationale_edges` | `rationale_graph_writer_node` | 前端 Graph、`negotiation_writer_node` | IBIS 图增量 |
| `revision_proposals` | `revision_proposal_node` | 前端 Diff | cell-level hunks |
| `negotiation_preparation` | `negotiation_writer_node` | Output Panel | 协商准备 |
| `coordinator_messages` | `response_composer_node` | Coordinator Chat 多轮 | `add_messages` 追加 |

---

### 上下文隔离（PRD §13.5）

| 内部视角 | 可读 | 应避免 |
|----------|------|--------|
| Brand Perspective | brief、品牌资料、PR feedback、相关脚本片段 | 无关 persona 细节 |
| Audience Perspective | script、active persona、平台语境 | 过多品牌内部推理 |
| Expert Perspective | script、rationale graph、brand/audience perspective results、references | — |
| Coordinator（composer） | 所有前台可见 artifacts | — |

---

## 三、推荐 Graph 节点（PRD §13.4）

```text
entry_node              ← 拉取 project、brief、script、persona、graph 快照
    ↓
task_router_node        ← 根据 trigger.task_type 与 requested_perspectives 路由
    ↓
brand_perspective_node
audience_perspective_node
expert_perspective_node
reference_retriever_node
    ↓
rationale_graph_writer_node
revision_proposal_node
negotiation_writer_node
    ↓
response_composer_node    ← 生成用户可见 Coordinator 回复
    ↓
persist_node              ← 写入 CoordinatorMessage、nodes、edges、references、proposals、prep
    ↓
stale_update_node         ← 更新 ArtifactStaleness
    ↓
END
```

**编排说明：** 并非每次运行都执行全部节点；`task_router_node` 按 `task_type` 选择子图。例如 `user_message` 可能只走部分 perspective + composer；`generate_revision_proposals` 侧重 expert + revision_proposal。

---

## 四、内部视角与前台 artifact 的关系

```text
Brief 解析
    ↓
Brand Perspective ──→ rationale_nodes（Issue / Reference 等）
    ↓
Audience Perspective（active persona）──→ Argument / Issue（观众视角）
    ↓
Expert Perspective + Rationale Graph ──→ RevisionProposal、Position、Argument
    ↓
Negotiation Writer ──→ NegotiationPreparation
Reference Retriever ──→ ReferenceItem（Output Panel + Graph Reference 节点）
    ↓
Response Composer ──→ CoordinatorMessage（自然语言 + artifact 引用）
```

用户通过 **Coordinator Chat** 触发；结构化结果同步到 **Node Graph** 与 **Output Panel**，不经过三个独立 Agent 面板。

---

## 五、持久化策略

1. **业务表（推荐 PostgreSQL，见 PRD §18）**  
   前端可查询：`CoordinatorMessage`、`RationaleNode`、`RationaleEdge`、`Persona`、`ReferenceItem`、`RevisionProposal`、`NegotiationPreparation`、`ScriptVersion`。

2. **LangGraph checkpointer**  
   仅用于运行恢复与调试；`thread_id = project_id`。

3. **版本绑定**  
   每条 message、node、reference、proposal、prep 应记录 `based_on_script_version_id`（或 `linked_script_refs[].script_version_id`）。

4. **MVP 轻量实现**  
   见 `technical_plan_lightweight.md`：MongoDB 嵌入 + 独立 collection 拆分策略，与完整规范化 schema 允许阶段性差异。

---

## 六、旧实体迁移对照

| 旧实体 | 新实体 / 表达方式 |
|--------|------------------|
| `AgentMessage`（`agent_type`） | `CoordinatorMessage`（`requested_perspectives`） |
| `BrandInsight` | `RationaleNode`（`node_type=issue/argument`，`source_type` 含 brand_*） |
| `AudienceAnalysis` | `RationaleNode` + 内部 `audience_perspective_result`；不再单独前台 pinned 分析卡 |
| `ExpertSuggestion` | `RevisionProposal` |
| `AgentStaleness`（brand/audience/expert） | `ArtifactStaleness`（按 artifact） |
| 三 Agent 独立 `messages` | 单一 `coordinator_messages` |
| 前台 Brand/Audience/Expert 面板 | Coordinator Chat + Node Graph + Output Panel |

---

## 七、外部触发示例

### Brief 上传后初始化项目

```python
state = CoordinatorState(
    project_id="proj_001",
    trigger=TriggerSignal(task_type="initialize_project"),
)
result = await graph.ainvoke(state, config={"configurable": {"thread_id": "proj_001"}})
```

### 用户带 quote 向 Coordinator 提问（指定观众视角）

```python
state = CoordinatorState(
    project_id="proj_001",
    trigger=TriggerSignal(
        task_type="user_message",
        user_message="这段台词会不会太硬广？",
        requested_perspectives=["audience"],
        quotes=[QuoteItem(
            text="这款产品真的改变了我的生活",
            row_id="row_005",
            column_id="col_scene",
            script_version_id="sv_003",
        )],
        active_persona_id="persona_001",
    ),
)
```

### 从 Issue 生成修改方案

```python
state = CoordinatorState(
    project_id="proj_001",
    trigger=TriggerSignal(
        task_type="generate_revision_proposals",
        target_node_ids=["node_issue_012"],
        requested_perspectives=["comprehensive"],
    ),
)
```

---

## 八、相关文档

- 产品需求：`docs/prd_new.md`
- MVP 开发计划：`docs/development_plan_P0.md`
- 轻量技术方案：`docs/technical_plan_lightweight.md`
