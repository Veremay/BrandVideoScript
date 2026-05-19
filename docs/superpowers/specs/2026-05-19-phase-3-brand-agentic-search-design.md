# Phase 3 品牌方 Agent 增强设计（Brief 上传 + Agentic Search）

> **状态：** 需求已锁定，待实现（本文档仅更新设计，不改代码）。  
> **关联：** `docs/prd.md` §4.2、§6；`docs/development_plan_P0.md` Phase 3；`docs/technical_plan_lightweight.md` §6、§8.1。

---

## 1. 需求摘要

| # | 需求 | MVP 裁决 |
|---|------|----------|
| 1 | Topbar **仅保留「上传品牌 Brief」**，删除「粘贴 Brief」入口 | 是 |
| 2 | Brief 上传并解析为文本后，**自动**触发品牌方 Agent 解析 **显式需求 / 隐式需求**（写入 `brand_insights`） | 是，非可选 |
| 3 | 品牌分析前先做 **Agentic Search**：外部检索（Tavily API）+ 内部 **llm-wiki** 品牌手册库 | 是 |
| 4 | Brief 摘要、检索结果、手册片段、已有 insights 等 **组合为 Brand Agent 上下文** | 是 |
| 5 | 与 PRD / 开发计划 / 技术方案文档对齐 | 本文档 |

---

## 2. UI：Brief 输入方式

### 2.1 变更

- **保留：** Topbar「上传品牌 Brief」按钮；支持 `.md` / `.txt` 文件选择。
- **删除：** 「粘贴 Brief」按钮及 `window.prompt` 粘贴流程（当前原型在 `EditorShell`）。
- **保留：** 上传后显示文件名；`parse_status` 与解析错误提示。

### 2.2 不在 MVP 范围

- PDF / DOC / DOCX / PPT 上传（仍列二期，与 `development_plan_P0.md` 一致）。
- Brief 纯文本粘贴作为独立入口（用户若需粘贴，可先存为 `.txt` 再上传）。

---

## 3. Brief 上传后的自动品牌分析流水线

Brief 文本就绪（`parse_status = parsed`）后，后端 **自动** 执行以下流水线，无需用户再点「分析 Brief」：

```text
POST /brief 成功 → 保存 brief.text
  → (可选) 8B 生成 brief.summary
  → 识别品牌名 / 品类（从 brief.text + filename）
  → Agentic Search（见 §4）
  → Brand Agent 初始分析（32B + 结构化输出）
  → 写入 brand_insights（explicit_requirement + implicit_requirement）
  → SSE 推送进度 / 结果到品牌方 Agent 面板（pinned tab + 可选对话区摘要）
```

### 3.1 显式 / 隐式需求

- **显式需求（`explicit_requirement`）：** Brief 中直接写明的要求（时长、必提卖点、禁用词、交付格式等）。
- **隐式需求（`implicit_requirement`）：** 未写明但品牌方/行业惯例会默认期待的内容（调性、审片红线、竞品避让等）。
- **品牌反馈（`brand_feedback`）：** 仍主要由用户对话或粘贴 PR 反馈产生；初始流水线可不预填，或仅在有 brief 内「反馈类」段落时生成。

### 3.2 与「可选触发」的差异

`development_plan_P0.md` 原 Phase 3.5「Brief 就绪后**可选**触发初始品牌分析」改为 **默认自动触发**。重新上传 Brief 时覆盖或合并策略由实现决定，文档建议：

1. 重新上传：清空该次分析产生的 `created_by=agent` 的 explicit/implicit insights，再跑新流水线。
2. `created_by=user` 的 pinned 项保留，除非用户确认覆盖。

---

## 4. Agentic Search

### 4.1 目标

在调用 LLM 做需求拆解前，为品牌方 Agent 补充 **可追溯的外部与内部依据**，降低「仅凭 Brief 臆测品牌规范」的风险。

### 4.2 两路检索

| 来源 | 实现（规划） | 说明 |
|------|----------------|------|
| **外部 Web Search** | [Tavily API](https://docs.tavily.com/)（或项目已安装的 Tavily CLI / MCP） | 按品牌名、产品名、行业关键词检索公开信息：品牌调性报道、过往合作案例、官方社媒口径等 |
| **内部 llm-wiki** | 仓库内 `llm-wiki/` 目录（待建） | 各品牌 **手册 Markdown**；按 `brand_slug` 或元数据匹配；RAG 式截取相关 chunk |

### 4.3 llm-wiki 目录约定（规划）

```text
llm-wiki/
  README.md                 # 索引说明、命名规范
  brands/
    {brand_slug}/           # 如 nike, loreal-cn
      meta.json             # display_name, aliases[], category, locale
      handbook.md           # 主品牌手册（LLM 友好 Markdown）
      guidelines/           # 可选：分主题拆页
        social-media.md
        review-checklist.md
```

- `brand_slug` 由 Brief 解析出的品牌名映射；支持 `meta.json` 中的 `aliases` 模糊匹配。
- 未命中 wiki 时仅依赖 Tavily + Brief，并在 `brand_research.matched_wiki` 中标记 `false`。

### 4.4 Agentic Search 行为（逻辑）

非单次固定查询，而是由 **Brand Research 子步骤**（可用 8B 规划 + 工具调用循环，或固定 2–3 步模板）完成：

1. **Query 规划：** 从 `brief.text` / `brief.summary` 提取品牌实体、品类、campaign 关键词。
2. **Wiki 检索：** 在 `llm-wiki/brands/` 下匹配品牌；对 `handbook.md` 做关键词 / 向量检索（MVP 可用标题分段 + 关键词匹配）。
3. **Web 检索：** 调用 Tavily `search`（及必要时 `extract` 单页），限制域名或条数，避免上下文爆炸。
4. **结果归并：** 去重、截断、附 `source_url` / `wiki_path`，写入 `project.brand_research`（见 §5）。

### 4.5 配置与环境变量（规划）

```text
TAVILY_API_KEY=...
BRAND_WIKI_ROOT=./llm-wiki    # 或绝对路径
BRAND_SEARCH_MAX_WEB_RESULTS=5
BRAND_SEARCH_MAX_WIKI_CHUNKS=8
```

MVP 若未配置 `TAVILY_API_KEY`，应降级为仅 llm-wiki + Brief，并在 UI/日志标明「未启用外部检索」。

---

## 5. Brand Agent 上下文组合

### 5.1 新增/扩展的 Project 字段（轻量方案）

在 `project` 文档上扩展（实现时落 `schemas.py`）：

```json
{
  "brief": {
    "filename": "campaign-brief.md",
    "text": "...",
    "summary": "...",
    "parse_status": "parsed",
    "uploaded_at": "..."
  },
  "brand_research": {
    "status": "idle | running | done | failed",
    "brand_slug": "example-brand",
    "matched_wiki": true,
    "queries": ["Example Brand 品牌调性", "..."],
    "web_snippets": [
      {
        "title": "...",
        "url": "https://...",
        "snippet": "...",
        "fetched_at": "..."
      }
    ],
    "wiki_snippets": [
      {
        "path": "llm-wiki/brands/example-brand/handbook.md",
        "heading": "## 视觉与调性",
        "snippet": "...",
        "fetched_at": "..."
      }
    ],
    "research_summary": "供 LLM 使用的 200–500 字归纳",
    "updated_at": "..."
  },
  "brand_insights": []
}
```

### 5.2 Brand Agent 调用时的上下文分层

与 `technical_plan_lightweight.md` §6.1 对齐，Brand Agent **固定上下文** 扩展为：

```text
1. brief.summary（无则 brief.text 前 N 字）
2. brand_research.research_summary +  Top-K web_snippets + wiki_snippets（带出处）
3. 已有 brand_insights（显式/隐式/反馈，供多轮对话）
4. conversation_summary（若有）
```

**动态上下文：** 用户消息、quotes、相关脚本行。

初始分析任务的 system / user prompt 应明确要求：

- 显式、隐式需求均需有 `evidence`（来自 brief、wiki 或 web，标注 `source_type`）。
- 无法从依据推断的隐式需求应标 `confidence: low` 或省略。

### 5.3 evidence.source_type 扩展

在现有 `brief | script | chat | pr_feedback` 基础上增加：

- `web`：Tavily 检索结果
- `brand_wiki`：llm-wiki 手册片段

---

## 6. API 与触发（规划）

| 步骤 | 接口 / 行为 |
|------|-------------|
| 上传 | `POST /api/projects/{id}/brief`（multipart，仅 .md/.txt） |
| 解析 | 同步或短异步：写入 `brief.text`，`parse_status=parsed` |
| 自动流水线 | 解析成功后 **服务端自动** 调用内部 `BrandBriefPipeline`（不必要求前端再 POST） |
| 进度 | 可选：`GET` 轮询 `brand_research.status` 或对品牌 Agent 通道发 SSE `event: progress` |
| 结构化结果 | 流水线结束写入 `brand_insights`；`POST .../agents/brand/analyze-brief` 保留为 **手动重跑** 入口 |

---

## 7. 验收标准（补充 PRD §15.3）

1. Topbar 仅有上传 Brief，无粘贴入口。
2. 上传合法 `.md`/`.txt` 后，无需额外点击即可在 pinned 区看到 Agent 生成的显式/隐式需求（或明确的 loading / failed 状态）。
3. `brand_research` 中可看到至少一种检索来源的记录（wiki 或 web，或明确降级原因）。
4. 每条自动生成的 insight 在详情中可展开 `evidence`，且能区分 brief / web / brand_wiki。
5. 品牌方 Agent 对话能引用检索摘要回答「依据是什么」。

---

## 8. 实现任务拆分（供 Phase 3 plan 引用）

1. 前端：移除粘贴 Brief；上传后展示解析与分析状态。
2. 后端：`brand_research` 模型与 Tavily 客户端封装；llm-wiki 读取与匹配。
3. 后端：`BrandBriefPipeline`（search → analyze → persist insights）。
4. Prompt：初始分析 + 结构化 JSON artifact（32B）。
5. 仓库：初始化 `llm-wiki/` 结构与 1–2 个示例品牌手册。
6. 文档与 `.env.example`：Tavily、wiki 路径说明。

---

## 9. 风险与降级

| 风险 | 规避 |
|------|------|
| Tavily 费用 / 限流 | 固定 max results；结果缓存到 `brand_research`；相同 brief hash 可复用 |
| Wiki 未覆盖品牌 | 仅 Web + Brief；UI 提示「无内部手册」 |
| 上下文过长 | `research_summary` + Top-K snippets；完整原文不进 prompt |
| 自动分析失败 | `brand_research.status=failed`；pinned 区展示重试；保留 brief 文本 |

---

## 10. 文档变更清单

| 文档 | 变更 |
|------|------|
| `docs/development_plan_P0.md` | Brief 仅上传；Phase 3 任务与验收 |
| `docs/prd.md` | Topbar、§6 品牌 Agent、§11 API、§13.6、§15.3 |
| `docs/technical_plan_lightweight.md` | `brand_research`、§6 上下文、§8.1 Brand Agent 流水线 |
| `docs/superpowers/plans/2026-05-19-phase-3-brand.md` | 任务列表扩展 |
| 本文档 | 权威设计说明 |
