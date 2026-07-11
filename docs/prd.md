# PRD：多视角 Agent 辅助的品牌合作视频脚本编辑系统

## 1. 产品概述

### 1.1 产品定位

本系统是一个面向独立内容创作者的品牌合作视频脚本编辑与协商准备工具。创作者在 Script Editor 中以表格形式编辑视频脚本，并通过品牌方 Agent、观众 Agent、专家 Agent 三个辅助面板，从品牌需求、观众接受度、内容创作策略三个角度获得反馈与修改建议。

产品核心原则：

1. 创作者始终保留脚本主导权。
2. AI 不直接覆盖脚本，只提供分析、建议、修改预览和解释。
3. 修改必须经过用户预览与确认后才写入编辑器。
4. 多 Agent 的目标不是生成唯一答案，而是帮助创作者理解冲突、权衡方案、准备协商。

### 1.2 目标用户

主要用户为独立视频创作者、自媒体博主、内容工作室成员，尤其是需要处理品牌 brief、PR 反馈、广告植入、观众接受度与自我表达之间冲突的创作者。

### 1.3 核心场景

创作者收到品牌合作 brief 后，将 brief 上传或输入系统，在表格化编辑器中整理视频脚本。品牌方 Agent 帮助拆解显性和隐性需求；观众 Agent 基于 persona 判断脚本是否自然、可信、有趣、广告感是否过强；专家 Agent 综合品牌方和观众反馈，生成多个可选修改方向，并提供面对品牌方质疑时的解释。

---

## 2. 当前原型功能总览

### 2.1 页面布局

当前页面采用三列 grid：

1. 左侧 Script Editor 主区域。
2. 中间竖向拖拽分割条。
3. 右侧 Agent 面板区域。

顶部为全局 Topbar，包括：

1. 产品名称：Creator Studio。
2. 上传品牌 Brief 按钮。
3. 品牌 Brief 文件名提示。
4. 可编辑项目名称。
5. 预览修改稿按钮。
6. 保存状态提示。

### 2.2 左侧 Script Editor

1. 表格视图。
2. 默认列：时长、画面、形式、备注、反馈建议。列名可以重命名。
3. 自动序号列，以 `#` 表头显示，不可编辑。
4. 行间插入按钮。
5. 列间插入按钮。
6. 选中行头后显示删除行按钮。
7. 选中列头后显示删除列按钮。
8. 时长输入校验。
9. 顶部时间轴可视化。
10. 时间段重叠提示。
11. 文本选中后出现【问品牌】【问观众】【问专家】浮层。

### 2.3 右侧 Agent 面板

Agent Panel 实现 accordion 结构：

1. 品牌方 Agent。
2. 观众 Agent。
3. 专家 Agent。

同一时间只展开一个面板。点击当前展开面板可以收起全部面板。

### 2.4 品牌方 Agent 当前功能

品牌方 Agent 包含：

1. 三个 pinned tab：显式需求、隐式需求、品牌反馈。
2. 每个 tab 中有可编辑条目。
3. 条目可以新增、删除、编辑。
4. 下方有对话区。
5. 支持从 Script Editor 选中文本后插入 quote tag。

### 2.5 观众 Agent 当前功能

观众 Agent 包含：

1. persona chip 列表。
2. 当前 persona 选择。
3. persona 新建弹窗。
4. persona 编辑弹窗。
5. persona 字段包括：名称、性别、年龄范围、喜好、生活行为（暂定，后续可能修改）。其中年龄范围 `age_range` 为 string，由用户自由填写，例如“18-24岁”“25岁左右”“大学生”“30+新手妈妈”，不做结构化枚举限制。
6. 对话区会根据当前 persona 显示欢迎语。
7. 支持从 Script Editor 选中文本后插入 quote tag。

### 2.6 专家 Agent 当前功能

专家 Agent 包含：

1. 专家 Agent 对话区。
2. 修改方向卡片。
3. 每一个方案支持预览修改。
4. 修改预览使用 diff overlay。
5. 用户可以逐段选择应用或不应用。
6. 支持全部应用。
7. 点击写入编辑器后，已选择的修改写入当前编辑器。

---

## 4. 信息架构与页面布局

### 4.1 页面区域

页面包含：

1. Topbar。
2. Script Editor 主工作区。
3. 可拖拽分割条。
4. Agent Accordion 面板。
5. Persona Modal。
6. Diff Overlay。
7. Selection Popup。
8. Hunk Popup。

### 4.2 Topbar

#### 功能

1. 展示产品名称。
2. 上传品牌 Brief。
3. 显示已选 Brief 文件名。
4. 编辑项目名称。
5. 打开专家修改预览。
6. 显示保存状态。

#### 后续实现要求

1. **仅提供「上传品牌 Brief」**，不提供「粘贴 Brief」入口（MVP）。
2. MVP 支持文件类型：**TXT、MD**；PDF、DOC、DOCX、PPT、PPTX 列入二期。
3. 上传并解析为文本后，**自动**执行品牌方 Agent 初始流水线：Agentic Search（Tavily + 内部 `llm-wiki` 品牌手册）→ 解析 **显式需求 / 隐式需求** → 写入 pinned 区对应 tab。
4. 项目名称应持久化到 Project 表。
5. 保存状态应与实际自动保存状态同步。

设计细则见 `docs/superpowers/specs/2026-05-19-phase-3-brand-agentic-search-design.md`。

---

## 5. Script Editor 功能需求

## 5.1 表格视图

### 5.1.1 当前默认列

| 列名   | 字段 key   | 输入类型     | 是否多行 |
| ---- | -------- | -------- | ---- |
| 时长   | duration | input    | 否    |
| 画面   | scene    | textarea | 是    |
| 形式   | format   | input    | 否    |
| 备注   | notes    | input    | 否    |
| 反馈建议 | feedback | textarea | 是    |

系统自动生成序号列，展示为 `#`，不属于业务列，不允许编辑和删除。

### 5.1.3 序号列规则

1. 序号列由系统自动生成。
2. 用户不能编辑序号。
3. 用户不能删除序号列。
4. 插入、删除、重排行后，序号自动更新。
5. 序号列不进入 `bizColumnDefs`，只由渲染层生成。

### 5.1.4 单元格编辑

功能规则：

1. 用户可以直接编辑业务单元格。
2. `画面` 和 `反馈建议` 为多行输入。
3. `时长` 为特殊输入，有格式校验。
4. 任意单元格变更后，保存状态变为“编辑中”。
5. 任意单元格变更后，时间轴重新渲染。
6. 任意单元格变更后，隐藏 textarea 同步更新。
7. 后续接入后端后，应触发自动保存 debounce。

验收标准：

* 用户可以修改任意业务列内容。
* 序号列不可编辑。
* 编辑后时间轴可更新。
* 编辑后保存状态变化。
* 刷新后内容应能从后端恢复。

---

## 5.2 行操作

### 5.2.1 插入行

当前交互：

1. 每两行之间存在一条 hover band。
2. hover 后出现加号按钮。
3. 点击后在对应位置插入空行。
4. 表格最后也可插入新行。

功能规则：

1. 新行包含所有当前业务列。
2. 新行所有业务字段默认为空。
3. 插入后序号自动更新。
4. 插入后应同步到脚本数据源。
5. 插入后应标记 Agent 输出可能过期。

### 5.2.2 删除行

当前交互：

1. 点击行头序号按钮后选中行。
2. 选中行后出现“删行”按钮。
3. 删除后重新渲染表格。
4. 当前原型不允许删除最后一行。

功能规则：

1. V1 保留“不允许删除最后一行”。
2. 删除前建议增加确认提示，避免误删。
3. 删除后序号自动更新。
4. 删除后应同步到后端。
5. 删除后应标记 Agent 输出可能过期。

---

## 5.3 列操作

### 5.3.1 插入列

当前交互：

1. 表头列边界位置有隐藏加号 hit area。
2. hover 后显示加号。
3. 点击后插入新列。
4. 新列默认名为“新列”。
5. 新列默认为单行 input。

功能规则：

1. 可以在任意业务列前后插入新列。
2. 新列 key 由系统生成。
3. 新列 label 默认为“新列”。
4. 新列默认 multiline = false。
5. 后续应支持编辑列名。
6. 后续应支持设置列类型，例如文本、多行文本、时长、标签。

### 5.3.2 删除列

当前交互：

1. 点击列头选中列。
2. 选中后显示“删除列”。
3. 点击后删除该业务列。
4. 至少保留一个业务列。

功能规则：

1. 序号列不可删除。
2. 业务列可删除。
3. 至少保留一个业务列。
4. 删除前建议增加确认提示。
5. 删除后所有行对应字段一并删除。
6. 删除后应同步到后端。

### 5.3.3 列名重命名

1. 双击列名进入编辑状态。
2. Enter 保存。
3. Escape 取消。
4. 空列名不允许保存。

---

## 5.4 时长与时间轴

### 5.4.1 当前时长格式

支持的主要格式：

1. `0-5`
2. `5-40`
3. `40-60`

时长语义为：起始秒-结束秒。

### 5.4.2 时间轴规则

1. 每一行有效时长对应一个时间轴片段。
2. 片段 left = start / totalEnd。
3. 片段 width = (end - start) / totalEnd。
4. totalEnd 取所有有效行的最大 end。
5. hover 片段显示 tooltip。
6. tooltip 显示片段摘要、起止时间和持续秒数。
7. 如果两个或多个片段重叠，时间轴上显示红色重叠层。

### 5.4.3 时长校验规则

有效格式：

```text
起始秒-结束秒
```

例如：

```text
0-5
5-40
40-60
```

校验规则：

1. 起始秒和结束秒必须为非负数字。
2. 结束秒必须大于起始秒。
3. 输入为空时不报错，但该行不进入时间轴。
4. 格式错误时在单元格内显示错误提示。
5. 格式错误时在时间轴下方显示总提示。
6. 格式错误的行不显示在时间轴中。

---

## 5.5 选中文本询问 Agent

### 5.5.1 当前交互

1. 用户在表格 input 或 textarea 中选中文本。
2. 选中文本长度大于 2 时出现浮层。
3. 浮层包含：问品牌、问观众、问专家。
4. 点击后展开对应 Agent 面板。
5. 被选中文本作为 quote tag 插入对应 Agent 输入区的文字末尾。
6. 系统不会自动发送，用户需要手动输入或点击发送。

### 5.5.2 后续实现规则

1. quote tag 需要记录来源位置：row_id、column_id、selection_start、selection_end。
2. 发送消息时，quote 与用户输入一起进入 Agent 上下文。
3. quote 需要保留原文快照，避免用户后续改动后上下文丢失。
4. 如果 quote 对应脚本内容被修改，应提示该 quote 来自旧版本。

---

## 6. 品牌方 Agent PRD

## 6.0 Brief 上传后的自动分析（MVP）

用户通过 Topbar **仅上传** Brief（`.md` / `.txt`）后，系统在后端自动完成：

1. 保存并解析 Brief 正文。
2. **Agentic Search：** 结合外部检索（规划使用 **Tavily API**）与内部 **`llm-wiki`** 品牌手册库（各品牌 Markdown 手册，按 `brand_slug` 组织）。
3. 将检索结果与 Brief 摘要组合为品牌方 Agent 的固定上下文。
4. 调用品牌方 Agent 生成结构化 **显式需求**、**隐式需求**，展示在 pinned 对应 tab；无需用户再点击「分析」。

重新上传 Brief 时，应重新执行上述流水线；用户手动编辑的 pinned 项按产品规则保留或提示覆盖。

## 6.1 当前前端结构

品牌方 Agent 当前包含：

1. Header：品牌方 Agent、状态 badge（含 Brief 解析 / 品牌分析进行中状态）。
2. Pinned 区：显式需求、隐式需求、品牌反馈三个 tab。
3. Pinned item：文本可编辑、可删除；初始显式/隐式项由上传 Brief 后的自动分析填充。
4. 新增按钮：添加需求/添加反馈。
5. Chat 区。
6. Quote tag 区。
7. Input + Send。
8. （建议）可展开查看本次 **品牌检索依据**（wiki 片段 / 网页摘要）。

## 6.2 pinned 数据结构

结构化 insight：

```json
{
  "insight_id": "string",
  "agent_type": "brand",
  "category": "explicit_requirement | implicit_requirement | brand_feedback",
  "title": "string",
  "content": "string",
  "reason": "string",
  "evidence": [
    {
      "source_type": "brief | pr_feedback | script | chat | web | brand_wiki",
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

## 6.4 前端展示建议

当前 pinned item 只展示 content。建议 V1 在不增加太多视觉复杂度的前提下新增：

1. hover 展开 reason。
2. 小标签展示 confidence。
3. 小标签展示 status。
4. 点击条目打开详情 popover，显示 evidence。
5. 用户可以标记：确认、待确认、忽略。

## 6.5 品牌方 Agent 对话需求

用户可以：

1. 询问某条显式需求的依据。
2. 追问某条隐式需求为什么重要。
3. 粘贴真实品牌方 PR 反馈。
4. 要求 Agent 从品牌方角度看某段脚本。
5. 要求 Agent 判断某个修改方案是否容易通过审片。

Agent 应输出：

1. 自然语言回复。
2. 可能新增或更新的 structured insights。
3. 更新依据。
4. 对专家 Agent 的 stale 通知。

---

## 7. 观众 Agent PRD

## 7.1 当前前端结构

观众 Agent 当前包含：

1. Header：观众 Agent、状态 badge。
2. Persona bar。
3. Persona chips。
4. Persona 编辑按钮。
5. 新增 persona 按钮。
6. Persona modal。
7. Chat 区。
8. Quote tag 区。
9. Input + Send。

## 7.2 当前 persona 字段

当前字段包括：

1. id。
2. icon。
3. name。
4. gender。
5. age_range。
6. preferences。
7. behavior。

其中 `age_range` 为 string，由用户自行填写，不做结构化枚举限制。示例包括：“18-24岁”“25岁左右”“大学生”“30+新手妈妈”“年轻职场人”。

## 7.3 建议 V1 数据结构

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

字段说明：`age_range` 不使用固定枚举，用户可自由填写年龄段或人群描述。系统仅将其作为 persona 描述文本注入观众 Agent prompt，不做数值范围校验。

## 7.4 Persona 管理功能

1. 新建 persona。
2. 编辑当前 persona。
3. 另存为新 persona。
4. 切换当前 persona。
5. 删除 persona。

## 7.5 观众 Agent 分析维度

观众 Agent 应基于当前 persona 输出结构化分析结果，并持久化为独立的 `AudienceAnalysis` 实体，而不是只存在于聊天消息中。这样专家 Agent 可以稳定读取最近一次或指定版本的观众分析结果。

观众 Agent 分析维度包括：

1. 自然度。
2. 趣味性。
3. 可信度。
4. 广告感。
5. 跳出风险。
6. 观众可能喜欢的片段。
7. 观众可能反感的片段。
8. 修改建议。

建议结构：

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

其中 `liked_parts` 和 `rejected_parts` 需要绑定 `row_id`，方便前端高亮对应脚本段落，也方便专家 Agent 生成 cell-level 修改方案。

## 7.6 触发机制

触发方式：

1. 用户在观众 Agent 对话框发送问题。
2. 用户选中文本后点击【问观众】。
3. 建议支持多 persona 对比分析。

---

## 8. 专家 Agent PRD

## 8.1 当前前端结构

专家 Agent 当前包含：

1. Header：专家 Agent、状态 badge。
2. Chat 区。
3. Proposal cards。
4. Quote tag 区。
5. Input + Send。
6. Diff overlay。
7. Hunk popup。

## 8.2 修改方案卡片

1. 方案标题。
2. 方案描述。
3. 预览修改按钮。

## 8.3 建议 V1 方案数据结构

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
  "based_on_audience_insight_ids": ["string"],
  "status": "draft | previewed | partially_applied | applied | dismissed",
  "created_at": "datetime"
}
```

## 8.4 Diff 预览机制

当前原型使用 `DIFF_SEGMENTS`：

```js
[
  { type: 'text', text: '...' },
  { type: 'hunk', id, context, removed, added },
  ...
]
```

该模型适合 V1 继续使用，但后端应返回更结构化的 hunks，并与表格行列绑定。

### 8.4.1 Hunk 状态

每个 hunk 有三种状态：

| 状态    | 含义  |
| ----- | --- |
| null  | 未决定 |
| true  | 应用  |
| false | 不应用 |

### 8.4.2 用户操作

1. 打开 diff overlay。
2. 悬停彩色改动。
3. hunk popup 显示【应用】【不应用】。
4. 用户可逐段选择。
5. 用户可点击【全部应用】。
6. 用户点击【写入编辑器】。
7. 系统根据 hunk state 拼接最终结果。
8. 写入 Script Editor。

### 8.4.3 后续需要修正

当前 commitDiff 会将结果写入隐藏 textarea，再通过旧文本解析回表格。正式开发中不建议继续这样做。

正式实现应：

1. hunk 直接绑定 row_id 和 column_id。
2. 应用 hunk 时只更新对应 cell。
3. 避免将全文文本再解析回表格造成结构损失。
4. 应用后生成新 script version。
5. 保留可回退记录。

## 8.5 专家方案内容要求

每个方案必须包含：

1. 修改方向。
2. 解决的问题。
3. 具体修改内容。
4. 修改原因。
5. 对品牌方需求的影响。
6. 对观众体验的影响。
7. 对创作者表达的影响。
8. 潜在风险。
9. 面对品牌方质疑时的解释话术。

当前原型卡片较简洁，建议在卡片中增加【查看理由】或【展开详情】。

---

## 9. Agent 联动机制

## 9.1 当前状态

当前原型中：

1. 品牌方或观众 Agent 回复后，会调用 `updateExpert()`。
2. 专家 Agent badge 变为“有新输入 ●”。
3. 这已经符合“半自动重新分析”的方向。

## 9.2 推荐 V1 机制

V1 采用用户触发重新分析，不自动生成完整专家方案。

规则：

1. Brand Agent insight 更新后，Expert Agent 标记为 stale。
2. Audience Agent feedback 更新后，Expert Agent 标记为 stale。
3. Script Editor 更新后，所有 Agent 结果都可能 stale。
4. Expert Agent 面板显示“有新输入”。
5. 用户点击【重新生成方案】后调用专家 Agent。

### 9.3 stale 状态

```json
{
  "project_id": "string",
  "brand": "up_to_date | stale_script_changed | generating | failed",
  "audience": "up_to_date | stale_script_changed | stale_persona_changed | generating | failed",
  "expert": "up_to_date | stale_script_changed | stale_brand_changed | stale_audience_changed | generating | failed",
  "updated_at": "datetime"
}
```

其中 `stale_persona_changed` 表示当前观众分析基于旧 persona；当用户编辑或切换 persona 后，需要标记 audience 结果过期。

---

## 10. 数据结构建议

## 10.1 Project

Project 保存项目级元数据，不直接保存 Brief 解析正文。Brief 文件和解析结果由独立 `BriefFile` 实体管理，Project 只引用当前使用的 Brief。

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
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

字段说明：

* `owner_id`：项目所属用户 ID，预留多用户和登录体系。
* `current_brief_file_id`：当前项目使用的 BriefFile ID。后续如果支持重新上传 brief，可以切换该引用。
* `current_script_version_id`：当前正在编辑的脚本版本。

## 10.2 BriefFile

BriefFile 是独立实体，用于追踪上传文件、解析状态和解析文本。解析是异步过程，因此不应只作为 Project 的两个字段保存。

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

字段说明：

* `brief_file_id`：Brief 文件唯一 ID。
* `file_url`：原始文件存储地址。
* `parse_status`：解析状态，用于前端展示进度和失败提示。
* `parsed_text`：解析后的文本，供品牌方 Agent 使用。

## 10.3 ScriptVersion

ScriptVersion 保存表格脚本的一个版本。由于用户可以动态增删列，`rows.cells` 必须通过 `column_id` 关联列定义，而不是使用固定 key object。

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

字段说明：

* `columns`：列定义，负责控制列名、类型、顺序和可编辑性。
* `rows.cells`：单元格数组，通过 `column_id` 与列定义关联，适配动态列。
* `created_reason`：版本来源，用于版本历史解释和回退。

## 10.4 AgentMessage

AgentMessage 保存用户与不同 Agent 的对话。`quotes` 使用数组，支持用户在同一条消息中引用多个脚本片段。

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

字段说明：

* `quotes`：引用片段列表。每个 quote 保存文本快照和来源位置。
* `script_version_id`：quote 来自哪个脚本版本，用于判断该引用是否过期。

## 10.5 BrandInsight

BrandInsight 对应品牌方 Agent pinned 区中的显式需求、隐式需求和品牌反馈。

```json
{
  "insight_id": "string",
  "project_id": "string",
  "category": "explicit_requirement | implicit_requirement | brand_feedback",
  "content": "string",
  "reason": "string",
  "evidence": [
    {
      "source_type": "brief | pr_feedback | script | chat | web | brand_wiki",
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

字段说明：

* `updated_by`：记录最后一次修改来自用户还是 Agent，便于追踪 pinned insight 的来源。
* `evidence`：保存判断依据，支持详情 popover 和专家 Agent 溯源。

## 10.6 Persona

Persona 是观众 Agent 的分析依据。`age_range` 为 string，由用户自由填写，不使用固定枚举，也不做结构化年龄范围校验。

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

* `age_range`：用户自由填写的人群年龄或阶段描述，例如“18-24岁”“25岁左右”“大学生”“年轻职场人”。
* `preferences`：内容偏好。
* `behavior`：生活行为和典型使用场景。
* `trust_trigger` / `reject_trigger`：触发信任或反感的因素。

## 10.7 AudienceAnalysis

AudienceAnalysis 是观众 Agent 的结构化分析结果，独立持久化，供专家 Agent 读取和版本对比使用。

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

字段说明：

* `persona_id`：该分析基于哪个 persona。
* `based_on_script_version_id`：该分析基于哪个脚本版本。
* `liked_parts` / `rejected_parts`：绑定具体 `row_id`，用于表格高亮和专家方案生成。

## 10.8 ExpertSuggestion

ExpertSuggestion 是专家 Agent 生成的修改方案。方案需要绑定它依赖的品牌 insight 和观众分析，以支持 stale 判断。

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

字段说明：

* `based_on_audience_analysis_ids`：记录方案使用了哪些观众分析结果。
* `hunks`：cell-level 修改单元，正式实现时应直接更新对应 row/cell，而不是全文重解析。

## 10.9 AgentStaleness

AgentStaleness 保存各 Agent 输出是否已过期。

```json
{
  "project_id": "string",
  "brand": "up_to_date | stale_script_changed | generating | failed",
  "audience": "up_to_date | stale_script_changed | stale_persona_changed | generating | failed",
  "expert": "up_to_date | stale_script_changed | stale_brand_changed | stale_audience_changed | generating | failed",
  "updated_at": "datetime"
}
```

---

## 11. API 建议

## 11.1 Project / Brief

### 创建项目

`POST /api/projects`

### 更新项目名称

`PATCH /api/projects/{project_id}`

### 上传 Brief

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

解析过程可以异步执行。解析完成后，Project 的 `current_brief_file_id` 指向该 BriefFile。

轻量 MVP（`technical_plan_lightweight.md`）将 Brief 嵌入 `project.brief`，解析成功后 **服务端自动** 执行 `BrandBriefPipeline`（Agentic Search + 显式/隐式需求分析），前端无需再调用分析接口。

### 手动重新分析（可选）

`POST /api/projects/{project_id}/agents/brand/analyze-brief`

用于 Brief 已存在时用户主动「重新跑一遍」品牌检索与需求拆解。

---

## 11.2 Script Editor

### 获取当前脚本

`GET /api/projects/{project_id}/script/current`

### 更新单元格

`PATCH /api/projects/{project_id}/script/cells`

```json
{
  "script_version_id": "string",
  "row_id": "string",
  "column_id": "string",
  "value": "string"
}
```

说明：由于 `rows.cells` 使用 `{ column_id, value }` 数组保存，更新单元格时必须使用 `column_id` 定位，不依赖列名或固定 key。

### 插入行

`POST /api/projects/{project_id}/script/rows`

```json
{
  "before_row_id": "string"
}
```

### 删除行

`DELETE /api/projects/{project_id}/script/rows/{row_id}`

### 插入列

`POST /api/projects/{project_id}/script/columns`

```json
{
  "before_column_id": "string",
  "label": "新列",
  "type": "text",
  "multiline": false
}
```

### 删除列

`DELETE /api/projects/{project_id}/script/columns/{column_id}`

### 重命名列

`PATCH /api/projects/{project_id}/script/columns/{column_id}`

```json
{
  "label": "新列名"
}
```

---

## 11.3 Agent

### 发送消息

`POST /api/projects/{project_id}/agents/{agent_type}/messages`

```json
{
  "content": "string",
  "quotes": [
    {
      "text": "string",
      "row_id": "string",
      "column_id": "string",
      "script_version_id": "string"
    }
  ],
  "persona_id": "string"
}
```

### 获取消息

`GET /api/projects/{project_id}/agents/{agent_type}/messages`

### 获取品牌 insight

`GET /api/projects/{project_id}/agents/brand/insights`

### 更新品牌 insight

`PATCH /api/projects/{project_id}/agents/brand/insights/{insight_id}`

### 创建品牌 insight

`POST /api/projects/{project_id}/agents/brand/insights`

### 删除品牌 insight

`DELETE /api/projects/{project_id}/agents/brand/insights/{insight_id}`

### 观众分析

`POST /api/projects/{project_id}/agents/audience/analyze`

### 专家方案生成

`POST /api/projects/{project_id}/agents/expert/suggestions/generate`

---

## 11.4 Expert Suggestion / Diff

### 获取专家方案

`GET /api/projects/{project_id}/agents/expert/suggestions`

### 预览方案

`GET /api/projects/{project_id}/agents/expert/suggestions/{suggestion_id}/preview`

### 应用 hunk

`POST /api/projects/{project_id}/agents/expert/suggestions/{suggestion_id}/apply`

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

---

## 12. 前端状态管理建议

建议维护以下状态：

```ts
type AppState = {
  project: Project;
  script: ScriptVersion;
  editor: {
    selectedRowId?: string;
    selectedColumnId?: string;
    selectedText?: string;
    saveStatus: 'saved' | 'editing' | 'saving' | 'failed';
  };
  layout: {
    agentsColWidth: number;
    activePanel: 'brand' | 'audience' | 'expert' | null;
  };
  brand: {
    insights: BrandInsight[];
    messages: AgentMessage[];
    activePinnedTab: 0 | 1 | 2;
  };
  audience: {
    personas: Persona[];
    activePersonaId?: string;
    analyses: AudienceAnalysis[];
    activeAnalysisId?: string;
    messages: AgentMessage[];
    modalMode: 'create' | 'edit' | null;
  };
  expert: {
    suggestions: ExpertSuggestion[];
    messages: AgentMessage[];
    activeSuggestionId?: string;
    diffOverlayOpen: boolean;
    hunkState: Record<string, true | false | null>;
  };
  stale: {
    brand: string;
    audience: string;
    expert: string;
  };
};
```

---

## 13. Agent 编排建议

建议使用 LangGraph 管理多 Agent 状态流。核心原则是：Agent 之间不直接调用彼此，而是通过共享 State 中的结构化字段传递结果。

### 13.1 State 设计原则

1. State 是一次图运行的共享上下文，不替代业务数据库。
2. 每个 Agent 只读取自己需要的字段，只写自己负责的字段。
3. State 保存的是快照和增量，不是无序堆叠的聊天记录。
4. Brand Agent 输出 `brand_insights`，Audience Agent 输出 `audience_analysis`，Expert Agent 从 State 中读取这些结构化结果。
5. 跨 Agent 通知通过 stale 标记完成，不自动串联触发完整下游生成。

### 13.2 GraphState 字段建议

```python
class CreatorStudioState(BaseModel):
    project_id: str
    brief_text: Optional[str] = None

    # 脚本快照：由 entry/load 节点从数据库拉取，Agent 节点只读
    script: Optional[ScriptSnapshot] = None

    # 本次外部触发信号
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

    errors: list[str] = Field(default_factory=list)
```

其中 `brand_messages`、`audience_messages`、`expert_messages` 使用 LangGraph 的 `add_messages` reducer。节点每次只返回新增消息，LangGraph 自动追加和去重。

### 13.3 TriggerSignal

前端每次触发 Agent 行为时，都应构造触发信号。

```python
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
```

注意：`quotes` 是数组，支持同一轮消息引用多个脚本片段。

### 13.4 节点设计

推荐节点：

1. `entry_node`：接收外部触发，设置 trigger，拉取 project、brief、script 快照。
2. `router_node`：根据 `trigger.agent` 分发到 brand / audience / expert。
3. `brand_agent_node`：处理品牌方 Agent 的分析和对话，输出 `brand_insights` 与 `brand_messages`。
4. `audience_agent_node`：处理观众 Agent 的分析和对话，输出 `audience_analysis` 与 `audience_messages`。
5. `expert_agent_node`：读取 script、brand_insights、audience_analysis，生成 `expert_suggestions`。
6. `persist_node`：将 State 中的新消息、insights、analysis、suggestions 写入业务数据库。
7. `stale_update_node`：根据本次更新内容设置其他 Agent 的 stale 标记。

### 13.5 Agent 之间的消息传递方式

Agent 之间不直接传自然语言消息，而是通过 State 中的结构化 artifact 传递。

推荐传递链路：

```text
Brief / Script
  ↓
Brand Agent → brand_insights
  ↓
Expert Agent 读取 brand_insights

Script / Persona
  ↓
Audience Agent → audience_analysis
  ↓
Expert Agent 读取 audience_analysis
```

不推荐：

```text
Brand Agent 的聊天回复 → 直接拼进 Expert Agent prompt
Audience Agent 的聊天回复 → 直接拼进 Expert Agent prompt
```

推荐：

```text
Brand Agent 聊天回复 + structured brand_insights
Audience Agent 聊天回复 + structured audience_analysis
Expert Agent 只优先读取结构化结果
```

这样可以降低上下文污染，提高可调试性，也方便做 stale 判断。

### 13.6 Brand Agent 节点

**Brief 上传触发（`trigger.reason = brief_uploaded`）** 在对话前执行：

1. Agentic Search：`llm-wiki` 品牌手册 + Tavily Web Search。
2. 写入 `brand_research`（queries、snippets、research_summary）。
3. 基于 Brief + 检索上下文生成显式/隐式 `brand_insights`。

**对话轮次** 输入：

1. `brief_text` / `brief_summary`。
2. `brand_research`（摘要与 Top-K 片段）。
3. `brand_insights`（已有 pinned 结构化结果）。
4. `script`（按需：quote 相关行或概要）。
5. 用户本轮消息。
6. `quotes`。
7. `brand_messages` 历史。

输出：

1. 显式需求。
2. 隐式需求。
3. 品牌反馈（多由用户 PR 输入或对话产生）。
4. evidence（`source_type` 含 `brief`、`web`、`brand_wiki` 等）。
5. reason。
6. confidence。
7. 新的 brand message。
8. `expert_stale = True`。

### 13.7 Audience Agent 节点

输入：

1. `script`。
2. `quotes`。
3. `active_persona_id`。
4. audience chat history。

输出：

1. `audience_analysis`。
2. 自然度评价。
3. 广告感评价。
4. 可信度评价。
5. 跳出风险。
6. 修改建议。
7. 新的 audience message。
8. `expert_stale = True`。

### 13.8 Expert Agent 节点

输入：

1. `script`。
2. `brand_insights`。
3. `audience_analysis`。
4. `quotes`。
5. 用户本轮要求。
6. expert chat history。

输出：

1. 多个方案卡片。
2. 方案理由。
3. trade-off。
4. explanation_to_brand。
5. cell-level hunks。
6. 新的 expert message。
7. `expert_stale = False`。

### 13.9 stale 更新规则

1. 脚本变更后：`brand_stale = true`，`audience_stale = true`，`expert_stale = true`。
2. persona 被编辑或切换后：`audience_stale = true`，如果已有专家方案依赖旧 audience analysis，则 `expert_stale = true`。
3. Brand Agent 更新 `brand_insights` 后：`expert_stale = true`。
4. Audience Agent 更新 `audience_analysis` 后：`expert_stale = true`。
5. Expert Agent 重新生成方案后：`expert_stale = false`。

### 13.10 State 持久化策略

LangGraph State 可以使用 PostgreSQL checkpointer 保存运行快照。业务数据仍然需要写入业务数据库。

建议：

1. `thread_id` 使用 `project_id`，一个项目对应一条 LangGraph 运行历史线。
2. checkpointer 保存图运行状态，便于恢复和调试。
3. `BrandInsight`、`AudienceAnalysis`、`ExpertSuggestion`、`AgentMessage` 等需要前端查询的结构化结果，仍然写入业务表。

---

## 14. MVP 开发优先级

## P0：将当前静态原型工程化

1. 拆分 React/Next.js 组件。
2. 将 inline JS 改为状态驱动。
3. 将表格数据从 DOM 读取改为 state source of truth。
4. 将 hidden textarea 移除或降级为 debug。
5. 实现项目、脚本、persona、insight 的后端持久化。
6. 实现自动保存。
7. 保留当前 UI 样式和核心交互。

## P1：Script Editor 稳定化

1. 单元格编辑。
2. 行插入/删除。
3. 列插入/删除。
4. 列名重命名。
5. 时长校验。
6. 时间轴和重叠提示。
7. 选中文本 quote。
8. 版本记录。

## P2：Agent 接入

1. Brief 上传和文本解析。
2. Brand Agent 结构化输出。
3. Brand pinned insight 后端化。
4. Persona CRUD。
5. Audience Agent 主动分析。
6. Agent streaming response。
7. Agent 消息持久化。

## P3：专家方案闭环

1. Expert Agent 多方案生成。
2. 每个方案包含完整理由和 trade-off。
3. Cell-level diff hunks。
4. 逐段应用/不应用。
5. 应用后生成新 script version。
6. 回退版本。
7. stale 状态联动。

---

## 15. 关键验收标准

### 15.1 Script Editor

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

### 15.2 Agent 交互

1. 用户选中文本后能出现问 Agent 浮层。
2. 点击问品牌/问观众/问专家后，对应 Agent 面板展开。
3. 选中文本能作为 quote tag 插入对应输入区。
4. 用户发送消息后，消息能持久化。
5. Agent 回复能持久化。

### 15.3 品牌方 Agent

1. Topbar **仅有** 上传 Brief，**无** 粘贴 Brief。
2. 上传 `.md`/`.txt` 并解析成功后，**自动** 填充显式需求、隐式需求 pinned 项（或展示明确失败/进行中状态）。
3. 能展示显式需求、隐式需求、品牌反馈三 tab。
4. 用户能编辑、新增、删除 pinned insight。
5. 每条 insight 后端都有 reason/evidence/confidence/status；自动生成的项 evidence 可指向 brief、web 或 brand_wiki。
6. 品牌分析使用了 Agentic Search（内部手册和/或 Tavily）；依据可在产品内查看或于对话中追问。
7. 用户输入 PR feedback 后可触发 insight 更新。

### 15.4 观众 Agent

1. 用户能新建 persona。
2. 用户能编辑 persona。
3. 用户能删除 persona。
4. 用户能切换当前 persona。
5. 观众 Agent 回复中明确使用了哪个 persona。
6. 观众 Agent 能评价自然度、可信度、广告感、跳出风险。

### 15.5 专家 Agent

1. 专家 Agent 能生成多个方案。
2. 每个方案包含理由、trade-off、品牌解释话术。
3. 用户能预览方案 diff。
4. 用户能逐段应用或不应用。
5. 用户点击写入后，只应用已接受的 hunk。
6. 应用后生成新脚本版本。
7. 用户能回退到上一版本。

---

## 16. 当前原型需要优先修正的开发点

1. 将 `DEFAULT_BIZ_COLUMN_DEFS` 中的默认列策略与产品需求统一，明确是否保留【反馈建议】。
2. 将时长格式写入产品说明，V1 统一为 `起始秒-结束秒`。
3. 增加列名重命名。
4. 删除行/列前增加确认提示。
5. 品牌 pinned item 从纯文本升级为 insight 对象。
6. Persona 增加删除功能。
7. 专家方案卡片增加展开详情。
8. 专家 diff hunk 与表格 row/cell 绑定，不再依赖全文字符串重解析。
9. Brief **仅上传**（无粘贴）；上传后自动 Agentic Search + 显式/隐式需求分析（见 `docs/superpowers/specs/2026-05-19-phase-3-brand-agentic-search-design.md`）。
10. Agent mock 回复替换为真实 LLM 接口。
11. 所有 Agent 输出绑定 script_version_id。
12. 增加版本历史与回退。

---

## 17. 推荐技术实现

### 17.1 前端

建议：

1. Next.js / React。
2. 状态管理：Zustand。
3. 表格：当前自定义表格可继续，但需要 state-first 重构。
4. Diff：当前 hunk 模型可保留，后续改成 cell-level patch。
5. UI：保留当前暗色视觉风格。
6. Streaming：SSE 或 WebSocket。

### 17.2 后端

建议：

1. FastAPI。
2. PostgreSQL。
3. SQLModel / SQLAlchemy。
4. Redis 用于 Agent 任务状态、缓存和流式输出状态。
5. 文件解析服务处理 Brief。
6. LangGraph 编排多 Agent。

### 17.3 数据持久化原则

1. Script table 以 JSON 结构保存。
2. 每次专家方案应用生成新版本。
3. 每条 Agent 输出记录来源版本。
4. 用户手动编辑和 Agent 生成内容都必须可追踪。

---
