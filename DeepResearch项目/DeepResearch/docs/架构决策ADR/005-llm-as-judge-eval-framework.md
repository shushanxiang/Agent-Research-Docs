# ADR-005: 引入 LLM-as-Judge 评估框架

## 状态
Accepted（已采纳）

## 背景
DeepResearch 输出的研究报告质量只能通过人工阅读判断，传统测试仅验证代码能否跑通，无法度量：
- 报告是否存在事实幻觉
- 信息覆盖是否遗漏关键维度
- 引用来源是否真实可查
- 各 Agent 节点的输出质量（Plan、Query、Critique）

## 决策
构建独立的 LLM-as-Judge 评估框架，支持端到端（E2E）和组件级（Component）两层评估，使用 Pydantic 结构化输出量化评估结果。

## 理由

### 两层评估设计：

**端到端（5 维度 × 1-5 分）**：事实准确性、信息覆盖度、逻辑结构、时效性、引用质量（含幻觉检测）

**组件级（7 个维度）**：Plan 评估、Query 评估、摘要保真度（monkey-patch 捕获原始搜索结果）、Critic 评估、引用审计（逐条验证 URL）、Plan-Query 对齐、Plan Reflection

### 关键技术决策：
- **Pydantic 结构化输出**：`E2EScore`, `PlanScore`, `QueryScore` 等，可量化对比、可 JSON 存档
- **安全格式化 (`_safe_format`)**：UUID 标记替换占位符，防止报告内容中的 `{key}` 字面文本被错误替换
- **Monkey-patch 注入**：运行时替换 `WebSearchAgent.step` 捕获原始搜索结果，不修改生产代码
- **独立模块**：`eval/` 目录下零耦合到 Agent 生产代码

### 放弃的方案：
- **人工评估**：不可规模化
- **规则匹配**：无法评估语义质量
- **集成到 Agent 代码**：增加耦合

### 风险与缓解：
- **风险**：Judge LLM 自身也有幻觉
- **缓解**：多次调用取平均 + 结构化评分标准减少主观性

## 后果

### 正面：
- 系统输出质量可量化追踪
- 组件级评估可定位问题节点（如 "Query 覆盖度低" → 改进 prompt）
- Pydantic 输出可直接序列化存档做历史对比

### 负面：
- 每次完整评估 10+ 次 LLM 调用，仅用于回归测试和重大变更验证
- Monkey-patch 依赖 `WebSearchAgent.step` 内部实现，重构需同步更新

## 相关文档
- [Evaluator 实现](../../eval/evaluator.py)
- [Judge 实现](../../eval/judge.py)
- [评估 Prompts](../../eval/prompts.py)

## 变更记录
- 2026-04-18: 初始决策 — 建立 LLM-as-Judge 评估框架
- 2026-04-19: 增加 Plan Reflection 评估维度
- 2026-04-20: 安全格式化解决 `{key}` 冲突
