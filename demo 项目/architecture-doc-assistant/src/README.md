# 建筑智能文档助手

> 基于 RAG 架构的建筑行业智能文档助手 — 规范法规查询 | 做法图集问答 | 知识沉淀

## 项目定位

面向建筑行业（设计院/施工单位）的智能文档管理平台，实现**统一存储、智能检索、知识问答**三大核心能力。

### 核心指标

| 指标 | 目标值 |
|------|--------|
| 规范条款查询 | ≤ 30 秒 |
| 图集节点查找 | ≤ 1 分钟 |
| 问答准确率 (Top 3) | ≥ 85% |
| 全文检索 (100万文档) | ≤ 3 秒 (P95) |

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 前端 | Streamlit | 管理后台、快速原型 |
| API 层 | FastAPI | RESTful API、鉴权、WebSocket |
| 业务逻辑 | LangChain | RAG Pipeline、Agent 编排 |
| 文档解析 | MinerU | PDF/图片结构化解析 + OCR |
| 向量存储 | Chroma | Dense + Sparse 混合检索 |
| 缓存/队列 | Redis | BM25 索引、语义缓存、Celery 队列 |
| Embedding | BGE-M3 | 8192 token 长文本、中英混合 |
| LLM | 通义千问 (Qwen-Max) | 问答生成、分析对比 |
| 关系数据库 | PostgreSQL | 元数据、用户、权限、日志 |
| 对象存储 | MinIO / 阿里云 OSS | 原始文件、解析产物 |

---

## 项目结构

```
src/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由 (documents/search/chat/atlas/regulations/admin/enterprise)
│   │   ├── core/         # 配置、安全、日志、依赖注入
│   │   ├── models/       # SQLAlchemy ORM 模型
│   │   ├── schemas/      # Pydantic 请求/响应模型
│   │   ├── services/     # 业务逻辑 (document/search/chat/parse/export)
│   │   ├── retrievers/   # 检索器 (HybridRetriever/AtlasSearch/RelationService)
│   │   ├── agents/       # LangChain Agent & Prompt 模板
│   │   └── utils/        # 工具函数 (hash/file/format)
│   ├── tasks/            # Celery 异步任务
│   ├── tests/            # 单元测试
│   └── Dockerfile
├── frontend/
│   ├── app.py            # Streamlit 主入口
│   ├── pages/            # 多页面
│   ├── components/       # 复用组件
│   └── Dockerfile
├── services/
│   └── mineru/           # MinerU 解析服务
│       └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   ├── init.sql          # 数据库初始化
│   └── k8s/              # Kubernetes 部署配置
└── docs/                 # 技术文档
```

---

## 快速启动

### 1. 克隆与配置

```bash
cd src/infra
cp .env.example .env          # 编辑 .env 填入 DASHSCOPE_API_KEY
```

### 2. 启动开发环境

```bash
docker-compose up -d
```

启动后：
- API 文档: `http://localhost:8000/docs`
- 管理后台: `http://localhost:8501`
- MinIO 控制台: `http://localhost:9001`

### 3. 停止

```bash
docker-compose down
```

---

## 模块依赖关系

```
┌──────────────┐
│   frontend   │──Streamlit 管理后台
└──────┬───────┘
       │ HTTP/WS
       ▼
┌──────────────┐
│   api/       │──FastAPI 路由注册
└──────┬───────┘
       │ 调用
       ▼
┌──────────────┐     ┌──────────────────┐
│  services/   │────▶│  retrievers/     │──Chroma + Redis 混合检索
│  document.py │     │  hybrid.py       │
│  search.py   │     │  atlas.py        │
│  chat.py     │     │  relation.py     │
│  parse.py    │     └──────────────────┘
│  export.py   │──────────▶ agents/     ──LangChain Agent + Prompt
└──────┬───────┘            prompts.py
       │
       ▼
┌──────────────┐     ┌──────────────────┐
│  models/     │     │  core/           │──config/security/logging/deps
│  document.py │     └──────────────────┘
│  session.py  │
└──────┬───────┘
       │ ORM
       ▼
┌──────────────┐
│ PostgreSQL   │
└──────────────┘
```

---

## 开发路线

| Sprint | 目标 | 关键交付 |
|--------|------|----------|
| 0 | 环境搭建 | Docker Compose 可运行 |
| 1 | 文档处理 | 上传、版本管理、MinerU 解析 |
| 2 | 规范结构化 | 章节/条款解析、Chroma 索引 |
| 3 | 图集结构化 | 节点解析、OCR、图集索引 |
| 4 | 规范问答 MVP | RAG Pipeline、废止检测 |
| 5 | 图集问答 MVP | 图文组装、缩略图生成 |
| 6 | 前端管理 | Streamlit 后台、权限、审计 |
| 7 | 高级功能 | 跨条款关联、图集对比、Word 导出 |
| 8 | 性能优化 | 缓存、索引、并发测试 |
| 9 | 验收测试 | 集成测试、UAT |
