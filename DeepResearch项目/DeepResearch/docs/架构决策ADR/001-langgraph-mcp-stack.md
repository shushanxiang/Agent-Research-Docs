# ADR-001: 选择 LangGraph + MCP 作为核心技术栈

## 状态
Accepted（已采纳）

## 背景
项目启动时需要确定以下关键技术选型：
- Agent 编排框架：需要支持多步骤流水线、并行扇出、条件循环
- Web 搜索后端：需要可靠的中文搜索能力
- LLM 接入层：需要兼容多种模型（企业内部已有多个 LLM API 端点）

## 决策
使用 LangGraph 作为 Agent 编排框架，使用阿里百炼 MCP (dashscope SDK) 作为 Web 搜索后端，使用 OpenAI 兼容协议接入 LLM。

## 理由

### 选择 LangGraph 的原因：
1. **原生支持复杂控制流**：StateGraph 提供条件边（conditional edges）、Send API 并行扇出、子图嵌套，比 LangChain AgentExecutor 的线性思维链灵活得多
2. **状态管理内建**：TypedDict + Annotated reducer 自动合并并行节点输出，无需手动加锁或协调
3. **OpenAI 兼容协议**：不绑定特定模型提供商，通过 `OPENAI_API_KEY` + `LLM_BASE_URL` 切换
4. **LangGraph Platform 支持**：可部署到 LangGraph Cloud，获得内建 Checkpointer、API Server 等能力

### 选择阿里百炼 MCP 的原因：
1. **业务约束**：企业内部使用，阿里云生态已具备访问权限
2. **托管搜索能力**：MCP `Application.call` 封装了搜索引擎选择和结果格式化
3. **零运维成本**：不需要自建 SearXNG 或维护 Google/Bing API 代理

### 放弃的方案：
- **LangChain AgentExecutor**：不支持复杂的 Fan-out + 条件循环组合
- **CrewAI / AutoGen**：2025 年 7 月时版本尚不稳定，API 频繁变动
- **直接调用 SerpAPI / Bing API**：需要额外采购和配额管理，且中文搜索效果不佳

### 风险与缓解：
- **风险**：MCP 服务限流影响搜索可用性
- **缓解**：后续引入令牌桶速率限制（参见 ADR-002）
- **风险**：LangGraph 版本升级可能引入 Breaking Changes
- **缓解**：锁定 `langgraph>=0.2.6` 最小版本，通过 pyproject.toml 控制

## 后果

### 正面：
- 图结构天然可 Mermaid 导出，调试体验好
- LangGraph Checkpoint 内建支持状态持久化
- 模型切换仅需修改环境变量

### 负面：
- LangGraph 概念较多（StateGraph, Send, interrupt），学习曲线较陡
- MCP 响应格式不稳定（多层次 JSON 嵌套），后续需构建防御性解析（参见 ADR-010）

## 相关文档
- [Agent 图定义](../../backend/src/agent/graph.py)
- [LLM 封装层](../../backend/src/agent/llm/llm.py)
- [Web 搜索 Agent](../src/agent/base_agent.py:407) — `WebSearchAgent` 类
- [MCP 配置](../../backend/.env.example)

## 变更记录
- 2026-03-15: 初始决策 — 选定 LangGraph + MCP + OpenAI 兼容协议技术栈 
