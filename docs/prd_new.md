# PRD：Coordinator Agent 驱动的品牌合作视频脚本编辑与协商准备系统

## 1. 产品概述

### 1.1 产品定位

本系统是一个面向独立内容创作者的品牌合作视频脚本编辑、方案推理与协商准备工具。创作者在 Script Editor 中以表格形式编辑品牌合作视频脚本，并通过统一的 Coordinator Agent Chat 获取多视角反馈、修改方案、协商准备与参考依据。

系统前台不再拆分为品牌方 Agent、观众 Agent、专家 Agent 三个独立面板。品牌方视角、观众视角、专家视角作为 Coordinator Agent 背后的内部分析能力存在，由 Coordinator 统一调度、汇总和写入结构化状态。

产品核心原则：

1. 创作者始终保留脚本主导权。
2. AI 不直接覆盖脚本，只提供分析、建议、修改预览和解释。
3. 修改必须经过用户预览与确认后才写入 Script Editor。
4. 多视角分析不用于生成唯一答案，而是帮助创作者理解冲突、比较方案、准备与品牌方沟通。
5. 系统的重要推理过程需要结构化沉淀到 Node Graph，而不是只停留在聊天记录中。
6. Node Graph 使用 IBIS-inspired 结构组织问题、立场、论据与依据，帮助创作者追踪修改和协商理由。

### 1.2 目标用户

主要用户为独立视频创作者、自媒体博主、内容工作室成员，尤其是需要在品牌 brief、PR 反馈、观众接受度、平台内容风格和自我表达之间进行权衡的创作者。

### 1.3 核心场景

创作者收到品牌合作 brief 后，将 brief 上传或输入系统，并在 Script Editor 中整理视频脚本。Coordinator Agent 解析 brief、生成初始 persona、识别脚本中的潜在问题，并将关键问题写入 IBIS Node Graph。

创作者可以在脚本中选中文本向 Coordinator 提问，也可以在 Node Graph 中围绕某个 Issue 追问。Coordinator 根据任务调用内部的品牌方视角、观众视角和专家视角，输出：

1. 品牌方可能在意的问题。
2. 观众可能产生的理解、兴趣或反感。
3. 脚本修改方案与替代方案。
4. 支持或反对不同方案的理由。
5. 可以用于与品牌方沟通的解释话术。
6. 相关依据和参考资料。

### 1.4 本版 PRD 的主要变化

相较于旧版，本版做以下结构调整：

1. 取消前台三个独立 Agent 面板。
2. 统一为 Coordinator Agent Chat。
3. Script Editor 和 Node Graph 作为主工作区的两个可切换主面板。
4. 增加 Persona 面板入口，用于查看、编辑和切换目标观众 persona。
5. Negotiation Preparation 和 References 放入同一个输出面板，通过 tab 切换。
6. Node Graph 按 IBIS 结构划分节点：Issue、Position、Argument、Reference。
7. 节点颜色不表示节点类型，而表示 Issue 来源或视角来源。
8. 原 BrandInsight、AudienceAnalysis、ExpertSuggestion 的前台表达统一收敛到 Rationale Graph、Revision Proposal、Negotiation Output 和 Reference Output。

---

## 2. 信息架构与页面布局

### 2.1 整体页面结构

页面采用“主工作区 + Coordinator Chat + 输出/状态入口”的结构。

推荐布局：

```text
Topbar
┌──────────────────────────────────────────────────────────────┐
│ Project / Brief / Save Status / View Controls / Persona Entry │
└──────────────────────────────────────────────────────────────┘

Main Layout
┌───────────────────────────────────────┬──────────────────────┐
│ Main Workspace                         │ Coordinator Chat      │
│ ┌ Script Editor / Node Graph Toggle ┐  │                      │
│ │                                    │  │ Unified AI入口       │
│ │ Script Editor 或 IBIS Node Graph   │  │                      │
│ │                                    │  │                      │
│ └────────────────────────────────────┘  │                      │
├───────────────────────────────────────┴──────────────────────┤
│ Output Panel: Negotiation Preparation / References            │
└───────────────────────────────────────────────────────────────┘
```

也可以将 Output Panel 实现为右侧下半区、底部抽屉或可收起侧栏，但信息架构上 Negotiation Preparation 和 References 必须属于同一个 panel，并通过 tab 切换。

### 2.2 页面区域

页面包含：

1. Topbar。
2. Main Workspace：Script Editor / Node Graph 可切换。
3. Coordinator Agent Chat。
4. Persona Panel Entry。
5. Output Panel：Negotiation Preparation / References 可切换。
6. Selection Popup。
7. Revision Diff Overlay。
8. Node Detail Drawer。
9. Version History Drawer。

### 2.3 Topbar

#### 功能

1. 展示产品名称。
2. 上传品牌 Brief。
3. 显示已选 Brief 文件名与解析状态。
4. 编辑项目名称。
5. 切换主工作区视图：Script Editor / Node Graph。
6. 打开 Persona Panel。
7. 打开 Version History。
8. 显示保存状态。

#### 实现要求

1. 上传 Brief 后调用后端解析接口。
2. 支持文件类型：PDF、DOC、DOCX、TXT、MD、PPT、PPTX。
3. 解析完成后触发 Coordinator 的初始项目理解。
4. 初始项目理解应生成：品牌需求相关 Issue、初始 persona、潜在冲突 Issue、Reference 条目。
5. 项目名称应持久化到 Project 表。
6. 保存状态应与实际自动保存状态同步。

---

## 3. Main Workspace

Main Workspace 是系统的主工作区，包含两个可切换视图：Script Editor 和 Node Graph。

### 3.1 视图切换规则

1. 用户可以在 Script Editor 和 Node Graph 之间切换。
2. 两个视图共享同一个 project state。
3. Script Editor 中的脚本行可以关联 Node Graph 中的 Issue、Position、Argument 和 Reference。
4. Node Graph 中的节点可以跳转到相关脚本行或单元格。
5. 当脚本发生变化时，相关节点和输出需要标记为可能过期。

---

## 4. Script Editor 功能需求

### 4.1 表格视图

Script Editor 以表格形式组织视频脚本。

默认业务列：

| 列名 | 字段 key   | 输入类型             | 是否多行 | 是否默认保留 |
| -- | -------- | ---------------- | ---- | ------ |
| 时长 | duration | duration input   | 否    | 是      |
| 画面 | scene    | textarea         | 是    | 是      |
| 形式 | format   | input            | 否    | 是      |
| 备注 | notes    | input / textarea | 可配置  | 是      |

系统自动生成序号列，展示为 `#`，不属于业务列，不允许编辑和删除。

“反馈建议”不建议作为默认列保留。Agent 反馈应以评论、节点关联、Revision Proposal 或 Output Panel 的形式存在，避免和用户脚本正文混在同一个表格字段中。如果开发上需要保留，可作为可选列或 debug 字段，而不是 V1 默认业务列。

### 4.2 序号列规则

1. 序号列由系统自动生成。
2. 用户不能编辑序号。
3. 用户不能删除序号列。
4. 插入、删除、重排行后，序号自动更新。
5. 序号列不进入业务列定义，只由渲染层生成。

### 4.3 单元格编辑

功能规则：

1. 用户可以直接编辑任意业务单元格。
2. `画面` 默认使用多行输入。
3. `时长` 为特殊输入，有格式校验。
4. 任意单元格变更后，保存状态变为“编辑中”。
5. 任意单元格变更后，时间轴重新渲染。
6. 任意单元格变更后，相关 Rationale Nodes、Revision Proposals、Negotiation Preparation、References 标记为可能过期。
7. 后端接入后，应触发自动保存 debounce。

验收标准：

1. 用户可以修改任意业务列内容。
2. 序号列不可编辑。
3. 编辑后时间轴可更新。
4. 编辑后保存状态变化。
5. 刷新后内容能从后端恢复。
6. 编辑后相关 AI 输出显示 stale 提示。

### 4.4 行操作

#### 插入行

1. 每两行之间存在 hover band。
2. hover 后出现加号按钮。
3. 点击后在对应位置插入空行。
4. 表格最后也可插入新行。
5. 新行包含所有当前业务列。
6. 新行所有业务字段默认为空。
7. 插入后序号自动更新。
8. 插入后同步到脚本数据源。
9. 插入后标记相关输出过期。

#### 删除行

1. 点击行头序号按钮后选中行。
2. 选中行后出现“删行”按钮。
3. 删除前需要确认提示。
4. V1 不允许删除最后一行。
5. 删除后序号自动更新。
6. 删除后同步到后端。
7. 删除后标记相关输出过期。
8. 如果被删除行绑定了节点或 quote，需要在节点详情中提示“关联脚本行已删除”。

### 4.5 列操作

#### 插入列

1. 可以在任意业务列前后插入新列。
2. 新列 `column_id` 由系统生成。
3. 新列默认名为“新列”。
4. 新列默认类型为 `text`。
5. 后续应支持设置列类型，例如文本、多行文本、时长、标签。

#### 删除列

1. 序号列不可删除。
2. 业务列可删除。
3. 至少保留一个业务列。
4. 删除前需要确认提示。
5. 删除后所有行对应字段一并删除。
6. 删除后同步到后端。
7. 如果被删除列绑定了 quote、node 或 hunk，需要保留旧文本快照。

#### 列名重命名

1. 双击列名进入编辑状态。
2. Enter 保存。
3. Escape 取消。
4. 空列名不允许保存。
5. 列名变化不影响 `column_id`。

### 4.6 时长与时间轴

#### 时长格式

V1 统一支持以下格式：

```text
起始秒-结束秒
```

示例：

```text
0-5
5-40
40-60
```

#### 校验规则

1. 起始秒和结束秒必须为非负数字。
2. 结束秒必须大于起始秒。
3. 输入为空时不报错，但该行不进入时间轴。
4. 格式错误时在单元格内显示错误提示。
5. 格式错误时在时间轴下方显示总提示。
6. 格式错误的行不显示在时间轴中。

#### 时间轴规则

1. 每一行有效时长对应一个时间轴片段。
2. 片段 left = start / totalEnd。
3. 片段 width = (end - start) / totalEnd。
4. totalEnd 取所有有效行的最大 end。
5. hover 片段显示 tooltip。
6. tooltip 显示片段摘要、起止时间和持续秒数。
7. 如果两个或多个片段重叠，时间轴上显示重叠层。

### 4.7 选中文本询问 Coordinator

旧版浮层中的“问品牌 / 问观众 / 问专家”不再展开不同 Agent 面板，而是统一进入 Coordinator Chat。

#### 推荐交互

用户在表格 input 或 textarea 中选中文本后，出现 Selection Popup：

1. 问 Coordinator。
2. 从品牌方视角分析。
3. 从观众视角分析。
4. 从专家视角给修改方案。
5. 加入 Node Graph 作为 Issue。

点击任一入口后：

1. 右侧 Coordinator Chat 聚焦。
2. 被选中文本作为 quote tag 插入 Coordinator 输入区。
3. 若用户选择了具体视角，输入框自动带入分析视角标记。
4. 系统不会自动发送，用户可以继续补充问题。

#### quote 规则

1. quote 需要记录来源位置：`row_id`、`column_id`、`selection_start`、`selection_end`。
2. quote 需要记录 `script_version_id`。
3. quote 需要保留原文快照。
4. 如果 quote 对应脚本内容被修改，应提示该 quote 来自旧版本。
5. 一条消息可以包含多个 quote。

---

## 5. IBIS Node Graph 功能需求

### 5.1 功能定位

Node Graph 是系统的结构化推理区，用于组织脚本修改和协商准备中的问题、立场、论据和依据。

Node Graph 采用 IBIS-inspired 结构，不再将品牌需求、观众反馈、冲突点、修改方案和参考资料作为彼此独立的节点类型，而是统一表示为：

1. Issue。
2. Position。
3. Argument。
4. Reference。

其中，节点类型由形状或图标表示；节点颜色用于表示 Issue 来源或视角来源。

### 5.2 节点类型

| 节点类型      | 含义                      | 典型内容                               |
| --------- | ----------------------- | ---------------------------------- |
| Issue     | 当前需要讨论、判断、解决或协商的问题      | “如何在不破坏创作者风格的情况下突出产品卖点？”           |
| Position  | 对某个 Issue 的一种立场、解释或解决方案 | “保留生活化开头，在第二段自然引入产品”               |
| Argument  | 支持或反对某个 Position 的理由    | “这样能降低硬广感，但品牌露出会偏晚”                |
| Reference | 支撑 Argument 的依据         | brief 原文、persona、品牌资料、案例、平台规则、创作知识 |

### 5.3 视觉编码规则

| 视觉元素       | 表达含义                                                        |
| ---------- | ----------------------------------------------------------- |
| 节点形状 / 图标  | IBIS 节点类型：Issue、Position、Argument、Reference                 |
| 节点颜色       | Issue 来源或视角来源                                               |
| 边类型        | 节点关系：responds-to、supports、opposes、evidenced-by、derived-from |
| 节点标签       | 业务语义：品牌需求、观众反馈、修改方案、沟通准备、案例依据                               |
| 节点状态 badge | open、resolved、needs negotiation、deferred、dismissed          |

### 5.4 Issue 来源颜色

颜色不用于表示节点类型，而用于表示 Issue 来源。

推荐来源分类：

| Source              | 说明                         |
| ------------------- | -------------------------- |
| brand_brief         | 来自品牌 brief 的显性需求或约束        |
| brand_feedback      | 来自真实品牌方 PR 反馈或审片意见         |
| brand_inferred      | Coordinator 从品牌方视角推理出的隐性需求 |
| audience_persona    | 来自目标观众 persona 的偏好或反感点     |
| audience_simulation | 来自观众视角模拟反馈                 |
| creator_input       | 来自创作者主动提出的问题、坚持或创作意图       |
| expert_analysis     | 来自内容策略、短视频结构、营销逻辑等专家分析     |
| system_detected     | 系统综合多方信息后识别出的冲突            |
| external_reference  | 由案例、品牌资料、平台规则或其他资料触发       |

前端可以将颜色映射配置化，避免颜色语义写死在组件中。

### 5.5 节点关系

| 关系类型           | 方向                           | 含义                           |
| -------------- | ---------------------------- | ---------------------------- |
| responds_to    | Position → Issue             | 某个 Position 回应某个 Issue       |
| supports       | Argument → Position          | 某个 Argument 支持某个 Position    |
| opposes        | Argument → Position          | 某个 Argument 反对某个 Position    |
| evidenced_by   | Argument → Reference         | 某个 Argument 由某个 Reference 支撑 |
| derived_from   | Issue / Argument → Reference | 某个问题或理由来自某个依据                |
| refines        | Issue → Issue                | 一个 Issue 是另一个 Issue 的细化      |
| conflicts_with | Position → Position          | 两个方案存在取舍冲突                   |
| updates        | Node → Node                  | 新节点更新旧节点                     |

### 5.6 节点操作

用户可以：

1. 查看节点详情。
2. 编辑节点标题和内容。
3. 修改节点状态。
4. 删除节点。
5. 合并重复节点。
6. 将节点绑定到脚本行或单元格。
7. 将脚本选中文本创建为 Issue、Argument 或 Reference。
8. 从某个 Issue 请求 Coordinator 生成 Positions。
9. 从某个 Position 请求 Coordinator 生成支持/反对理由。
10. 将关键 Issue 发送到 Negotiation Preparation。

### 5.7 节点状态

| 状态                | 含义           |
| ----------------- | ------------ |
| open              | 尚未处理         |
| in_review         | 正在讨论或分析      |
| resolved          | 已通过脚本修改或决策解决 |
| needs_negotiation | 需要与品牌方确认或协商  |
| deferred          | 暂缓处理         |
| dismissed         | 用户判断不重要或不采用  |

### 5.8 节点与脚本联动

1. 节点可绑定一个或多个 script refs。
2. script ref 包含 `row_id`、`column_id`、文本快照、脚本版本。
3. 在 Script Editor 中点击行，可显示相关节点列表。
4. 在 Node Graph 中点击节点，可跳转到相关脚本行。
5. 当脚本内容变化后，相关节点显示 stale 或 changed badge。
6. 如果节点依据的是旧脚本版本，需要在详情中提示。

### 5.9 Node Graph 生成与更新

触发方式：

1. Brief 上传并解析完成后，Coordinator 自动生成初始 Issue 和 Reference。
2. 用户选中文本后选择“加入 Node Graph 作为 Issue”。
3. 用户在 Chat 中要求分析某段脚本。
4. Coordinator 识别到品牌、观众、创作者表达之间的冲突。
5. 用户输入真实品牌方反馈。
6. 用户编辑 persona 后重新分析观众视角。
7. 用户手动新增节点。

更新规则：

1. Coordinator 不应静默覆盖用户确认过的节点。
2. 若生成内容与已有节点高度相似，应建议合并或更新。
3. 用户手动编辑过的节点需要记录 `updated_by = user`。
4. 新生成节点需要记录来源、依据、脚本版本和置信度。

---

## 6. Coordinator Agent Chat 功能需求

### 6.1 功能定位

Coordinator Agent Chat 是所有 AI 交互的统一入口。用户不再与品牌方 Agent、观众 Agent、专家 Agent 三个前台面板分别对话，而是统一向 Coordinator 提问。

Coordinator 负责：

1. 理解用户问题。
2. 判断需要调用哪些内部视角。
3. 读取当前脚本、brief、persona、Node Graph 和 references。
4. 输出自然语言回答。
5. 生成或更新结构化 artifacts。
6. 将重要结论写入 Node Graph、Revision Proposal、Negotiation Preparation 或 References。

### 6.2 内部视角

Coordinator 背后保留以下内部能力，但不作为独立面板暴露：

| 内部能力                   | 作用                                |
| ---------------------- | --------------------------------- |
| Brand Perspective      | 解析 brief、推理隐性需求、模拟品牌方反馈、判断审片风险    |
| Audience Perspective   | 基于 persona 评价自然度、可信度、广告感、跳出风险和兴趣点 |
| Expert Perspective     | 综合多方信息生成修改方案、解释 trade-off、准备协商话术  |
| Reference Retriever    | 检索 brief、品牌资料、案例、创作知识或平台规则        |
| Rationale Graph Writer | 将重要分析写入 IBIS Node Graph           |
| Negotiation Writer     | 将关键 Issue 和 Position 转化为协商准备输出    |

### 6.3 Chat 输入区

输入区包含：

1. 文本输入框。
2. quote tag 列表。
3. 当前上下文提示，例如“正在询问第 3 行画面”。
4. 可选视角 chips：品牌方、观众、专家、综合。
5. 当前 persona 提示。
6. 发送按钮。

视角 chips 只是提示 Coordinator 的分析角度，不改变前台面板。

### 6.4 Chat 输出类型

Coordinator 的回复可以包含以下类型：

1. 普通自然语言分析。
2. Issue 建议。
3. Position / 修改方向。
4. Supporting / Opposing Arguments。
5. Reference 引用。
6. Revision Proposal。
7. Negotiation Preparation。
8. “写入 Node Graph”按钮。
9. “生成修改方案”按钮。
10. “加入协商准备”按钮。
11. “查看依据”按钮。

### 6.5 Chat 与 Node Graph 联动

1. Coordinator 识别出关键问题时，应提示是否写入 Node Graph。
2. 对于高置信度、明确来自 brief 的 Issue，可以自动写入 Node Graph，但需要标记来源。
3. 对于推理性较强的 Issue，应先显示为 suggested node，由用户确认后写入。
4. Chat 中的每条结构化输出应可追溯到对应节点或引用。

### 6.6 Chat 与 Script Editor 联动

1. Chat 回复可以引用具体脚本行。
2. 修改建议必须以 Revision Proposal 形式生成，不直接覆盖脚本。
3. 用户可以打开 diff overlay 预览修改。
4. 用户可以逐段接受或拒绝修改。
5. 写入后生成新 script version。

### 6.7 Chat 历史

1. 所有用户消息和 Coordinator 回复需要持久化。
2. 消息应保存引用的 quote。
3. 消息应保存本轮使用的 persona、script_version、selected nodes 和生成 artifacts。
4. 消息中可保存 internal trace id，但不需要向用户暴露完整内部调用链。

---

## 7. Persona Panel Entry

### 7.1 功能定位

Persona 不再作为观众 Agent Panel 的一部分，而是作为独立的状态管理入口存在。它用于查看、编辑和切换当前目标观众设定，并影响 Coordinator 进行观众视角分析时的上下文。

### 7.2 入口位置

Persona Panel Entry 可以放在：

1. Topbar。
2. Coordinator Chat header。
3. Node Graph 的 Persona Node 详情中。

推荐 Topbar 保留常驻入口，Chat header 显示当前 active persona。

### 7.3 Persona 功能

用户可以：

1. 查看当前 persona。
2. 新建 persona。
3. 编辑 persona。
4. 复制当前 persona 为新 persona。
5. 删除 persona。
6. 切换 active persona。
7. 根据 brief 和平台重新生成 persona。
8. 查看 persona 关联的 Issue 和 Argument。

### 7.4 Persona 字段

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

字段说明：

1. `age_range` 为 string，由用户自由填写，不做结构化枚举限制。
2. `preferences` 描述内容偏好。
3. `behavior` 描述生活行为和内容消费场景。
4. `ad_sensitivity` 描述对广告植入的敏感程度。
5. `trust_trigger` 描述触发信任的因素。
6. `reject_trigger` 描述触发反感的因素。

### 7.5 Persona 与 Node Graph 联动

1. 每个 persona 可以生成一个或多个 Reference Node。
2. Coordinator 基于 persona 生成的观众反馈应体现为 Argument 或 Issue。
3. persona 变更后，与旧 persona 相关的观众视角节点需要标记 stale。
4. 如果某个 Position 依赖旧 persona 的 Argument，相关 Position 也需要提示依据可能过期。

---

## 8. Output Panel：Negotiation Preparation / References

### 8.1 功能定位

Negotiation Preparation 和 References 放在同一个 Output Panel 中，通过 tab 切换。

该 panel 的定位是输出区，不是聊天区，也不是主编辑区。它用于承载 Coordinator 从脚本、Node Graph 和 references 中整理出的可复用结果。

### 8.2 Negotiation Preparation Tab

Negotiation Preparation 用于帮助创作者准备和品牌方正式沟通。

#### 输出内容

1. 品牌方可能质疑的问题。
2. 创作者可以如何解释当前创作选择。
3. 当前脚本中需要协商的 Issue。
4. 每个 Issue 对应的可选 Position。
5. 每个 Position 的支持理由和风险。
6. 哪些内容可以让步。
7. 哪些内容建议坚持。
8. 需要向品牌方确认的问题清单。
9. 可直接发送给品牌方的说明版本。
10. 与脚本行和 Node Graph 节点的关联。

#### 示例结构

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

### 8.3 References Tab

References 用于展示方案、论据和协商建议背后的依据。

#### 输出内容

1. brief 原文引用。
2. 真实 PR feedback 引用。
3. 品牌资料。
4. 产品资料。
5. 同领域视频案例。
6. 平台内容规则或创作规律。
7. persona 依据。
8. Node Graph 中 Reference Node 的详情。
9. 某个 Argument 或 Position 的证据链。

#### Reference Item 结构

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

### 8.4 Output Panel 与其他区域联动

1. 从 Negotiation Preparation 点击 Issue，可跳转到 Node Graph。
2. 从 Negotiation Preparation 点击脚本引用，可跳转到 Script Editor。
3. 从 References 点击引用，可查看来源详情。
4. Coordinator 生成修改方案时，应自动关联相关 References。
5. 用户可以从 Node Graph 的 Issue 一键生成 Negotiation Preparation。

---

## 9. Revision Proposal 与 Diff 机制

### 9.1 功能定位

Revision Proposal 是 Coordinator 或内部 Expert Perspective 生成的可执行修改方案。它不属于独立专家 Agent 面板，而是可以从 Chat、Node Graph 或 Negotiation Preparation 中触发和查看。

### 9.2 方案内容要求

每个方案必须包含：

1. 方案标题。
2. 目标 Issue。
3. 修改方向。
4. 具体修改内容。
5. 修改原因。
6. 对品牌方需求的影响。
7. 对观众体验的影响。
8. 对创作者表达的影响。
9. 潜在风险。
10. 面对品牌方质疑时的解释话术。
11. 关联的 Node Graph 节点。
12. 关联的 References。
13. cell-level diff hunks。

### 9.3 Revision Proposal 数据结构

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

### 9.4 Diff 预览规则

1. 打开 diff overlay。
2. 每个 hunk 直接绑定 `row_id` 和 `column_id`。
3. 用户可以逐段选择应用或不应用。
4. 用户可以全部应用。
5. 用户点击“写入编辑器”后，只应用已接受的 hunk。
6. 应用后生成新 script version。
7. 不能通过全文字符串重解析写回表格。
8. 应保留版本回退记录。

### 9.5 Hunk 状态

| 状态    | 含义  |
| ----- | --- |
| null  | 未决定 |
| true  | 应用  |
| false | 不应用 |

---

## 10. 数据结构建议

### 10.1 Project

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

### 10.2 BriefFile

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

### 10.3 ScriptVersion

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
        {
          "column_id": "col_001",
          "value": "0-5"
        },
        {
          "column_id": "col_002",
          "value": "开场画面"
        }
      ]
    }
  ],
  "created_reason": "manual_edit | revision_proposal_applied | import | rollback",
  "created_at": "datetime"
}
```

### 10.4 CoordinatorMessage

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

### 10.5 RationaleNode

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

### 10.6 RationaleEdge

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

### 10.7 Persona

沿用第 7.4 节数据结构。

### 10.8 ReferenceItem

沿用第 8.3 节数据结构。

### 10.9 NegotiationPreparation

沿用第 8.2 节数据结构。

### 10.10 RevisionProposal

沿用第 9.3 节数据结构。

### 10.11 ArtifactStaleness

旧版按 brand、audience、expert 三个前台 Agent 标记 stale。新版应按前台 artifact 标记 stale。

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

---

## 11. API 建议

### 11.1 Project / Brief

#### 创建项目

`POST /api/projects`

#### 更新项目

`PATCH /api/projects/{project_id}`

#### 上传 Brief

`POST /api/projects/{project_id}/brief`

返回：

```json
{
  "brief_file_id": "string",
  "project_id": "string",
  "filename": "string",
  "file_url": "string",
  "parse_status": "pending | parsing | parsed | failed",
  "parsed_text": "string"
}
```

#### 触发初始项目理解

`POST /api/projects/{project_id}/coordinator/initialize`

用途：解析 brief 后生成初始 persona、Reference、Issue 和潜在冲突。

### 11.2 Script Editor

#### 获取当前脚本

`GET /api/projects/{project_id}/script/current`

#### 更新单元格

`PATCH /api/projects/{project_id}/script/cells`

```json
{
  "script_version_id": "string",
  "row_id": "string",
  "column_id": "string",
  "value": "string"
}
```

#### 插入行

`POST /api/projects/{project_id}/script/rows`

```json
{
  "before_row_id": "string"
}
```

#### 删除行

`DELETE /api/projects/{project_id}/script/rows/{row_id}`

#### 插入列

`POST /api/projects/{project_id}/script/columns`

```json
{
  "before_column_id": "string",
  "label": "新列",
  "type": "text",
  "multiline": false
}
```

#### 删除列

`DELETE /api/projects/{project_id}/script/columns/{column_id}`

#### 重命名列

`PATCH /api/projects/{project_id}/script/columns/{column_id}`

```json
{
  "label": "新列名"
}
```

### 11.3 Coordinator Chat

#### 发送消息

`POST /api/projects/{project_id}/coordinator/messages`

```json
{
  "content": "string",
  "requested_perspectives": ["brand", "audience", "expert", "comprehensive"],
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
  "related_node_ids": ["string"]
}
```

#### 获取消息

`GET /api/projects/{project_id}/coordinator/messages`

#### 触发指定任务

`POST /api/projects/{project_id}/coordinator/run`

```json
{
  "task_type": "analyze_script | generate_issue | generate_positions | generate_arguments | generate_revision_proposals | generate_negotiation_preparation | retrieve_references",
  "target_node_ids": ["string"],
  "target_script_refs": [
    {
      "row_id": "string",
      "column_id": "string"
    }
  ],
  "active_persona_id": "string",
  "user_instruction": "string"
}
```

### 11.4 Persona

#### 获取 personas

`GET /api/projects/{project_id}/personas`

#### 新建 persona

`POST /api/projects/{project_id}/personas`

#### 更新 persona

`PATCH /api/projects/{project_id}/personas/{persona_id}`

#### 删除 persona

`DELETE /api/projects/{project_id}/personas/{persona_id}`

#### 切换 active persona

`PATCH /api/projects/{project_id}/active-persona`

```json
{
  "persona_id": "string"
}
```

### 11.5 Rationale Graph

#### 获取图

`GET /api/projects/{project_id}/rationale-graph`

#### 创建节点

`POST /api/projects/{project_id}/rationale-graph/nodes`

#### 更新节点

`PATCH /api/projects/{project_id}/rationale-graph/nodes/{node_id}`

#### 删除节点

`DELETE /api/projects/{project_id}/rationale-graph/nodes/{node_id}`

#### 创建边

`POST /api/projects/{project_id}/rationale-graph/edges`

#### 删除边

`DELETE /api/projects/{project_id}/rationale-graph/edges/{edge_id}`

#### 从脚本创建 Issue

`POST /api/projects/{project_id}/rationale-graph/issues/from-script-selection`

```json
{
  "quote": {
    "text": "string",
    "row_id": "string",
    "column_id": "string",
    "selection_start": 0,
    "selection_end": 10,
    "script_version_id": "string"
  },
  "source_type": "creator_input",
  "title": "string"
}
```

### 11.6 Revision Proposal / Diff

#### 获取方案

`GET /api/projects/{project_id}/revision-proposals`

#### 生成方案

`POST /api/projects/{project_id}/revision-proposals/generate`

#### 预览方案

`GET /api/projects/{project_id}/revision-proposals/{proposal_id}/preview`

#### 应用 hunk

`POST /api/projects/{project_id}/revision-proposals/{proposal_id}/apply`

```json
{
  "accepted_hunk_ids": ["string"],
  "rejected_hunk_ids": ["string"]
}
```

返回：

```json
{
  "new_script_version_id": "string",
  "applied_hunk_count": 3
}
```

### 11.7 Output Panel

#### 获取 Negotiation Preparation

`GET /api/projects/{project_id}/outputs/negotiation-preparation`

#### 生成 Negotiation Preparation

`POST /api/projects/{project_id}/outputs/negotiation-preparation/generate`

#### 获取 References

`GET /api/projects/{project_id}/outputs/references`

#### 添加 Reference

`POST /api/projects/{project_id}/outputs/references`

---

## 12. 前端状态管理建议

建议维护以下状态：

```ts
type AppState = {
  project: Project;
  script: ScriptVersion;

  layout: {
    mainView: 'script' | 'graph';
    coordinatorWidth: number;
    outputPanelOpen: boolean;
    outputPanelTab: 'negotiation' | 'references';
    personaPanelOpen: boolean;
    nodeDetailOpen: boolean;
    versionHistoryOpen: boolean;
  };

  editor: {
    selectedRowId?: string;
    selectedColumnId?: string;
    selectedText?: string;
    saveStatus: 'saved' | 'editing' | 'saving' | 'failed';
    durationErrors: Record<string, string>;
  };

  coordinator: {
    messages: CoordinatorMessage[];
    input: string;
    quotes: QuoteRef[];
    requestedPerspectives: Array<'brand' | 'audience' | 'expert' | 'comprehensive'>;
    isStreaming: boolean;
  };

  personas: {
    items: Persona[];
    activePersonaId?: string;
    modalMode: 'create' | 'edit' | null;
  };

  graph: {
    nodes: RationaleNode[];
    edges: RationaleEdge[];
    selectedNodeId?: string;
    filterSourceTypes: string[];
    filterNodeTypes: Array<'issue' | 'position' | 'argument' | 'reference'>;
  };

  revision: {
    proposals: RevisionProposal[];
    activeProposalId?: string;
    diffOverlayOpen: boolean;
    hunkState: Record<string, true | false | null>;
  };

  output: {
    negotiationPreparations: NegotiationPreparation[];
    references: ReferenceItem[];
  };

  stale: {
    rationaleGraph: string;
    revisionProposals: string;
    negotiationPreparation: string;
    references: string;
  };
};
```

---

## 13. Agent 编排建议

### 13.1 总体原则

建议使用 LangGraph 管理 Coordinator 与内部视角的状态流。

核心原则：

1. 前台只有 Coordinator Chat。
2. 内部可以保留 Brand Perspective、Audience Perspective、Expert Perspective 等节点。
3. 内部节点之间不直接传递大段自然语言，而是通过结构化 artifacts 传递。
4. 每个内部节点只读取必要上下文，避免上下文污染。
5. 重要结果写入业务数据库，而不是只存在 LangGraph State。
6. LangGraph State 是一次运行上下文，不替代业务数据库。

### 13.2 GraphState 建议

```python
class CoordinatorState(BaseModel):
    project_id: str
    brief_text: Optional[str] = None
    script: Optional[ScriptSnapshot] = None
    active_persona: Optional[PersonaSnapshot] = None

    trigger: Optional[TriggerSignal] = None

    # User-facing chat
    coordinator_messages: Annotated[list, add_messages] = Field(default_factory=list)

    # Structured artifacts
    rationale_nodes: list[RationaleNodeItem] = Field(default_factory=list)
    rationale_edges: list[RationaleEdgeItem] = Field(default_factory=list)
    references: list[ReferenceItem] = Field(default_factory=list)
    revision_proposals: list[RevisionProposalItem] = Field(default_factory=list)
    negotiation_preparation: Optional[NegotiationPreparationItem] = None

    # Internal perspective outputs
    brand_perspective_result: Optional[BrandPerspectiveResult] = None
    audience_perspective_result: Optional[AudiencePerspectiveResult] = None
    expert_perspective_result: Optional[ExpertPerspectiveResult] = None

    errors: list[str] = Field(default_factory=list)
```

### 13.3 TriggerSignal

```python
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
        "retrieve_references"
    ]
    user_message: Optional[str] = None
    requested_perspectives: list[Literal["brand", "audience", "expert", "comprehensive"]] = Field(default_factory=list)
    quotes: list[QuoteItem] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    active_persona_id: Optional[str] = None
```

### 13.4 推荐节点

1. `entry_node`：接收外部触发，拉取 project、brief、script、persona、graph 快照。
2. `task_router_node`：判断用户任务类型和需要的内部视角。
3. `brand_perspective_node`：处理 brief、品牌需求、品牌反馈、审片风险。
4. `audience_perspective_node`：基于 active persona 分析自然度、可信度、广告感和跳出风险。
5. `expert_perspective_node`：综合品牌、观众、创作者表达和内容策略生成方案。
6. `reference_retriever_node`：检索 brief、品牌资料、案例、平台规则和知识库。
7. `rationale_graph_writer_node`：将重要结论转换为 Issue、Position、Argument、Reference。
8. `revision_proposal_node`：生成 cell-level 修改方案。
9. `negotiation_writer_node`：生成协商准备输出。
10. `response_composer_node`：生成给用户看的 Coordinator 回复。
11. `persist_node`：持久化 messages、nodes、edges、references、proposals、outputs。
12. `stale_update_node`：更新 artifact stale 状态。

### 13.5 上下文隔离

1. Brand Perspective 可以读取 brief、品牌资料、真实 PR feedback、相关脚本片段，但不应读取无关 persona 细节。
2. Audience Perspective 可以读取 script、active persona、平台语境，但不应读取过多品牌内部推理，以避免污染观众视角。
3. Expert Perspective 可以读取 script、rationale graph、brand perspective result、audience perspective result、references。
4. Coordinator 可以读取所有前台可见 artifacts，用于生成整合回答。

### 13.6 持久化策略

1. `thread_id` 使用 `project_id`，一个项目对应一条 Coordinator 运行历史线。
2. LangGraph checkpointer 保存运行快照，便于恢复和调试。
3. 业务数据仍然写入 PostgreSQL。
4. 前端需要查询的结构化结果包括：CoordinatorMessage、RationaleNode、RationaleEdge、Persona、ReferenceItem、RevisionProposal、NegotiationPreparation、ScriptVersion。

---

## 14. Stale 更新规则

### 14.1 脚本变化

当 Script Editor 中任意 cell 被修改：

1. `rationale_graph = stale_script_changed`。
2. `revision_proposals = stale_script_changed`。
3. `negotiation_preparation = stale_script_changed`。
4. 与旧脚本绑定的 nodes 显示 stale badge。

### 14.2 Brief 变化

当 brief 被重新上传或解析结果更新：

1. `rationale_graph = stale_brief_changed`。
2. `references = stale_brief_changed`。
3. `revision_proposals = stale_graph_changed`。
4. `negotiation_preparation = stale_graph_changed`。

### 14.3 Persona 变化

当 active persona 被编辑或切换：

1. `rationale_graph = stale_persona_changed`。
2. `revision_proposals = stale_persona_changed`。
3. 与旧 persona 相关的 Argument 和 Reference 显示 stale badge。

### 14.4 Node Graph 变化

当用户新增、修改、删除 Issue / Position / Argument / Reference：

1. `revision_proposals = stale_graph_changed`。
2. `negotiation_preparation = stale_graph_changed`。
3. 如果修改的是 Reference Node，则 `references` 也可能 stale。

---

## 15. MVP 开发优先级

### P0：界面结构重构

1. 移除前台 Brand / Audience / Expert accordion 面板。
2. 新增统一 Coordinator Agent Chat。
3. Main Workspace 支持 Script Editor / Node Graph 切换。
4. 增加 Persona Panel Entry。
5. 增加 Output Panel，并支持 Negotiation Preparation / References tab 切换。
6. 保留 Script Editor 的基础表格编辑能力。

### P1：Script Editor 稳定化

1. 单元格编辑。
2. 行插入/删除。
3. 列插入/删除。
4. 列名重命名。
5. 时长校验。
6. 时间轴和重叠提示。
7. 选中文本 quote。
8. 自动保存。
9. 版本记录。

### P2：Persona 与 Coordinator Chat 接入

1. Persona CRUD。
2. active persona 切换。
3. Coordinator 消息发送与持久化。
4. quote tag 接入 Coordinator。
5. requested perspectives chips。
6. streaming response。
7. Chat 回复关联脚本行和节点。

### P3：IBIS Node Graph

1. RationaleNode / RationaleEdge 数据结构。
2. Issue / Position / Argument / Reference 节点渲染。
3. 节点颜色表示 Issue 来源。
4. 节点与脚本行绑定。
5. 节点增删改。
6. 从脚本选中文本创建 Issue。
7. Coordinator 自动生成 suggested nodes。
8. 节点状态管理。

### P4：Revision Proposal 与协商准备闭环

1. Coordinator 生成多个 Revision Proposals。
2. 每个方案包含 trade-off、风险、品牌解释话术。
3. Cell-level diff hunks。
4. 用户逐段应用/不应用。
5. 应用后生成新 script version。
6. Negotiation Preparation 生成。
7. References 生成和关联。
8. Output Panel 支持导出。

### P5：可追溯性与高级能力

1. Node Graph 与 References 的证据链展示。
2. 版本对比。
3. 回滚版本。
4. 多 persona 对比。
5. 节点合并与重复检测。
6. 更细粒度的上下文隔离和权限控制。

---

## 16. 关键验收标准

### 16.1 页面结构

1. 页面不再展示三个独立 Agent 面板。
2. 用户只能看到统一 Coordinator Agent Chat。
3. Script Editor 和 Node Graph 可以在主工作区切换。
4. Persona 有独立入口。
5. Negotiation Preparation 和 References 在同一个 panel 中通过 tab 切换。

### 16.2 Script Editor

1. 用户可以编辑表格中的脚本内容。
2. 序号列不可编辑、不可删除。
3. 用户可以在任意两行之间插入行。
4. 用户可以在任意两列之间插入列。
5. 用户可以删除普通行和普通列。
6. 用户不能删除最后一个业务列。
7. 用户不能删除最后一行。
8. 时长输入错误时能显示明确错误提示。
9. 时间轴能根据有效时长渲染。
10. 时间重叠能被标记出来。

### 16.3 Coordinator Chat

1. 用户选中文本后能将 quote 插入 Coordinator 输入框。
2. 用户可以选择品牌方、观众、专家或综合视角作为分析提示。
3. 用户发送消息后，消息能持久化。
4. Coordinator 回复能持久化。
5. Coordinator 能生成可写入 Node Graph 的结构化建议。
6. Coordinator 能生成 Revision Proposal，而不是直接改写脚本。

### 16.4 Persona Panel

1. 用户能新建 persona。
2. 用户能编辑 persona。
3. 用户能删除 persona。
4. 用户能切换 active persona。
5. `age_range` 为自由文本。
6. active persona 会影响 Coordinator 的观众视角分析。
7. persona 修改后，相关观众视角节点显示 stale。

### 16.5 IBIS Node Graph

1. Node Graph 至少支持 Issue、Position、Argument、Reference 四类节点。
2. 节点形状或图标能区分 IBIS 类型。
3. 节点颜色能表示 Issue 来源。
4. 用户能查看节点详情。
5. 用户能编辑、删除、确认节点。
6. 用户能将节点绑定到脚本行。
7. 用户能从脚本选中文本创建 Issue。
8. Coordinator 能自动建议 Issue、Position、Argument 和 Reference。
9. 节点能与 Negotiation Preparation 和 References 关联。

### 16.6 Output Panel

1. Negotiation Preparation 和 References 在同一个 panel 中。
2. 用户可以在两个 tab 之间切换。
3. Negotiation Preparation 能展示品牌方可能质疑、创作者解释、可让步/应坚持内容。
4. References 能展示 brief、persona、案例、品牌资料或创作知识依据。
5. Output Panel 中的内容可以跳转到相关 Node Graph 节点或脚本行。

### 16.7 Revision Proposal

1. Coordinator 能生成多个修改方案。
2. 每个方案包含理由、trade-off、风险和品牌解释话术。
3. 用户能预览方案 diff。
4. 用户能逐段应用或不应用。
5. 用户点击写入后，只应用已接受的 hunk。
6. 应用后生成新脚本版本。
7. 用户能回退到上一版本。

---

## 17. 当前原型需要优先修正的开发点

1. 移除右侧 Agent Accordion 的前台结构。
2. 将三个 Agent 的对话入口合并为 Coordinator Chat。
3. 将 Selection Popup 的行为改为向 Coordinator 插入 quote，而不是展开某个 Agent 面板。
4. 增加主工作区 view switch：Script Editor / Node Graph。
5. 新增 IBIS Node Graph 的基础数据模型和渲染。
6. 将原 pinned insights、audience analysis、expert suggestions 的前台表达迁移到 RationaleNode、RevisionProposal、NegotiationPreparation 和 References。
7. 增加 Persona Panel Entry，并保留 persona CRUD。
8. 将 Negotiation Preparation 和 References 整合为同一个 Output Panel 的两个 tab。
9. 专家 diff hunk 与表格 row/cell 绑定，不再依赖全文字符串重解析。
10. Brief 上传接入真实解析流程。
11. Coordinator mock 回复替换为真实 LLM / LangGraph 接口。
12. 所有结构化输出绑定 script_version_id。
13. 增加版本历史与回退。

---

## 18. 推荐技术实现

### 18.1 前端

建议：

1. Next.js / React。
2. 状态管理：Zustand。
3. 表格：当前自定义表格可继续，但需要 state-first 重构。
4. Node Graph：React Flow 或等价图编辑库。
5. Diff：保留 hunk 模型，但必须升级为 cell-level patch。
6. UI：保留当前暗色视觉风格。
7. Streaming：SSE 或 WebSocket。

### 18.2 后端

建议：

1. FastAPI。
2. PostgreSQL。
3. SQLModel / SQLAlchemy。
4. Redis 用于 Agent 任务状态、缓存和流式输出状态。
5. 文件解析服务处理 Brief。
6. LangGraph 编排 Coordinator 与内部视角节点。

### 18.3 数据持久化原则

1. Script table 以 JSON 结构保存。
2. 每次修改方案应用生成新版本。
3. 每条 Chat 消息、Node、Reference、Proposal、Preparation 都必须记录来源脚本版本。
4. 用户手动编辑和 Coordinator 生成内容都必须可追踪。
5. 前端可见的结构化结果必须写入业务表。
6. LangGraph checkpointer 仅用于运行恢复和调试，不替代业务数据表。

---

## 19. 一句话系统定义

本系统是一个以 Coordinator Agent 为统一入口、以 Script Editor 和 IBIS Node Graph 为主工作区的品牌合作视频脚本编辑与协商准备工具。它通过多视角内部推理帮助创作者识别脚本问题、比较修改立场、追踪支持与反对理由，并生成面向品牌沟通的协商准备和参考依据。
