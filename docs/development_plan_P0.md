# BrandVideo MVP 开发计划

> 基于 `docs/prd_new.md` 与 `docs/technical_plan_lightweight.md` 整理。  
> 数据结构规范见 `docs/data_structures.md`；已锁定决策见 [§0](#0-已锁定决策)。

---

## 0. 已锁定决策

| # | 决策 | 说明 |
|---|------|------|
| 1 | **UI 重建** | 移除前台 Brand / Audience / Expert 三面板；按 PRD §2 实现 Main Workspace + Coordinator Chat + Output Panel。 |
| 2 | **统一 AI 入口** | 仅 **Coordinator Agent Chat**；品牌/观众/专家为内部视角（PRD §6、§13）。 |
| 3 | **默认脚本列** | `duration`、`scene`、`format`、`notes`；**不含**「反馈建议」默认列（PRD §4.1）。 |
| 4 | **Brief 格式（MVP）** | 仅 **`.md` / `.txt` 上传** 与 **纯文本粘贴**；PDF/DOC/PPT 等列入二期（与 PRD 全格式支持分阶段）。 |
| 5 | **主工作区** | Script Editor ↔ IBIS Node Graph 可切换，共享 project state（PRD §3）。 |
| 6 | **输出区** | Negotiation Preparation 与 References **同一 Output Panel**，tab 切换（PRD §8）。 |

**技术栈裁决（轻量 MVP）：** MongoDB、Redis、FastAPI、Next.js + Zustand、SSE、SiliconFlow（Qwen3-8B / 32B）。LangGraph / PostgreSQL 为 PRD 推荐终态，MVP 可先 Service + SSE，见 [§2](#2-文档对齐)。

**版本策略：** 日常编辑可更新 `project.current_script`（轻量路径）；Revision Proposal apply、手动保存、回滚时写入 `script_snapshots` / `ScriptVersion`。结构化 artifact 记录 `based_on_script_version_id`。

**过期标记：** MVP 优先 `project.stale` 布尔或简化 reason；目标 schema 为 `ArtifactStaleness`（PRD §10.11、`data_structures.md` §11）。

---

## 1. 北极星闭环

```text
user_id 进入 → 创建/打开项目 → 上传/粘贴 Brief（MD/TXT）
→ Script Editor 编辑脚本 ↔ Node Graph 追踪 Issue/Position/Argument/Reference
→ Coordinator Chat（可选视角 chips + quote）→ Revision Proposal + Diff
→ 逐段确认 hunk 写回脚本 → Negotiation Preparation / References（Output Panel）
```

**MVP 完成定义：** 用户能独立完成上述路径一次，并通过 [§8 验收清单](#8-验收清单) 中与当前阶段对应的条目。

---

## 2. 文档对齐

| 主题 | prd_new / data_structures | 本计划（MVP） |
|------|---------------------------|---------------|
| 产品 PRD | `prd_new.md` | 验收以 PRD §16 为准 |
| 数据库 | PostgreSQL（PRD §18） | MongoDB，数据主要嵌入 `projects` |
| Agent 编排 | LangGraph Coordinator（PRD §13） | Coordinator Service + SSE；LangGraph 二期 |
| Brief 实体 | 独立 BriefFile | 嵌入 `project.brief` |
| Brief 文件类型 | PDF/DOC/…/MD/TXT | **MVP：MD + TXT + 粘贴** |
| 前台 Agent | 无三面板 | Coordinator Chat only |
| 品牌/观众/专家输出 | RationaleNode、RevisionProposal 等 | 逐步落库，可先 mock 再结构化 |
| 脚本版本 | ScriptVersion 体系 | `current_script` + 关键时刻 snapshot |
| 鉴权 | owner_id（远期） | 自定义 `user_id` + localStorage |

`data_structures.md` 为规范化目标；MVP 允许字段子集与嵌入文档，但命名与语义不向旧三 Agent 模型回退。

---

## 3. 仓库结构

```text
BrandVideo/
  frontend/          # Next.js, TypeScript, Zustand, React Flow（Node Graph）
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

- 序号列 `#`：仅前端渲染，不进入 `columns`。
- 时长格式 V1：`起始秒-结束秒`（如 `0-5`）。

---

## 5. 分阶段计划（对齐 PRD §15）

### Phase 0 — 界面结构重构（PRD P0）

**目标：** 布局与信息架构符合新 PRD；Script Editor 基础能力保留；尚无真实 Coordinator LLM。

| ID | 任务 | 参考 |
|----|------|------|
| 0.1 | 移除右侧 Brand / Audience / Expert accordion | PRD §17.1 |
| 0.2 | 新增 **Coordinator Chat** 列（可 mock 对话） | PRD §6 |
| 0.3 | Main Workspace：**Script Editor / Node Graph** 切换占位 | PRD §3 |
| 0.4 | Topbar：Brief 入口、Persona Entry、视图切换、保存状态 | PRD §2.3、§7 |
| 0.5 | **Output Panel**：Negotiation / References tab 壳 | PRD §8 |
| 0.6 | Selection Popup → 向 Coordinator 插入 quote（非展开 Agent 面板） | PRD §4.7、§17.3 |
| 0.7 | `docker-compose`、FastAPI 骨架、`user_id` 进入、Project CRUD | 技术方案 §3–4 |
| 0.8 | `current_script` debounce 同步；Topbar `editing/saving/saved` | PRD §4.3 |

**Phase 0 验收：**

- [ ] 页面无三个独立 Agent 面板
- [ ] 可见 Coordinator Chat、主工作区切换、Output Panel 双 tab
- [ ] Persona 有 Topbar 入口（可先空壳）
- [ ] 项目与脚本可持久化并刷新恢复

**Phase 0 不做：** IBIS 图真实渲染、LangGraph、Brief 多格式解析、Revision Diff 闭环。

---

### Phase 1 — Script Editor 稳定化（PRD P1）

**目标：** PRD §16.2 Script Editor 条目。

| ID | 任务 |
|----|------|
| 1.1 | 单元格编辑；序号列不可编辑/删除 |
| 1.2 | 行插入/删除（hover band、确认、保留最后一行） |
| 1.3 | 列插入/删除/重命名；不可删最后一个业务列 |
| 1.4 | 时长校验、时间轴、重叠提示 |
| 1.5 | 选中文本 → quote → Coordinator 输入区 |
| 1.6 | 脚本变更 → `stale`（rationale / proposals / negotiation 等） |
| 1.7 | 版本记录 API 壳（snapshot 列表 / restore 占位） |

**Gate：** 冻结 `current_script` JSON schema。

---

### Phase 2 — Persona 与 Coordinator Chat（PRD P2）

| ID | 任务 |
|----|------|
| 2.1 | Persona CRUD、`active_persona_id`；`age_range` 自由文本 | PRD §7 |
| 2.2 | `POST .../coordinator/stream`（SSE）替代三 Agent stream | PRD §11.3 |
| 2.3 | `coordinator_messages` 持久化；`requested_perspectives` chips | PRD §10.4 |
| 2.4 | quote、persona、script_version 写入消息元数据 | PRD §6.7 |
| 2.5 | SiliconFlow + ModelRouter；8B 对话 / 32B 结构化 | 技术方案 §7 |
| 2.6 | 回复可关联 `related_node_ids`（先 ID 占位） | PRD §6.5 |

**验收：** PRD §16.3、§16.4 核心项。

---

### Phase 3 — IBIS Node Graph（PRD P3）

| ID | 任务 |
|----|------|
| 3.1 | `RationaleNode` / `RationaleEdge` API 与 MongoDB 存储 | `data_structures.md` §5–6 |
| 3.2 | React Flow：Issue / Position / Argument / Reference 形状与来源色 | PRD §5 |
| 3.3 | 节点 CRUD、状态 badge、与脚本行双向跳转 | PRD §5.6–5.8 |
| 3.4 | 选中文本「加入 Node Graph 为 Issue」 | PRD §5.9 |
| 3.5 | Coordinator 建议节点（artifact SSE）；不静默覆盖用户确认节点 | PRD §5.9 |
| 3.6 | Brief 上传（MD/TXT）→ 初始 Issue / Reference 生成 | PRD §2.3 |

**验收：** PRD §16.5。

---

### Phase 4 — Revision Proposal 与协商准备（PRD P4）

| ID | 任务 |
|----|------|
| 4.1 | `RevisionProposal` + cell-level `hunks` 生成与列表 | PRD §9 |
| 4.2 | Diff overlay；hunk 状态 null/true/false；写入编辑器 | PRD §9.4–9.5 |
| 4.3 | apply 前校验 cell == `removed`；apply 后 snapshot / 新版本 | PRD §9.4 |
| 4.4 | `NegotiationPreparation`、`ReferenceItem` 生成与 Output Panel 展示 | PRD §8 |
| 4.5 | 从 Issue 生成协商准备；节点 / 脚本跳转 | PRD §8.4 |
| 4.6 | Topbar 版本历史与回退 | PRD §16.7 |

**验收：** PRD §16.6、§16.7。

---

### Phase 5 — 整合与可追溯性（PRD P5 + 答辩）

| ID | 任务 |
|----|------|
| 5.1 | 证据链：Graph ↔ References ↔ 脚本行 | PRD P5 |
| 5.2 | LangGraph `CoordinatorState` 接入（可选） | `data_structures.md` §二 |
| 5.3 | `ArtifactStaleness` 完整枚举与 UI badge | PRD §14 |
| 5.4 | 演示数据、错误态、README | — |
| 5.5 | 全量 PRD §16 验收勾选 | — |

---

## 6. 时间线（参考）

| 阶段 | 约周数 | 累计 | 对应 PRD |
|------|--------|------|----------|
| P0 结构重构 | 1–1.5 | 1.5 | PRD P0 |
| P1 Script Editor | 1.5–2 | 3.5 | PRD P1 |
| P2 Coordinator + Persona | 1–1.5 | 5 | PRD P2 |
| P3 Node Graph | 1.5–2 | 7 | PRD P3 |
| P4 Proposal + Output | 1.5–2 | 9 | PRD P4 |
| P5 整合 | 0.5–1 | 10 | PRD P5 |

**关键路径：** P0 布局 → P1 表格 → P2 Coordinator SSE → P3 Graph → P4 hunk apply。

---

## 7. 测试策略

| 层 | 范围 |
|----|------|
| 后端单元 | 时长解析、删列同步 cells、hunk `removed` 校验、ArtifactStaleness 规则 |
| 后端集成 | Project CRUD、script PATCH、coordinator messages、graph nodes/edges、proposal apply |
| 前端 | 时间轴、Graph 渲染、Coordinator quote、Output tab 切换 |
| E2E（可选） | Brief → 编辑脚本 → Coordinator 对话 → 应用一段 hunk → 查看 Negotiation tab |

---

## 8. 验收清单

### 8.1 Phase 0 — 页面结构（PRD §16.1）

- [ ] 无三个独立 Agent 面板
- [ ] 统一 Coordinator Agent Chat
- [ ] Script Editor / Node Graph 主工作区可切换（Graph 可先占位）
- [ ] Persona 独立入口
- [ ] Negotiation Preparation 与 References 同 panel、tab 切换

### 8.2 Phase 1 — Script Editor（PRD §16.2）

- [ ] 可编辑业务单元格；序号列不可编辑
- [ ] 任意两行间插入行；末尾可插入
- [ ] 可删除普通行/列（有确认）；不可删最后一行、最后业务列
- [ ] 时长错误提示；时间轴；重叠标记
- [ ] 选中文本 → quote 进入 Coordinator 输入区

### 8.3 Phase 2 — Coordinator + Persona（PRD §16.3–16.4）

- [ ] 消息发送/持久化；streaming 回复
- [ ] 可选 brand / audience / expert / comprehensive 视角 chips
- [ ] Persona 新建/编辑/删除/切换；`age_range` 自由文本
- [ ] active persona 影响观众视角分析；persona 变更触发相关 stale

### 8.4 Phase 3 — Node Graph（PRD §16.5）

- [ ] 四类 IBIS 节点；颜色表 Issue 来源
- [ ] 节点详情、编辑、删除、绑定脚本行
- [ ] 从选中文本创建 Issue；Coordinator 建议节点

### 8.5 Phase 4 — Output + Revision（PRD §16.6–16.7）

- [ ] Negotiation / References tab 内容可展示与跳转
- [ ] 多 Revision Proposal；Diff 逐段应用；仅应用已接受 hunk
- [ ] apply 后脚本更新与版本回退

---

## 9. 暂缓项（MVP 不排期）

1. LangGraph checkpointer + PostgreSQL 全量迁移  
2. Brief：PDF、DOC、DOCX、PPT 解析（PRD 已定义，实现后置）  
3. 独立 BriefFile collection（可先嵌入）  
4. 每次 cell 编辑自动生成 ScriptVersion（用 snapshot 关键时刻代替）  
5. 节点合并、重复检测、多 persona 对比（PRD P5）  
6. 正式登录、多人协作、细粒度权限  

---

## 10. 风险与规避

| 风险 | 规避 |
|------|------|
| UI 重构范围大 | P0 先布局与路由，Graph/Output 可占位 |
| MongoDB `projects` 膨胀 | `coordinator_messages`、`rationale_nodes`、`script_snapshots` 独立 collection |
| 旧三 Agent 代码残留 | Phase 0 明确删除 accordion 与 `agents/{type}/stream` 前台调用 |
| hunk 与手动编辑冲突 | apply 前校验 `removed` 与当前 cell 一致 |
| LLM 成本 | brief 摘要、局部脚本、requested_perspectives 按需调内部节点 |

---

## 11. 相关文档

- 产品需求：`docs/prd_new.md`
- 数据结构：`docs/data_structures.md`
- 轻量技术方案：`docs/technical_plan_lightweight.md`
- 旧版 PRD（归档参考）：`docs/prd.md`
