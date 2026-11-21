# 架构设计说明

> 本文档描述当前代码骨架的分层结构、模块职责、数据流与扩展点，供后续开发参考。

## 一、设计目标

- **分层解耦**：渠道发现、抓取、分析、持久化各自独立，通过抽象接口协作。
- **可替换**：模型提供方、抓取方式、存储实现、分析策略均可在不改上层流程的前提下替换。
- **可扩展**：预留流式输出、向量化去重、增量分析、新数据源接入等扩展点。
- **轻量起步**：核心依赖标准库，第三方依赖按需引入；骨架可导入、可查看配置，具体实现逐步补齐。

## 二、分层结构

```
┌─────────────────────────────────────────────┐
│  CLI 入口 (src/cli.py)                        │  命令解析、参数装配
├─────────────────────────────────────────────┤
│  流程编排 (src/pipeline/orchestrator.py)       │  串联各阶段，依赖注入
├──────────┬──────────┬──────────┬─────────────┤
│ collector│ crawler  │ analyzer │  storage    │  业务能力层（接口 + 实现）
│ 渠道发现  │ 抓取收集  │ 分析归纳  │ 台账/文件    │
├──────────┴──────────┴──────────┴─────────────┤
│  llm (src/llm) 模型接入层：抽象接口 + 工厂注册  │
├─────────────────────────────────────────────┤
│  models (领域模型)  config (配置)              │  基础层
└─────────────────────────────────────────────┘
```

## 三、模块职责

| 模块 | 路径 | 职责 | 当前状态 |
| --- | --- | --- | --- |
| 配置 | `src/config/settings.py` | 读取环境变量 / `.env`，提供全局配置与数据目录 | 已实现 |
| 领域模型 | `src/models/domain.py` | `Target`、`SiteRecord`、`RawDocument`、`AnalysisResult` 等统一结构 | 已实现 |
| 模型接入 | `src/llm/` | `LLMProvider` 抽象、LM Studio 兼容实现、工厂注册 | 接口 + 本地实现骨架 |
| 渠道发现 | `src/collector/` | LLM 推荐候选站点，JSON 解析为站点记录 | 接口 + LLM 实现 |
| 抓取收集 | `src/crawler/` | HTTP 抓取、正文提取、生成原始资料 | 接口 + HTTP 实现（BS4，trafilatura 可选） |
| 分析归纳 | `src/analyzer/` | 首次分析、增量分析、结果溯源 | 接口 + LLM 实现（全量归纳 + 增量提示词，带来源文件清单） |
| 持久化 | `src/storage/` | 站点台账仓储接口、SQLite 实现、文件路径与命名约定 | 接口 + SQLite 实现 + 命名约定 |
| 流程编排 | `src/pipeline/` | 串联三阶段，注入各组件 | 已实现（含 `analyze_all` 全量归纳与台账回写） |
| 命令行 | `src/cli.py` | 子命令入口、环境检查 | 已接入 `doctor` / `discover` / `collect` / `analyze` |

## 四、数据流（对应业务四阶段）

1. **需求输入**：CLI 传入对象（国家 / 人 / 机构）与类型（财政 / 结构 / 历史），构造 `Target`。
2. **渠道发现**：`ChannelCollector.discover()` 产出 `SiteRecord` 列表；`Pipeline` 将新站点写入 `SiteRepository` 台账。
3. **抓取收集**：`Crawler.fetch()` 抓取 `PENDING` 站点，生成 `RawDocument`；按「时间 + 内容」命名存入 `data/raw/`；台账记录状态与来源文件。
4. **分析归纳**：`DocumentAnalyzer.analyze()` 归纳资料产出 `AnalysisResult`（含来源文件清单）；增量场景调用 `analyze_incremental()`，只处理 `last_analyzed_at` 之后的更新。

## 五、核心抽象与扩展点

### 1. 模型提供方（`src/llm/base.py`）

- 新增云端模型或其他本地后端：实现 `LLMProvider`，在 `factory._REGISTRY` 注册，或运行时 `register_provider()`。
- 预留能力：`chat_stream()` 流式输出、`embed()` 向量化（后续用于语义去重 / 检索）。
- 推理模型兼容：部分模型先输出 `reasoning_content`（思考链）、正式 `content` 滞后；接口在 `content` 为空时回退取 `reasoning_content`，正式分析时需给足 `max_tokens`。

### 2. 业务组件接口

- `ChannelCollector`：可替换为 LLM 推荐、搜索引擎、手工清单、RSS 等不同来源。
- `Crawler`：可替换为静态抓取、正文提取库、浏览器动态渲染等。
- `DocumentAnalyzer`：可替换提示词模板、模型组合、规则 + 模型混合策略。
- `SiteRepository`：可替换为 SQLite、JSON 文件或后续 ORM 数据库。

### 3. 装配方式

- `Pipeline` 通过构造函数接收各组件，便于在测试中注入替身（mock）。
- 后续可在 `pipeline` 层增加装配工厂，按配置选择具体实现。

## 六、关键设计决策

| 决策点 | 当前选择 | 后续替换路径 |
| --- | --- | --- |
| 数据模型 | 标准库 `dataclass` + `Enum` | 可平滑迁移到 pydantic，上层接口不变 |
| 配置加载 | dataclass + 环境变量，可选 `.env` | 可迁移到 pydantic-settings |
| HTTP 客户端 | `httpx`（延迟导入） | 不影响业务接口，可换 requests 等 |
| 台账存储 | 抽象接口 + SQLite 文件实现 | 必要时按接口换 ORM / 其他数据库 |
| 文件命名 | 集中在 `storage/paths.py` | 调整命名规则只改该模块 |

## 七、后续落地顺序

1. ~~仓储 SQLite 实现~~（已完成：站点增查改、状态筛选、增量时间与来源文件）。
2. ~~LLM 连通性测试~~（已完成：`doctor` 检查可达性、模型匹配与最小对话）。
3. ~~抓取实现~~（已完成：HTTP 抓取 + 正文提取 + 落盘 `data/raw/`，台账记录来源文件）。
4. ~~渠道发现~~（已完成：LLM 推荐站点、JSON 解析容错、去重入库）。
5. ~~分析实现~~（已完成：提示词模板 + 归纳整理 + 结果落盘 `data/output/` + 来源溯源，台账回写已分析状态与时间）。
6. 增量分析：CLI 接入 `incremental`，按 `last_analyzed_at` 过滤更新内容（分析器增量方法已预留）。
7. 测试与错误处理、日志规范。

## 八、目录一览

```
src/
├── cli.py                 # 命令行入口
├── config/settings.py     # 配置加载
├── models/domain.py       # 领域数据模型
├── llm/                   # 模型接入：base / lm_studio / factory
├── collector/             # 渠道发现：base / llm_collector / prompts
├── crawler/               # 抓取：base / http_crawler
├── analyzer/              # 分析：base / llm_analyzer / prompts
├── storage/               # 仓储接口 + SQLite 实现 + 路径命名 + 落盘
└── pipeline/orchestrator.py # 流程编排
data/                      # 运行数据（不纳入 Git，含 .gitkeep 占位）
docs/                      # 设计文档
```
