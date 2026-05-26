# BrandVideo MVP

品牌合作视频脚本编辑系统。当前阶段：**Phase 0**（主工作区与工程底座），依据 [`docs/development_plan.md`](docs/development_plan.md) 与 [`docs/pipeline.md`](docs/pipeline.md)。

## 目录

```text
frontend/          Next.js + TypeScript + Zustand
backend/           FastAPI + MongoDB + Redis
docker-compose.yml MongoDB + Redis
docs/              流程、开发计划、技术方案
```

## 启动依赖服务

```bash
docker compose up -d
```

## 后端

```bash
cd backend
uv sync
copy .env.example .env
uv run uvicorn app.main:app --reload
```

默认 API 地址为 `http://localhost:8000/api`。

## 前端

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

默认页面地址为 `http://localhost:3000`。

## Phase 0 验收项

- [x] 无前台 Brand / Audience / Expert 三面板
- [x] 统一 **Coordinator Chat**（mock 对话，FAB 打开）
- [x] **Script Editor** ↔ **Node Graph** 主工作区切换（图为演示占位）
- [x] Topbar：**Brief** 上传 / 粘贴、**Persona** 入口、视图切换、保存状态
- [x] **无** 固定 Negotiation / References Output Panel
- [x] 选中文本 → quote 插入 Coordinator
- [x] `docker-compose`、FastAPI、`user_id` 进入、Project CRUD
- [x] `current_script` debounce 同步（默认五列；`feedback` 为品牌反馈只读列，内容由分享页 sync 写入）

**Phase 0 不做：** 真实 LLM 解析、项目内持久化 IBIS 图、分享链接、协商弹窗。

## 本地探测（可选）

```bash
cd backend
uv run python scripts/phase0_probe.py
```
