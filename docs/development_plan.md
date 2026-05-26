# BrandVideo 开发计划

> **主依据：** [`docs/pipeline.md`](./pipeline.md)（系统流程 13 步）  
> **补充依据：** `docs/prd_new.md`、`docs/data_structures.md`  
> **技术实现：** [`docs/technical_plan.md`](./technical_plan.md)  
> **归档参考：** `docs/development_plan_P0.md`、`docs/technical_plan_lightweight.md`

---

## 0. 已锁定决策

| # | 决策 | 说明 |
|---|------|------|
| 1 | **流程主文档** | 产品与技术分阶段以 `pipeline.md` 的 13 步为准，不再以旧 PRD 三 Agent 面板为前台模型。 |
| 2 | **统一 AI 入口** | 创作者只通过 **Coordinator Agent Chat** 与系统交互；Brand / Audience / Expert 为 Coordinator 调度的内部 Agent。 |
| 3 | **上下文隔离** | 各 Agent 只读各自所需 State 字段，避免自然语言聊天串线（见 `pipeline.md` §2、`technical_plan.md` §5）。 |
| 4 | **创作者主导** | AI 不直接覆盖整份脚本；修改以 **Expert 多方向方案 + 可选 cell-level hunk** 呈现，由创作者确认后写回。 |
| 5 | **默认脚本列** | `duration`、`scene`、`format`、`notes`、**`feedback`（品牌反馈，只读）**；创作者可见、不可编辑；品牌方在分享页填写，经 sync 写入（Phase 6）。 |
| 6 | **Brief 格式（MVP）** | `.md` / `.txt` 上传 + 纯文本粘贴；PDF/DOC/PPT 等二期。 |
| 7 | **主工作区** | Script Editor ↔ IBIS Node Graph 可切换，共享 project state。 |
| 8 | **输出形态（MVP）** | **Negotiation Preparation**：按需按钮 → **弹窗**（`pipeline.md` §11）；**References** 与固定 Output Panel **MVP 不做**（`pipeline.md` §4、§12）。 |
| 9 | **外部工具** | Brand Agent：Tavily + Brand Wiki；Expert Agent：领域案例/脚本结构 **知识库工具接口**（可先 stub）。 |
| 10 | **技术栈** | MongoDB、Redis、FastAPI、Next.js + Zustand、SSE、SiliconFlow（Qwen3-8B / 32B）；LangGraph 二期可选。 |

**版本策略：** 日常编辑更新 `project.current_script`；应用方案、hunk、手动保存、回滚时写入 `script_snapshots`。结构化产物绑定 `based_on_script_version_id`。

**过期标记：** MVP 可用 `project.stale` 简化字段；目标 schema 见 `data_structures.md` §11。

---

## 1. 系统流程总览（对齐 pipeline.md）

| 步骤 | pipeline.md | 开发计划阶段 |
|------|-------------|--------------|
| 1 | Brief 上传与项目初始化 | Phase 0–1 |
| 2 | 多智能体初始解析（Brand / Audience / Expert） | Phase 2 |
| 3 | 生成初始 IBIS 节点图 | Phase 2 |
| 4 | 创作者进入主工作区（Coordinator 统一入口） | Phase 0 |
| 5 | Script Editor 中脚本创作 | Phase 1 |
| 6 | 基于脚本内容触发多视角反馈 → 结构化节点 | Phase 3–4 |
| 7 | Node Graph 组织冲突与权衡 | Phase 4 |
| 8 | Persona 面板维护观众视角 | Phase 3 |
| 9 | 真实品牌反馈（分享链接 + feedback 列） | Phase 6 |
| 10 | Expert Agent 生成多方向修改方案 | Phase 5 |
| 11 | Negotiation Preparation（弹窗） | Phase 7 |
| 12 | References 输出 | **暂缓（二期）** |
| 13 | 最终创作资产包 | Phase 8 验收 |

```text
Brief 上传
  → Coordinator 调度 Brand / Audience / Expert 初始解析
  → 初始 IBIS 节点图 + 初始 Persona
  → 主工作区：Script Editor ↔ Node Graph + Coordinator Chat
  → 脚本编辑 / 选段提问 → 新节点或节点更新
  → Expert 多方向修改方案（创作者选用）
  → [可选] 品牌方分享链接填写 feedback → 新节点 + 待协商列表
  → 生成 Negotiation Preparation 弹窗
  → 交付：脚本 + 节点图 + Persona + 方案集 + 协商材料
```

**MVP 完成定义：** 创作者能独立完成上述路径（不含 References、不含固定 Output Panel），并通过 [§7 验收清单](#7-验收清单) 对应条目。

---

## 2. 最终交付物（pipeline.md §13）

| 资产 | 说明 |
|------|------|
| 持续迭代的脚本 | `current_script` + 关键 snapshot |
| 结构化节点图 | Issue / Position / Argument / Reference |
| 可编辑 Persona | 含平台语境、广告敏感度等 |
| 多个修改方案 | Expert 方向：保守 / 平衡 / 创作者主导 / 观众友好等 |
| 协商准备材料 | 弹窗展示，非 MVP 固定侧栏 |
| References | **二期** |

**产品价值：** 在品牌方正式 review 前，帮助创作者识别冲突、理解隐性需求、预测观众反应，并准备可解释、可协商的方案。

---

## 3. 文档与实现范围对齐

| 主题 | prd_new / data_structures | 本计划（MVP） |
|------|---------------------------|---------------|
| 流程叙述 | PRD 各章 | **`pipeline.md` 优先** |
| 数据库 | PostgreSQL（PRD §18） | MongoDB，主数据嵌入 `projects` |
| Agent 编排 | LangGraph | CoordinatorService + SSE；LangGraph 二期 |
| Brief | 多格式 | **MD + TXT + 粘贴** |
| 品牌反馈 | PR feedback | **分享链接 + `feedback` 列** |
| 协商输出 | Output Panel tab | **按钮触发弹窗** |
| References | Output Panel | **不做** |
| 鉴权 | owner_id | 自定义 `user_id` + localStorage |

`data_structures.md` 为字段规范化目标；命名与语义不向「前台三 Agent 面板」回退。

---

## 4. 仓库结构

```text
BrandVideo/
  frontend/          # Next.js, TypeScript, Zustand, React Flow
  backend/           # FastAPI, Motor/PyMongo
  docker-compose.yml # MongoDB + Redis
  docs/
    pipeline.md              # 流程主文档
    development_plan.md      # 本文件
    technical_plan.md        # 技术方案
    data_structures.md
```

---

## 5. 默认脚本列（Phase 1 冻结）

| 列名 | key | type | multiline |
|------|-----|------|-----------|
| 时长 | duration | duration | 否 |
| 画面 | scene | textarea | 是 |
| 形式 | format | text | 否 |
| 备注 | notes | text | 否 |

- 序号列 `#`：仅前端渲染。
- 时长格式 V1：`起始秒-结束秒`（如 `0-5`）。
- **`feedback`（品牌反馈）列：** 创作者工作区**只读展示**；品牌方在分享页**可编辑**；`brand-feedback/sync` 合并后创作者可见真实原话，见 Phase 6。

---

## 6. 分阶段计划

### Phase 0 — 主工作区与工程底座（pipeline §4）

**目标：** Coordinator 为统一入口的布局；项目与脚本可持久化；尚无真实多 Agent 解析。

| ID | 任务 | pipeline |
|----|------|----------|
| 0.1 | 移除前台 Brand / Audience / Expert 三面板 | §4 |
| 0.2 | Coordinator Chat（可先 mock） | §4 |
| 0.3 | Main Workspace：Script Editor / Node Graph 切换占位 | §4 |
| 0.4 | Topbar：Brief 入口、Persona 入口、视图切换、保存状态 | §4 |
| 0.5 | **不做** 固定 Negotiation / References Output Panel | §4 |
| 0.6 | 选中文本 → quote 插入 Coordinator | §6 |
| 0.7 | `docker-compose`、FastAPI、`user_id` 进入、Project CRUD | §1 |
| 0.8 | `current_script` debounce 同步 | §5 |

**验收：** 无三 Agent 面板；可见 Coordinator、主工作区切换、Persona 入口；项目/脚本刷新可恢复。

**不做：** 真实 LLM 解析、完整 Graph、分享链接、协商弹窗。

---

### Phase 1 — Script Editor（pipeline §5）

**目标：** 创作者在表格中主导撰写脚本；变更写入 Shared State。

| ID | 任务 |
|----|------|
| 1.1 | 单元格编辑；序号列不可编辑/删除 |
| 1.2 | 行插入/删除（确认、保留最后一行） |
| 1.3 | 列插入/删除/重命名 |
| 1.4 | 时长校验、时间轴、重叠提示 |
| 1.5 | 脚本 PATCH debounce；`stale` 触发（图/方案/协商材料） |
| 1.6 | snapshot 列表 / restore API 壳 |

**Gate：** 冻结 `current_script` JSON schema。

---

### Phase 2 — Brief 与初始多智能体解析（pipeline §1–3）

**目标：** Brief 上传后，Coordinator 调度三 Agent 完成首次解析并生成初始节点图。

| ID | 任务 | Agent / 能力 |
|----|------|----------------|
| 2.1 | Brief 上传/粘贴（MD/TXT）；`brief.summary` | §1 |
| 2.2 | **Brand Agent**：显式/隐性需求；Tavily + Brand Wiki（可先接现有 research 路由） | §2 |
| 2.3 | **Persona 数据分析接口**（`provision-from-analytics`，不读 Brief）；Audience Agent **不**参与 Persona 生成 | §8、`technical_plan.md` §4.3 |
| 2.4 | **Expert Agent**：Brief 对创作的影响、结构建议（知识库接口 stub） | §2 |
| 2.5 | 解析结果写入 Shared State；**上下文隔离**校验 | §2 |
| 2.6 | **初始 IBIS 图**：Brand → Expert 产出品牌向节点；Persona 就绪后 Audience → Expert 补观众向节点（无独立 GraphWriter） | §3 |
| 2.7 | `POST .../brief/parse`、`POST .../persona/provision-from-analytics` | 技术方案 §8 |

**验收：** `provision-from-analytics` 可写入 Persona；上传 Brief 后可见品牌向 Issue 节点；Persona 就绪后可生成观众向节点。

---

### Phase 3 — Persona 与 Coordinator 对话（pipeline §6、§8）

**目标：** Persona 可编辑；通过 Coordinator 对脚本选段提问并触发内部分析。

| ID | 任务 |
|----|------|
| 3.1 | Persona CRUD、`active_persona_id`；字段对齐 pipeline §8 |
| 3.2 | `coordinator_messages` 持久化；`requested_perspectives` chips |
| 3.3 | quote、persona、script_version 写入消息元数据 |
| 3.4 | 脚本变更后，对**变动范围**触发增量分析（非全量重跑） |
| 3.5 | Coordinator 回复可关联 `related_node_ids` |
| 3.6 | SiliconFlow + ModelRouter（8B 对话 / 32B 结构化） |

**验收：** 选段提问 → 流式回复；Persona 修改后 Audience 相关 stale/再分析可感知。

---

### Phase 4 — IBIS Node Graph 工作区（pipeline §6–7）

**目标：** 在图中查看、编辑冲突；Coordinator 建议可落成节点。

| ID | 任务 |
|----|------|
| 4.1 | React Flow：Issue / Position / Argument / Reference；来源配色 | §3、§7 |
| 4.2 | 节点 CRUD；与脚本行双向跳转 | §7 |
| 4.3 | 选中文本「加入图为 Issue」；`created_by: user` | §6、§7 |
| 4.4 | Coordinator artifact：新/更新节点；不静默覆盖用户已确认节点 | §6 |
| 4.5 | Issue 状态：`open`、`resolved`、`needs_negotiation` 等 | §7 |
| 4.6 | **待协商列表** `negotiation_queue`：创作者将 Issue 加入 TO BE NEGOTIATED | §9 |

**验收：** 图中可见多立场 Argument；可标记待协商 Issue。

---

### Phase 5 — Expert 多方向修改方案（pipeline §10）

**目标：** 冲突或用户请求时，Expert 输出多个可选方向而非单一「正确答案」。

| ID | 任务 |
|----|------|
| 5.1 | `RevisionProposal`（或 `ModificationScheme`）含 `direction`：保守 / 平衡 / 创作者主导 / 观众友好 | §10 |
| 5.2 | 每方案：修改说明、针对 Issue、牺牲点、沟通场景、可能被质疑点、回应话术 | §10 |
| 5.3 | 可选 cell-level `hunks`；Diff overlay；逐 hunk 接受/拒绝 | 技术方案 §4.6 |
| 5.4 | apply 前校验 `removed`；apply 后 snapshot | 技术方案 §4.3 |
| 5.5 | 方案与 `target_issue_ids`、`related_node_ids` 绑定 | §10 |

**验收：** 同一 Issue 至少可见 2 种不同方向方案；应用 hunk 后脚本更新且可回退。

---

### Phase 6 — 品牌方分享与真实反馈（pipeline §9）

**目标：** 品牌方仅见脚本表；feedback 列驱动新一轮解析与节点。

| ID | 任务 |
|----|------|
| 6.1 | 生成只读 **share link**（仅 script 表格，无 Graph/Chat/Persona） | §9 |
| 6.2 | 分享视图启用 `feedback` 列（品牌方可编辑） | §9 |
| 6.3 | 创作者同步品牌 feedback 后，Brand Agent 解析明确/新增约束 | §9 |
| 6.4 | Expert 基于真实反馈生成新策略；新 IBIS 节点与旧节点对照 | §9 |
| 6.5 | 创作者将 Issue 加入待协商列表 | §9 |

**验收：** 品牌方链接仅见表格；feedback 回写后产生新节点或更新状态。

---

### Phase 7 — Negotiation Preparation 弹窗（pipeline §11）

**目标：** 创作者点击按钮生成协商材料，以 **弹窗** 展示（非 MVP 固定 Output Panel）。

| ID | 任务 |
|----|------|
| 7.1 | `POST .../outputs/negotiation/generate`；输入：脚本、图、Persona、待协商 Issue、方案摘要 | §11 |
| 7.2 | 输出：设计意图、已满足需求、分歧点、理由、让步空间、底线、话术、沟通顺序 | §11 |
| 7.3 | 前端 Modal；节点/脚本行跳转 | §11 |
| 7.4 | 脚本/图/方案变更 → 协商材料 `stale` | §11 |

**验收：** 一键生成弹窗内容；待协商 Issue 出现在材料中。

---

### Phase 8 — 整合、演示与答辩（pipeline §13）

| ID | 任务 |
|----|------|
| 8.1 | 端到端演示数据：Brief → 图 → 脚本 → 提问 → 方案 → 协商弹窗 | §13 |
| 8.2 | 证据链：Graph ↔ 脚本行 ↔ 方案（References 占位说明） | §12–13 |
| 8.3 | `ArtifactStaleness` 完整枚举与 UI badge | 技术方案 §5 |
| 8.4 | LangGraph 接入（可选） | 技术方案 §3 |
| 8.5 | README、错误态、全量验收勾选 | — |

---

## 7. 验收清单

### 7.1 Phase 0 — 主工作区

- [x] 无三个独立 Agent 面板
- [x] 统一 Coordinator Chat
- [x] Script Editor / Node Graph 可切换（Graph 可先占位）
- [x] Persona 独立入口
- [x] **无** MVP 要求的固定 Negotiation/References 侧栏

### 7.2 Phase 1 — Script Editor

- [x] 业务列可编辑；序号列不可编辑
- [x] 行/列增删（有确认与边界规则）
- [x] 时长校验与时间轴
- [x] 选中文本 → Coordinator quote
- [x] 脚本 PATCH debounce；`stale` 触发（图/方案/协商材料）
- [x] snapshot 列表 / restore API 壳

### 7.3 Phase 2 — Brief 与初始解析

- [ ] Brief MD/TXT/粘贴入库
- [ ] 初始 Persona 与 IBIS 节点生成
- [ ] 节点 `source_type` 可区分 Brand / Audience / Expert

### 7.4 Phase 3–4 — Coordinator + Graph + Persona

- [ ] Coordinator 消息持久化与 SSE
- [ ] Persona 编辑影响后续 Audience 分析
- [ ] 选段提问可产生或更新节点
- [ ] 图中编辑、删除、待协商标记

### 7.5 Phase 5–7 — 方案、品牌反馈、协商

- [ ] 多方向 Expert 方案可查看与部分应用
- [ ] 分享链接仅暴露脚本；feedback 回流
- [ ] Negotiation Preparation 弹窗内容完整

### 7.6 Phase 8 — 最终资产

- [ ] 可导出/展示：脚本 + 图 + Persona + 方案 + 协商材料
- [ ] References 明确标注为二期

---

## 8. 时间线（参考）

| 阶段 | 约周数 | 累计 | pipeline 步骤 |
|------|--------|------|---------------|
| P0 工作区 | 1–1.5 | 1.5 | §4 |
| P1 Script | 1.5–2 | 3.5 | §5 |
| P2 Brief+初始解析 | 1.5–2 | 5.5 | §1–3 |
| P3 Coordinator+Persona | 1–1.5 | 7 | §6、§8 |
| P4 Node Graph | 1.5–2 | 9 | §7 |
| P5 Expert 方案 | 1–1.5 | 10.5 | §10 |
| P6 品牌反馈 | 1 | 11.5 | §9 |
| P7 协商弹窗 | 0.5–1 | 12.5 | §11 |
| P8 整合 | 0.5–1 | 13.5 | §13 |

**关键路径：** P0 → P1 → P2（Brief+初始图）→ P3（Coordinator）→ P4（Graph）→ P5（方案）→ P7（协商）。

---

## 9. 测试策略

| 层 | 范围 |
|----|------|
| 后端单元 | 时长解析、上下文隔离、hunk 校验、stale 规则、share token 权限 |
| 后端集成 | Brief 解析任务、coordinator stream、graph CRUD、proposal apply、negotiation generate |
| 前端 | 时间轴、Graph、quote、协商弹窗、分享页只读脚本 |
| E2E（可选） | Brief → 初始图 → 写脚本 → Coordinator 提问 → 应用方案 → 生成协商弹窗 |

---

## 10. 暂缓项（MVP 不排期）

1. **References** 输出与固定 Output Panel（`pipeline.md` §12）  
2. Brief：PDF、DOC、DOCX、PPT 解析  
3. LangGraph checkpointer + PostgreSQL 全量迁移  
4. 平台语境完全由数据分析动态配置（MVP 可配置常量）  
5. 每次 cell 编辑自动生成 ScriptVersion  
6. 正式登录、多人实时协作、细粒度权限  

---

## 11. 风险与规避

| 风险 | 规避 |
|------|------|
| pipeline 与旧 PRD 表述冲突 | 以 `pipeline.md` 为准更新验收项 |
| Brand Wiki / 知识库未就绪 | Tavily + stub 接口；结构化字段先 mock |
| 分享链接泄露项目数据 | 仅 token 映射 script 快照；无 Graph API |
| 多方案 + hunk 复杂度高 | Phase 5 先文本方案，hunk 可子集交付 |
| LLM 成本 | brief 摘要、变动片段、按需调度 Agent |

---

## 12. 相关文档

- 系统流程：**`docs/pipeline.md`**
- 技术方案：**`docs/technical_plan.md`**
- 数据结构：`docs/data_structures.md`
- 产品需求：`docs/prd_new.md`
- 归档：`docs/development_plan_P0.md`、`docs/technical_plan_lightweight.md`
