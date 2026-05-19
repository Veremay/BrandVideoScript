# BrandVideo MVP 开发计划

> 基于 `prd.md` 与 `technical_plan_lightweight.md` 整理。  
> 已锁定决策见 [§0](#0-已锁定决策)。

---

## 0. 已锁定决策

| # | 决策 | 说明 |
|---|------|------|
| 1 | **UI 重建** | 不依赖外部 HTML 原型；按 PRD §2 交互与浅色视觉在 Next.js 中 state-first 实现。 |
| 2 | **Brief 格式（MVP）** | 仅支持 **`.md` / `.txt` 上传** 与 **纯文本粘贴**；PDF/DOC/PPT 等列入二期。 |
| 3 | **默认列** | 保留 **「反馈建议」**（`feedback`，textarea）；与 PRD §5.1.1 一致。 |

**技术栈裁决（轻量方案）：** MongoDB、Redis、FastAPI、Next.js + Zustand、SSE、SiliconFlow（Qwen3-8B / 32B）。暂不引入 LangGraph、PostgreSQL、每次编辑 ScriptVersion。

**版本策略：** 日常编辑更新 `project.current_script`；仅在专家 apply 前后、手动保存、导入时写入 `script_snapshots`。PRD 中的「版本回退」对应 snapshot restore。

**过期标记：** MVP 用 `script.updated_at`（及可选 `snapshot_id`）判断 quote / 分析是否可能过期；不实现完整 `based_on_script_version_id` 体系。

---

## 1. 北极星闭环

```text
user_id 进入 → 创建/打开项目 → 上传/粘贴 Brief（MD/TXT）
→ 表格编辑脚本 → 品牌/观众/专家 Agent 反馈
→ 专家多方案 + cell-level hunk → Diff 预览 → 逐段确认 → 写回脚本
```

**MVP 完成定义：** 用户能独立完成上述路径一次，并通过 [§8 验收清单](#8-验收清单) 中与当前阶段对应的条目。

---

## 2. 文档对齐（实现时以本计划为准）

| 主题 | PRD / data_structures | 本计划 |
|------|----------------------|--------|
| 数据库 | PostgreSQL（远期） | MongoDB，数据嵌入 `projects` |
| Agent 编排 | LangGraph（远期） | Brand / Audience / Expert Service + SSE |
| Brief 实体 | 独立 BriefFile（远期） | 嵌入 `project.brief` |
| Brief 文件类型 | 多种格式 | **MVP：MD + TXT + 粘贴** |
| 脚本版本 | 每次编辑 ScriptVersion | `current_script` + 关键时刻 snapshot |
| 默认业务列 | 5 列含 feedback | **保留 feedback** |
| 鉴权 | 正式登录（远期） | 自定义 `user_id` + localStorage |

`data_structures.md` 作为论文/二期规范化参考，MVP 不逐表实现。

---

## 3. 仓库结构

```text
BrandVideo/
  frontend/          # Next.js, TypeScript, Zustand
  backend/           # FastAPI, Motor/PyMongo
  docker-compose.yml # MongoDB + Redis
  docs/
```

---

## 4. 默认脚本列（Phase 1 冻结）

| 列名 | key | type | multiline |
|------|-----|------|-----------|
| 时长 | duration | duration | 否 |
| 画面 | scene | textarea | 是 |
| 形式 | format | text | 否 |
| 备注 | notes | text | 否 |
| 反馈建议 | feedback | textarea | 是 |

- 序号列 `#`：仅前端渲染，不进入 `columns`。
- 时长格式 V1：`起始秒-结束秒`（如 `0-5`）。

---

## 5. 分阶段计划

### Phase 0 — 基础工程与数据闭环

**目标：** 前后端可运行；项目与脚本可持久化；尚无真实 Agent。

| ID | 任务 | 参考 |
|----|------|------|
| 0.1 | `docker-compose`：MongoDB、Redis | 技术方案 §2 |
| 0.2 | FastAPI 骨架：健康检查、`POST /api/users/enter` | §3、§10 |
| 0.3 | `users` / `projects` collection；Project CRUD | §4.1 |
| 0.4 | `GET/PATCH` script（`current_script` 含默认 5 列空表） | §4.2、§10 |
| 0.5 | Next.js：user_id 门页 → 项目列表 → 编辑器**空壳**（三列 grid + Topbar 占位） | PRD §2.1 |
| 0.6 | Zustand `AppState` 骨架 | 技术方案 §11 |
| 0.7 | 脚本 debounce 同步后端；Topbar 保存状态 `editing/saving/saved` | PRD §5.1.4 |
| 0.8 | `LLMClient` + `ModelRouter` 接口壳（可 mock，不接真实调用） | §7 |

**Phase 0 验收：**

- [ ] 输入 `user_id` 后刷新仍保持登录态
- [ ] 可新建项目、打开项目
- [ ] 可修改脚本并刷新后从 MongoDB 恢复
- [ ] 保存状态在 Topbar 正确变化
- [ ] `docker-compose up` 一键启动依赖服务

**Phase 0 不做：** Brief 解析、Agent、完整表格交互、文件上传 UI。

---

### Phase 1 — Script Editor 与页面壳

**目标：** 无 Agent 时达到 PRD §15.1；布局达到 PRD §2。

| ID | 任务 |
|----|------|
| 1.1 | 表格：单元格编辑、行/列插入删除、列重命名 |
| 1.2 | 序号列、删行/删列确认、禁止删最后一行/最后一业务列 |
| 1.3 | 时长校验、时间轴、重叠提示 |
| 1.4 | 文本选中 → 【问品牌/观众/专家】浮层；展开对应 accordion |
| 1.5 | Agent 区 accordion（对话可 mock） |
| 1.6 | 可拖拽分割条；暗色视觉 |
| 1.7 | Script API：`rows`/`columns` CRUD + cells PATCH；写入后 `stale.* = true` |

**验收：** PRD §15.1 全部；§15.2.1–3（浮层与 quote UI，消息可 mock）。

**Gate：** 冻结 `current_script` JSON schema，后续 Agent 只读此结构。

---

### Phase 2 — Agent 基础设施

| ID | 任务 |
|----|------|
| 2.1 | `POST /api/projects/{id}/agents/{type}/stream`（SSE：`token` / `artifact` / `done` / `error`） |
| 2.2 | `agent_messages` 持久化；前端流式 placeholder |
| 2.3 | Redis：`stream:{request_id}`、上下文 cache |
| 2.4 | `GET` 历史消息；最近 N 轮 + 摘要字段 |
| 2.5 | 接入 SiliconFlow；按任务类型路由 8B / 32B |
| 2.6 | UI 展示 `project.stale` 基础布尔 |

**验收：** 任一 Agent 能流式返回并落库；中断可重试。

---

### Phase 3 — Brief + 品牌方 Agent

| ID | 任务 |
|----|------|
| 3.1 | Brief：**上传 `.md` / `.txt`** 或粘贴纯文本 → `project.brief` |
| 3.2 | 文本读取 + `parse_status`；生成 `brief.summary`（8B） |
| 3.3 | Brand Agent 流式对话 + quote |
| 3.4 | BrandInsight（32B）→ `brand_insights`；pinned 三 tab 可编辑 |
| 3.5 | Brief 就绪后可选触发初始品牌分析 |

**验收：** PRD §15.3；§15.2.4–5（品牌侧）。

**MVP 明确不做：** PDF/DOC/DOCX/PPT 解析。

---

### Phase 4 — 观众 Agent + Persona

| ID | 任务 |
|----|------|
| 4.1 | Persona CRUD + `active_persona_id` |
| 4.2 | Audience Agent 流式 + `audience_analysis`（32B） |
| 4.3 | 回复标明当前 persona |
| 4.4 | persona 变更触发 stale 规则 |

**验收：** PRD §15.4。

---

### Phase 5 — 专家方案闭环

| ID | 任务 |
|----|------|
| 5.1 | Expert 多方案 + `hunks[]`（32B） |
| 5.2 | 方案卡片 + 展开详情 |
| 5.3 | Diff overlay；逐段接受/拒绝 |
| 5.4 | apply 前校验 cell 值 == `hunk.old` |
| 5.5 | apply 前后 `script_snapshots`；restore API |
| 5.6 | Topbar「预览修改稿」 |
| 5.7 | 写回 `current_script`；`stale.expert = false` |

**验收：** PRD §15.5 全部。

---

### Phase 6 — 整合与答辩准备

| ID | 任务 |
|----|------|
| 6.1 | 固定演示数据（sample brief.md + 3–5 行脚本） |
| 6.2 | LLM 失败、hunk 冲突、SSE 中断等错误态 |
| 6.3 | 上下文缓存与成本抽查 |
| 6.4 | 全量验收清单勾选 |
| 6.5 | README：环境变量、启动、演示路径 |

---

## 6. 时间线（参考）

| 阶段 | 约周数 | 累计 |
|------|--------|------|
| P0 | 1 | 1 |
| P1 | 1.5–2 | 3 |
| P2 | 1 | 4 |
| P3 | 1 | 5 |
| P4 | 1 | 6 |
| P5 | 1.5–2 | 8 |
| P6 | 0.5–1 | 9 |

**关键路径：** P0 脚本持久化 → P1 表格稳定 → P2 SSE → P5 hunk apply。

---

## 7. 测试策略

| 层 | 范围 |
|----|------|
| 后端单元 | 时长解析、删列同步 cells、hunk `old` 校验、stale 规则 |
| 后端集成 | Project CRUD、script PATCH、snapshot apply/restore |
| 前端 | 时间轴、重叠检测、accordion 互斥 |
| E2E（可选） | 建项目 → 改 cell → 品牌对话 → 专家 apply 一段 |

每阶段结束执行对应验收子集后再进入下一阶段。

---

## 8. 验收清单

### 8.1 Phase 0

- [ ] user_id 持久化
- [ ] 项目 CRUD + script 读写
- [ ] 自动保存 debounce + 状态展示

### 8.2 Phase 1 — Script Editor（PRD §15.1）

- [ ] 可编辑业务单元格；序号列不可编辑
- [ ] 任意两行间插入行；表格末尾可插入
- [ ] 可删除普通行/列（有确认）
- [ ] 不可删最后一行、最后一个业务列、序号列
- [ ] 时长错误有明确提示
- [ ] 时间轴随有效时长渲染
- [ ] 时间重叠可标记
- [ ] 选中文本出现问 Agent 浮层
- [ ] 点击问 Agent 展开对应面板
- [ ] quote 可插入输入区（mock 即可）

### 8.3 Phase 3 — 品牌（PRD §15.3）

- [x] 显式/隐式/品牌反馈三 tab
- [x] insight 可增删改
- [x] insight 含 reason / evidence / confidence / status（点击展开）
- [x] MD/TXT Brief 上传或粘贴可解析为文本

### 8.4 Phase 4 — 观众（PRD §15.4）

- [ ] Persona 新建/编辑/删除/切换
- [ ] 回复标明 persona
- [ ] 自然度、可信度、广告感等结构化分析

### 8.5 Phase 5 — 专家（PRD §15.5）

- [ ] 多方案 + 理由/trade-off
- [ ] Diff 预览 + 逐段应用
- [ ] 仅应用已接受 hunk
- [ ] apply 后脚本更新 + snapshot
- [ ] 可回退 snapshot

---

## 9. 暂缓项（MVP 不排期）

1. LangGraph / PostgreSQL checkpointer  
2. 每次编辑生成 ScriptVersion  
3. 独立 BriefFile collection  
4. Brief：PDF、DOC、DOCX、PPT 等  
5. AudienceAnalysis 历史列表、多 persona 对比  
6. 正式登录注册、多人协作  
7. 复杂任务队列  

---

## 10. 风险与规避

| 风险 | 规避 |
|------|------|
| MongoDB `projects` 文档膨胀 | `agent_messages`、`script_snapshots` 独立 collection |
| hunk 与手动编辑冲突 | apply 前校验 `old`；不一致提示重新生成 |
| LLM 成本 | brief 摘要、局部脚本上下文、最近 N 轮、Redis 缓存 |
| SSE 中断 | 完成后才写最终 assistant message；前端可重试 |

---

## 11. 相关文档

- 产品需求：`docs/prd.md`
- 轻量技术方案：`docs/technical_plan_lightweight.md`
- 远期数据结构：`docs/data_structures.md`
