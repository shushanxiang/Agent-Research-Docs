# ADR-010: 结构化 JSON 输出的鲁棒性处理

## 状态
Accepted（已采纳）

## 背景
LLM 经常输出不规范的 JSON：尾逗号、缺少代码围栏、JSON 外夹杂解释文本。早期仅做简单正则匹配 ` ```json ... ``` ` + `json.loads()`，经常因格式不规范崩溃，导致流水线中断。

## 决策
建立多层 JSON 提取策略，在 `Post.extract_pattern()` 中实现从宽松到严格的逐级尝试。

## 理由

### 提取策略（4 级降级）：

```
Level 1: 正则匹配 ```json ... ``` 围栏
  ↓ 失败
Level 2: 枚举所有 {...} 候选区间
  - 括号平衡验证 (depth counter)
  - 尾逗号清理: ,\s*([}\]]) → \1
  - json.loads() 验证 → 选最长有效 JSON
  ↓ 失败
Level 3: 最长候选区间包裹在 {...} 中重试
  ↓ 失败
Level 4: 返回原始文本（非 JSON 模式如 markdown 提取）
```

### 尾逗号清理：
LLM 最常见错误 — `"key": "value",}` 在解析前自动修复。

### 放弃的方案：
- **仅匹配围栏**：成功率约 80%
- **json_repair 库**：引入额外依赖，对小错误过度修复
- **function calling 强制结构**：与自由文本 + JSON 混合输出模式冲突

## 后果

### 正面：
- JSON 解析成功率从约 80% 提升到 95%+
- LLM 输出格式变化不影响系统稳定性

### 负面：
- 尾逗号清理可能掩盖真正结构错误（概率极低）
- 候选区间策略在多个无关 `{}` 时可能选错（至今未出现）

## 相关文档
- [Post 处理类](../../backend/src/agent/post.py) — `extract_pattern`, `_clean_json`, `_extract_json`
- [JsonAgent 入口](../src/agent/base_agent.py:308)

## 变更记录
- 2026-05-24: 初始决策 — 多层 JSON 提取 + 尾逗号清理
