# 数据结构修订版 + LangGraph State 设计

---

## 一、修订后的数据结构

### 1. Project

```json
{
  "project_id": "string",
  "owner_id": "string",
  "title": "string",
  "brand_name": "string",
  "video_topic": "string",
  "platform": "xiaohongshu | douyin | bilibili | other",
  "brief_file_id": "string",
  "brief_text": "string",
  "current_script_version_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**修改说明：** 新增 `owner_id`，预留多用户归属，避免后续接入认证时补 migration。

---

### 2. BriefFile（新增独立实体）

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

**修改说明：** 原 PRD 没有独立定义此结构，仅在 API 返回里出现。解析是异步的，需要独立实体追踪状态。

---

### 3. ScriptVersion

`cells` 从固定 key object 改为 column_id 关联的数组，支持动态列。

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
  "created_reason": "manual_edit | expert_suggestion_applied | import",
  "created_at": "datetime"
}
```

**修改说明：** 原 `cells: { duration: "0-5", scene: "..." }` 使用固定 key，与动态列（用户可增删列）冲突。改为数组后，通过 `column_id` 关联，列被删除时 cells 里对应条目一并清理，结构自洽。

---

### 4. AgentMessage

`quote` 从单对象改为数组，支持多段引用。

```json
{
  "message_id": "string",
  "project_id": "string",
  "agent_type": "brand | audience | expert",
  "role": "user | assistant | system",
  "content": "string",
  "quotes": [
    {
      "text": "string",
      "row_id": "string",
      "column_id": "string",
      "script_version_id": "string"
    }
  ],
  "created_at": "datetime"
}
```

**修改说明：** 用户可以多次选中文本插入 quote tag，单 object 无法满足。改为 `quotes` 数组。

---

### 5. BrandInsight

补回 `updated_by` 字段。

```json
{
  "insight_id": "string",
  "project_id": "string",
  "category": "explicit_requirement | implicit_requirement | brand_feedback",
  "content": "string",
  "reason": "string",
  "evidence": [
    {
      "source_type": "brief | pr_feedback | script | chat",
      "quote": "string",
      "row_id": "string",
      "column_id": "string"
    }
  ],
  "confidence": "high | medium | low",
  "status": "new | confirmed | pending | ignored",
  "created_by": "agent | user",
  "updated_by": "agent | user",
  "based_on_script_version_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**修改说明：** Section 10.4 漏了 `updated_by`，从 Section 6.2 补回，后端追踪谁最后修改了 insight 所必需。

---

### 6. Persona

`age` 从 string 改为结构化范围。

```json
{
  "persona_id": "string",
  "project_id": "string",
  "name": "string",
  "icon": "string",
  "gender": "string",
  "age_range": "18-24 | 25-34 | 35-44 | 45+",
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

**修改说明：** 原 `age: string` 太宽泛（"25岁"、"年轻人"等都能填），会导致 LLM prompt 中的受众分析不稳定。改为枚举 `age_range`，既限制了输入，也方便在 prompt 中直接用于受众推断。

---

### 7. AudienceAnalysis（新增独立实体）

```json
{
  "analysis_id": "string",
  "project_id": "string",
  "persona_id": "string",
  "based_on_script_version_id": "string",
  "summary": "string",
  "naturalness_score": 3,
  "credibility_score": 3,
  "ad_sensitivity_score": 3,
  "key_risks": ["string"],
  "liked_parts": [
    { "row_id": "string", "reason": "string" }
  ],
  "rejected_parts": [
    { "row_id": "string", "reason": "string" }
  ],
  "suggestions": ["string"],
  "created_at": "datetime"
}
```

**修改说明：** 原 PRD 分析结果只存在对话消息里。结构化分析结果应独立持久化，绑定 `script_version_id` + `persona_id`，方便专家 Agent 读取以及后续多版本对比。`liked_parts` / `rejected_parts` 补了 `row_id` 以便与脚本表格精准关联。

---

### 8. ExpertSuggestion

补回 `based_on_audience_insight_ids`，hunk 结构补全。

```json
{
  "suggestion_id": "string",
  "project_id": "string",
  "title": "string",
  "direction": "brand_first | audience_natural | balanced | creator_expression | custom",
  "description": "string",
  "target_problem": "string",
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
  "based_on_script_version_id": "string",
  "based_on_brand_insight_ids": ["string"],
  "based_on_audience_analysis_ids": ["string"],
  "status": "draft | previewed | partially_applied | applied | dismissed",
  "created_at": "datetime"
}
```

**修改说明：** 原 Section 10.6 漏了 `based_on_audience_insight_ids`（且已改名为 `based_on_audience_analysis_ids` 对应新的独立实体）。这个字段是 stale 联动的依据：当关联的 audience analysis 更新后，系统才能精准标记哪些 suggestion 需要 stale。

---

### 9. AgentStaleness

补全 audience 的 `stale_persona_changed` 枚举值。

```json
{
  "project_id": "string",
  "brand": "up_to_date | stale_script_changed | generating | failed",
  "audience": "up_to_date | stale_script_changed | stale_persona_changed | generating | failed",
  "expert": "up_to_date | stale_script_changed | stale_brand_changed | stale_audience_changed | generating | failed",
  "updated_at": "datetime"
}
```

**修改说明：** 原 PRD audience 缺少 `stale_persona_changed`。用户切换或编辑 persona 后，基于旧 persona 的分析结果就已过期，需要单独标记。

---

## 二、LangGraph State 设计

### 设计原则

LangGraph 的 State 是整个图（Graph）中所有节点共享的上下文。这个系统有三个 Agent，核心原则是：

- **每个 Agent 只读自己需要的字段，只写自己负责的字段**
- **State 是快照 + 增量，不是聊天历史的堆叠**
- **Agent 之间不直接调用对方，通过 State 中的字段传递输出**

---

### GraphState 定义

```python
from typing import Annotated, Literal, Optional
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


# ── 脚本快照（只读，节点不得直接修改，需通过专门节点更新）──
class CellSnapshot(BaseModel):
    column_id: str
    value: str

class RowSnapshot(BaseModel):
    row_id: str
    order: int
    cells: list[CellSnapshot]

class ColumnDef(BaseModel):
    column_id: str
    key: str
    label: str
    type: str
    multiline: bool

class ScriptSnapshot(BaseModel):
    script_version_id: str
    columns: list[ColumnDef]
    rows: list[RowSnapshot]


# ── 品牌方 Agent 输出 ──
class BrandInsightItem(BaseModel):
    insight_id: str
    category: Literal["explicit_requirement", "implicit_requirement", "brand_feedback"]
    content: str
    reason: str
    confidence: Literal["high", "medium", "low"]
    status: Literal["new", "confirmed", "pending", "ignored"]
    created_by: Literal["agent", "user"]
    updated_by: Literal["agent", "user"]


# ── 观众 Agent 输出 ──
class AudienceAnalysisResult(BaseModel):
    analysis_id: str
    persona_id: str
    summary: str
    naturalness_score: int
    credibility_score: int
    ad_sensitivity_score: int
    key_risks: list[str]
    liked_parts: list[dict]
    rejected_parts: list[dict]
    suggestions: list[str]


# ── 专家 Agent 输出 ──
class HunkItem(BaseModel):
    hunk_id: str
    row_id: str
    column_id: str
    context: str
    removed: str
    added: str

class ExpertSuggestionItem(BaseModel):
    suggestion_id: str
    title: str
    direction: str
    description: str
    rationale: str
    brand_tradeoff: str
    audience_tradeoff: str
    creator_tradeoff: str
    risk: str
    explanation_to_brand: str
    hunks: list[HunkItem]
    based_on_brand_insight_ids: list[str]
    based_on_audience_analysis_ids: list[str]


# ── Quote（用户从脚本中圈出的引用）──
class QuoteItem(BaseModel):
    text: str
    row_id: str
    column_id: str
    script_version_id: str


# ── 触发信号（控制哪个节点运行）──
class TriggerSignal(BaseModel):
    agent: Literal["brand", "audience", "expert"]
    reason: Literal[
        "brief_uploaded",
        "user_message",
        "script_changed",
        "persona_changed",
        "user_request_regenerate"
    ]
    user_message: Optional[str] = None
    quotes: list[QuoteItem] = Field(default_factory=list)
    active_persona_id: Optional[str] = None


# ── 主 State ──
class CreatorStudioState(BaseModel):

    # 项目基础
    project_id: str
    brief_text: Optional[str] = None

    # 脚本快照（每次涉及脚本的节点执行前，从 DB 拉取最新版本填入）
    script: Optional[ScriptSnapshot] = None

    # 触发信号（由 entry node 设置，各 Agent 节点根据此决定是否执行）
    trigger: Optional[TriggerSignal] = None

    # 品牌方 Agent
    brand_insights: list[BrandInsightItem] = Field(default_factory=list)
    brand_messages: Annotated[list, add_messages] = Field(default_factory=list)
    brand_stale: bool = False

    # 观众 Agent
    active_persona_id: Optional[str] = None
    audience_analysis: Optional[AudienceAnalysisResult] = None
    audience_messages: Annotated[list, add_messages] = Field(default_factory=list)
    audience_stale: bool = False

    # 专家 Agent
    expert_suggestions: list[ExpertSuggestionItem] = Field(default_factory=list)
    expert_messages: Annotated[list, add_messages] = Field(default_factory=list)
    expert_stale: bool = False

    # 错误收集（各节点写入，不互相覆盖）
    errors: list[str] = Field(default_factory=list)
```

---

### State 字段职责说明

| 字段 | 写入方 | 读取方 | 说明 |
|---|---|---|---|
| `script` | `load_script_node` | Brand / Audience / Expert | 每次图执行开始时拉取快照，只读 |
| `brief_text` | `load_script_node` | Brand Agent | Brief 全文，Brand 分析的原始输入 |
| `trigger` | 入口节点 | Router | 决定本次运行进入哪条分支 |
| `brand_insights` | Brand Agent | Expert Agent | 结构化品牌需求，专家依赖此生成方案 |
| `brand_messages` | Brand Agent | Brand Agent（多轮） | 使用 `add_messages` 自动追加，不覆盖 |
| `brand_stale` | 入口节点 / Script 变更节点 | Brand Agent | 为 true 时提示 Brand 重新分析 |
| `audience_analysis` | Audience Agent | Expert Agent | 受众评分，专家依赖此做 trade-off |
| `audience_messages` | Audience Agent | Audience Agent（多轮） | 同上 |
| `audience_stale` | 入口节点 / Persona 变更节点 | Audience Agent | persona 切换 / 脚本变更时置为 true |
| `expert_suggestions` | Expert Agent | 前端 / Apply 节点 | 多方案卡片 |
| `expert_stale` | Brand / Audience 更新后 | Expert Agent | brand_insights 或 audience_analysis 更新后置为 true |

---

### 消息追加机制

`brand_messages` / `audience_messages` / `expert_messages` 使用 LangGraph 的 `add_messages` reducer：

```python
from langgraph.graph import add_messages
from typing import Annotated

brand_messages: Annotated[list, add_messages]
```

`add_messages` 会自动按 message_id 去重并追加，节点每次只需返回新消息，不需要手动管理历史。

---

## 三、Graph 结构与节点设计

### 节点列表

```
entry_node          ← 接收外部触发，设置 trigger，拉取 script 快照
    ↓
router_node         ← 根据 trigger.agent 分发到对应 Agent 节点
    ↓
brand_agent_node    ← 处理品牌 Agent 的分析和对话
audience_agent_node ← 处理观众 Agent 的分析和对话
expert_agent_node   ← 处理专家 Agent 的方案生成
    ↓
persist_node        ← 将 State 中的输出写入数据库
    ↓
stale_update_node   ← 根据本次哪个 Agent 输出了新内容，更新其他 Agent 的 stale 标记
    ↓
END
```

### 代码示例

```python
from langgraph.graph import StateGraph, END

def router_node(state: CreatorStudioState):
    """根据 trigger 决定走哪条分支"""
    return state.trigger.agent  # 返回 "brand" | "audience" | "expert"


def brand_agent_node(state: CreatorStudioState) -> dict:
    """品牌方 Agent 节点"""
    messages = build_brand_prompt(
        brief_text=state.brief_text,
        script=state.script,
        history=state.brand_messages,
        trigger=state.trigger
    )
    response = call_llm(messages)  # 调用 LLM，流式或同步

    new_insights = parse_insights(response)      # 解析结构化 insights
    new_message = build_assistant_message(response)

    return {
        "brand_insights": new_insights,
        "brand_messages": [new_message],         # add_messages 自动追加
        "brand_stale": False,
        "expert_stale": True,                    # 通知专家需要重新分析
    }


def audience_agent_node(state: CreatorStudioState) -> dict:
    messages = build_audience_prompt(
        script=state.script,
        persona_id=state.active_persona_id,
        history=state.audience_messages,
        trigger=state.trigger
    )
    response = call_llm(messages)
    analysis = parse_audience_analysis(response)
    new_message = build_assistant_message(response)

    return {
        "audience_analysis": analysis,
        "audience_messages": [new_message],
        "audience_stale": False,
        "expert_stale": True,                    # 通知专家需要重新分析
    }


def expert_agent_node(state: CreatorStudioState) -> dict:
    messages = build_expert_prompt(
        script=state.script,
        brand_insights=state.brand_insights,     # 直接从 State 读取
        audience_analysis=state.audience_analysis,  # 直接从 State 读取
        history=state.expert_messages,
        trigger=state.trigger
    )
    response = call_llm(messages)
    suggestions = parse_suggestions(response)
    new_message = build_assistant_message(response)

    return {
        "expert_suggestions": suggestions,
        "expert_messages": [new_message],
        "expert_stale": False,
    }


# ── 构建图 ──
builder = StateGraph(CreatorStudioState)

builder.add_node("entry", entry_node)
builder.add_node("router", router_node)
builder.add_node("brand_agent", brand_agent_node)
builder.add_node("audience_agent", audience_agent_node)
builder.add_node("expert_agent", expert_agent_node)
builder.add_node("persist", persist_node)
builder.add_node("stale_update", stale_update_node)

builder.set_entry_point("entry")
builder.add_edge("entry", "router")

builder.add_conditional_edges("router", lambda s: s.trigger.agent, {
    "brand": "brand_agent",
    "audience": "audience_agent",
    "expert": "expert_agent",
})

for agent_node in ["brand_agent", "audience_agent", "expert_agent"]:
    builder.add_edge(agent_node, "persist")

builder.add_edge("persist", "stale_update")
builder.add_edge("stale_update", END)

graph = builder.compile()
```

---

## 四、Agent 之间的消息传递方式

这个系统的 Agent 关系是**单向依赖链**，不是对等协商：

```
Brief
  ↓
Brand Agent  →  brand_insights
                    ↓
Audience Agent  →  audience_analysis
                    ↓
              Expert Agent（综合两者生成方案）
```

### 传递方式：通过 State 字段，而非直接调用

**不要**让 Expert Agent 直接调用 Brand Agent 或 Audience Agent 的接口。正确做法是：

- Brand Agent 执行完毕 → 将 `brand_insights` 写入 State
- Audience Agent 执行完毕 → 将 `audience_analysis` 写入 State
- Expert Agent 执行时 → 从 State 中读取 `brand_insights` 和 `audience_analysis`，构建 prompt

这样每个 Agent 节点之间没有耦合，调度顺序由 Router 决定，测试和替换某个 Agent 都互不影响。

### 跨对话轮次的上下文传递

每个 Agent 有独立的 `messages` 历史列表。LLM 调用时，构建 prompt 的方式是：

```python
def build_expert_prompt(script, brand_insights, audience_analysis, history, trigger):
    system_prompt = """你是一位专业的内容创作顾问..."""

    # 1. 把品牌和观众分析结果注入 system 上下文
    context = f"""
## 当前品牌方需求
{format_insights(brand_insights)}

## 当前观众分析
{format_analysis(audience_analysis)}

## 当前脚本
{format_script(script)}
    """

    # 2. 用历史消息做多轮对话
    messages = [
        {"role": "system", "content": system_prompt + context},
        *history,  # 展开历史消息
    ]

    # 3. 追加本轮用户输入（含 quotes）
    if trigger.user_message:
        user_content = trigger.user_message
        if trigger.quotes:
            quoted = "\n".join([f"> {q.text}" for q in trigger.quotes])
            user_content = f"{quoted}\n\n{user_content}"
        messages.append({"role": "user", "content": user_content})

    return messages
```

### 跨 Agent 信号：通过 stale 标记，而非事件

当 Brand Agent 更新了 `brand_insights`，**不需要立刻触发 Expert Agent**。正确的做法是：

```python
# brand_agent_node 返回时，顺手设置
return {
    "brand_insights": new_insights,
    "brand_messages": [new_message],
    "expert_stale": True,   # ← 这就是给 Expert 的"信号"
}
```

前端读取 `expert_stale == True` 后，在专家面板显示「有新输入，点击重新生成」按钮。用户主动触发时，新的一轮图执行才会运行 Expert Agent 节点。这样避免了 Agent 自动串联带来的不可控费用和幻觉叠加。

---

## 五、外部触发示例

### 用户上传 Brief

```python
initial_state = CreatorStudioState(
    project_id="proj_001",
    trigger=TriggerSignal(
        agent="brand",
        reason="brief_uploaded"
    )
)
result = await graph.ainvoke(initial_state)
```

### 用户在观众 Agent 发送消息

```python
state = CreatorStudioState(
    project_id="proj_001",
    trigger=TriggerSignal(
        agent="audience",
        reason="user_message",
        user_message="这段台词观众会觉得太硬广吗？",
        quotes=[QuoteItem(
            text="这款产品真的改变了我的生活",
            row_id="row_005",
            column_id="col_scene",
            script_version_id="v_003"
        )],
        active_persona_id="persona_001"
    )
)
result = await graph.ainvoke(state)
```

### 用户主动触发专家重新生成方案

```python
state = CreatorStudioState(
    project_id="proj_001",
    trigger=TriggerSignal(
        agent="expert",
        reason="user_request_regenerate"
    )
)
result = await graph.ainvoke(state)
```

---

## 六、State 持久化策略

LangGraph 支持内置的 checkpointer，推荐接入 PostgreSQL：

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
graph = builder.compile(checkpointer=checkpointer)

# 每次调用时传入 thread_id（对应 project_id）
config = {"configurable": {"thread_id": "proj_001"}}
result = await graph.ainvoke(state, config=config)
```

这样每次图执行结束后，State 快照会自动持久化到 PostgreSQL，下次执行时可以从上一个 checkpoint 恢复。`thread_id` 直接用 `project_id` 即可，一个项目对应一条 State 历史线。

不需要另外维护一套 State 持久化逻辑；只有 `brand_insights`、`audience_analysis`、`expert_suggestions` 这类需要被前端查询的结构化输出，才需要同时写入业务数据库。