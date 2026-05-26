# BrandVideo 技术方案

> **主依据：** [`docs/pipeline.md`](./pipeline.md)  
> **开发排期：** [`docs/development_plan.md`](./development_plan.md)  
> **数据结构：** [`docs/data_structures.md`](./data_structures.md)  
> **归档参考：** `docs/technical_plan_lightweight.md`

---

## 1. 方案目标

实现 `pipeline.md` 描述的闭环：**Brief → 多 Agent 解析 → IBIS 节点图 → 脚本创作与反馈 → Expert 多方向方案 → 品牌真实反馈 → 协商准备弹窗**，最终交付一组可协商的创作资产（§13），而非单一自动成片。

**MVP 技术边界（与 pipeline 一致）：**

| 能力 | MVP |
|------|-----|
| Coordinator 统一 Chat | ✅ |
| Brand / Audience / Expert 内部 Agent | ✅ |
| Tavily、Brand Wiki（Brand） | ✅（Wiki 可先 stub） |
| Expert 知识库工具接口 | ✅ stub |
| IBIS Node Graph | ✅ |
| Expert 多方向修改方案 + 可选 hunk | ✅ |
| 品牌分享链接 + feedback 列 | ✅ |
| Negotiation Preparation **弹窗** | ✅ |
| 固定 Output Panel（Negotiation/References tab） | ❌ |
| References 生成与展示 | ❌ 二期 |

**核心原则：**

1. 前台仅 Coordinator；三 Agent 不直接暴露聊天面板。  
2. AI 不直接覆盖脚本；方案与 hunk 需创作者确认。  
3. 推理沉淀为 IBIS 节点，而非仅聊天文本。  
4. Agent 间通过 **结构化 State** 传递，上下文按角色隔离。  
5. 轻量栈：MongoDB 嵌入 + Redis 缓存 + SSE；LangGraph 二期可选。

---

## 2. 技术栈

### 2.1 前端

```text
Next.js · React · TypeScript · Zustand · React Flow · SSE client
```

| 模块 | 职责 |
|------|------|
| Script Editor | 表格编辑、时长轴、选区 quote |
| Node Graph | IBIS 可视化、待协商标记、与脚本互跳 |
| Coordinator Chat | 统一提问、视角 chips、流式回复 |
| Persona 面板 | CRUD、切换 active persona |
| 方案 Diff | Expert 方案预览、hunk 接受/拒绝 |
| 协商弹窗 | 按需生成 Negotiation Preparation |
| 品牌分享页 | 只读脚本 + 可编辑 feedback 列 |

### 2.2 后端

```text
FastAPI · MongoDB (Motor) · Redis · SiliconFlow API
```

| 模块 | 职责 |
|------|------|
| Project / Script / Brief API | 持久化与 debounce 同步 |
| CoordinatorService | 按 `task_type` 调度内部 Agent |
| Agent 模块 | Brand / Audience / Expert 结构化输出 |
| GraphService | IBIS 节点边 CRUD |
| ProposalService | 多方向方案与 hunk apply |
| ShareService | 品牌方只读链接与 feedback 回写 |
| NegotiationService | 协商材料生成 |
| Tool 适配层 | Tavily、Brand Wiki、Expert KB |

### 2.3 编排演进

**MVP：** `CoordinatorService` 内顺序调用，语义对齐 `data_structures.md` 推荐节点列表。

**二期：** LangGraph，`thread_id = project_id`；业务数据仍写 MongoDB。

```text
CoordinatorService
  ├─ entry_context_loader     # 按 Agent 角色裁剪上下文（见 §4）
  ├─ task_router
  ├─ brand_agent              # + tavily_tool, brand_wiki_tool → BrandPerspectiveResult + proposed_nodes/edges
  ├─ audience_agent           # 仅 script + persona + platform；不读 brief
  ├─ expert_agent             # + knowledge_base_tool → 方案 / 节点 / 协商材料
  ├─ response_composer        # SSE token；按 requested_perspectives 控制披露
  └─ persist_node             # 合并各 Agent 结构化输出写入 MongoDB
```

**无独立 GraphWriter / SchemeWriter / NegotiationWriter。** IBIS 节点、ModificationScheme、NegotiationPreparation 均由三 Agent（以 Expert 汇总为主）在结构化输出中给出，由 `persist_node` 统一落库。

---

## 3. 流程驱动的系统架构

```text
                    ┌─────────────────┐
                    │  Brief Upload   │
                    └────────┬────────┘
                             ▼
              ┌──────────────────────────────┐
              │     CoordinatorService        │
              │  task_type: brief_initial_parse│
              └──────────────┬───────────────┘
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
   ┌──────────┐      ┌─────────────┐     ┌──────────┐
   │  Brand   │      │  Audience   │     │  Expert  │
   │  Agent   │      │  Agent      │     │  Agent   │
   └────┬─────┘      └──────┬──────┘     └────┬─────┘
        │                   │                  │
        └─────────┬─────────┴────────┬─────────┘
                  ▼                  ▼
         ┌────────────────┐  ┌──────────────┐
         │  Shared State  │  │ Initial IBIS │
         │  (structured)  │  │    Graph     │
         └────────┬───────┘  └──────────────┘
                  │
    ┌─────────────┴─────────────┐
    ▼                           ▼
┌─────────────┐         ┌───────────────┐
│Script Editor│◄───────►│  Node Graph   │
└──────┬──────┘         └───────┬───────┘
       │                        │
       │  quote / script_delta  │
       ▼                        ▼
┌─────────────────────────────────────────┐
│         Coordinator Chat (SSE)           │
└────────────────────┬────────────────────┘
                     ▼
            ┌─────────────────┐
            │ Expert Schemes   │
            │ (+ hunk apply)   │
            └────────┬─────────┘
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
┌──────────────┐          ┌───────────────────┐
│ Share Link   │          │ Negotiation Modal  │
│ (feedback)   │          │ (on-demand generate)│
└──────────────┘          └───────────────────┘
```

---

## 4. Shared State 与上下文隔离

### 4.1 CoordinatorState（逻辑模型）

与 `data_structures.md` §二对齐；MVP 映射到 `projects` 嵌入字段 + `coordinator_messages`。

| 字段 | 写入方 | 主要读取方 |
|------|--------|------------|
| `brief_*` | Brand / entry | **Brand**、Expert、Coordinator |
| `active_persona` | Persona 数据分析 / 用户编辑 | **Audience**、Expert、Coordinator |
| `brand_perspective_result` | Brand Agent | Expert、Coordinator |
| `audience_perspective_result` | Audience Agent | Expert、Coordinator |
| `expert_perspective_result` | Expert Agent | Coordinator |
| `rationale_nodes` / `rationale_edges` | 三 Agent（`proposed_*`）+ 用户 | 前端 Graph；Expert 读子图摘要 |
| `modification_schemes` | Expert Agent | 前端 Diff、Coordinator |
| `negotiation_preparation` | Expert Agent（`generate_negotiation`） | 协商弹窗、Coordinator |
| `negotiation_queue` | 用户 | Expert（生成协商材料时） |
| `brand_feedback_rows` | Share sync + Brand Agent | Brand、Expert、Coordinator |

### 4.2 上下文隔离矩阵（Brand ⊥ Audience）

**原则：** Brand 与 Audience **互不读取**对方的 Persona / Requirements；Expert 读取双方**结构化输出**；Coordinator **可读全部持久化 artifact**，但按 `requested_perspectives` 控制**对用户披露**（读权限 ≠ 回答内容）。

| 读者 | 可读 | 禁止（跨视角污染） |
|------|------|-------------------|
| **Brand** | `brief`、Tavily、Brand Wiki、品牌 feedback 行、相关脚本片段 | `Persona` 全文、`AudiencePerspectiveResult`、`*_persona` / `audience_simulation` 节点 |
| **Audience** | `active_persona`、`platform_context`、脚本片段 / quote | **`brief` 任意字段**、`BrandPerspectiveResult`、`*_brief` / `brand_inferred` / `brand_feedback` 节点 |
| **Expert** | 脚本、IBIS **子图摘要**、§13.1 + §13.2 结构化结果、知识库 | Brand / Audience **聊天原文**、Coordinator 长历史 |
| **Coordinator** | 上述全部 artifact + 本轮 `trigger` / quote | 编排层不替代 Agent 推理 |

**共享输入（不算破坏隔离）：** 仅 `platform_context`、脚本正文、用户 quote。  
**不算共享输入：** `brief` 仅 Brand（及 Expert、Coordinator）可读；Persona 仅 Audience（及 Expert、Coordinator）可读。

实现：`build_agent_context(role, project, trigger)` 在代码层白名单过滤；禁止把完整 `project` 对象传入各 Agent prompt。

### 4.3 Persona 数据分析接口（预留）

Persona **不由 Audience Agent 从 Brief 推断**。初始与刷新 Persona 走独立 **数据分析管线**（平台统计、品类受众模型等），与 Brief / Brand 解析解耦。

```python
# backend/app/services/persona_analytics.py（预留）

class PersonaAnalyticsContext(BaseModel):
    project_id: str
    platform_context: Literal["xiaohongshu", "douyin", "bilibili", "other"]
    content_category: str | None = None   # 内容类型，如「美妆测评」
    brand_name: str | None = None
    video_topic: str | None = None
    locale: str = "zh-CN"


class PersonaAnalyticsProvider(Protocol):
    async def generate_personas(self, ctx: PersonaAnalyticsContext) -> list[Persona]:
        ...
```

| 阶段 | 实现 |
|------|------|
| MVP | `StubPersonaAnalyticsProvider`：按 `platform_context` 返回模板 Persona |
| 二期 | 对接真实数据分析服务（HTTP / 内部批任务） |

**HTTP（预留）：**

```http
POST /api/projects/{project_id}/persona/provision-from-analytics
```

请求体（**不含 brief**）：

```json
{
  "platform_context": "xiaohongshu",
  "content_category": "美妆测评",
  "brand_name": "示例品牌",
  "video_topic": "联名开箱"
}
```

响应：

```json
{
  "personas": [],
  "active_persona_id": "persona_001",
  "analytics_meta": {
    "provider": "stub | internal_analytics | ...",
    "model_version": "string",
    "generated_at": "datetime"
  }
}
```

**流程：** 项目创建或平台/品类变更 → `provision-from-analytics` 写入 `project.personas` → 可选触发 `persona_ready` 任务（Audience + Expert 补观众向节点）。Brief 上传 **不** 自动调用 Audience Agent 生成 Persona。

---

## 5. 内部 Agent 与工具

### 5.1 Brand Agent（pipeline §2、§9）

**输入：** `brief.text` / `brief.summary`、可选脚本片段、品牌 feedback 行。  
**输出（结构化）：** 显式需求、隐性需求、约束、evidence、confidence。  
**工具：**

| 工具 | 用途 | MVP |
|------|------|-----|
| `tavily_search` | 检索品牌公开资料 | 复用 `research` 路由 / `tavily_client` |
| `brand_wiki_lookup` | 品牌知识库 | stub → 配置文件或本地 JSON |

### 5.2 Audience Agent（pipeline §6、§8）

**输入：** `active_persona`（来自 §4.3 数据分析或用户编辑）、`platform_context`、脚本片段 / quote。  
**禁止输入：** `brief`、`brief.summary`、`BrandPerspectiveResult`、任何 `brand_*` 图节点。

**输出（`AudiencePerspectiveResult`）：** 自然度/广告感/信任/跳出风险、`structured_issues`、可选 `proposed_nodes` / `proposed_edges`（由 `persist_node` 落库）。  
**不负责：** Persona 字段的初始生成（见 §4.3）。

**触发：** Persona 就绪或变更后；Coordinator `requested_perspectives` 含 `audience`；`script_delta` / `quote_analysis`（仅脚本+persona 上下文）。

### 5.3 Expert Agent（pipeline §2、§10、§11）

**输入：** 脚本片段、IBIS 子图摘要、`brand_perspective_result`、`audience_perspective_result`、知识库检索；`generate_negotiation` 时另读 `negotiation_queue`。  
**禁止输入：** Brand / Audience 聊天原文。

**输出：** `ExpertPerspectiveResult`；**ModificationScheme[]**（多方向）；`generate_negotiation` 时 **NegotiationPreparation**；可选 `proposed_nodes` / `proposed_edges`（合并冲突、补 Position/Argument）。  
**工具：**

| 工具 | 用途 | MVP |
|------|------|-----|
| `domain_case_retriever` | 同领域优质案例 | stub / 静态集 |
| `script_structure_kb` | 脚本结构经验 | stub |

每个方案字段（pipeline §10）：`direction`、`changes_summary`、`target_issue_ids`、`tradeoffs`、`communication_scene`、`brand_objection`、`response_script`、可选 `hunks[]`。

**方向枚举建议：**

```text
conservative | balanced | creator_led | audience_friendly
```

### 5.4 结构化产物归属（无独立 Writer）

| 产物 | 产出 Agent | 落库 |
|------|------------|------|
| IBIS `proposed_nodes` / `proposed_edges` | Brand、Audience、Expert | `persist_node` → `project.rationale_*` |
| `ModificationScheme` | Expert | `persist_node` → `project.modification_schemes` |
| `NegotiationPreparation` | Expert（`task_type=generate_negotiation`） | `persist_node` → `project.negotiation_preparation` |
| `Persona[]` | **PersonaAnalyticsProvider**（§4.3） | 直接写 `project.personas` |

**`source_type`（节点配色）：** `brand_brief | brand_feedback | brand_inferred | audience_persona | audience_simulation | expert_strategy | creator_manual`  
**`node_type`：** `issue | position | argument | reference`

---

## 6. 触发类型与 Coordinator 路由

| `task_type` | 触发场景 | 调用链 |
|-------------|----------|--------|
| `brief_initial_parse` | Brief 上传完成 | Brand → Expert（初始品牌向节点）→ persist → composer |
| `persona_provisioned` | 数据分析返回 Persona | Audience → Expert（观众向节点）→ persist → composer（可选） |
| `user_message` / `quote_analysis` | Coordinator 提问 | router → Brand / Audience / Expert（按 perspectives）→ Expert 综合? → persist → composer |
| `script_delta` | 脚本变更（节流） | Audience 和/或 Expert（按需）→ persist |
| `brand_feedback_sync` | 品牌 feedback 回流 | Brand → Expert → persist → composer |
| `generate_modification_schemes` | 请求修改方案 | Expert → persist → composer |
| `generate_negotiation` | 生成协商弹窗 | Expert → persist → composer（可短流式） |

`requested_perspectives`：`brand | audience | expert | comprehensive`。`comprehensive` = 并行 Brand + Audience → Expert 汇总 → composer。

---

## 7. 数据存储（MongoDB）

### 7.1 Collections（MVP）

```text
users
projects              # 嵌入 brief, script, personas, graph, schemes, stale, negotiation_queue
coordinator_messages
script_snapshots
share_sessions          # 品牌方分享 token → script 视图
```

体积增大后可拆：`rationale_nodes`、`rationale_edges`、`modification_schemes`。

### 7.2 Project 文档（核心字段）

```json
{
  "_id": "project_id",
  "user_id": "custom_user_id",
  "title": "string",
  "platform_context": "xiaohongshu | douyin | bilibili | other",
  "brief": {
    "filename": "string",
    "text": "string",
    "summary": "string",
    "parse_status": "pending | parsing | parsed | failed",
    "uploaded_at": "datetime"
  },
  "current_script": { "columns": [], "rows": [], "updated_at": "datetime" },
  "current_script_version_id": "string",
  "personas": [],
  "active_persona_id": "string",
  "rationale_nodes": [],
  "rationale_edges": [],
  "modification_schemes": [],
  "negotiation_queue": ["issue_node_id"],
  "negotiation_preparation": null,
  "stale": {
    "rationale_graph": "up_to_date | stale_script_changed | ...",
    "modification_schemes": "up_to_date | stale_graph_changed | ...",
    "negotiation_preparation": "up_to_date | stale_*"
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 7.3 Script 列规则

- 默认列：`duration`, `scene`, `format`, `notes`（见 `development_plan.md` §5）。  
- `feedback`（品牌反馈）：默认列存在；创作者侧**只读**；品牌方在 ShareSession **可写**；`brand-feedback/sync` 合并后创作者可见内容。  
- 序号列 `#` 仅前端渲染。

### 7.4 ModificationScheme（Expert 方案）

```json
{
  "scheme_id": "string",
  "title": "string",
  "direction": "conservative | balanced | creator_led | audience_friendly",
  "target_issue_ids": [],
  "changes_summary": "string",
  "tradeoffs": { "brand": "string", "audience": "string", "creator": "string" },
  "communication_scene": "string",
  "brand_objection": "string",
  "response_script": "string",
  "hunks": [
    {
      "hunk_id": "string",
      "row_id": "string",
      "column_id": "string",
      "removed": "string",
      "added": "string"
    }
  ],
  "related_node_ids": [],
  "based_on_script_version_id": "string",
  "status": "draft | previewed | partially_applied | applied | dismissed"
}
```

apply hunk：校验当前 cell == `removed` → 更新 cell → 写 snapshot。

### 7.5 ShareSession（品牌方视图）

```json
{
  "_id": "share_token",
  "project_id": "string",
  "script_snapshot": { "columns": [], "rows": [] },
  "includes_feedback_column": true,
  "expires_at": "datetime",
  "created_at": "datetime"
}
```

品牌方 `PATCH` 仅允许更新 `feedback` 列；创作者 `POST .../brand-feedback/sync` 合并回主项目并触发 `brand_feedback_sync` 任务。

### 7.6 NegotiationPreparation

```json
{
  "prep_id": "string",
  "design_intent": "string",
  "satisfied_brand_needs": ["string"],
  "open_disputes": [
    {
      "issue_node_id": "string",
      "summary": "string",
      "our_position": "string",
      "acceptable_concession": "string",
      "non_negotiable_line": "string",
      "talking_points": ["string"]
    }
  ],
  "recommended_communication_order": ["issue_node_id"],
  "based_on_script_version_id": "string",
  "created_at": "datetime"
}
```

---

## 8. API 设计（按 pipeline 分组）

### 8.1 用户与项目

```http
POST /api/users/enter
GET  /api/projects?user_id=
POST /api/projects
GET  /api/projects/{project_id}
PATCH /api/projects/{project_id}
```

### 8.2 Brief（§1）

```http
POST  /api/projects/{project_id}/brief
PATCH /api/projects/{project_id}/brief
POST  /api/projects/{project_id}/brief/parse    # 触发 brief_initial_parse，返回 task_id 或 SSE
```

### 8.3 Script（§5）

```http
GET   /api/projects/{project_id}/script
PATCH /api/projects/{project_id}/script/cells
POST  /api/projects/{project_id}/script/rows
DELETE /api/projects/{project_id}/script/rows/{row_id}
# columns CRUD 同上
GET   /api/projects/{project_id}/script/snapshots
POST  /api/projects/{project_id}/script/snapshots/{id}/restore
```

脚本 PATCH 成功后异步标记 `stale`；可选触发 `script_delta` 分析（节流）。

### 8.4 Coordinator（§4、§6）

```http
POST /api/projects/{project_id}/coordinator/stream
GET  /api/projects/{project_id}/coordinator/messages
```

请求体：

```json
{
  "message": "string",
  "task_type": "user_message | quote_analysis | ...",
  "requested_perspectives": ["comprehensive"],
  "quotes": [{ "text": "", "row_id": "", "column_id": "" }],
  "target_node_ids": []
}
```

### 8.5 Persona（§8）

```http
POST  /api/projects/{project_id}/persona/provision-from-analytics   # §4.3，不读 brief
GET/PATCH/POST/DELETE /api/projects/{project_id}/personas[/{persona_id}]
PATCH /api/projects/{project_id}/active-persona
```

### 8.6 Graph（§3、§7）

```http
GET/POST/PATCH/DELETE /api/projects/{project_id}/graph/nodes[/{node_id}]
GET/POST/DELETE       /api/projects/{project_id}/graph/edges[/{edge_id}]
PATCH /api/projects/{project_id}/graph/nodes/{node_id}/negotiation-queue  # 加入/移出待协商
```

### 8.7 Modification Schemes（§10）

```http
GET  /api/projects/{project_id}/modification-schemes
POST /api/projects/{project_id}/modification-schemes/generate   # Coordinator → Expert
POST /api/projects/{project_id}/modification-schemes/{id}/apply
```

### 8.8 品牌分享（§9）

```http
POST  /api/projects/{project_id}/share
GET   /api/share/{token}                    # 只读脚本 + feedback 列
PATCH /api/share/{token}/feedback           # 品牌方提交
POST  /api/projects/{project_id}/brand-feedback/sync
```

### 8.9 协商准备（§11）

```http
POST /api/projects/{project_id}/negotiation/generate
GET  /api/projects/{project_id}/negotiation/latest
```

**不做（MVP）：**

```http
# GET/POST .../outputs/references  → 二期
```

---

## 9. SSE 事件协议

```http
POST /api/projects/{project_id}/coordinator/stream
Content-Type: text/event-stream
```

| event | data 说明 |
|-------|-----------|
| `token` | `{"content":"..."}` 流式自然语言 |
| `artifact` | `rationale_nodes`, `modification_schemes`, `personas` 等 |
| `done` | `message_id`, `generated_artifact_ids` |
| `error` | `{"message":"..."}` |

**结构化落库流程：**

```text
LLM stream → 前端展示 token
          → 后端累积 content
          → JSON 解析 + Pydantic 校验
          → 失败则 8B 修复重试
          → 写入 MongoDB
```

Redis keys：

```text
context:{project_id}:{task_type}:{context_hash}
llm_cache:{prompt_hash}
stream:{request_id}
```

---

## 10. LLM 与成本

| 场景 | 模型建议 |
|------|----------|
| Coordinator 对话、composer | Qwen3-8B |
| Brand/Audience/Expert 结构化、协商生成 | Qwen3-32B |
| JSON 修复 | Qwen3-8B |

**上下文策略：**

- Brief：**仅 Brand / Expert**；Audience prompt 中不得出现 brief 字段。  
- Persona：**仅 Audience / Expert**；Brand prompt 中不得出现 `active_persona` 全文。  
- Script：quote 传所在行 ±1 行。  
- Graph：Expert / Coordinator 传子图摘要；Brand 仅 `brand_*` 节点，Audience 仅 `audience_*` 节点。  
- 历史：composer 最近 5–10 轮；Expert 不读完整聊天史。  
- `script_delta`：仅 `changed_row_ids` 对应行。

---

## 11. 前端状态（Zustand）

```ts
type AppState = {
  user: { userId?: string };
  project: Project | null;
  script: Script | null;

  layout: {
    mainView: "script" | "graph";
    coordinatorOpen: boolean;
    personaPanelOpen: boolean;
    negotiationModalOpen: boolean;  // 替代 MVP 固定 outputPanel
  };

  coordinator: {
    messages: CoordinatorMessage[];
    quotes: QuoteRef[];
    requestedPerspectives: Perspective[];
    isStreaming: boolean;
  };

  graph: {
    nodes: RationaleNode[];
    edges: RationaleEdge[];
    negotiationQueue: string[];
  };

  schemes: {
    items: ModificationScheme[];
    diffOverlayOpen: boolean;
    hunkState: Record<string, boolean | null>;
  };

  stale: Record<string, string>;
};
```

---

## 12. Stale 规则

| 事件 | 影响 |
|------|------|
| script cell 变更 | `rationale_graph`, `modification_schemes`, `negotiation_preparation` |
| brief 更新/重解析 | graph, schemes, negotiation |
| persona 变更 | graph, schemes |
| graph 用户编辑 | schemes, negotiation |
| 新 artifact 写入且 version 匹配 | 对应项 → `up_to_date` |

---

## 13. 安全与分享

1. `share_token` 随机、可过期；不暴露 `project_id` 给其他用户接口。  
2. 分享页 API 无 Graph、Chat、Persona、Brief 端点。  
3. 品牌方写权限仅限 `feedback` 列。  
4. 创作者需显式 `sync` 才把 feedback 并入主项目并触发 Agent。

---

## 14. 实现阶段映射

| 开发 Phase | 技术交付 |
|------------|----------|
| P0 | 布局、Project/Script API、Coordinator mock |
| P1 | Script CRUD、debounce、stale、snapshots 壳 |
| P2 | Brief parse（Brand+Expert）、PersonaAnalytics stub、Tavily |
| P3 | coordinator/stream、messages、Audience（无 brief） |
| P4 | Graph API + React Flow、negotiation_queue |
| P5 | ModificationScheme + hunk apply |
| P6 | ShareSession + feedback sync |
| P7 | Negotiation generate + Modal |
| P8 | E2E、stale badge、可选 LangGraph |

---

## 15. 与旧方案差异摘要

| 项 | technical_plan_lightweight | 本方案（pipeline 对齐） |
|----|---------------------------|-------------------------|
| 流程依据 | prd_new 为主 | **pipeline.md 13 步** |
| 输出 UI | Output Panel 双 tab | **协商弹窗**；References 二期 |
| 品牌反馈 | 较弱 | **分享链接 + feedback 列** |
| Expert 产出 | RevisionProposal / hunk 为主 | **多方向 ModificationScheme** + 可选 hunk |
| Brand 工具 | 泛化 research | **Tavily + Brand Wiki** 明示 |
| Expert 工具 | 未强调 | **知识库接口 stub** |
| 待协商 | needs_negotiation 状态 | + **`negotiation_queue` 列表** |

---

## 16. 上下文隔离：可能的问题与应对

### 16.1 设计收益

1. **Audience 可信**：评脚本时不被品牌 KPI / 隐性需求锚定，广告感与信任度更接近「真实观众」。  
2. **Brand 不偏观众**：品牌分析不会迎合 Persona 的 `reject_trigger` 等推断字段。  
3. **冲突留在 Expert**：要求在 Expert 汇合后才产生多方向 `ModificationScheme`，符合协商型工作流。  
4. **Coordinator 可讲清权衡**：合成层掌握全貌，便于向创作者解释；披露仍可按视角过滤。

### 16.2 风险与应对

| 风险 | 说明 | 应对 |
|------|------|------|
| Persona 与 Brief 目标人群不一致 | 数据分析给出的人群与 Brief 中「面向 Z 世代」等表述可能不同 | **允许分歧**；Expert 在方案中显式标注；不在 Audience 侧读 Brief 消歧 |
| Persona 数据分析未就绪 | 无 `active_persona` 时 Audience 无法工作 | UI 提示先执行 `provision-from-analytics`；Brief 解析不阻塞 Persona 流程 |
| IBIS 图成为泄漏通道 | 全图含 `brand_inferred` 节点 | `build_agent_context` 按 `source_type` 过滤；Expert / Coordinator 可读全图 |
| Expert 过早「和稀泥」 | 同时读品牌与观众结构化结果易输出单一折中 | 强制多 `direction` + 必填 `tradeoffs`；控制 token（摘要字段，非整包 JSON） |
| Coordinator 全读但过度披露 | 用户只选 `audience` 却看到品牌隐性需求 | **读权限与披露分离**：`compose_reply(visible_perspectives=...)` |
| 只跑单 Agent 信息不全 | 「品牌和观众谁更不满」需综合判断 | `task_router`：`comprehensive` → Brand ∥ Audience → Expert |
| 品牌 feedback 误当观众声 | feedback 列是品牌原话 | Audience **不读** feedback；仅 Brand 解析，Expert 综合 |
| Persona 变更后 Brand 结果过期 | Brand 不读 Persona，但 Expert 依赖旧观众结论 | `stale_persona_changed`；用户再次请求观众/综合视角时重跑 Audience |
| 无 Writer 导致节点格式不一 | 三 Agent 均可能输出 `proposed_nodes` | 统一 Pydantic schema + `persist_node` 校验；Expert 负责合并冲突边 |

### 16.3 共享输入边界（再强调）

| 数据 | Brand | Audience | Expert | Coordinator |
|------|:-----:|:--------:|:------:|:-----------:|
| `brief` / `brief.summary` | ✅ | ❌ | ✅ | ✅ |
| `active_persona` | ❌ | ✅ | ✅ | ✅ |
| `platform_context` | ✅ | ✅ | ✅ | ✅ |
| `current_script` / quote | ✅ | ✅ | ✅ | ✅ |
| `BrandPerspectiveResult` | — | ❌ | ✅ | ✅ |
| `AudiencePerspectiveResult` | ❌ | — | ✅ | ✅ |

---

## 17. 相关文档

- [`docs/pipeline.md`](./pipeline.md)
- [`docs/development_plan.md`](./development_plan.md)
- [`docs/data_structures.md`](./data_structures.md)
- [`docs/prd_new.md`](./prd_new.md)
