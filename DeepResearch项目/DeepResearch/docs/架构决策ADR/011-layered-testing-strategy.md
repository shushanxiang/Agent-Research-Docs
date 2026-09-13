# ADR-011: 分层测试策略与测试套件构建

## 状态
Accepted（已采纳）

## 背景
项目早期仅有几个散落测试，依赖真实 API，运行慢且不稳定。架构复杂度增长（Sub-Graph、异常分类、异步化、流式输出）后，测试缺失成为最大风险。需要在保持测试速度（<30s）的同时覆盖核心逻辑。

## 决策
建立分层测试策略，用 mock 隔离外部依赖，实现快速可重复的测试套件。

## 理由

### 测试分层：

| 层级 | marker | 内容 | 数量 | 耗时 |
|------|--------|------|------|------|
| Unit | `unit` | Agent/LLM/Utils/Config 单测 | ~120 | <5s |
| Integration | `integration` | 子图拓扑、节点行为、路由逻辑 | ~90 | <15s |
| E2E | - | 完整流水线（真实 API） | ~4 | 5-10min |

### Mock 策略：
- Agent.astep/step → AsyncMock/MagicMock，返回固定结构响应
- WebSearchAgent → mock `Application.call`
- FactStore → mock `_get_kb_store()` 隔离 Milvus
- Redis → 连接本地测试 DB，不 mock

### 关键覆盖：
- **Graph 拓扑**：节点存在性、条件边路由、循环边
- **Agent 行为**：TransientError→3次重试、PermanentError→0次重试、流式回退
- **Integration**：ResearchAgent 搜索循环、WriterAgent Debate Loop、Plan 确认流程

## 后果

### 正面：
- 214 个测试 <20s 跑完，可集成 pre-commit hook
- 分层策略使 CI 不依赖外部 API
- 子图级集成测试使重构风险大幅降低

### 负面：
- Mock 需与真实实现保持同步
- Integration 测试不验证 LLM 输出质量（依赖 ADR-005 LLM-as-Judge 补充）

## 相关文档
- [测试目录](../../test/)
- [Pytest 配置](../pyproject.toml:59)
- [test_graph.py](../../test/test_graph.py)

## 变更记录
- 2026-05-25: 分层测试策略建立，补齐 169 个测试 
- 2026-05-27: 异步+流式测试增至 214 个 
