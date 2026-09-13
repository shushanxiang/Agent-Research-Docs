# ADR-004: 选择 Milvus 作为向量知识库 + Redis 搜索缓存

## 状态
Accepted（已采纳）

## 背景
DeepResearch 系统每次研究都会产生大量搜索事实。随着企业内部使用积累，存在以下需求：
- 跨研究任务的知识复用（避免重复搜索已知信息）
- 基于语义相似度检索历史事实
- 搜索结果的跨请求缓存（同一查询不重复调用 MCP）

## 决策
使用 Milvus 向量数据库存储研究事实，配合兼容 OpenAI 的 Embedding API 生成向量。同时引入 Redis 作为搜索缓存后端。

## 理由

### 为什么 Milvus？

1. **自托管部署**：数据不出域，符合企业内部使用要求
2. **Dynamic Field**（Milvus 2.5+）：新增元数据列无需 migration
3. **IVF_FLAT 索引**：事实量级预估 10 万级，精度和性能平衡

**Embedding 设计**：
- 独立配置（`EMBEDDING_BASE_URL` + `EMBEDDING_API_KEY`），可与 LLM 使用不同提供商
- 配置缺失时自动降级使用 LLM 的 base_url 和 api_key
- 维度自检测：实际维度与配置不匹配时告警
- 重试机制：401/403→永久失败，429/5xx→最多 3 次重试

**放弃的方案**：
- ChromaDB — 2025 年 Q3 时生产特性不成熟
- Pinecone/Weaviate Cloud — 云服务，数据需出域
- 纯 Redis — 不支持向量检索

### 为什么 Redis 搜索缓存？

1. **统一后端**：后续 checkpointer + 缓存 + 任务队列共用 Redis（参见 ADR-008）
2. **TTL 自带过期**：`SETEX` 原子写入 + 1h 自动过期
3. **跨实例共享**：多进程并发读写天然支持

**降级策略**：Redis 不可用 → 自动降级为进程内内存缓存，对业务透明。

**放弃的方案**：
- 仅内存缓存 — 跨请求命中率 0%

## 后果

### 正面：
- 知识复用降低搜索 API 调用量约 20-30%
- 搜索缓存跨请求命中率从 0% 提升到 60-70%
- Docker Compose 三服务编排（Backend + Milvus + Redis），部署简单

### 负面：
- 新增 Milvus + Redis 两个基础设施依赖
- 事实提取依赖 LLM（`FactExtractor`），每次搜索 +1 次 LLM 调用

## 相关文档
- [FactStore 实现](../../backend/src/agent/kb/fact_store.py)
- [FactExtractor 实现](../../backend/src/agent/kb/extractor.py)
- [搜索缓存实现](../../backend/src/agent/search_cache.py)
- [KB 生命周期管理](009-kb-lifecycle-management.md)

## 变更记录
- 2026-04-05: Milvus 知识库上线 
- 2026-04-08: Redis 搜索缓存上线 
- 2026-04-12: Embedding API 独立配置 + 重试机制
- 2026-04-15: 缓存降级策略 
