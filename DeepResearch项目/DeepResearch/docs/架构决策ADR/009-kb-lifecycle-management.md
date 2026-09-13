# ADR-009: KB 生命周期管理模式设计

## 状态
Accepted（已采纳）

## 背景
知识库中的事实会随时间老化。例如"2025年Q1市场规模达15亿美元"在 Q3 可能已被新数据取代，但旧事实仍在向量检索时返回并影响查询生成。需要机制来管理事实的时效性。

## 决策
实现四档生命周期模式，通过环境变量 `KB_LIFECYCLE_MODE` 切换，控制事实的过滤、衰减和标记行为。

## 理由

### 四种模式：

| 模式 | 过滤 | 衰减 | 标记 | 适用场景 |
|------|------|------|------|----------|
| `off` | 不 | 不 | 不 | 纯语义搜索，不顾时效 |
| `inform` | 不 | 不 | 是 | 展示时效信息但不干预检索 |
| `freshness` | 是（统一阈值） | 是 | 是 | **默认**，Plan LLM 判断敏感度等级 |
| `lifecycle` | 是（按类别 TTL） | 是 | 是 | 精细化按类别管理 |

### Freshness 模式（默认）：
- Plan 阶段 LLM 判断时效敏感度 → `fresh_level`（high/medium/low）
- 对应年龄阈值：high=7天, medium=30天, low=180天
- 置信度衰减：`decay_factor = max(0.3, 1.0 - age_days / (max_age * 2))`

### Lifecycle 模式（高级）：
按事实类别独立 TTL：
- `market_data`: 7天, `product_info`: 30天, `strategy`: 90天, `technology`: 180天, `historical`: 永不过期

### 设计原则：
- **渐进增强**：从 off → inform → freshness → lifecycle 逐步升级
- **零代码切换**：环境变量控制

## 后果

### 正面：
- 知识库不被陈旧数据污染
- 默认 freshness 模式无需手动标注即可工作

### 负面：
- 分类依赖 LLM `FactExtractor`，误分类导致 TTL 偏差
- 4 模式 × 3 维度的测试组合较多

## 相关文档
- [生命周期模式定义](../../backend/src/agent/kb/lifecycle.py)
- [FactStore 查询逻辑](../src/agent/kb/fact_store.py:109)
- [FactExtractor 分类提取](../../backend/src/agent/kb/extractor.py)
- [ADR-004: Milvus + Redis 缓存](004-milvus-and-redis-cache.md)

## 变更记录
- 2026-05-18: freshness 模式上线
- 2026-05-20: lifecycle、inform、off 模式补齐
