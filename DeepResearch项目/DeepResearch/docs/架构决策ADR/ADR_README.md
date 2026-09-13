# Architecture Decision Records (ADR) — 架构决策记录

本文档记录了 DeepResearch 系统所有重要的技术选型和架构设计。

## 决策清单

| 编号 | 标题 | 状态 |
|------|------|------|
| [001](001-langgraph-mcp-stack.md) | 选择 LangGraph + MCP 作为核心技术栈 | Accepted |
| [002](002-hitl-and-rate-limit.md) | 引入 Human-in-the-Loop + Web 搜索速率限制 | Accepted |
| [003](003-subgraph-multi-agent-refactor.md) | 单体 Agent 图重构为 Sub-Graph 多 Agent 架构 | Accepted |
| [004](004-milvus-and-redis-cache.md) | 选择 Milvus 向量知识库 + Redis 搜索缓存 | Accepted |
| [005](005-llm-as-judge-eval-framework.md) | 引入 LLM-as-Judge 评估框架 | Accepted |
| [006](006-exception-classification-retry.md) | 异常分类与重试体系设计 | Accepted |
| [007](007-full-async-and-streaming.md) | 全链路异步化 + LLM 流式输出 | Accepted |
| [008](008-redis-streams-task-queue.md) | 选择 Redis Streams 作为异步任务队列 | Accepted |
| [009](009-kb-lifecycle-management.md) | KB 生命周期管理模式设计 | Accepted |
| [010](010-robust-json-extraction.md) | 结构化 JSON 输出的鲁棒性处理 | Accepted |
| [011](011-layered-testing-strategy.md) | 分层测试策略与测试套件构建 | Accepted |
| [012](012-cross-encoder-reranker.md) | 引入交叉编码器重排序提升检索相关性 | Accepted |

## 关键依赖关系

```
001 技术栈
 ├→ 002 HITL + 速率限制
 │    ├→ 003 Sub-Graph 重构
 │    │    ├→ 004 Milvus + 缓存
 │    │    │    ├→ 009 KB 生命周期
 │    │    │    ├→ 012 交叉编码器重排序
 │    │    │    └→ 008 Redis Streams (依赖 Redis 已就绪)
 │    │    ├→ 005 LLM-as-Judge
 │    │    └→ 006 异常分类
 │    └→ 007 异步化 + 流式输出 ← 008 Redis Streams 的前提
 └→ 010 JSON 鲁棒提取 (独立增强)
 └→ 011 分层测试 (横切)
```

## 约定

- 每份 ADR 命名：`NNN-short-title.md`，编号按时序递增
- 状态流转：`Proposed` → `Accepted` → `Deprecated` / `Superseded by ADR-XXX`
- 当新决策替代旧决策时，旧 ADR 状态更新为 `Deprecated` 或 `Superseded`

## 业务约束

以下不纳入 ADR 范围（业务定位决定）：

1. **CI/CD、分布式追踪、灰度发布** — 需基础设施平台支持，非项目范围
2. **多租户、权限管理** — 面向企业内部单一团队
3. **公网安全防护** — 仅内部使用
