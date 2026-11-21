# AI 信息收集工具（ai_tool）

基于本地大模型的自动化资料收集与整理工具：给定关注对象与资料类型，由 AI 协助发现信息渠道、抓取并分析网页资料，按时间增量更新，最终输出带来源溯源的整理结果。

> 项目已完成分层代码骨架（接口与编排就绪，具体实现逐步补齐），架构细节见 [`docs/architecture.md`](./docs/architecture.md)。

## 一、项目构思

输入关注的**对象**（国家、人物、机构等）和**资料类型**（财政、结构、历史等），系统按以下四个阶段运转：

1. **需求输入**：告诉 AI 要找什么对象、什么类型的资料。
2. **收集渠道**：AI 寻找相关网站，并保存链接。
3. **收集资料**：AI 分析已收集网站的资料并保存。
   - 未被分析的网站与已被分析的网站分开存放；
   - 记录分析时间，不重复分析过去已分析的资料；
   - 二次分析指令启动时，只分析该网站自上次分析时间之后的更新内容；
   - 资料文件按「时间 + 内容」命名。
4. **分析资料**：AI 对资料做归纳整理，未分析与已分析分开存放；输出整理好的资料，并标注结果提取自哪几个文件。

原始构思见 [`架构.txt`](./架构.txt)。

## 二、技术栈与现有环境

| 类别 | 选型 / 现有环境 | 说明 |
| --- | --- | --- |
| 开发语言 | Python 3.12 | 本机已安装 Python 3.12.10 |
| 大模型 | LM Studio 本地模型 | 主用 9B 千问（Qwen）；LM Studio 提供 OpenAI 兼容的本地接口 |
| 模型调试 | Cherry Studio | 用于对话调试、提示词与效果对比 |
| 代码编辑 | VS Code | 开发环境 |
| 版本管理 | Git + GitHub | 远程仓库：`https://github.com/yumeng2050/ai_tool` |
| 本地界面 | FastAPI + 原生页面 | 本机回环访问的简易 Web 界面，复用现有 CLI / Pipeline 流程 |

### 模型接入思路

- 优先调用 **LM Studio 本地服务**（OpenAI 兼容接口，默认地址 `http://localhost:1234/v1`），在 LM Studio 中加载 Qwen 9B 模型并开启 Local Server。
- 在代码中封装统一的模型客户端，便于在本地模型、其他本地模型或云端接口之间切换。
- 9B 参数量模型能力有限，复杂归纳任务可预留切换到更大模型的能力；提示词模板分层维护，便于调优。

## 三、代码目录结构

```
ai_tool/
├── README.md              # 项目说明（本文件）
├── requirements.txt       # Python 依赖
├── start.bat              # 双击一键启动本地 Web 界面
├── .env.example           # 配置模板（模型端点、模型名等）
├── docs/
│   └── architecture.md    # 分层架构、模块职责与扩展点说明
├── src/
│   ├── cli.py             # 命令行入口（doctor / discover / collect / analyze ...）
│   ├── config/            # 配置加载（环境变量 / .env）
│   ├── models/            # 领域数据模型（Target / SiteRecord / RawDocument ...）
│   ├── llm/               # 模型接入：抽象接口 + LM Studio 实现 + 工厂注册
│   ├── collector/         # 渠道发现（抽象接口）
│   ├── crawler/           # 网页抓取与正文提取（抽象接口）
│   ├── analyzer/          # 资料分析、增量分析（抽象接口 + LLM 归纳实现 + 提示词模板）
│   ├── storage/           # 站点台账仓储接口 + 文件路径命名约定
│   ├── pipeline/          # 流程编排，串联各阶段并注入组件
│   └── web/               # 本地 Web 界面：FastAPI 接口 + 静态单页
└── data/                  # 运行数据（不纳入 Git，含 .gitkeep 占位）
    ├── sites/             # 站点台账
    ├── raw/               # 抓取的原始资料
    └── output/            # 整理后的资料
```

各层均面向抽象接口编程，模型提供方、抓取方式、存储实现、分析策略均可独立替换，详见 [架构文档](./docs/architecture.md)。

## 四、核心设计要点

### 1. 站点台账

用 SQLite（或 JSON）记录每个信息源，建议字段：

| 字段 | 说明 |
| --- | --- |
| url | 网站链接 |
| target | 关注对象（国家 / 人 / 机构） |
| category | 资料类型（财政 / 结构 / 历史） |
| status | 未分析 / 已分析 |
| first_found_at | 首次发现时间 |
| last_analyzed_at | 最近一次分析时间 |
| source_files | 由该站点产出的资料文件清单 |

### 2. 增量分析

- 台账记录每个站点的 `last_analyzed_at`；
- 二次分析时，只抓取并处理该时间点之后的更新内容；
- 已分析过的历史资料不重复进入分析流程。

### 3. 文件命名与存放

- 原始资料、分析结果按「时间 + 内容摘要」命名；
- 未分析 / 已分析的网站与资料分别放在不同目录；
- 整理结果必须记录来源文件列表，实现可溯源。

### 4. 抓取与正文提取

- 使用 HTTP 客户端抓取页面，配合正文提取工具去除导航、广告等噪声；
- 遵守目标站点的访问规则，控制请求频率，避免高频抓取。

## 五、快速开始

1. 准备 Python 3.12 虚拟环境：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. 安装依赖：

   ```powershell
   pip install -r requirements.txt
   ```

3. 打开 LM Studio，加载 Qwen 9B 模型并启动 Local Server（默认 `http://localhost:1234/v1`）。
4. 复制 `.env.example` 为 `.env`，填写模型端点、模型名等配置（`.env` 不纳入 Git）。
5. 检查配置与环境是否就绪：

   ```powershell
   python -m src.cli doctor
   ```

6. 启动本地 Web 界面（二选一）：
   - 双击项目根目录 `start.bat`，会自动启动服务并打开浏览器；
   - 或命令行执行：

     ```powershell
     python -m src.web.server
     ```

     然后访问 `http://127.0.0.1:8000`（仅本机访问）。

7. 命令行方式同样可用：`doctor` / `discover` / `collect` / `analyze` 已接入，`incremental`（增量二次分析）待后续接线。

## 六、开发路线图

- [x] 项目骨架、配置加载、分层抽象与目录初始化
- [x] LLM 客户端连通性测试（`doctor` 检查可达性、模型匹配与对话返回）
- [x] 站点台账（SQLite）与状态管理
- [x] 网页抓取与正文提取（HTTP 抓取、BS4 正文提取、落盘 raw）
- [x] 渠道发现：LLM 生成候选站点并入库
- [x] 全量资料分析：读取 `data/raw/`、LLM 归纳、结果落盘 `data/output/` 并回写台账状态
- [x] 结果归纳整理与来源溯源（结果附来源文件清单）
- [x] 本地简易 Web 界面：模型状态、目标发现、站点台账、抓取收集、分析结果查看，双击 `start.bat` 启动
- [ ] 增量（二次）分析：CLI 接入，按 `last_analyzed_at` 过滤站点更新内容
- [ ] 命令行 / 交互入口串联通车（增量命令待接）
