# Phase 4 观众 Agent + Persona 设计

> **状态：** 需求已锁定，待实现（本文档负责设计，不直接改代码）。
> **关联：** `docs/prd.md` §7、§15.4；`docs/development_plan_P0.md` Phase 4；`docs/technical_plan_lightweight.md` §4.5、§4.6、§5、§8.2。

---

## 1. 需求摘要

| # | 需求 | MVP 裁决 |
|---|------|----------|
| 1 | Persona CRUD（增删改）+ 当前 persona 切换 | 是 |
| 2 | Persona 字段保留 PRD §7.2 全部基础字段，`age_range` 自由文本 | 是 |
| 3 | 观众 Agent 流式回复，结构化输出 `audience_analysis`（32B） | 是 |
| 4 | 每次回复显式标明当前 persona（chat & 结构化结果） | 是 |
| 5 | persona 编辑 / 切换后将 `stale.audience` 与 `stale.expert` 置为 true | 是 |
| 6 | 多 persona 历史对比、历史分析列表 | 否（暂缓） |

---

## 2. UI

### 2.1 Persona Bar（观众 Agent panel 顶部）

- 复用现有 `persona-bar` 容器：
  - `chip` 按 `personas[]` 渲染，当前 `active_persona_id` 显示 `active` 状态。
  - 末尾保留「+」chip，弹出新建 modal。
  - 每个 chip 长按 / 编辑按钮触发编辑 modal（MVP 选用「悬停显示编辑钩子」简化体验）。
- 顶部右侧增加「同步分析」按钮：触发当前 persona 在最新脚本下的 audience_analysis 生成（实际通过对话面板 `发送` 实现，按钮不是必需，验收以发送框为准）。

### 2.2 Persona Modal

- `create | edit` 两种模式共用一个 modal。
- 字段（与 PRD §7.2/§7.3 对齐）：
  - 必填：name
  - 选填：icon（emoji 单字符或字符串）、gender、age_range（自由文本）、preferences、behavior、platform_context
  - `ad_sensitivity` 单选：low / medium / high（默认 medium）
  - `trust_trigger` / `reject_trigger`：逗号分隔输入框，存为字符串数组
- 操作：保存（POST/PATCH）、取消、删除（仅 edit 模式）。

### 2.3 Audience Analysis Card

- 位于观众 Agent panel 中、对话区之上的折叠卡片：
  - 顶部一行：「分析摘要 · 基于 persona = {name}」+ `更新于` 时间戳。
  - 三个分数 chip：自然度 / 可信度 / 广告感（1-5）。
  - 折叠区：风险列表、liked_parts、rejected_parts、suggestions。
- 当 `audience_analysis` 为空时显示占位「与观众 Agent 对话以生成结构化分析」。
- 当 `stale.audience = true` 时卡片右上角显示「分析可能过期」徽标。

---

## 3. 后端数据模型

### 3.1 `project.personas[]`

```jsonc
{
  "persona_id": "persona_xxxxxxxxxxxx",
  "name": "年轻职场人",
  "icon": "👩‍💼",
  "gender": "女",
  "age_range": "25-32 岁",
  "preferences": "通勤效率、健康饮食、轻量护肤",
  "behavior": "刷小红书、看 B 站测评、抖音晚上 22-24 点活跃",
  "platform_context": "小红书 / 抖音",
  "ad_sensitivity": "medium",
  "trust_trigger": ["真实日常场景", "明确缺点说明"],
  "reject_trigger": ["夸张转折", "硬广独白"],
  "data_source": "manual",
  "created_at": "2026-05-19T...",
  "updated_at": "2026-05-19T..."
}
```

### 3.2 `project.active_persona_id`

string | null。删除当前 persona 时若集合非空回退到首个 persona；为空则置 null。

### 3.3 `project.audience_analysis`

轻量版只保留**当前 persona 的最近一次**分析，不存历史列表。

```jsonc
{
  "analysis_id": "analysis_xxxxxxxxxxxx",
  "persona_id": "persona_xxxxxxxxxxxx",
  "persona_name": "年轻职场人",
  "based_on_script_updated_at": "2026-05-19T...",
  "summary": "整体可信度可接受，但中段广告感偏强。",
  "naturalness_score": 3,
  "credibility_score": 4,
  "ad_sensitivity_score": 4,
  "key_risks": ["品牌口播过早", "缺乏真实使用细节"],
  "liked_parts": [
    {"row_id": "row_xxx", "reason": "通勤场景具体可信"}
  ],
  "rejected_parts": [
    {"row_id": "row_yyy", "reason": "转折生硬，像硬广"}
  ],
  "suggestions": ["把第 3 段的形容词替换为账单 / 时长等具体数字。"],
  "updated_at": "2026-05-19T..."
}
```

### 3.4 `project.stale.audience`

- 脚本变更：`stale.audience = true`（已在 `_write_script` 中处理）。
- 新建 / 编辑 / 删除 persona：`stale.audience = true`，`stale.expert = true`。
- 切换 `active_persona_id`：`stale.audience = true`，`stale.expert = true`（旧分析基于旧 persona）。
- 观众 Agent 产出新 `audience_analysis`：`stale.audience = false`，`stale.expert = true`。

---

## 4. API

| 方法 / 路径 | 用途 |
|-------------|------|
| `POST   /api/projects/{project_id}/personas` | 新建 persona |
| `PATCH  /api/projects/{project_id}/personas/{persona_id}` | 编辑 persona |
| `DELETE /api/projects/{project_id}/personas/{persona_id}` | 删除 persona |
| `PATCH  /api/projects/{project_id}/active-persona` | 切换当前 persona |

请求体均带 `user_id`，与现有项目接口一致。返回 `ProjectResponse`。

观众 Agent 复用既有：

```
POST /api/projects/{project_id}/agents/audience/stream
GET  /api/projects/{project_id}/agents/audience/messages
```

---

## 5. Audience Agent 上下文（system prompt）

固定上下文：
1. `active_persona`（结构化展开）
2. `script_summary`（脚本摘要 + row_id）
3. `audience_analysis_existing`（若已有，作为对比基线，避免重复打分）
4. `recent_messages`（最近 5-10 轮观众对话）
5. `quotes`（用户引用的脚本片段）

prompt 要求：
- 回答首段必须出现「以 {persona_name} 视角」或类似前缀，便于 PRD §15.4 第 5 条验收。
- 给评分时基于 1-5 整数。
- 结构化分析作为 artifact 块输出（见 §6）。

---

## 6. 结构化输出协议：`<audience_analysis>` artifact

在自然语言回答最后追加（可省略，若本次无需更新结构化分析）：

```
<audience_analysis>
{
  "summary":"...",
  "naturalness_score":3,
  "credibility_score":4,
  "ad_sensitivity_score":4,
  "key_risks":["..."],
  "liked_parts":[{"row_id":"row_xxx","reason":"..."}],
  "rejected_parts":[{"row_id":"row_yyy","reason":"..."}],
  "suggestions":["..."]
}
</audience_analysis>
```

约束（与 brand_insight_proposals 协议风格一致）：
- 仅在确实产出结构化分析时输出；闲聊轮次可省略。
- JSON 严格合法，禁止注释 / 多余字段 / Markdown 围栏。
- `row_id` 必须来自当前脚本摘要中出现过的 row_id。
- 评分必须 1-5 整数；不可推断时省略字段，避免输出 0 / null。
- artifact 块必须放在回答末尾；前端流式时不展示该块原文。

后端 `agent_stream`：
- 流式阶段：检测 `<audience_analysis` 标记开始 → 屏蔽块体不下发到前端（同 brand 做法）。
- 流结束后：解析 JSON → 校验 row_id 与评分 → 写入 `project.audience_analysis` → SSE 发 `event: artifact { type: "audience_analysis", analysis, persona_id, persona_name }`。
- 解析失败时不写库、不报错，仅在 `done` 事件附 `analysis_persisted: false`。

---

## 7. Stale 联动

| 触发 | stale.audience | stale.expert |
|------|----------------|--------------|
| 脚本写入（已有） | true | true |
| 新建 persona | true | true |
| 编辑 persona | true | true |
| 删除 persona | true | true |
| 切换 active persona | true | true |
| Audience Agent 产出新分析 | **false** | true |
| Brand Agent 产出新 insight（已有） | — | true |

注：删除当前 active persona 时若回退到其他 persona，仍按「切换」处理。

---

## 8. 与 Phase 3 / 5 的衔接

- Brand Agent / brand_insights 与本期无直接交互，但 Expert Agent (Phase 5) 将同时读取 `brand_insights` 与 `audience_analysis`。本期需保证 audience_analysis 写入即可。
- Phase 5 不需要 audience history，因此 `audience_analysis` 只保留单条最新结果。

---

## 9. 验收（对应 PRD §15.4）

1. Persona 列表显示来自 `project.personas`，且新建 / 编辑 / 删除 / 切换都能持久化。
2. 观众 Agent 回复首段明确标识当前 persona 名称。
3. 流式结束后，audience analysis 卡片显示结构化分数与建议。
4. 切换或编辑 persona 后，audience analysis 卡片显示「分析可能过期」徽标（`stale.audience=true`）。
5. 删除 persona：UI 提供二次确认；删除当前 persona 自动切换或置空。
6. PRD §15.4 第 6 条「评价自然度 / 可信度 / 广告感 / 跳出风险」由结构化分析覆盖。

---

## 10. 风险与降级

| 风险 | 规避 |
|------|------|
| LLM 不遵循 artifact 协议 | 与 brand_insight_proposals 共享容错解析；解析失败保留对话文本 |
| row_id 编造 | 解析时丢弃未出现在当前脚本中的 row_id |
| 没有 persona 也想分析 | 提示用户至少创建一个 persona；后端拒绝调用 audience stream（返回 error event） |
| 多 persona 并发分析 | MVP 只保留最近一次，多 persona 对比留二期 |

---

## 11. 文档变更清单

| 文档 | 变更 |
|------|------|
| `docs/development_plan_P0.md` | Phase 4 任务与验收（已存在条目，将打 ✓） |
| `docs/prd.md` | 无需修改（已对齐） |
| `docs/technical_plan_lightweight.md` | 无需修改（已含 §4.5 / §4.6 / §8.2） |
| `docs/superpowers/plans/2026-05-19-phase-4-audience.md` | 配套实施 plan |
| 本文档 | 权威设计说明 |
