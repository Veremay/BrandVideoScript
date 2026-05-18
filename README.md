# BrandVideo MVP

品牌合作视频脚本编辑系统。当前实现处于 `development_plan_P0.md` 的 Phase 0：基础工程与项目/脚本数据闭环。

## 目录

```text
frontend/          Next.js + TypeScript + Zustand
backend/           FastAPI + MongoDB + Redis
docker-compose.yml MongoDB + Redis
docs/              PRD 与开发计划
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

## Phase 0 已覆盖

- 自定义 `user_id` 进入，前端写入 `localStorage`
- 用户与项目数据持久化到 MongoDB
- 项目创建、列表、打开
- `current_script` 默认 5 列空表
- 脚本单元格最小编辑与 debounce 保存
- Topbar 保存状态：编辑中、保存中、已保存、保存失败
- `LLMClient` 与 `ModelRouter` mock 壳
