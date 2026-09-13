# ADR-006: 异常分类与重试体系设计

## 状态
Accepted（已采纳）

## 背景
早期对所有 LLM/MCP 调用使用裸 `except Exception` 处理，导致：
- 认证失败（401）和速率限制（429）被同等对待（统一重试 3 次），无效重试浪费时间和配额
- 重试逻辑分散在 18 处代码中，行为不一致
- 异常信息丢失，排查困难（日志仅 "调用失败"）

## 决策
建立三层异常分类体系，将异常分为 TransientError（可恢复）和 PermanentError（不可恢复），统一所有 Agent 的重试行为。

## 理由

### 异常分类：
```
AgentError (基类)
├── TransientError (可恢复 → 重试 3 次，指数退避)
│   ├── LLMRateLimitError / LLMServerError / LLMNetworkError
│   ├── MCPRateLimitError / MCPServerError / MCPEmptyResultError
│   └── KBConnectionError / KBEmbeddingError
└── PermanentError (不可恢复 → 快速失败，零重试)
    ├── LLMAuthError / LLMBadRequestError
    ├── MCPAuthError / MCPAccessDeniedError / MCPParseError
    └── KBEmbeddingFatalError / KBConfigError
```

### 重试策略：
- TransientError: 3 次重试，基础退避 1.5s → 3s → 4.5s
- MCP 429: 延长退避 5s → 10s → 15s
- PermanentError: 零重试，直接抛出
- 重试耗尽：返回安全默认值（`""` / `None`），不崩溃流水线

### OpenAI SDK 异常翻译 (`_translate_openai_error`)：
将 OpenAI SDK 6 种原生异常按 HTTP status_code 精确映射到 Agent 异常体系（429→`LLMRateLimitError`, 401→`LLMAuthError`, 5xx→`LLMServerError` 等）。

### 统一重试函数：
抽取 `_retry_with_classified_errors()` 公共函数，所有 Agent 共用，消除 18 处分散的内联重试代码。

## 后果

### 正面：
- 401/403 认证错误即时失败，不再浪费重试时间（约 30s → 0s）
- 重试行为统一，新增 Agent 类型自动获得成熟重试逻辑
- 异常 `request_id` 字段保留，方便与 API 方协查

### 负面：
- 异常类层级 3 层继承，新增异常需理解分类逻辑
- 部分边界场景（408 Request Timeout）未单独分类，归入默认分支

## 相关文档
- [异常类定义](../../backend/src/agent/exceptions.py)
- [Agent 重试逻辑](../src/agent/base_agent.py:109) — `_retry_with_classified_errors`
- [LLM 异常翻译](../src/agent/llm/llm.py:27) — `_translate_openai_error`

## 变更记录
- 2026-04-21: 初始决策 — 建立三层异常分类体系 by @yunfang
- 2026-04-25: 新增 KB 相关异常类型 by @yunfang
- 2026-04-28: 抽取 `_retry_with_classified_errors` 统一重试函数 by @yunfang
