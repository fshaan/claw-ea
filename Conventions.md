# Conventions

> 本文件记录 claw-ea 的目录布局、文件命名、代码风格、测试组织等约定。
> 所有约定都应当被代码实际遵守；如出现违反，要么改代码要么改本文件。

---

## 1. 目录结构

```
claw-ea/
├── pyproject.toml                # uv + hatchling 构建配置
├── README.md                     # 中文优先（用户主要语言）
├── README.en.md                  # 英文版（次要）
├── CHANGELOG.md                  # 按版本倒序，每个 release 一段
├── CLAUDE.md                     # Claude Code 项目指南
├── Decisions.md                  # 产品/架构决策（why）
├── Conventions.md                # 文件/目录约定（本文件）
├── TODOS.md                      # 进行中工作 + Post-MVP 延后清单
├── src/claw_ea/                  # Python MCP 服务器主代码
│   ├── server.py                 # MCP server 入口（含 __main__ 守护）
│   ├── config.py                 # 配置加载/保存/验证
│   ├── converters.py             # 转换器 dispatcher、routing、fallback chain
│   ├── eventkit_utils.py         # 共享 EKEventStore 初始化和权限
│   └── tools/                    # 每个 MCP 工具一个模块
│       ├── ocr.py
│       ├── attachment.py
│       ├── converter.py          # convert_to_markdown MCP wrapper
│       ├── obsidian.py
│       ├── calendar.py
│       ├── reminder.py
│       └── setup.py
├── openclaw-plugin/              # OpenClaw 原生插件（TypeScript）
│   └── src/
│       ├── index.ts              # 插件入口
│       ├── mcp-bridge.ts         # 子进程 + JSON-RPC 桥接
│       └── tools.ts              # 工具注册到 OpenClaw
├── tests/                        # pytest 测试
├── docs/                         # 项目文档（非用户面向）
│   ├── design/                   # 设计文档（按日期前缀命名）
│   └── superpowers/              # superpowers 工作流产物
└── scripts/                      # 一次性脚本（迁移、维护）
```

`.gspowers/`、`.omc/`、`.planning/`、`.claude/` 等以 `.` 起头目录是工具产物，**不入主代码评审范围**。

---

## 2. 命名约定

### Python 模块
- `src/claw_ea/converters.py`：**单数形式**——这是分发器（dispatcher），全项目唯一
- `src/claw_ea/tools/converter.py`：**单数形式**——MCP 工具 wrapper，对应一个 tool 名
- 通用规则：模块名描述**它做什么**而非**它包含什么**——避免 `utils.py`、`helpers.py`、`misc.py`

### 文件命名
- 设计文档：`docs/design/YYYY-MM-DD-name.md`（日期前缀便于排序）
- 笔记输出（写入 obsidian）：`{date}-{category}-{hash[:8]}.md`（content-hash 去重）
- 一次性脚本：`scripts/<动作>_<对象>.py`（如 `migrate_legacy_inbox.py`）
- **含 PHI 的一次性运维脚本**：严禁放仓库（含 `src/`、根目录），即便 gitignore 也会被
  索引/备份/扫描。归档到仓库外 `~/.claw-ea/ops-archive/`（与 config.yaml 同处 PHI 运行域）

### 附件在笔记内的引用
- **图片 / PDF**：用 `![[file]]` 嵌入语法，在 Obsidian 笔记内**内联渲染展示**
- **其余类型**（docx/xlsx/…）：用 `[[file]]` 链接（Obsidian 无法内联渲染）
- 实现：`src/claw_ea/tools/obsidian.py` 的 `_render_attachment_ref()`，`_render_body`
  与 `_render_verbatim_header` 共用，避免两处判定漂移

### 配置文件
- 用户配置：`~/.claw-ea/config.yaml`（**不**放项目目录下，跨项目隔离）
- 测试配置：`pyproject.toml` 内 `[tool.pytest.ini_options]`

### 启动脚本
- **无硬编码路径**：启动脚本（如 `run-server.sh`）严禁包含绝对路径。必须使用 `cd "$(dirname "$0")"` 定位到项目根目录。
- **环境隔离**：脚本应显式指定使用项目内的虚拟环境（`./.venv/bin/python`）。
- **PYTHONPATH**：由于采用 `src/` 布局，启动脚本必须包含 `export PYTHONPATH="$PYTHONPATH:./src"`，确保模块可见性。

---

## 3. 代码风格

### Python
- **版本**: Python 3.11+（用 `dict[str, list[str]]` 等 PEP 585 原生泛型，不要 `typing.Dict`）
- **包管理**: `uv`（不用 pip、poetry、pdm）
- **lint**: `ruff check`（不用 flake8/pylint）
- **依赖**: 主依赖在 `[project.dependencies]`，开发依赖在 `[dependency-groups.dev]`
- **MCP 构造**: 仅使用 `FastMCP` 官方标准参数，严禁添加如 `json_response` 等非标准字段，防止协议握手失败。

### 类型注解
- 函数签名 MUST 带返回类型注解
- 参数类型注解尽量加，但单测试 fixture 可省

### 错误处理
- 工具内不做"agent 可恢复的错误"包装——返回 raw error 让 agent LLM 决策
- 系统级错误（FileNotFoundError、PermissionError）原样抛出
- 用户输入验证只在系统边界做（MCP 工具入口、config 加载），内部模块互信

### 注释
- 默认不写注释——好的命名 + 类型注解已经表达意图
- 例外：常量魔法值（如 `ALARM_OFFSET_MIN = -15  # 默认提前 15 分钟提醒`）、非显然的算法选择、外部 API 怪癖的 workaround

---

## 4. 测试组织

### pyproject.toml 注册的 marks
```toml
markers = [
    "macos: tests requiring macOS APIs (EventKit, Vision)",
    "converter: tests requiring real converter CLIs (docling, markitdown)",
]
```

### 测试分层
| Mark | 何时运行 | 内容 |
|---|---|---|
| (无 mark) | CI 默认 | mock 测试，随处可跑 |
| `@pytest.mark.macos` | macOS 本地手动 / CI macOS runner | 真 EventKit/Vision API |
| `@pytest.mark.converter` | 已装转换器 CLI 的环境 | 真 docling/markitdown/mineru |

### 命令
```bash
uv run pytest                          # 默认（mock）
uv run pytest -m "not macos"           # 显式排除 macos
uv run pytest -m macos                 # 仅 macos
uv run pytest -m converter             # 仅 converter
uv run pytest tests/test_obsidian.py -k "test_dedup"  # 单测试
```

### 测试文件命名
- 一对一：`tests/test_<module>.py` 对应 `src/claw_ea/tools/<module>.py`
- 集成：`tests/test_integration_<scenario>.py`

---

## 5. Git / 提交约定

### Commit message
- 格式：`<type>(<scope>): <description>`
- 常用 type：`feat`、`fix`、`docs`、`test`、`chore`、`refactor`
- scope 例：`converters`、`obsidian`、`plugin`、`server`
- 示例（来自项目历史）:
  - `feat(plugin): register convert_to_markdown tool in index.ts`
  - `fix(converters): use 'mineru' CLI name instead of legacy 'magic-pdf'`
  - `chore: bump version and changelog (v0.1.4.0)`

### 分支
- 主分支：`main`（启用了分支保护）
- 功能分支：`feat/<short-name>`（如 `feat/md-first`）
- 修复分支：`fix/<short-name>`

### 版本
- SemVer：`v<major>.<minor>.<patch>`
- 当前版本号源：CHANGELOG.md 顶部 + `pyproject.toml` 的 `version` 字段（两者必须同步）

---

## 6. 文档约定

### README 双语
- `README.md` 中文优先（用户主要语言）
- `README.en.md` 英文版本，内容与中文同步
- 提交涉及功能变化的改动 MUST 同时更新两份

### CHANGELOG
- 顶部最新版本，倒序排列
- 每版本含 `### Added` / `### Changed` / `### Fixed` 子段（按需）

### 设计文档
- 路径：`docs/design/YYYY-MM-DD-<topic>.md`
- 含 frontmatter：`title`、`date`、`author`、`status`（draft / approved / superseded）
- `supersedes:` 字段引用被替代的旧文档

### CLAUDE.md
- 用于 Claude Code 项目指南
- 包含：项目概述、架构、工具列表、命令、关键设计决策、配置示例、领域逻辑

---

## 7. 配置文件结构

`~/.claw-ea/config.yaml` 顶层段：

| 段名 | 作用 |
|---|---|
| `user` | 用户身份（name + aliases），用于会议/手术日程匹配 |
| `obsidian` | vault 路径 + notes 子目录 |
| `attachments` | 附件归档路径 + 是否按日期组织 |
| `apple` | calendar_name + reminder_list |
| `categories` | 业务分类的具体配置（如 surgery 时间槽、用户角色） |
| `converters` | 可选；覆盖 CLI 路径、routing 表、lmstudio 端点 |

详细 schema 见 `CLAUDE.md` 的 "Config File" 段。

---

## 8. OpenClaw Workspace 同步

`~/.openclaw/workspace/` 内的 `AGENTS.md` 和 `TOOLS.md` 与项目代码**必须手动同步**。

### 何时需要同步
- 新增 / 删除 / 重命名 MCP 工具
- 改变 agent 行为（分类逻辑、合并策略、approval 流程）
- frontmatter schema 变化

### 同步路径
1. 改 `src/claw_ea/tools/<module>.py` 实现
2. 改 `src/claw_ea/server.py` 注册
3. 改 `openclaw-plugin/src/tools.ts` TS 工具定义
4. 改 `openclaw-plugin/PROMPT_TEMPLATE.md`（项目内模板源）
5. 同步到 `~/.openclaw/workspace/AGENTS.md` 和 `TOOLS.md`（用户环境）
6. 重启 OpenClaw

---

## 9. 设计原则速查（不重复 Decisions.md，仅列出适用约定）

- **Capture-First**：原文零损失优先（v2 重设计后）
- **LLM-as-Router**：agent 输出仅 `{type, category, action_set}`，不输出 content
- **Verbatim by Default**：text/image 消息原样落地
- **AI 调研补充必须可识别**：双段结构 + 视觉分隔 + 来源标注
- **确定性工具优先**：文件转 MD 用 MinerU/docling，不用 LLM 描述
