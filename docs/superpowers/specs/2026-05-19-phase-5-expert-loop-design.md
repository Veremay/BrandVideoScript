# Phase 5 专家方案闭环设计

> **状态：** 需求已锁定，待实现（本文档负责设计，不直接改代码）。
> **关联：** `docs/prd.md` §8、§15.5；`docs/development_plan_P0.md` Phase 5；`docs/technical_plan_lightweight.md` §4.7、§5、§8.3、§9.5、§9.8。

---

## 1. 需求摘要

| # | 需求 | MVP 裁决 |
|---|------|----------|
| 1 | Expert Agent 生成多方案（含 cell-level `hunks`），32B 模型 + 结构化输出 | 是 |
| 2 | 方案卡片可展开查看理由、trade-off、风险、面对品牌质疑的解释 | 是 |
| 3 | Diff overlay：逐 hunk 查看 old → new，逐段接受/拒绝/全部接受 | 是 |
| 4 | apply 前校验 `cell.value == hunk.old`，不一致提示重新生成 | 是 |
| 5 | apply 前后写 `script_snapshots`；提供 snapshot 列表与 restore API | 是 |
| 6 | Topbar「预览修改稿」打开当前 active suggestion 的 diff overlay | 是 |
| 7 | apply 完成后 `current_script` 更新、`stale.expert=false`、suggestion.status 同步 | 是 |
| 8 | 全文 diff（逐字符高亮），方案历史列表，多人协作 | 否（暂缓） |

---

## 2. UI

### 2.1 专家 Agent panel

```
┌─ 专家 Agent ─────────────────────────────────┐
│ Header（badge：已同步 / 有新输入 / 生成中）│
│ ─────────────────────────────────────────│
│ [方案卡片 1]  ⭐推荐                        │
│   方向 chip · 标题                          │
│   一行 description                          │
│   [预览修改] [展开详情]                     │
│ [方案卡片 2]                                │
│ ...                                         │
│ ─────────────────────────────────────────│
│ 对话区（共享 AgentChat 组件）              │
│ Quote tag + Input + 发送                    │
└──────────────────────────────────────────┘
```

- `project.expert_suggestions` 数组按 `created_at` 倒序渲染为卡片。
- 顶部 badge：
  - `stale.expert = true` → 「有新输入」橙色徽标。
  - 流式中 → 「生成中…」。
  - `expert_suggestions` 为空且非 stale → 「等待生成」。
- 方案卡片状态：
  - `draft`：可点「预览修改」/「展开详情」。
  - `applied` / `partially_applied`：显示已写入 N/总 N hunk，badge 灰色。
  - `dismissed`：折叠在「已忽略」抽屉里（MVP 简化：直接在卡片角落显示「已忽略」）。

### 2.2 方案卡片展开详情

展开内容（垂直顺序）：
1. `direction` chip（brand_first / audience_natural / balanced / creator_expression / custom）。
2. `target_problem`（小标题：解决的问题）。
3. `rationale`（推理理由）。
4. trade-offs 三列（品牌 / 观众 / 创作者）。
5. `risk` + `explanation_to_brand`（折叠区，标题：「面对品牌的解释话术」）。
6. Hunks 概览：每个 hunk 显示 `row_id · column_label` + 缩略 diff（删除红、新增绿）。

### 2.3 Diff Overlay

- 全屏 modal 覆盖编辑器，左上角项目标题 + 「预览修改稿」+ 当前 suggestion 标题。
- 顶部操作栏：
  - 「全部应用」「全部不应用」按钮（一键设置 `hunkState`）。
  - 「重置」清空 `hunkState`。
  - 右上「写入编辑器」：调用 apply API，仅 accepted=true 的 hunk 进入 `accepted_hunk_ids`。
  - 关闭 (`×`) 仅关闭 overlay，不调用 apply。
- 主体：按 hunk 顺序列出，每一项展示：
  - 头部：`#01 row_xx / 画面` + 状态 chip（应用 / 不应用 / 未决定）。
  - 上下文行 `context`（若有）。
  - 双面板 diff：左 `old`、右 `new`，整体红/绿底色。
  - 操作按钮：`✓ 应用`、`✗ 不应用`，再次点击切换为 `未决定`。
  - `Why`（hunk.reason）小字说明。
- apply 后：
  - 校验失败的 hunk 在响应中标记并提示「脚本已变化，建议重新生成方案」。
  - 校验成功的 hunk 写入 cell，`current_script.updated_at` 刷新。
  - 自动关闭 overlay，刷新 project 和脚本，`hunkState` 清空。

### 2.4 Topbar「预览修改稿」

- 已有按钮：替换为可点击。逻辑：
  - 若存在 `status=draft` 的最新 suggestion，则点击打开该 suggestion 的 diff overlay。
  - 否则展示 toast「暂无可预览的专家方案」。

### 2.5 Snapshot 历史

- Topbar 旁新增「版本」入口：弹出 drawer。
- drawer 列出最近 20 条 `script_snapshots`（reason、时间、`applied_hunk_count` 元数据）。
- 每条提供「回退到此版本」按钮，调用 restore API，restore 操作本身也会先写一份当前 `current_script` 作为 `manual_save` snapshot。

---

## 3. 后端数据模型

### 3.1 `project.expert_suggestions[]`

轻量化（与 `technical_plan_lightweight.md` §4.7 一致），增加少量 PRD §8.3 字段供卡片展开。

```jsonc
{
  "suggestion_id": "suggestion_xxxxxxxxxxxx",
  "title": "强化真实感",
  "direction": "balanced",                       // PRD §8.3 五选一 + custom
  "description": "把抽象表达替换为账单 / 路况 / 缺点等具体细节。",
  "target_problem": "中段广告感偏强，导致观众跳出风险升高。",
  "rationale": "结合 audience_analysis 指出的 ad_sensitivity_score=4 与 brand 显式需求「卖点要可感知」。",
  "brand_tradeoff": "品牌口播位置不变，但表达更具体，可能减弱「品牌优先」氛围。",
  "audience_tradeoff": "提升真实感与可信度，但需要博主补充实际细节。",
  "creator_tradeoff": "需要博主补充真实使用故事，写作成本增加。",
  "risk": "若细节不真实易被识别为编造。",
  "explanation_to_brand": "我们将卖点拆解为具体生活细节，更易被目标用户接受……",
  "hunks": [
    {
      "hunk_id": "hunk_xxxxxxxxxxxx",
      "row_id": "row_xxx",
      "column_id": "col_scene",
      "old": "我每天都要喝这个",
      "new": "上班通勤路上一杯，开会前一杯，一天大约两杯。",
      "reason": "用具体次数和场景替换泛指。"
    }
  ],
  "based_on_brand_insight_ids": ["insight_xxx"],
  "based_on_audience_analysis_id": "analysis_xxx",
  "status": "draft",                              // draft | applied | partially_applied | dismissed
  "created_at": "2026-05-19T...",
  "updated_at": "2026-05-19T..."
}
```

说明：
- `direction` 允许的取值：`brand_first | audience_natural | balanced | creator_expression | custom`。
- `target_problem` / `rationale` / `brand_tradeoff` / `audience_tradeoff` / `creator_tradeoff` / `risk` / `explanation_to_brand` 全部为 string；缺失时存空串而非 null。
- `hunks` 中 `old` / `new` 都是 cell 全量字符串（覆盖式替换），便于 apply 时直接赋值。
- `based_on_brand_insight_ids` / `based_on_audience_analysis_id` 由后端在 `save_expert_suggestions` 时回填，方便后续 stale 判断。

### 3.2 `script_snapshots` collection（新增）

每条记录一份完整 `current_script` 快照。

```jsonc
{
  "_id": "snapshot_xxxxxxxxxxxx",
  "project_id": "project_xxx",
  "user_id": "u1",
  "reason": "before_expert_apply",                // manual_save | before_expert_apply | after_expert_apply | before_restore | import
  "suggestion_id": "suggestion_xxx",              // 可选，apply 时回填
  "applied_hunk_ids": ["hunk_xxx"],               // 仅 after_expert_apply 时填写
  "script": { "columns": [...], "rows": [...], "updated_at": "..." },
  "created_at": "2026-05-19T..."
}
```

`script_snapshots` 走独立 collection，避免 `projects` 文档膨胀。

### 3.3 `project.stale.expert` 与触发链

| 触发 | stale.expert |
|------|--------------|
| 脚本写入（已有） | true |
| Brand Agent 产出新 insight（已有） | true |
| Audience Agent 产出新分析（已有） | true |
| persona 编辑 / 切换 / 删除（已有 §4） | true |
| Brief 上传重新触发 brand pipeline（已有） | true |
| **Expert Agent 产出新 suggestions** | **false** |
| **Expert apply 完成** | **false** |
| Snapshot restore | true（恢复后脚本回到旧版，所有结构化结果都可能过期，遵循脚本写入规则） |

---

## 4. Expert Agent 上下文（system prompt）

固定上下文：
1. `brand_entity`（与 brand agent 共用）。
2. `brand_insights`（与 brand agent 共用 formatter，按显式/隐式/反馈分组）。
3. `audience_analysis_detail`：persona 名称、`based_on_script_updated_at`、`summary`、三项评分、`key_risks`、`liked_parts`/`rejected_parts`、`suggestions`，以及 persona 关键画像（avoid 重复展开 persona 全字段，只取 `ad_sensitivity` + 触点）。
4. `script_cells`：**带 row/column 锚点的逐 cell 文本**，模型基于此输出 hunk。格式：
   ```
   row_001 / col_duration「时长」: 0-5
   row_001 / col_scene「画面」: 镜头扫过厨房
   row_001 / col_format「形式」: 口播
   ```
   - 每行最多 240 字符，截断时尾部加 `…`，并将原始值在 cells 字典里给 parser 使用。
   - 多行 cell（textarea）以 `\n  ` 缩进续接。
5. `quotes`：用户引用片段（与现有 `format_quotes` 一致）。
6. `recent_messages`：最近 8 轮 expert chat 消息。

prompt 强制约束：
- 输出 1-3 个方案，覆盖至少两个不同 `direction`。
- 每个方案 hunks 数量 1-6。
- hunk 必须只覆写**业务列**且不能改 `col_duration`（duration 列由用户手工维护；如有时长建议放在自然语言里）。
- `old` 字段必须与当前 cell 完全一致；不能裁剪、扩展或换行差异。
- 输出格式见 §5。

---

## 5. 结构化输出协议：`<expert_suggestions>` artifact

```
<expert_suggestions>
{
  "items": [
    {
      "title": "...",
      "direction": "balanced",
      "description": "...",
      "target_problem": "...",
      "rationale": "...",
      "brand_tradeoff": "...",
      "audience_tradeoff": "...",
      "creator_tradeoff": "...",
      "risk": "...",
      "explanation_to_brand": "...",
      "hunks": [
        {
          "row_id": "row_xxx",
          "column_id": "col_scene",
          "old": "...",
          "new": "...",
          "reason": "..."
        }
      ]
    }
  ]
}
</expert_suggestions>
```

约束：
- 与现有 `<brand_insight_proposals>` / `<audience_analysis>` 协议风格保持一致。
- JSON 严格合法，禁止注释 / 多余字段 / Markdown 围栏。
- 仅在确实生成新方案时输出（追问澄清时不输出）。
- `row_id` / `column_id` 必须来自上下文中真实出现的 cell，否则后端解析时整条 hunk 被丢弃。
- `direction` 必须在允许枚举内（不允许时回退为 `custom`）。
- 最多 3 条 item，每个 item 最多 6 个 hunk；每个字段截断长度由后端 parser 强制。
- 整个 JSON 块必须位于回答末尾；流式时前端不展示该块原文。

### 5.1 容错策略

- 拼写容错：允许 `<expert_suggestion>` / `<expert_suggestions>` / `<expert_suggestion_proposals>` 大小写、单复数变体，与 brand parser 同款正则放宽方案。
- 缺失闭合标签：从 open marker 到字符串末尾视为 body。
- ` ```json` Markdown 围栏：与 brand parser 一致用 fence 抽取。
- 字段缺失/类型错误：单条 hunk 跳过；整个 item 缺关键字段（如无任何有效 hunk）则整体丢弃。
- 解析失败：不写库，`done` 事件附 `suggestions_persisted_count: 0`，前端保留自然语言回复。

---

## 6. apply 与 snapshot 流程

### 6.1 apply API

```
POST /api/projects/{project_id}/expert-suggestions/{suggestion_id}/apply
{
  "user_id": "u1",
  "accepted_hunk_ids": ["hunk_001", "hunk_002"],
  "rejected_hunk_ids": ["hunk_003"]
}
```

服务端流程：

```text
1. 加载 project；定位 suggestion；筛 accepted 列表中真实存在的 hunk。
2. 校验 hunk.old == 当前 cell 值；
   - 不一致 → 标记 conflict，跳过该 hunk。
3. 若全部 conflict：返回 409 { skipped:[...], applied:[] }，不写 current_script，不生成 snapshot。
4. 否则：
   a. 写 before_snapshot（reason=before_expert_apply，附带 suggestion_id）。
   b. 依次 update_cell（行/列定位，复用 script_ops.update_cell）。
   c. 写 after_snapshot（reason=after_expert_apply，附带 applied_hunk_ids）。
   d. 更新 suggestion.status：
      - 全部 accepted hunk 都成功 → applied。
      - 部分成功（含 conflict 或 rejected） → partially_applied。
   e. 更新 suggestion.updated_at。
   f. 标记 stale.expert=false，update current_script 已通过 update_cell 走 _write_script，但 _write_script 会把 stale.* 全部置 true（含 expert）。
     - **要点：** apply 流程要绕开 _write_script，直接用专用 `_apply_script` helper，避免把 stale.expert 重置为 true。
5. 返回：
   {
     project: ProjectResponse,
     applied_hunk_ids: [...],
     skipped_hunk_ids: [...],
     conflict_hunk_ids: [...],
     before_snapshot_id: "snapshot_x",
     after_snapshot_id: "snapshot_y"
   }
```

冲突响应建议：
- HTTP 200 + `applied_hunk_count = 0` 也能让前端读取 conflict 列表 → 用 200 + payload `applied_hunk_count` 区分，避免前端额外处理 409。

### 6.2 snapshot API

```
GET  /api/projects/{project_id}/script/snapshots?user_id=...           → { snapshots: [...] }
POST /api/projects/{project_id}/script/snapshots                       → 手动 manual_save
POST /api/projects/{project_id}/script/snapshots/{snapshot_id}/restore → 写 before_restore snapshot → 覆盖 current_script → 返回 Project
```

`restore` 流程：

```text
1. 加载 project；加载 snapshot（必须同 project_id + user_id）。
2. 写 before_restore snapshot：reason=before_restore，记录原 current_script。
3. _write_script(project, snapshot.script) → stale.brand/audience/expert 全 true。
4. 返回 Project。
```

### 6.3 stale 与触发链总结

| 触发 | 影响 |
|------|------|
| Expert apply 成功 | stale.expert=false；不动 stale.brand / stale.audience |
| Expert apply 全冲突 | 不写 snapshot，不动 stale |
| Snapshot manual_save | 不动 stale |
| Snapshot restore | stale.brand/audience/expert = true（通过 _write_script 已实现） |
| 用户编辑脚本 | 已有 stale 全部 true 行为 |

---

## 7. SSE 事件扩展

```text
event: token
data: {"content": "..."}

event: artifact
data: {
  "type": "expert_suggestions",
  "items": [ ... 已校验、与持久化一致的方案 ... ],
  "persisted_count": 2,
  "trace_run_id": "run_xxx"
}

event: done
data: { "message_id": "msg_xxx", "suggestions_persisted_count": 2 }

event: error
data: { "message": "..." }
```

前端在收到 `suggestions_persisted_count > 0` 时 `fetchProject` 刷新；同时刷新 `agent_messages`。

---

## 8. API 草案

| 方法 / 路径 | 用途 |
|-------------|------|
| `POST   /api/projects/{id}/expert-suggestions/{sid}/apply` | 应用 hunk（见 §6.1） |
| `PATCH  /api/projects/{id}/expert-suggestions/{sid}` | 仅修改 `status`（用户手动 dismiss / 重置 draft） |
| `GET    /api/projects/{id}/script/snapshots` | 列出最近快照（最多 20 条） |
| `POST   /api/projects/{id}/script/snapshots` | 手动写一个 manual_save snapshot |
| `POST   /api/projects/{id}/script/snapshots/{sid}/restore` | 回退到指定快照 |

请求体均含 `user_id`，与现有项目接口一致。

Expert Agent 流式接口复用：

```
POST /api/projects/{id}/agents/expert/stream
GET  /api/projects/{id}/agents/expert/messages
```

---

## 9. 验收（对应 PRD §15.5）

1. 与专家 Agent 对话后，能在专家面板看到 1-3 张方案卡片，含理由/trade-off/品牌解释话术（卡片可展开）。
2. 点击方案卡片「预览修改」打开 Diff Overlay，按 hunk 展示 old → new。
3. 用户可逐 hunk 应用/不应用，也可一键全部应用。
4. 点击「写入编辑器」后：
   - 仅 accepted hunk 写入 cell；
   - apply 前后各生成 1 条 snapshot；
   - 卡片 status 变为 `applied` / `partially_applied`；
   - `stale.expert=false`。
5. 若有 hunk.old 与当前 cell 不一致，apply 接口返回的 `conflict_hunk_ids` 在前端提示「脚本已变化，建议重新生成」。
6. Snapshots drawer 列出快照，点击「回退到此版本」能将 `current_script` 恢复并触发自动刷新。
7. Topbar「预览修改稿」按钮在存在 draft suggestion 时直接打开 Diff Overlay，否则给出 toast 提示。

---

## 10. 风险与降级

| 风险 | 规避 |
|------|------|
| 模型不遵循 artifact 协议或 row_id/column_id 编造 | parser 严格按当前 script 校验，丢弃非法 hunk；整个方案无有效 hunk 时丢弃整条方案 |
| 模型混淆 `old` 与建议总结，写出与 cell 不一致的字符串 | apply 接口 cell 比对失败的 hunk 标记 conflict 并跳过，全冲突时不创建 snapshot |
| 用户在生成方案后手动编辑了对应 cell | apply 时校验冲突，前端弹提示「脚本已变化」，建议用户重新生成方案 |
| Snapshot 数量过多导致 Mongo 写量增加 | restore 前才写 before_restore snapshot；提供「清理旧快照」（暂缓） |
| Expert Agent 在追问类对话中生成 hunk 干扰主流程 | 协议强制：闲聊轮次不输出 `<expert_suggestions>`；parser 解析失败即跳过 |
| Diff Overlay 同时显示多方案造成 UI 复杂 | MVP 一次只显示一个 suggestion 的 hunk 集合，方案切换通过卡片入口完成 |

---

## 11. 与 Phase 3 / 4 的衔接

- Brand / Audience 已经写入 `project.brand_insights` 与 `project.audience_analysis`，Expert Agent 直接读取，不再读取 brand/audience 完整聊天历史。
- Expert apply 不会触发 brand/audience stale，符合「Expert apply 等价于一次脚本修改」的原则吗？
  - 不会。apply 流程刻意绕开 `_write_script` 的 stale 重置，仅清 stale.expert。这样既能让用户看到「方案已写入」，又避免立即触发 brand/audience 全部重跑。
  - 如需让 brand/audience 也重新分析，可后续在 UI 增加显式「重新评估」按钮，调用 brand/audience stream，本期不做。
- Snapshot restore 走 `_write_script`，stale 全 true：符合「回退到旧脚本意味着所有结构化结果都可能过期」的语义。

---

## 12. 文档变更清单

| 文档 | 变更 |
|------|------|
| `docs/development_plan_P0.md` | Phase 5 任务勾选；§8.5 Phase 5 验收勾选 |
| `docs/prd.md` | 无需修改（已对齐） |
| `docs/technical_plan_lightweight.md` | 无需修改（已含 §4.7 / §8.3 / §9.5 / §9.8） |
| `docs/superpowers/plans/2026-05-19-phase-5-expert-loop.md` | 配套实施 plan |
| 本文档 | 权威设计说明 |
