# ADR-012: 引入交叉编码器重排序提升检索相关性

## 状态
Accepted（已采纳）

## 背景
当前检索管道存在两个阶段的召回结果未做二次精排：

1. **KB 检索**（`FactStore.query`）：Milvus 用 COSINE 距离做 ANN 召回，top_k 候选直接按向量距离排序。但双塔模型的语义表达能力有限，可能将语义相近但实际不相关的事实排到前面。
2. **Web 搜索**（`_web_search`）：DashScope MCP API 返回搜索引擎排序的前 10 条结果，全部送入 LLM 做摘要。其中可能包含与搜索意图无关或低质量的结果，污染后续的 critique 判断和报告质量。

需要在两个检索阶段引入交叉编码器（Cross-Encoder）进行二次语义精排，以"重排序"替代"简单截断"，提升送入下游（LLM query generation / LLM summarization）的信号质量。

## 决策
使用 DashScope TextReRank API（`gte-rerank` 模型）作为交叉编码器服务，在 KB 检索和 Web 搜索两个阶段各自独立插入精排步骤，由两个独立开关控制。

## 理由

### 为什么用 DashScope TextReRank 而不是本地模型？

1. **零新依赖**：项目已依赖 `dashscope`，`TextReRank` 类在已安装版本中即可用，无需引入 `sentence-transformers` 或 `FlagEmbedding`
2. **统一认证**：复用 `DASHSCOPE_API_KEY` → `APP_TOKEN` 的回退链，与现有 Web 搜索/MCP 完全一致，运维零额外成本
3. **API 简洁**：`TextReRank.call(query, documents, top_n)` 一次调用即可评分全部文档，返回 `[{index, relevance_score}, ...]`，无需手动管理 batch
4. **单次调用评分全量文档**：比用 LLM 逐条打分的方案（N 次 LLM 调用）快 10-50 倍，成本低一个数量级

### 为什么两个独立开关？

KB 精排和 Web 精排面向不同场景，效果也独立：

- KB 精排影响 `_generate_queries` 中注入 LLM 的已知事实质量，间接影响搜索方向
- Web 精排影响 LLM 摘要的输入质量，直接影响 critique 判断和最终报告

分开控制允许渐进式启用、A/B 对比、以及按场景调参（如 KB 场景可能用更大的 `top_k`）。

### 架构设计

```
                  ┌──────────────────┐
                  │  RerankerService │  ← 封装 TextReRank API
                  │  (reranker.py)   │     sync + async
                  └────────┬─────────┘
                           │
            ┌──────────────┼──────────────┐
            │                             │
    ┌───────▼────────┐          ┌────────▼────────┐
    │ FactStore.query│          │   _web_search() │
    │ (kb_enabled)   │          │ (web_enabled)   │
    └───────┬────────┘          └────────┬────────┘
            │                             │
  Milvus ANN top_k=20          MCP API 返回 10 条
  → reranker 精排 top_k       → reranker 评分/过滤
  → 置信度/时效过滤            → resolve_urls
  → 返回 hits                  → LLM 摘要
```

### 降级策略

`rerank()` 方法永不抛出异常。降级路径：

| 场景 | 处理 |
|------|------|
| API Key 未配置 | `logger.warning` → 直通原始文档 |
| 401/403 认证失败 | `logger.error` → 直通（不重试） |
| 429 速率限制 | 3 次重试，指数退避（5s/10s/15s），耗尽后直通 |
| 5xx 服务端错误 | 3 次重试，线性退避（2s/4s/6s），耗尽后直通 |
| 网络异常 | 同 5xx |
| 响应无结果 | 直通原始文档 |
| 任意未预期异常 | 捕获 → `logger.error` → 直通 |

降级时返回原始文档顺序，`score=0.0`，业务不受影响。

### KB 精排的召回策略

reranker 启用时，Milvus 搜索的 `limit` 从 `top_k` 扩大为 `max(top_k * 3, 20)`，确保有足够候选供精排。例如 `top_k=10` 时，先召回 30 条，精排后保留 10 条。

## 后果

### 正面：
- KB 注入 LLM 的事实更相关，减少无关信息干扰查询生成
- Web 搜索摘要的输入更聚焦，减少低质量 snippet 影响 critique 判断
- 两个开关独立，可分别验证效果后逐步推广
- 依赖零新增，部署成本为零
- 降级策略保证管道可靠性不受 reranker 可用性影响

### 负面：
- 每个 KB 查询额外 1 次 API 调用（仅在 `kb_enabled=true` 时）
- 每个 Web 搜索额外 1 次 API 调用（仅在 `web_enabled=true` 时）
- `gte-rerank` 模型对超长文本（>512 tokens）的评分精度可能下降，需关注 snippet 截断策略
- 精排后结果数减少（`top_k=5`），可能丢失一些边缘相关信息

### 未解决的问题：
- 两个阶段的 `top_k` 和 `min_score` 最佳取值需通过 LLM-as-Judge 评估框架（ADR-005）对比确定
- 是否需要为 KB 和 Web 分别配置不同的 `top_k`（当前共享 `RERANKER_TOP_K`）

## 相关文档
- [RerankerService 实现](../../backend/src/agent/reranker.py)
- [FactStore.query 精排改造](../../backend/src/agent/kb/fact_store.py)
- [_web_search 精排改造](../../backend/src/agent/sub_agents/research_agent.py)
- [Configuration 新增字段](../../backend/src/agent/configuration.py)
- [测试套件](../../backend/test/test_reranker.py)
- [ADR-004: Milvus + Redis 缓存](004-milvus-and-redis-cache.md)
- [ADR-005: LLM-as-Judge 评估框架](005-llm-as-judge-eval-framework.md)

## 变更记录
- 2026-05-30: 交叉编码器重排序上线，KB 精排 + Web 精排双开关 
