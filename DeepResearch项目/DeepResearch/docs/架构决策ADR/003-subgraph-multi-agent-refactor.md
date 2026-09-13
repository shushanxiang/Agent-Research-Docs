# ADR-003: 单体 Agent 图重构为 Sub-Graph 多 Agent 架构

## 状态
Accepted（已采纳）

## 背景
早期版本是一个单体 StateGraph，所有逻辑（计划生成、搜索、评估、报告写作）在一个扁平图中。随着功能增长出现以下问题：
- 单文件超过 400 行，难以独立测试和修改
- 无法独立调试搜索循环或写作逻辑，必须跑全图
- 报告写作只有一次 `final_answer` 节点，质量不可控
- 搜索评估循环与写作逻辑耦合，改动一处影响全局

## 决策
将单体图拆分为三个独立的子图（Sub-Graph），每个子图作为独立 StateGraph 编译，通过主图节点的条件边串联。

### 架构图：
```
MainGraph
  ├── generate_plan     (Plan → 等待人工确认 → 确认/重新规划)
  ├── ResearchAgent     (子图: 查询生成 → 并行搜索 → 评估 → 循环)
  └── WriterAgent       (子图: 提纲 → 草稿 → Critic审稿 → 修订循环 → 润色)
```

## 理由

### 子图拆分原则：
1. **ResearchAgent**：封装"搜索→评估→补搜"循环，对外暴露 END 信号（信息充足/达到最大循环次数）
2. **WriterAgent**：封装"提纲→写作→审稿→修订"循环，内建 Debate Loop
3. **主图**：仅负责 Plan 确认流程和子图调度

### Debate Loop 设计（WriterAgent 内部）：
- Critic 使用 JsonAgent 对草稿评分，输出 `CritiqueResult`（severity: critical/major/minor + problem + suggestion）
- Writer 在修订模式下接收反馈逐条修改
- 退出条件：`ready_for_polish=True` 或 `revision_count >= max_revisions(3)`
- 退出后进入 `cite_and_polish`：LLM 润色 + 短链接还原 + 引用去重

### 放弃的方案：
- **单体图 + 增加节点**：测试困难和代码膨胀不可避免
- **微服务拆分（独立进程）**：过度工程化，增加网络延迟和运维复杂度

### 风险与缓解：
- **风险**：子图状态传递依赖 `OverallState` 字段，新增字段需两处同步
- **缓解**：State 字段集中管理，Annotated reducer 自动合并

## 后果

### 正面：
- 每个子图可独立编译、可视化、调试
- Debate Loop 使报告质量可控（评分 <6 自动修订）
- 测试从 20+ 增长到 214 个，覆盖率 85%+

### 负面：
- Critic 节点额外消耗 1 次 LLM 调用（+5-10 秒延迟）
- OverallState 字段数从 8 个增长到 23 个

## 相关文档
- [MainGraph 定义](../../backend/src/agent/graph.py)
- [ResearchAgent 子图](../../backend/src/agent/sub_agents/research_agent.py)
- [WriterAgent 子图](../../backend/src/agent/sub_agents/writer_agent.py)
- [State 定义](../../backend/src/agent/state.py)
- [Critic Schema](../src/agent/tools_and_schemas.py:54) — `CritiqueResult`

## 变更记录
- 2026-03-18: 初始决策 — 单体图拆分为 Sub-Graph 多 Agent 架构
- 2026-03-20: WriterAgent 增加 Debate Loop 
- 2026-03-26: 修复 state 原地修改和 ready_for_polish 路由问题
