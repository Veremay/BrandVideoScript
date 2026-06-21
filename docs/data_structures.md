# 数据结构 + Coordinator State 设计

> **主依据：** [`docs/pipeline.md`](./pipeline.md)  
> **开发排期：** [`docs/development_plan.md`](./development_plan.md)  
> **技术实现：** [`docs/technical_plan.md`](./technical_plan.md)  
> **产品补充：** `docs/prd_new.md` §10、§13、§14  
>
> 旧版 `BrandInsight` / `AudienceAnalysis` / `ExpertSuggestion` / 三 Agent 前台模型已废弃，见 [§八、迁移对照](#八旧实体迁移对照)。

**MVP 范围提示：** `ReferenceItem` 与固定 Output Panel **不做**；`NegotiationPreparation` 以**按需弹窗**交付；Brief MVP 为 MD/TXT/粘贴，可嵌入 `projects.brief`。

---

## 一、业务数据结构

### 1. Project

规范化目标（PostgreSQL 多表）与 MVP（MongoDB 嵌入）字段语义一致。

```json
{
  "project_id": "string",
  "user_id": "string",
  "owner_id": "string",
  "title": "string",
  "brand_name": "string",
  "video_topic": "string",
  "platform_context": "xiaohongshu | douyin | bilibili | other",
  "brief": {
    "filename": "string",
    "text": "string",
    "summary": "string",
    "parse_status": "pending | parsing | parsed | failed",
    "uploaded_at": "datetime"
  },
  "current_script": {
    "columns": [],
    "rows": [],
    "updated_at": "datetime"
  },
  "current_script_version_id": "string",
  "active_persona_id": "string",
  "personas": [],
  "rationale_nodes": [],
  "rationale_edges": [],
  "modification_schemes": [],
  "negotiation_queue": ["issue_node_id"],
  "negotiation_preparation": null,
  "stale": {},
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

| 字段 | 说明 |
|------|------|
| `user_id` | MVP 自定义 ID 隔离项目 |
| `owner_id` | 远期正式鉴权 |
| `platform_context` | 视频平台语境（MVP 可配置常量，后期接数据分析） |
| `brief` | MVP 嵌入；完整版可拆 `BriefFile` |
| `consideration_queue` | 创作者采纳的 **TO BE CONSIDERED** Position 列表（`pipeline.md` §10） |
| `negotiation_preparation` | 最近一次生成的协商材料（弹窗读取） |

结构化 artifact 应记录 `based_on_script_version_id`（或 `linked_script_refs[].script_version_id`）。

---

### 2. Brief / BriefFile

**MVP：** Brief 嵌入 `project.brief`（见上表）。

**完整版（二期多格式解析）：** 独立实体追踪 `parse_status`。

```json
{
  "brief_file_id": "string",
  "project_id": "string",
  "filename": "string",
  "file_url": "string",
  "parse_status": "pending | parsing | parsed | failed",
  "parsed_text": "string",
  "summary": "string",
  "created_at": "datetime"
}
```

MVP 文件类型：`.md`、`.txt`、纯文本粘贴。PDF/DOC/PPT 等见 `development_plan.md` §10。

---

### 3. Script / ScriptVersion

`cells` 通过 `column_id` 关联；序号列 `#` **不进入** `columns`。

```json
{
  "script_version_id": "string",
  "project_id": "string",
  "version_no": 1,
  "columns": [
    {
      "column_id": "string",
      "key": "duration | scene | format | notes | feedback",
      "label": "string",
      "type": "duration | text | textarea | tag",
      "multiline": false,
      "editable": true,
      "deletable": true,
      "order": 0,
      "visibility": "creator | brand_share_only"
    }
  ],
  "rows": [
    {
      "row_id": "string",
      "order": 0,
      "cells": [
        { "column_id": "col_001", "value": "0-5" }
      ]
    }
  ],
  "created_reason": "manual_edit | scheme_applied | brand_feedback_sync | import | rollback",
  "created_at": "datetime"
}
```

**默认业务列（创作者工作区）：** `duration`、`scene`、`format`、`notes`。

| 列 key | 说明 |
|--------|------|
| `duration` | 时长，格式 `起始秒-结束秒`（如 `0-5`） |
| `scene` | 画面（多行） |
| `format` | 形式 |
| `notes` | 备注 |
| `feedback` | **品牌反馈**：品牌方在分享页填写；`sync` 后写入 `current_script` 对应单元格。创作者工作区**只读可见**，不可自行编辑（`pipeline.md` §9）。 |

**快照时机：** 应用 ModificationScheme hunk 前后、手动保存、品牌 feedback 合并、回滚。

---

### 4. ShareSession（品牌方分享）

品牌方仅可见脚本表格，不可见 Graph / Chat / Persona / Brief。

```json
{
  "share_token": "string",
  "project_id": "string",
  "script_snapshot": {
    "columns": [],
    "rows": []
  },
  "includes_feedback_column": true,
  "expires_at": "datetime",
  "created_at": "datetime"
}
```

| 规则 | 说明 |
|------|------|
| 写权限 | 品牌方仅可 PATCH `feedback` 列 |
| 回流 | 创作者 `brand-feedback/sync` 后触发 `brand_feedback_sync` 任务 |
| 安全 | token 随机、可过期；不暴露完整 Project API |

---

### 5. CoordinatorMessage

统一 Chat 消息；**无** `agent_type`。

```json
{
  "message_id": "string",
  "project_id": "string",
  "user_id": "string",
  "role": "user | assistant | system",
  "content": "string",
  "task_type": "user_message | quote_analysis | brief_initial_parse | script_delta | brand_feedback_sync | generate_negotiation",
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

`generated_artifact_ids` 可关联：`node_id`、`scheme_id`、`prep_id` 等（**不含** MVP 未实现的 `reference_id`）。

---

### 6. RationaleNode（IBIS）

> **生成原则（自下而上 · 冲突驱动）：** 论证网络以 **Position 为基本单元**，先有各方立场；当 **≥2 个 Position 相互冲突**时才**派生** Issue。**Issue 不能单独存在——Issue 即冲突**，必须由 ≥2 个 Position 通过 `responds_to` 指向，并建议在冲突 Position 间建立 `conflicts_with`。Position 可作为根节点独立存在（暂无冲突）；Argument 必须 `supports`/`opposes` 某 Position。服务端在合并时对不满足 ≥2 Position 的 **agent 生成 Issue 直接报错**（`validate_ibis_graph_integrity`），而非静默丢弃。
>
> **Agent 分工：** Brand / Audience **只产 Position**；Expert 负责在各方 Position 间识别冲突并派生 Issue（连 `responds_to` + `conflicts_with`）。
>
> **用户手建 Issue：** 创作者在画布上新建 Issue 后，可在该节点菜单手动点击 **Generate positions**，触发 Expert **围绕该 Issue 组织 ≥2 个对立 Position**（`responds_to` + `conflicts_with`，`populate_issue_with_positions`）。节点创建本身是即时的、不自动跑 Agent。
>
> **Update Map = 锚定式 reconcile（`sync_graph_from_script` → `run_reconcile_pipeline` → `apply_reconcile`）：** 每次更新地图，Expert 对**每个已有 Issue**（含 active/resolved）逐个复评，返回 `still_holds` / `resolved` / `modified`，并可报告 Position/Argument 的实质修改与全新冲突：
> - `still_holds` → 节点与 id 完全不变（resolved 的会被复活回 active）。
> - `resolved`（仅 Issue 层）→ id 不变，`lifecycle=resolved`，画布半透明 + 【已解决】；仅 Issue 及其 `responds_to`/`conflicts_with` 边变灰，关联 Position/Argument 保持 active。resolved Issue 不再受 ≥2 约束、可复活。
> - `modified`（任意节点）→ **新建节点（新 id）继承旧节点全部边**，旧节点移出 live 图（仅留在更新前快照），新节点 `change_mark=modified` 并记 `predecessor_id`。
> - 全新冲突 → 正常新增，`change_mark=new`。
> - **用户节点（`created_by=user`）永不被 supersede/resolve**，只在节点上挂 `suggestion`（如 `resolved?` / `modify?`）由创作者自行处理。
> - **id 引用不迁移：** `consideration_queue` / `ModificationScheme` 仍绑定原 id；若该节点已不在 live 图中，前端在 TO BE CONSIDERED 列表显示「立场已更新/已失效」标签供清理。

```json
{
  "node_id": "string",
  "project_id": "string",
  "node_type": "issue | position | argument | reference",
  "title": "string",
  "content": "string",
  "source_type": "brand_brief | brand_feedback | brand_inferred | audience_persona | audience_simulation | expert_strategy | creator_manual | external_reference",
  "source_perspective": "brand | audience | creator | expert | system",
  "business_tags": ["brand_requirement | audience_feedback | conflict | revision_option | negotiation_point | evidence"],
  "stance": "support | oppose | neutral | not_applicable",
  "confidence": "high | medium | low",
  "status": "open | in_review | resolved | needs_negotiation | deferred | dismissed",
  "in_consideration_queue": false,
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
  "lifecycle": "active | resolved | superseded",
  "change_mark": "none | modified | new",
  "predecessor_id": "string | null",
  "resolved_at": "datetime | null",
  "suggestion": "string | null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

> `lifecycle`/`change_mark`/`predecessor_id`/`resolved_at`/`suggestion` 由 reconcile（Update Map）维护，见上方「生成原则」。`superseded` 节点不会出现在 live 图中，仅存在于更新前快照。

**形状 / 图标：** `node_type`（IBIS 类型）  
**颜色 / 来源：** `source_type`（`pipeline.md` §3）

| source_type（MVP 主路径） | 来源 Agent / 角色 |
|---------------------------|-------------------|
| `brand_brief` | Brand Agent，Brief 解析 |
| `brand_feedback` | Brand Agent，真实品牌 feedback 列 |
| `brand_inferred` | Brand Agent，隐性需求推测（Tavily / Brand Wiki） |
| `audience_persona` | Audience Agent，Persona 驱动 |
| `audience_simulation` | Audience Agent，脚本模拟反馈 |
| `expert_strategy` | Expert Agent，创作策略 |
| `creator_manual` | 创作者手动创建 |
| `external_reference` | 二期 References |

`in_consideration_queue: true` 表示 Position 在 **TO BE CONSIDERED LIST** 中（与 `project.consideration_queue` 同步）。创作者采纳该立场，并用于生成修改方案。

---

### 7. RationaleEdge

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

| relation_type | 典型方向 | 说明 |
|---------------|----------|------|
| responds_to | Position → Issue | 立场归属于某冲突（Issue 需 ≥2 条） |
| conflicts_with | Position ↔ Position | **两立场冲突**，是 Issue 派生的依据 |
| supports | Argument → Position | |
| opposes | Argument → Position | |
| evidenced_by | Argument → Reference | |
| derived_from | Issue / Argument → Reference | |
| refines | Issue → Issue | |
| updates | Node → Node | |

---

### 8. Persona

Audience Agent 维护；Brief 初始解析可自动生成，创作者可编辑（`pipeline.md` §8）。

```json
{
  "persona_id": "string",
  "project_id": "string",
  "name": "string",
  "icon": "string",
  "gender": "string",
  "age_range": "string",
  "description": "string",
  "preferences": "string",
  "behavior": "string",
  "viewing_motivation": "string",
  "platform_context": "string",
  "ad_sensitivity": "low | medium | high",
  "ad_sensitivity_notes": "string",
  "trust_trigger": ["string"],
  "reject_trigger": ["string"],
  "data_source": "manual | persona_analytics | imported_data",
  "analytics_meta": {
    "provider": "stub | internal_analytics",
    "model_version": "string",
    "generated_at": "datetime"
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

| 字段 | pipeline 对应 |
|------|----------------|
| `description` | 目标观众描述 |
| `age_range` | 年龄范围（**自由文本**） |
| `preferences` | 兴趣偏好 |
| `behavior` | 内容消费习惯 |
| `viewing_motivation` | 观看动机 |
| `reject_trigger` | 可能的反感点 |
| `ad_sensitivity` / `ad_sensitivity_notes` | 对广告植入的敏感点 |
| `data_source` | `persona_analytics` = 数据分析管线生成（**非** Brief、**非** Audience Agent） |

Persona 变更 → `stale_persona_changed`；Audience Agent 后续分析使用新 persona。

**Audience Agent 不读取 Brief，也不负责生成 Persona 初始字段。**

---

### 8.1 PersonaAnalyticsInput / Output（预留）

与 Brief / Brand 解析解耦。详见 `technical_plan.md` §4.3。

**请求上下文（不含 brief）：**

```json
{
  "project_id": "string",
  "platform_context": "xiaohongshu | douyin | bilibili | other",
  "content_category": "string",
  "brand_name": "string",
  "video_topic": "string",
  "locale": "zh-CN"
}
```

**响应：**

```json
{
  "personas": [],
  "active_persona_id": "string",
  "analytics_meta": {
    "provider": "stub | internal_analytics",
    "model_version": "string",
    "generated_at": "datetime"
  }
}
```

MVP：`StubPersonaAnalyticsProvider` 按平台返回模板；二期对接真实数据分析服务。

---

### 9. ModificationScheme（Expert 多方向修改方案）

替代旧版 `ExpertSuggestion` / 主路径替代 `RevisionProposal`（`pipeline.md` §10）。由 Expert Agent / `modification_scheme_writer` 生成；**不直接覆盖脚本**。

```json
{
  "scheme_id": "string",
  "project_id": "string",
  "title": "string",
  "direction": "conservative | balanced | creator_led | audience_friendly | custom",
  "target_issue_ids": ["string"],
  "changes_summary": "string",
  "rationale": "string",
  "tradeoffs": {
    "brand": "string",
    "audience": "string",
    "creator": "string"
  },
  "sacrifice": "string",
  "communication_scene": "string",
  "brand_objection": "string",
  "response_script": "string",
  "risk": "string",
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
  "based_on_script_version_id": "string",
  "status": "draft | previewed | partially_applied | applied | dismissed",
  "created_at": "datetime"
}
```

| direction | 含义（pipeline §10） |
|-----------|---------------------|
| `conservative` | 更贴近品牌需求 |
| `balanced` | 兼顾品牌露出与内容自然性 |
| `creator_led` | 保留创意表达，附解释理由 |
| `audience_friendly` | 降低广告感，提高接受度 |

**Hunk 规则：** 绑定 `row_id` + `column_id`；apply 前校验当前 cell == `removed`；用户决策 `null | true | false`  per hunk。

**别名：** 历史文档中的 `RevisionProposal` 字段语义映射到本实体（`proposal_id` → `scheme_id`，`brand_first` → `conservative` 等），新代码统一使用 `ModificationScheme`。

---

### 10. NegotiationPreparation

创作者点击按钮**按需生成**，弹窗展示（`pipeline.md` §11）；**非** MVP 固定 Output Panel。

```json
{
  "prep_id": "string",
  "project_id": "string",
  "title": "string",
  "based_on_script_version_id": "string",
  "design_intent": "string",
  "satisfied_brand_needs": ["string"],
  "open_disputes": [
    {
      "issue_node_id": "string",
      "summary": "string",
      "our_position": "string",
      "acceptable_concession": "string",
      "non_negotiable_line": "string",
      "talking_points": ["string"],
      "related_node_ids": ["string"],
      "related_script_refs": [
        { "row_id": "string", "column_id": "string", "text_snapshot": "string" }
      ]
    }
  ],
  "recommended_communication_order": ["issue_node_id"],
  "related_issue_ids": ["string"],
  "status": "draft | reviewed | exported",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

| 内容块 | pipeline §11 |
|--------|----------------|
| `design_intent` | 当前脚本核心设计意图 |
| `satisfied_brand_needs` | 已满足的品牌需求 |
| `open_disputes` | 尚存在分歧的问题（优先来自 `negotiation_queue`） |
| `acceptable_concession` / `non_negotiable_line` | 让步空间 / 创作底线 |
| `talking_points` | 面对品牌质疑的回应话术 |
| `recommended_communication_order` | 建议沟通顺序 |

---

### 11. ReferenceItem（二期）

`pipeline.md` §12：**MVP 不做**。结构保留供 References 输出与 Graph `external_reference` 节点使用。

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
  "related_script_refs": [],
  "created_at": "datetime"
}
```

---

### 12. ArtifactStaleness

按前台 **artifact** 标记过期；不再按 brand / audience / expert 三 Agent 面板。

```json
{
  "project_id": "string",
  "rationale_graph": "up_to_date | stale_script_changed | stale_brief_changed | stale_persona_changed | stale_brand_feedback | generating | failed",
  "modification_schemes": "up_to_date | stale_script_changed | stale_graph_changed | stale_persona_changed | stale_brand_feedback | generating | failed",
  "negotiation_preparation": "up_to_date | stale_script_changed | stale_graph_changed | stale_brand_feedback | generating | failed",
  "references": "up_to_date | stale_brief_changed | stale_external_source_changed | generating | failed",
  "updated_at": "datetime"
}
```

MVP 可简化为 `stale_*: true` + `reason` 字符串。

| 触发事件 | 影响字段 |
|----------|----------|
| 脚本 cell 变更 | `rationale_graph`、`modification_schemes`、`negotiation_preparation` |
| Brief 上传/重解析 | `rationale_graph`；`modification_schemes`、`negotiation_preparation` → graph 相关 |
| active persona 变更 | `rationale_graph`、`modification_schemes` |
| Node Graph 用户编辑 | `modification_schemes`、`negotiation_preparation` |
| 品牌 feedback sync | `rationale_graph`、`modification_schemes`、`negotiation_preparation` → `stale_brand_feedback` |
| 新 artifact 写入且 version 匹配 | 对应项 → `up_to_date` |

---

### 13. 内部 Agent 结构化输出（不直接暴露前台）

Agent 间只传递以下结构，**不互传大段聊天原文**（`pipeline.md` §2）。

#### 13.1 BrandPerspectiveResult

```json
{
  "explicit_requirements": [{ "text": "string", "evidence": "string", "confidence": "high | medium | low" }],
  "implicit_requirements": [{ "text": "string", "evidence": "string", "confidence": "high | medium | low" }],
  "constraints": ["string"],
  "pr_risks": ["string"],
  "proposed_nodes": [],
  "proposed_edges": [],
  "tool_calls_used": ["tavily_search | brand_wiki_lookup"]
}
```

**禁止**向 Audience Agent 提供：本结构全文、`brief`、任何 `brand_*` 图节点。

#### 13.2 AudiencePerspectiveResult

```json
{
  "naturalness": "string",
  "ad_sense": "string",
  "trust": "string",
  "drop_off_risk": "string",
  "suggestions": ["string"],
  "structured_issues": [{ "title": "string", "content": "string" }],
  "proposed_nodes": [],
  "proposed_edges": []
}
```

**禁止**向 Brand Agent 提供：本结构全文、`active_persona` 全文、任何 `audience_*` 图节点。  
**禁止** Audience Agent 读取 `brief`（Persona 来自 §8.1 数据分析）。

#### 13.3 ExpertPerspectiveResult

```json
{
  "brief_impact_summary": "string",
  "creation_constraints": ["string"],
  "strategy_notes": ["string"],
  "recommended_directions": ["conservative | balanced | creator_led | audience_friendly"],
  "modification_schemes": [],
  "negotiation_preparation": null,
  "proposed_nodes": [],
  "proposed_edges": [],
  "tool_calls_used": ["domain_case_retriever | script_structure_kb"]
}
```

**说明：** 无独立 GraphWriter / SchemeWriter / NegotiationWriter；`proposed_*`、`modification_schemes`、`negotiation_preparation` 均由 Expert（及 Brand/Audience 的 `proposed_*`）产出，经 `persist_node` 写入 `project`。

---

## 二、Coordinator State 设计

### 设计原则

1. 前台只有 **Coordinator Chat**；Brand / Audience / Expert 为内部 Agent。
2. 内部 Agent 通过 **§13 结构化结果** 与 IBIS 节点传递，不互传聊天原文。
3. 各 Agent **上下文隔离**（见下表）。
4. LangGraph State 是一次运行上下文；持久化写入 MongoDB / PostgreSQL 业务表。
5. `thread_id = project_id`（LangGraph 二期）。

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
        "brief_initial_parse",
        "persona_provisioned",
        "user_message",
        "quote_analysis",
        "script_delta",
        "persona_changed",
        "brand_feedback_sync",
        "generate_modification_schemes",
        "generate_negotiation",
        # 二期
        "retrieve_references",
    ]
    user_message: Optional[str] = None
    requested_perspectives: list[Literal["brand", "audience", "expert", "comprehensive"]] = Field(default_factory=list)
    quotes: list[QuoteItem] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    changed_row_ids: list[str] = Field(default_factory=list)
    active_persona_id: Optional[str] = None


class CoordinatorState(BaseModel):
    project_id: str
    platform_context: Optional[str] = None
    brief_text: Optional[str] = None
    brief_summary: Optional[str] = None
    script: Optional[ScriptSnapshot] = None
    active_persona: Optional[dict] = None
    negotiation_queue: list[str] = Field(default_factory=list)

    trigger: Optional[TriggerSignal] = None

    coordinator_messages: Annotated[list, add_messages] = Field(default_factory=list)

    rationale_nodes: list[dict] = Field(default_factory=list)
    rationale_edges: list[dict] = Field(default_factory=list)
    modification_schemes: list[dict] = Field(default_factory=list)
    negotiation_preparation: Optional[dict] = None

    brand_perspective_result: Optional[dict] = None
    audience_perspective_result: Optional[dict] = None
    expert_perspective_result: Optional[dict] = None
    brand_feedback_rows: list[dict] = Field(default_factory=list)

    references: list[dict] = Field(default_factory=list)  # 二期

    errors: list[str] = Field(default_factory=list)
```

---

### State 字段职责

| 字段 | 写入方 | 读取方 | 说明 |
|------|--------|--------|------|
| `brief_summary` | entry / Brand | Brand, Expert, Coordinator | Audience **不可读** |
| `active_persona` | PersonaAnalytics / 用户 | Audience, Expert, Coordinator | Brand **不可读** |
| `script` | entry | Brand, Audience, Expert | 按任务裁剪行/quote |
| `negotiation_queue` | 用户 | Expert（`generate_negotiation`） | 待协商 Issue id |
| `brand_perspective_result` | Brand Agent | Expert, Coordinator | §13.1 |
| `audience_perspective_result` | Audience Agent | Expert, Coordinator | §13.2 |
| `expert_perspective_result` | Expert Agent | Coordinator | §13.3 |
| `brand_feedback_rows` | sync + Brand | Brand, Expert, Coordinator | Audience **不读** |
| `rationale_*` | 三 Agent `proposed_*` + 用户 | 前端；Expert 子图摘要 | `persist_node` 合并 |
| `modification_schemes` | Expert | 前端 Diff, Coordinator | |
| `negotiation_preparation` | Expert | 协商弹窗, Coordinator | `generate_negotiation` |
| `coordinator_messages` | composer | Chat | `add_messages` |

---

### 上下文隔离（Brand ⊥ Audience）

| 读者 | 可读 | 禁止 |
|------|------|------|
| **Brand** | brief、Wiki/Tavily、feedback 行、脚本片段 | Persona、`AudiencePerspectiveResult`、`audience_*` 节点 |
| **Audience** | Persona、`platform_context`、脚本片段 | **brief**、`BrandPerspectiveResult`、`brand_*` 节点 |
| **Expert** | 脚本、子图摘要、§13.1 + §13.2、知识库 | 另两 Agent 聊天原文 |
| **Coordinator** | 全部持久化 artifact | 披露按 `requested_perspectives` 过滤 |

共享输入仅限：`platform_context`、脚本、用户 quote。  
风险与应对见 `technical_plan.md` §16。

---

## 三、推荐编排图（三 Agent + persist，无 Writer）

```text
entry_context_loader    ← 按角色白名单裁剪（§ 上下文隔离）
    ↓
task_router
    ↓
brand_agent             ← Tavily, Brand Wiki → §13.1 + proposed_*
audience_agent          ← 无 brief；persona + script → §13.2 + proposed_*
expert_agent            ← 汇总 + schemes + negotiation + proposed_*
    ↓
persist_node            ← 合并 proposed_* / schemes / prep → MongoDB
    ↓
response_composer
    ↓
stale_update_node
    ↓
END

（并行）persona_analytics_provider → project.personas   # 不经 Audience Agent
```

| task_type | 典型子图 |
|-----------|----------|
| `brief_initial_parse` | Brand → Expert → persist → composer |
| `persona_provisioned` | Audience → Expert → persist → composer（可选） |
| `user_message` / `quote_analysis` | router → Agent(s) → Expert? → persist → composer |
| `script_delta` | Audience / Expert（按需）→ persist |
| `brand_feedback_sync` | Brand → Expert → persist → composer |
| `generate_modification_schemes` | Expert → persist → composer |
| `generate_negotiation` | Expert → persist → composer |

---

## 四、数据流（pipeline 主路径）

```text
Persona 数据分析（§8.1）→ project.personas
Brief 上传 → Brand → Expert 初始品牌向节点
Persona 就绪 → Audience → Expert 观众向节点（可选）
    ↓
主工作区：Script Editor ↔ Node Graph + Coordinator Chat
    ↓
脚本编辑 / 选段 quote → 结构化节点增量
    ↓
Expert → ModificationScheme（多方向，可选 hunks）→ 创作者确认 apply
    ↓
[可选] 分享链接 → 品牌 feedback 列 → brand_feedback_sync → 新节点
    ↓
Issue 加入 negotiation_queue → generate_negotiation → 协商弹窗
    ↓
交付资产：脚本 + 图 + Persona + 方案集 + 协商材料（References 二期）
```

---

## 五、持久化策略

| 层 | MVP | 终态 |
|----|-----|------|
| 主存储 | MongoDB `projects` 嵌入 + `coordinator_messages` + `script_snapshots` + `share_sessions` | PostgreSQL 多表 |
| 可拆 collection | `rationale_nodes`、`modification_schemes` | 同上 |
| LangGraph checkpointer | 二期；`thread_id = project_id` | 运行恢复 only |
| 版本绑定 | 所有 artifact 带 `based_on_script_version_id` | 同左 |

---

## 六、旧实体迁移对照

| 旧实体 | 新实体 / 表达方式 |
|--------|------------------|
| `AgentMessage`（`agent_type`） | `CoordinatorMessage`（`task_type`、`requested_perspectives`） |
| `BrandInsight` | `RationaleNode` + `BrandPerspectiveResult` |
| `AudienceAnalysis` | `RationaleNode` + `AudiencePerspectiveResult` |
| `ExpertSuggestion` | `ModificationScheme` |
| `RevisionProposal` | **`ModificationScheme`**（字段别名见 §9） |
| `AgentStaleness` | `ArtifactStaleness`（`modification_schemes` 替代 `revision_proposals`） |
| 三 Agent 前台面板 | Coordinator Chat + Script / Graph |
| Output Panel（Negotiation/References tab） | **协商弹窗**；References **二期** |
| 默认 `feedback` 列 | **仅 ShareSession 视图** |

---

## 七、外部触发示例

### Brief 上传后初始解析（不含 Audience；Persona 走 §8.1）

```python
state = CoordinatorState(
    project_id="proj_001",
    trigger=TriggerSignal(task_type="brief_initial_parse"),
)
```

### Persona 数据分析完成后（可选跟进）

```python
state = CoordinatorState(
    project_id="proj_001",
    active_persona={...},
    trigger=TriggerSignal(task_type="persona_provisioned"),
)
```

### 用户带 quote 提问（观众视角）

```python
state = CoordinatorState(
    project_id="proj_001",
    trigger=TriggerSignal(
        task_type="quote_analysis",
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

### 从 Issue 生成多方向修改方案

```python
state = CoordinatorState(
    project_id="proj_001",
    trigger=TriggerSignal(
        task_type="generate_modification_schemes",
        target_node_ids=["node_issue_012"],
        requested_perspectives=["comprehensive"],
    ),
)
```

### 品牌 feedback 回流后同步

```python
state = CoordinatorState(
    project_id="proj_001",
    trigger=TriggerSignal(task_type="brand_feedback_sync"),
)
```

### 生成协商准备（弹窗）

```python
state = CoordinatorState(
    project_id="proj_001",
    negotiation_queue=["node_issue_003", "node_issue_012"],
    trigger=TriggerSignal(task_type="generate_negotiation"),
)
```

---

## 八、相关文档

- 系统流程：**[`docs/pipeline.md`](./pipeline.md)**
- 开发计划：**[`docs/development_plan.md`](./development_plan.md)**
- 技术方案：**[`docs/technical_plan.md`](./technical_plan.md)**
- 产品需求：`docs/prd_new.md`
- 归档：`docs/development_plan_P0.md`、`docs/technical_plan_lightweight.md`
