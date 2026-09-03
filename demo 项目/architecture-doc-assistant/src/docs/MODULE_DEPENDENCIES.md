# ── 模块依赖图 ──
#
# 本文件记录了 architecture-doc-assistant 各模块之间的调用关系，
# 用于新人快速理解代码结构和开发时的依赖约束。

## 层级依赖规则

```
表示层 (frontend/)     →     路由层 (app/api/)      单向依赖
路由层 (app/api/)      →     服务层 (app/services/)  单向依赖
服务层 (app/services/) →     检索层 (app/retrievers/) 单向依赖
服务层 (app/services/) →     Agent层 (app/agents/)    单向依赖
所有层                 →     核心层 (app/core/)       全局依赖
所有层                 →     数据层 (app/models/)     全局依赖（仅 ORM）
```

## 模块清单

### 1. `app/core/` — 基础设施层
| 文件 | 职责 | 被依赖 |
|------|------|--------|
| `config.py` | 全局配置 (Settings via pydantic) | 所有模块 |
| `security.py` | JWT + 密码哈希 | `api/` 认证路由 |
| `logging.py` | 日志初始化 | `main.py` 启动时调用 |
| `deps.py` | FastAPI Depends (用户/角色校验) | `api/` 所有路由 |

### 2. `app/api/` — 路由层
| 文件 | 路由前缀 | 核心方法 |
|------|----------|----------|
| `documents.py` | `/api/v1/documents` | upload, list, get, delete |
| `search.py` | `/api/v1/search` | regulations, atlas |
| `chat.py` | `/api/v1/chat` | regulation, atlas, sessions |
| `atlas.py` | `/api/v1/atlas` | nodes/compare, nodes/export |
| `regulations.py` | `/api/v1/regulations` | detail, related |
| `admin.py` | `/api/v1/admin` | users, roles, logs |
| `enterprise.py` | `/api/v1/enterprise` | spaces, permissions |

### 3. `app/services/` — 业务服务层
| 文件 | 类 | 调用方 |
|------|---|--------|
| `document.py` | DocumentService | `api/documents.py` |
| `search.py` | SearchService | `api/search.py` |
| `chat.py` | RegulationQAService, AtlasQAService | `api/chat.py` |
| `parse.py` | ParseService | `tasks/parse.py` (Celery) |
| `export.py` | ExportService | `api/atlas.py` |

### 4. `app/retrievers/` — 检索器层
| 文件 | 类 | 被 service 依赖 |
|------|---|-----------------|
| `hybrid.py` | HybridRetriever (RRF+Rerank) | `services/search.py`, `services/chat.py` |
| `atlas.py` | AtlasSearchService | `services/search.py` |
| `relation.py` | ClauseRelationService, NodeComparisonService | `services/chat.py` |

### 5. `app/agents/` — Agent 编排层
| 文件 | 内容 | 被依赖 |
|------|------|--------|
| `prompts.py` | 所有 Prompt 模板常量 | `services/chat.py`, `services/parse.py` |
| `__init__.py` | LangChain Agent 工具集 | 由 service 按需加载 |

### 6. `app/models/` — 数据模型层
| 文件 | 实体 |
|------|------|
| `document.py` | Document, Regulation, Chapter, Clause, AtlasNode, Image |
| `session.py` | ChatSession |

### 7. `tasks/` — 异步任务层
| 文件 | 任务 | Celery Queue |
|------|------|--------------|
| `parse.py` | parse_document_task, build_index_task, ocr_task | default |

---

## 核心数据流

### 文档入库链路
```
User → API(/documents/upload) → DocumentService.upload()
    → Celery(parse_document_task)
        → MinerU 解析
        → 元数据提取 (LLM)
        → PostgreSQL 写入
        → Celery(build_index_task)
            → 文本切片 → BGE-M3 → Chroma
```

### 规范问答链路
```
User → API(/chat/regulation) → RegulationQAService.answer()
    → HybridRetriever.retrieve() → [Chroma Dense + Sparse + Redis BM25]
    → RRF 融合 → Rerank
    → 版本校验 (废止检测)
    → Prompt 组装 → 通义千问 → 溯源标注 → Response
```

### 图集问答链路
```
User → API(/chat/atlas) → AtlasQAService.answer()
    → [Chroma atlas_nodes + Chroma images]
    → 节点去重合并
    → 图片 URL 组装
    → Prompt 组装 → 通义千问 → 图文 Response
```
