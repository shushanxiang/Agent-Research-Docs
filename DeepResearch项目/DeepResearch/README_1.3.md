# DeepResearch · 全面版（README v1.3）

[![Author](https://img.shields.io/badge/Author-🌲⛰️🐘-white.svg)](Author)    	[![Version](https://img.shields.io/badge/Version-1.3-white.svg)](Version) 

> 基于 **LangGraph** 构建的多智能体 DeepResearch 应用：覆盖「规划 → 研究 → 写作」全链路，支持 **Human-in-the-Loop 人机协同**、**多 Agent 子图编排**、**向量知识库（Milvus）**、**用户认证** 与 **搜索缓存 / 任务队列（Redis）**，并配套 React 前端与可量化的评估框架。

![DeepResearch 概览](./app.png)

---

## 1. 项目简介

本项目展示如何使用 LangGraph 搭建一个完整的 DeepResearch 应用，与单一 Agent 的 Demo 不同，本版本将流程重构为**可独立测试的子图**：

| 阶段 | 子图 / 模块 | 说明 |
| --- | --- | --- |
| 规划 | `generate_plan`（图内节点） | 生成研究计划，**需人在前端确认（plan_status）后才继续** |
| 研究 | `research_agent_graph` | 查询生成 → Web 搜索 → 结果评估，多轮循环；可检索知识库（KB）并做交叉编码器精排 |
| 写作 | `writer_agent_graph` | 提纲 → 草稿 → 引用核查与润色评审 |

配套能力：

- **用户认证**：FastAPI 中间件 + PostgreSQL 用户表（bcrypt），前端登录/注册（`auth/`）；
- **向量知识库**：Milvus + DashScope Embedding + `gte-rerank` 精排 + 知识生命周期（`kb/`）；
- **任务与缓存**：Redis 承载会话、搜索缓存、异步任务队列与事件流（`task_queue.py`、`search_cache.py`）；
- **前端**：React 19 + Vite + LangGraph SDK，流式渲染研究过程（ActivityTimeline / ChatMessages）；
- **评估体系**：组件级 + 端到端（E2E）评测框架（`eval/`），judge 模型自动打分并输出报告。

---

## 2. 技术栈

| 层 | 技术 |
| --- | --- |
| 后端框架 | Python 3.11+、FastAPI、LangGraph ≥0.2.6、langchain ≥0.3.19、langgraph-sdk / cli / api |
| 持久化 | PostgreSQL（asyncpg + SQLAlchemy 2.0，用户与认证）、Redis（会话/缓存/队列）、Milvus（向量） |
| LLM 接入 | OpenAI 兼容协议（`LLM_BASE_URL`，如阿里云百炼 DashScope）；Web 搜索经 MCP（dashscope SDK） |
| 检索增强 | DashScope `text-embedding-v4`（1024 维）、交叉编码器 `gte-rerank` |
| 前端 | React 19、Vite 6、TypeScript、Tailwind CSS 4、Radix UI、`@langchain/langgraph-sdk` |

---

## 3. 系统架构

```mermaid
flowchart LR
    U[用户浏览器] --> F[React 前端 :5173]
    F -- /runs /threads /assistants /api 代理 --> LG[LangGraph Runtime :2024]

    subgraph LG[LangGraph Runtime<br/>backend/]
        A[FastAPI app.py<br/>认证中间件 / 模型列表 / 事件流]
        G[主图 graph.py]
        G --> P[计划节点 generate_plan]
        P -- 计划待确认 --> F
        P -- 确认通过 --> R[ResearchAgent 子图]
        R --> W[WriterAgent 子图]
        A --> Q[(Redis<br/>会话/搜索缓存/任务队列)]
        A --> PG[(PostgreSQL<br/>用户表)]
        G --> KB[(Milvus<br/>向量知识库)]
    end

    LG -- OpenAI 兼容 --> LLM[DashScope / 百炼 LLM]
    LG -- MCP Web 搜索 --> WS[Web Search]
```

---

## 4. 目录结构

```text
DeepResearch-06-全面版/
├── backend/                          # 后端服务（LangGraph 平台 + FastAPI）
│   ├── langgraph.json                # LangGraph 平台配置（graph 入口 + http app + .env）
│   ├── pyproject.toml                # Python 项目配置（pip install -e .）
│   ├── .env.example                  # 环境变量模板（复制为 .env 后填写）
│   ├── 模型配置说明.md                # AVAILABLE_MODELS 配置说明
│   ├── src/agent/                    # Agent 核心代码
│   │   ├── app.py                    # FastAPI 入口（认证、/api/models、任务队列、事件流）
│   │   ├── graph.py                  # 主图编排（规划 → 研究 → 写作）
│   │   ├── state.py / configuration.py / prompts.py
│   │   ├── base_agent.py / tools_and_schemas.py / post.py / utils.py
│   │   ├── sub_agents/               # research_agent.py / writer_agent.py 子图
│   │   ├── auth/                     # 登录注册、会话、中间件
│   │   ├── db/                       # SQLAlchemy 引擎、模型、init_db.py
│   │   ├── kb/                       # 知识库：抽取 / 事实存储 / 生命周期
│   │   ├── llm/                      # LLM 统一封装
│   │   ├── reranker.py / search_cache.py / task_queue.py / logger.py
│   │   └── logs/                     # 运行日志（ZhiPoAI_DR_*.log）
│   ├── eval/                         # 评估框架（run_eval.py + judge + 测试集）
│   ├── test/                         # pytest 单元/集成测试
│   ├── htmlcov/                      # 覆盖率报告（可选）
│   └── *.png                         # 子图/架构示意图
├── frontend/                         # React 前端
│   ├── package.json / vite.config.ts # Vite 代理 → http://127.0.0.1:2024
│   └── src/                          # 组件 / AuthContext / api.ts / useResearchStream.ts
├── docs/                             # 架构决策 ADR、测试指引、评估框架、安全设计等
├── run.sh / run_*.bat / run_eval.bat # 一键启动脚本（见第 8 节）
└── README_1.3.md        			  # 本文档
```

---

## 5. 环境要求

| 依赖 | 版本要求 | 用途 |
| --- | --- | --- |
| Python | **3.11 ~ 3.13**（`pyproject.toml` 要求 >=3.11） | 后端 |
| Node.js + npm | Node 18+（推荐 20/22 LTS） | 前端 |
| PostgreSQL | 任意可用实例（推荐 14+） | 用户认证表存储 |
| Redis | 任意可用实例（推荐 7+） | 会话 / 搜索缓存 / 任务队列 |
| Milvus | 2.x standalone 或 Lite | 知识库向量检索 |
| LLM API Key | 阿里云百炼（DashScope）或任意 OpenAI 兼容服务 | 大模型调用 |

> 没有 Docker 也没关系：Milvus 可使用 `milvus-lite`，Redis/PostgreSQL 使用本机安装的服务即可。

---

## 6. 快速开始（从零跑通）

### 6.1 获取代码并安装后端依赖

```bash
cd backend

# 强烈建议使用独立虚拟环境（conda / venv 均可）
# conda create -n deepresearch python=3.11 -y && conda activate deepresearch

pip install -e .
# 国内镜像加速可加：-i https://pypi.tuna.tsinghua.edu.cn/simple
# 如运行时提示缺失包，可手动补装：
# pip install langgraph langgraph-sdk langgraph-cli langgraph-api langchain openai \
#             fastapi dashscope pymilvus sqlalchemy[asyncio] asyncpg passlib[bcrypt] \
#             python-dotenv langgraph-checkpoint-redis
```

### 6.2 安装前端依赖

```bash
cd frontend
npm install        # 或 pnpm install / yarn
```

### 6.3 配置环境变量（backend/.env）

```bash
cd backend
cp .env.example .env    # Windows: copy .env.example .env
```

按你的实际账号修改（**不要把密钥提交到 git**）：

```env
# ── LLM API ─────────────────────────────────────────────
APP_TOKEN=sk-你的LLM_API_Key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ── Embedding（知识库向量化，可选，未配则 KB 不可用）────
EMBEDDING_API_KEY=sk-你的API_Key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4

# ── Web 搜索（MCP / dashscope）─────────────────────────
MCP_APP_ID=你的MCP工具ID
# DASHSCOPE_API_KEY=sk-xxx          # 不配则回退用 APP_TOKEN

# ── 数据服务连接 ────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/deepresearch
REDIS_URL=redis://localhost:6379/0
MILVUS_URI=http://localhost:19530
EMBEDDING_DIM=1024

# ── 可选：LangSmith 追踪 / 模型列表 / 检索参数 ──────────
# LANGSMITH_API_KEY=lsv2_xxx
# AVAILABLE_MODELS=[{"model_id":"qwen3.6-flash","display_name":"Qwen-Flash","icon":"Zap","icon_color":"yellow-400"}, ...]
# KB_LIFECYCLE_MODE=freshness
# RERANKER_KB_ENABLED=false / RERANKER_WEB_ENABLED=false / RERANKER_MODEL=gte-rerank
```

> ⚠️ `AVAILABLE_MODELS` 为 JSON 数组，格式错误会回退到内置默认模型。模型 ID 必须与你的 `LLM_BASE_URL` 供应商真实支持的模型名一致，详见 `backend/模型配置说明.md`。

### 6.4 启动外部依赖服务

以 Docker 一键方式为例（如已有自建服务可跳过）：

```bash
# PostgreSQL
docker run -d --name dr-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=deepresearch -p 5432:5432 postgres:16

# Redis
docker run -d --name dr-redis -p 6379:6379 redis:7
```

Milvus（standalone 需 etcd + MinIO，推荐按[官方文档](https://milvus.io/docs)用 `milvus-lite` 或 compose 部署）；`pymilvus` 在代码中会自动创建 collection，无需手动建。

### 6.5 初始化数据库

建表 + 唯一索引 + 写入初始账号（`zhangsan/zhangsan`、`lisi/lisi`，密码同用户名）：

```bash
cd backend
python -m agent.db.init_db        # 在 backend 目录下执行（需已安装依赖并配好 .env）
# 重置数据库（危险，会删表）：python -m agent.db.init_db --drop
```

> 依赖 `DATABASE_URL` 指向的 PostgreSQL 中已存在对应数据库（本例库名为 `deepresearch`）。

### 6.6 启动后端（LangGraph Runtime，端口 2024）

```bash
cd backend
langgraph dev --no-browser --allow-blocking
# Windows 下如遇中文乱码先执行：set PYTHONIOENCODING=utf-8 && set PYTHONUTF8=1
```

> 推荐用仓库内脚本 `run_backend.bat`（Windows）直接运行。前端依赖 LangGraph 标准端点（`/threads`、`/runs`、`/assistants`），**请使用 langgraph dev 方式启动**；仅调试纯 API 时才用 `run_uvicorn_backend.bat`（uvicorn 直跑 `agent.app:app`，不提供 LangGraph SDK 端点）。

### 6.7 启动前端（Vite，端口 5173）

```bash
cd frontend
npm run dev -- --host
# Windows: run_fontend.bat
```

### 6.8 验证安装成功 ✅

| 检查项 | 方法 | 预期 |
| --- | --- | --- |
| 后端存活 | 浏览器打开 `http://127.0.0.1:2024/ok` | 返回 `{"ok": true}` |
| 模型列表 API | `http://127.0.0.1:2024/api/models` | 返回配置的模型 JSON |
| Studio 调试 | `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024` | 可视化看板 |
| 前端页面 | `http://localhost:5173/app/` | 出现登录/注册页 |
| 账号登录 | 使用 `zhangsan / zhangsan` | 登录成功进入聊天界面 |
| 发起研究 | 输入一个主题并确认研究计划 | 时间线流式展示 搜索 → 研究 → 写作 → 报告 |

---

## 7. 关键环境变量速查

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `APP_TOKEN` | ✅ | - | 大模型 API Key（OpenAI 兼容） |
| `LLM_BASE_URL` | ✅ | - | 模型服务地址，如百炼兼容端点 |
| `DATABASE_URL` | ✅ | - | PostgreSQL 连接串（asyncpg，用户库） |
| `REDIS_URL` | ✅ | - | Redis 连接串（会话/缓存/队列） |
| `MCP_APP_ID` | 按需 | - | Web 搜索 MCP 应用 ID（dashscope） |
| `EMBEDDING_API_KEY/MODEL/BASE_URL` | 按需 | `text-embedding-v4` | 知识库向量化，KB 功能需要 |
| `MILVUS_URI` | 按需 | `http://localhost:19530` | 向量库地址 |
| `EMBEDDING_DIM` | 按需 | `1024` | 向量维度（与模型一致） |
| `AVAILABLE_MODELS` | 否 | 内置默认模型 | 前端可选模型 JSON 列表 |
| `LANGSMITH_API_KEY` | 否 | - | LangSmith 链路追踪 |
| `KB_LIFECYCLE_MODE` | 否 | `freshness` | KB 新鲜度过滤策略（off/inform/freshness/lifecycle） |
| `RERANKER_KB_ENABLED` / `RERANKER_WEB_ENABLED` | 否 | `false` | 是否启用 gte-rerank 精排 |
| `RERANKER_MODEL` | 否 | `gte-rerank` | 精排模型 |
| `WEB_SEARCH_MAX_QPS` | 否 | `12` | Web 搜索限流 |
| `NUMBER_OF_INITIAL_QUERIES` | 否 | `2` | 初始搜索查询数 |
| `MAX_RESEARCH_LOOPS` | 否 | `2` | 最大研究循环数 |

---

## 8. 一键启动脚本速查

所有脚本在**项目根目录**执行（Windows 用 `.bat`，macOS/Linux 参考 `.sh`）：

| 脚本 | 作用 | 说明 |
| --- | --- | --- |
| `run_backend.bat` | 安装依赖并启动后端 | `pip install -e .` + `langgraph dev --no-browser --no-reload --allow-blocking` |
| `run_backend2.bat` | 同上（带 UTF-8 编码支持） | Windows 中文乱码时优先用这个 |
| `run_uvicorn_backend.bat` | uvicorn 直跑 FastAPI | 纯 API 调试用，**不含 LangGraph SDK 端点** |
| `run_fontend.bat` / `.sh` | 启动前端 | `npm run dev -- --host [--force]` |
| `run.sh` | Linux/macOS 完整流程 | 先 export 各 Key 再装依赖（记得把占位符改成你的值） |
| `run_eval.bat` | 运行组件级评估 | 见第 9 节 |

> `.bat` 脚本顶部保留了 `APP_TOKEN` / `LLM_BASE_URL` / `MCP_APP_ID` / `LANGSMITH_API_KEY` 的 `set` 示例，已配置 `.env` 时无需重复设置。

---

## 9. 测试与评估

```bash
cd backend

# 单元测试（无需外部服务）
python -m pytest -m unit
# 全部测试（含需 Redis/DB 的集成用例，视环境而定）
python -m pytest

# 覆盖率（可选）
python -m pytest --cov=agent --cov-report=html

# 评估：全部模式（e2e + comp）
python -m eval.run_eval --mode all --judge-model deepseek-v4-pro --output results.json

# 单主题评估
python -m eval.run_eval --mode e2e --topic "规范驱动开发SDD与AGENTS.md的关系"
```

评估报告会以 `eval_report_YYYYMMDD_HHMMSS.json` 形式输出到 `backend/`。

---

## 10. 常见问题排查（FAQ）

| 现象 | 原因 / 处理 |
| --- | --- |
| `pip install -e .` 报依赖解析失败 | 升级 pip（`pip install -U pip`）或使用 Python 3.11/3.12 干净环境 |
| 后端启动即连接报错（Redis/PostgreSQL/Milvus） | 服务未启动或 `.env` 连接串不对；先 `docker ps` / `pg_isready` 排查 |
| 前端页面能开但发送任务报 502 / 代理失败 | 后端必须是 `langgraph dev` 启动（2024 端口）；确认 vite 代理目标为 `http://127.0.0.1:2024` |
| 登录/注册报 500 | `init_db` 未执行或 `DATABASE_URL` 指向的库不存在；先建库再 `python -m agent.db.init_db` |
| 模型列表为空或调用报"模型不存在" | `AVAILABLE_MODELS` 中 `model_id` 与 `LLM_BASE_URL` 供应商实际模型名不一致；参考 `backend/模型配置说明.md` |
| Windows 控制台中文乱码 | 设 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`，或直接使用 `run_backend2.bat` |
| 端口被占用（2024 / 5173 / 6379） | `netstat -ano | findstr 2024` 定位进程后释放，或修改启动端口 |
| 需要修改模型列表后重启才生效 | `AVAILABLE_MODELS` 属后端启动读取，改完需重启后端并刷新前端 |

---

## 11. 相关文档

- `backend/模型配置说明.md` —— 前后端模型列表（`AVAILABLE_MODELS`）配置
- `docs/架构决策ADR/` —— 关键架构决策记录
- `docs/评估框架ReadMe.md` —— 评估框架说明
- `docs/测试指引.md` —— 测试编写与运行指引
- `docs/大模型安全设计.md` —— 安全设计说明
- `docs/项目工作量.md` —— 项目工作量记录
- `README_1.3.md` —— 快速入门文档

---

## 12. 安全提示

- **请勿将真实 API Key / 数据库口令提交到 Git**。若项目需要开源或分享，请先将其中的 `APP_TOKEN`、`LANGSMITH_API_KEY`、`MCP_APP_ID` 等替换为占位符（如 `sk-xxxx`），并把 `.env` 加入 `.gitignore`。
- 初始账号（`zhangsan` / `lisi`）密码与用户名相同，**部署到公网前请修改或删除**。
