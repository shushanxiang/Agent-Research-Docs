# ADR-007: 全链路异步化 + LLM 流式输出

## 状态
Accepted（已采纳）

## 背景
有两个相互关联的需求需要一同解决：
1. **异步化**：所有 Agent 调用使用同步方法，在 LangGraph 节点内用 `asyncio.to_thread` 包裹，占用线程池且无法实现流式输出
2. **流式输出**：研究报告生成需要 30-60 秒，用户看不到任何进展，体验差

这两个需求技术上紧密耦合 —— 流式输出依赖异步 LLM 客户端，异步化是流式输出的前提。因此合并为一个决策。

## 决策
分层渐进式异步化（LLM → Agent → Node → KB），在此基础上打通全链路 token 级流式输出：LLM → Agent → Graph Node → Redis Streams → SSE → 前端。

## 理由

### 异步化策略（4 阶段）：

| 阶段 | 层次 | 新增方法 | 改动 |
|------|------|----------|------|
| Phase 1 | LLM | `agenerate_response()`, `astream_response()` | `llm.py` |
| Phase 2 | Agent | `astep()`, `astream_step()`, `acall()` | `base_agent.py` |
| Phase 3 | Node | `async def` nodes + `await agent.astep()` | research/writer agent |
| Phase 4 | KB | `_aembed()` | `fact_store.py` |

核心原则：**双模共存**，同步方法保留，异步方法新增而非替换。

### 流式输出链路：
```
OpenAI (stream=True) → async for chunk
  → Agent.astream_step(on_token)
    → on_token(text, node)  逐 token 回调
      → _emit_token          Graph config 注入的回调
        → XADD Redis Stream  {"token": {...}}
          → SSE data: {...}
            → 前端 setStreamingContent(prev + text)
```

### 流式回退：
`astream_step()` 先尝试 3 次流式调用 → 全部失败后回退到非流式 `astep()` → 完整结果作为单次 `on_token` 回调，前端无感知。

### 流式节点选择：
仅在输出较长的节点启用流式（其他节点 <200 tokens，非流式即可）：
- `generate_plan` — 计划生成（200-500 tokens）
- `cite_and_polish` — 最终润色（1000-3000 tokens）

### 前端状态管理：
- `streamingNode`：当前流式节点名（用于 "正在生成..." 标签）
- `streamingContent`：当前节点累计文本（逐 token 追加渲染）
- 节点切换时自动重置 buffer

### 放弃的方案：
- **全量 async 重写**：breaking 所有调用方，风险过高
- **仅异步化不做流式**：解决了线程池问题但用户体验无改善
- **仅流式不做异步**：技术上不可行，流式依赖 `AsyncOpenAI`

### 风险与缓解：
- **风险**：sync/async 双模增加维护负担
- **缓解**：核心逻辑共享（prompt_format → call），仅 I/O 层不同
- **风险**：双通道（token 事件 + 图事件）增加 Redis Stream 写入频率
- **缓解**：仅在 2 个长输出节点启用流式，短节点走常规图事件

## 后果

### 正面：
- 所有 Graph 节点不占用线程池
- 流式输出端到端打通，用户可实时看到 AI "正在书写"
- 异步速率限制（`asyncio.Lock`）避免同步锁争用
- 流式回退确保即使流式 API 不稳定，系统仍可完成工作

### 负面：
- 双模代码需要两套测试（sync + async）
- `astream_step()` 回退逻辑使调用链路较复杂
- MCP 和 Embedding 仍通过 `to_thread` 桥接，未实现原生异步 I/O

## 相关文档
- [LLM 流式实现](../src/agent/llm/llm.py:125) — `astream_response`
- [Agent 流式实现](../src/agent/base_agent.py:238) — `astream_step`
- [Graph 节点流式注入](../src/agent/graph.py:56) — `on_token` 回调
- [前端 SSE 流式处理](../../../frontend/src/lib/useResearchStream.ts:123)
- [速率限制器异步实现](../src/agent/base_agent.py:66) — `aacquire`

## 变更记录
- 2026-04-30: Phase 1-2 — LLM + Agent 层异步化（AsyncOpenAI + astep + astream_step）
- 2026-05-05: Phase 3 — Node 层异步化（graph nodes async def）
- 2026-05-08: Phase 4 — KB 层异步化 + 流式端到端打通 + 前端流式渲染
- 2026-05-10: 流式回退策略完善 
