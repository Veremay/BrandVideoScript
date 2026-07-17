# BrandVideo

品牌合作视频脚本编辑与协商准备系统。创作者通过 **Coordinator Agent** 统一入口，在脚本编辑、IBIS 节点图与多智能体分析之间协作，识别品牌需求、观众反应与创作策略之间的冲突，并生成可协商的修改方案。

**当前阶段：** Phase 0–4 已完成，Phase 5–7 进行中。详见 [`docs/development_plan.md`](docs/development_plan.md) 与 [`docs/pipeline.md`](docs/pipeline.md)。

## 功能概览

| 模块 | 说明 |
|------|------|
| **Brief 解析** | 上传 `.md` / `.txt` 或粘贴文本；Coordinator 调度 Brand / Audience / Expert 完成初始解析 |
| **Script Editor** | 表格化脚本编辑（时长、画面、形式、备注、`feedback` 只读列）；行/列增删、时长轴校验、debounce 自动保存 |
| **IBIS Node Graph** | React Flow 可视化 Issue / Position / Argument；来源配色、待协商标记、与脚本行互跳 |
| **Coordinator Chat** | 统一 AI 入口；选段 quote 提问、SSE 流式回复、消息持久化 |
| **Persona** | 数据分析接口生成初始观众画像，支持编辑并影响后续 Audience 分析 |
| **Brand Wiki** | 本地品牌知识库；Brand Agent 检索 + Tavily 联网补充 |
| **修改方案** | Expert 多方向修改方案（保守 / 平衡 / 创作者主导 / 观众友好）；可选 cell-level hunk |
| **品牌分享** | 生成只读分享链接，品牌方填写 `feedback` 列后同步回创作者工作区 |
| **协商准备** | 一键生成 Negotiation Preparation 弹窗材料（进行中） |

**两种项目模式：**

- **Setting 1（full）**：完整流程——Brief 解析 → Persona → IBIS 图 → 脚本创作与多视角反馈
- **Setting 2（vanilla）**：轻量模式——跳过 Brief/图/Persona，直接进入脚本编辑

## 技术栈

```text
frontend/   Next.js 15 · React 19 · TypeScript · Zustand · React Flow
backend/    FastAPI · Motor (MongoDB) · Redis · SSE · SiliconFlow LLM · Tavily
infra/      docker-compose (MongoDB 7 + Redis 7)
```

## 快速开始

### 1. 启动依赖服务

```bash
docker compose up -d
```

### 2. 后端

```bash
cd backend
uv sync
copy .env.example .env   # Linux/macOS: cp .env.example .env
```

编辑 `backend/.env`，至少配置：

| 变量 | 说明 |
|------|------|
| `SILICONFLOW_API_KEY` | [SiliconFlow](https://siliconflow.cn) API Key，用于 LLM 推理 |
| `TAVILY_API_KEY` | [Tavily](https://app.tavily.com) API Key，Brand Agent 联网检索（可选） |
| `BRAND_WIKI_ROOT` | 品牌 Wiki 根目录，默认 `backend/data/brand_wiki` |

启动 API：

```bash
uv run uvicorn app.main:app --reload
```

默认地址：`http://localhost:8000/api`

### 3. 前端

```bash
cd frontend
npm install
copy .env.example .env.local   # Linux/macOS: cp .env.example .env.local
npm run dev
```

默认地址：`http://localhost:3000`

首次进入需输入 `user_id`（本地标识，存入 localStorage）。

## 目录结构

```text
BrandVideo/
├── frontend/              # Next.js 应用
│   └── src/
│       ├── app/           # 页面（主页、分享页 /share/[token]）
│       ├── components/    # ScriptGrid、MapView、CoordinatorChat 等
│       ├── lib/           # API 客户端、类型、工具函数
│       └── store/         # Zustand 全局状态
├── backend/
│   ├── app/
│   │   ├── api/routes/    # REST + SSE 路由
│   │   ├── services/      # Agent、LLM、工具层
│   │   ├── repositories/  # MongoDB 数据访问
│   │   └── prompts/       # Agent 系统提示词
│   ├── data/brand_wiki/   # 品牌知识库（原始手册 + compiled 页面）
│   ├── scripts/           # 运维与蒸馏脚本
│   └── tests/             # 单元测试
├── docs/                  # 流程、开发计划、技术方案
└── docker-compose.yml
```

## Brand Wiki

品牌手册经蒸馏脚本编译为结构化 Markdown 页面，供 Brand Agent 检索：

```bash
cd backend
uv run python scripts/distill_brand_wiki.py              # 处理新手册
uv run python scripts/distill_brand_wiki.py --force       # 重新蒸馏全部
uv run python scripts/distill_brand_wiki.py --file 2022观夏品牌手册.md
```

编译产物位于 `backend/data/brand_wiki/<brand>/`，包含 `_index.md`、`_agent-guide.md`、分节页面与 `error_book.yaml`。

## Activity Logs

用户行为写入 MongoDB 集合 `activity_logs`（由 `ACTIVITY_LOG_ENABLED` 控制，默认开启）：

| `event_type` | 含义 |
|--------------|------|
| `http` | API 访问（method / path / status / duration） |
| `mutation` | 数据变更审计（action + before / after） |

同一请求可用 `request_id` 关联。导出与查询**默认包含全部类型**。

脚本导出：

```bash
cd backend
uv run python scripts/export_activity_logs.py --project-id PROJECT_ID --user-id USER_ID
uv run python scripts/export_activity_logs.py --project-id PROJECT_ID --user-id USER_ID --out my_logs.json
# 只要某一种类型时再过滤：
uv run python scripts/export_activity_logs.py --project-id PROJECT_ID --user-id USER_ID --event-type mutation
```

HTTP API：`GET /api/projects/{project_id}/activity-logs?user_id=...`（可选 `event_type`、`download=true`）。

## 测试

```bash
cd backend
uv run python -m unittest discover -s tests -p "test_*.py"
```

未配置 `SILICONFLOW_API_KEY` 时，部分涉及 LLM 的测试会使用 mock 降级。

## 开发进度

依据 [`docs/development_plan.md`](docs/development_plan.md) §7 验收清单：

| 阶段 | 状态 | 要点 |
|------|------|------|
| Phase 0 主工作区 | ✅ | Coordinator Chat、Script/Graph 切换、项目 CRUD |
| Phase 1 Script Editor | ✅ | 表格编辑、时长轴、debounce 保存、snapshot |
| Phase 2 Brief 与初始解析 | ✅ | 三 Agent 解析、初始 IBIS 图、Persona 生成 |
| Phase 3–4 Coordinator + Graph | ✅ | SSE 对话、选段提问产节点、图中编辑与待协商 |
| Phase 5–7 方案 / 分享 / 协商 | 🚧 | 多方向方案、分享链接 feedback 回流、协商弹窗 |
| Phase 8 整合验收 | ⬜ | 端到端演示、staleness UI、文档完善 |

**MVP 暂缓：** References 输出、固定 Output Panel、Brief PDF/DOC 解析、正式登录与多人协作。

## 相关文档

- 系统流程：[`docs/pipeline.md`](docs/pipeline.md)
- 开发计划：[`docs/development_plan.md`](docs/development_plan.md)
- 技术方案：[`docs/technical_plan.md`](docs/technical_plan.md)
- 数据结构：[`docs/data_structures.md`](docs/data_structures.md)
