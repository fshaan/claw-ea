# Decisions

> 本文件记录 claw-ea 的产品/架构决策**为什么**这样做。决策按时间倒序排列。
> 决策一旦写入此处，应视为长期生效；如要推翻，新增一条决议引用并解释原因。

---

## 2026-06-08 — 文件处理按类型分流 + 迁移残留清理

### 图片/PDF 走 agent 视觉直读 + 内链嵌入
- **决议**: 图片/PDF **不再默认转换格式**——由 agent 多模态视觉直接归纳核心内容写入笔记，
  原文件作为内链附件用 `![[file]]` 在笔记中渲染展示；`convert_to_markdown`/`ocr_image`
  降级为 agent 缺视觉能力时的兜底。office 文档（docx/pptx/xlsx）仍优先本机离线 MinerU
  （docling 兜底）；csv/html 走 markitdown/docling；其余类型由大模型决定提取方案，
  但原始文件始终经 `save_attachment` 归档。
- **为什么**: agent 本就有多模态能力，对图片/PDF 再走转换器是多余且有损的一环；
  让 agent 直读 + 原文件内联展示，信息更完整、笔记更可读。符合「Agent vs Tool 边界」
  原则——理解任务归 agent，副作用工具只做写入。
- **实现**: `obsidian.py` 新增 `_render_attachment_ref()` 按扩展名判定嵌入/链接；
  convert/obsidian docstring 去除「所有文件必须转换」强制措辞，改为按类型分流。
- **过程**: 经 codex 二次审查，修复 2 个 P2（工具契约自相矛盾、csv/html 误标 MinerU 默认）。

### venv 搬迁损坏修复（接续 2026-05-08 迁移审计）
- **决议**: 项目从 `Workspace/Claude` 搬到 `Workspace/devs` 后，`.venv` 整目录复制导致
  console script（pytest/mcp/uvicorn 等）shebang 烤死旧绝对路径。已**非破坏式重建**
  （备份→`uv sync`→验证→删备份）。pyproject `dev` 双源（optional-dependencies 与
  dependency-groups）版本对齐 `pytest>=9.0.2`，保留两个安装入口。
- **为什么**: 重建是唯一能修好 console-script shebang 的方式；`.venv/bin/python -m x`
  能绕过 shebang 但 `uv run x` 和 MCP/console 入口不能。
- **经验**: uv 项目整目录搬迁后，`.venv` 的 python 软链指向共享 store 仍可用，但 `bin/`
  下 console script 的 shebang 写死旧路径——表现为 `uv run <tool>` 坏而
  `.venv/bin/python -m <tool>` 正常。重建即解，不必怀疑解释器版本（曾误判为 `Path|None`
  的 Python 版本问题，实为坏 venv 产物）。迁移审计还需覆盖 README 内的配置路径。

### 含 PHI 的一次性脚本归档到仓库外
- **决议**: 含真实患者信息的已执行一次性运维脚本移出仓库到 `~/.claw-ea/ops-archive/`，
  工作树零 PHI。`.gitignore` 增补 `.gspowers/`、`.omc/`、`.venv.bak/`。
- **为什么**: PHI 留在 git 工作树即便 gitignore 也会被 Spotlight 索引、Time Machine
  备份、其它工具扫描——只有移出仓库根才真正消除暴露面。遵守工作空间「PHI 不进 git」红线。

---

## 2026-05-08 — 路径迁移修复与启动健壮性

- **决议**: 
  - 启动脚本 `run-server.sh` 统一使用相对路径和 `PYTHONPATH` 显式导出。
  - 移除 `FastMCP` 初始化中的非标准 `json_response` 参数。
- **为什么**: 项目从 `Workspace/Claude` 迁移到 `Workspace/devs` 后，由于脚本内部硬编码了旧路径导致启动失败。
  - **相对路径**: 使用 `cd "$(dirname "$0")"` 确保脚本在任何目录下运行都能定位到虚拟环境。
  - **PYTHONPATH**: 对于 `src/` 布局，必须显式将 `src` 目录加入 Python 搜索路径，否则 `-m claw_ea.server` 会找不到模块。
  - **标准参数**: `json_response` 在官方 `mcp` SDK 中非标准，移除以保证跨版本兼容性，防止握手失败。
- **经验**: 迁移项目后必须执行全局路径审计，尤其是 `.venv`、启动脚本和 MCP 客户端配置。

---

## 2026-05-07 — 手术流程反转：建日历 → 建提醒事项

- **决议**: 手术通知**改为只建提醒事项**，不建日历事件、不建笔记
- **为什么**: 实际使用发现日历事件冗余——手术时间由排班决定、不需要日历视图，提醒事项更轻量直接；且手术台次时间可由 `schedule_time_slots` 推算，不需要手动输入到日历
- **推翻**: v0.1.3.1 的"仅建日历事件"决议
- **台次推算**: `{房间}-{台次数}` 格式（如 502-2），台次数映射 `schedule_time_slots[N]` → `due_date`（ISO-8601）
- **根因修复**: `schedule_time_slots` 配置存在于 config.yaml 但从未写入 agent prompt；本次同步更新 AGENTS.md + TOOLS.md

---

## 2026-05-06 — Capture-First v2 重设计（Q1-Q8）

设计源：`docs/design/2026-04-30-capture-first-redesign.md`

### 触发原因
实际使用中 LLM-as-extractor 范式频繁产生"几乎空白"的 md 文件——frontmatter 有 category 但 body 只有占位符。LLM 同时承担"识别 + 分类 + 字段提取"三件事，提取环节最易失败，结果是"原文丢了，提取也没成功"双重信息损失。

### 8 条决议

#### Q1: 日历/提醒时间字段获取 → B 极简抽取 + 抓不到走 A
- **决议**: 只抽明确时间表达（"明天下午 3 点"、"5/8 14:00"），抽不到则不自动建事件，agent 提示用户口述补充
- **为什么**: 平衡了零成本场景（明确时间）和容错（含糊场景不建错事件）。避免 LLM "猜时间"产生错误日历项
- **实施**: agent prompt 加置信度自评——能 100% 锁定 ISO 时间戳才传 `start_time`

#### Q2: 想法调研动作时机 → B 异步
- **决议**: idea 类消息原文先入创意池（不阻塞），后台触发 AI 调研后追加 `## AI 调研补充` 段
- **为什么**: capture-first 原则——原文零损失优先，调研失败不影响入库
- **实施** (2026-05-06 PR-7): B+C 混合模型——OpenClaw cron 创建一次性延迟任务（`--at +2min --delete-after-run`），agent 收到 system-event 后独立执行 web_search + vault 检索。cron 不可用时降级为用户 `/research` 手动触发
- **Spike**: `docs/spikes/2026-05-06-openclaw-background-tasks.md` — 确认 OpenClaw 内置 cron scheduler（croner v10.0.1），支持秒级精度、独立 model/thinking 配置

#### Q3: 调研信息来源 → 本地 vault + web 混合
- **决议**: 本地 obsidian vault 检索 + web_search 联合，supplement 段区分两类来源
- **为什么**: 本地给上下文一致性（能引用已有笔记），web 给新鲜度，两者互补

#### Q4: 多消息合并策略 → C 混合
- **决议**: 默认自动（同 sender + 5min 窗口），用户用 "/split" 显式覆盖
- **为什么**: 5min 窗口符合实际转发节奏；用户覆盖语义提供逃生通道

#### Q5: 与 my2nd-brain qp skill 的清盘契约 → claw-ea 写 qp 命名空间（v2 翻转）
- **决议**: claw-ea 直接写 qp v1.5.0 路由表能消费的 `type` 值（meeting_minutes / document / idea / review / writing），qp 一行不改
- **为什么 v1 → v2 翻转**: 2026-04-30 v1 决议要求 qp 新增来源识别规则；2026-05-06 复核 qp v1.5.0 SKILL.md 后发现该规则未实施，且不应实施——让 qp 维护来源特殊分支不健康
- **教训**: 跨工具契约不能假设双方协调；必须落到至少单边代码可独立验证

#### Q6: 图片 OCR 默认开关 → A 默认关
- **决议**: 移除 capture 流程的 ocr_image 自动调用，原图通过 wiki-link 嵌入；OpenClaw agent 多模态 LLM 直接读图
- **为什么**: capture-first 下原图保真，OCR 是 v1 兼容遗物；多模态 agent 已具备直接读图能力

#### Q7: 存量"几乎空白"笔记处理 → B 标 legacy + 移 _legacy/
- **决议**: 一次性迁移脚本扫描 inbox，body < 50 字符且无附件 → 加 `legacy: true` + `legacy_reason`，mv 到 `_legacy/`
- **为什么**: 可恢复（不删数据） + 不污染搜索/路由（隔离到子目录）

#### Q8: 转换器 routing 策略 → 统一 MinerU
- **决议**: 取消 academic vs default 双链路，PDF/docx/pptx/xlsx/图片默认走 MinerU 3.1.6；docling 降为 fallback
- **为什么**: MinerU 3.1.6 已扩展为多格式解析器，能力覆盖原 docling 主链路场景；简化降低维护成本
- **影响面**: converters.py ~15 行简化（拍平 routing dict） + agent prompt 移除 hint 指引

---

## 2026-04-30 — MinerU 集成升级 v2.7.6 → v3.1.6

- **决议**: 升级 uvx-managed MinerU；CLI 从 `magic-pdf` 改名为 `mineru`
- **为什么**: 2.7.6 仅 PDF；3.1.6 扩展为多格式文档解析器，且 `magic-pdf` 已弃用
- **修复**: commit a8c8f4b 更新 converters.py 调用为 `mineru` CLI
- **副产品发现**: 项目本地有两份 MinerU 安装（PATH 版 3.0.9 vs venv 版 3.1.6），简化为 PATH 直连

---

## v0.1.4.0（2026-03-27）— 删除工具补全

- **决议**: 新增 `delete_calendar_event` / `delete_reminder` MCP 工具
- **为什么**: 实际使用中确认了缺失。原始设计仅 create，但用户场景需要纠错路径（建错事件后删除）
- **约束**: 必须由 agent 先向用户确认才能调用——不允许静默删除

---

## v0.1.3.1（2026-03-26）— Surgery 流程精简

- **决议**: 手术通知**仅**建日历事件，不建 Obsidian 笔记、不建提醒
- **为什么**: 笔记承载会议议程/任务的语义价值；手术通知只需"明天 9 点动 X 患者"，日历事件足够；建笔记和提醒造成冗余
- **配套**: 日历事件默认 15 分钟前提醒（commit ff96483）

---

## v0.1.3.0（2026-03-26）— Markdown-First 内容管道

- **决议**: 新增 `convert_to_markdown` MCP 工具 + `raw_body_path` 参数模式
- **为什么**: 大文件（PDF/docx/pptx）转换后内容很长，把 markdown 字符串塞进 MCP 响应会撑爆 agent 上下文。改为返回临时文件路径，`create_obsidian_note` 通过 `raw_body_path` 读取后写入笔记，临时文件自动清理
- **副产品**: 服务器启动时清理失效临时文件（commit 215f680）

---

## v0.1.2.0（2026-03-26）— 转换器 fallback chain 与 passthrough

- **决议**:
  - 5 个转换器后端组成自动 fallback chain（docling → markitdown → mineru → lmstudio → vision_ocr）
  - 新增 passthrough converter 处理 plaintext 文件（.txt/.md/.rst/.log）
  - `is_usable()` 质量检测：转换输出非空且 80% 以上字符可见才算成功，否则走 fallback
- **为什么**: 单一转换器对所有格式不可能最优；fallback 自动化避免用户配置；passthrough 避免对纯文本做无意义转换
- **教训**: dedup hash 必须包含 raw_body 内容（commit c0cdd1d 修复——之前漏掉导致同一文件不同转换结果不去重）

---

## v0.1.0-v0.1.1 — 核心架构决策

### Agent vs Tool 边界（核心设计原则）
- **决议**: MCP 服务器只提供 side-effect 工具（写文件、调系统 API、读系统状态）；所有"理解"任务（消息分类、图片理解、审批对话格式化）由 agent LLM 处理
- **为什么**: 让 agent 自由组合工具，避免工具内嵌"理解"逻辑导致脆弱

### No classify_message tool
- **决议**: 不提供消息分类工具；分类是 agent 的工作，工具描述里包含期望的 JSON schema
- **为什么**: 分类逻辑在工具内会随领域演化频繁改动；放在 agent prompt 里用户和 agent 都能看见、可调

### No prepare_schedule_items tool
- **决议**: 格式化审批摘要是文本生成，agent 直接做，不需要工具
- **为什么**: 同上原则

### No setup_wizard tool
- **决议**: 配置流程拆成三个原子工具（detect_obsidian_vault / list_apple_calendars / save_config），由 agent 编排
- **为什么**: 编排逻辑在 agent prompt 中可读可改；wizard 工具内嵌交互逻辑会变成死代码

### pyobjc 而非 AppleScript
- **决议**: Apple Calendar / Reminders 用 pyobjc-framework-EventKit
- **为什么**: 中文医疗术语含特殊字符，AppleScript 字符串转义易破；pyobjc 返回正确的事件 ID 和错误信息

### Content-hash 去重
- **决议**: 笔记文件名 `{date}-{category}-{hash[:8]}.md`，重复消息产生相同 hash 自动跳过
- **为什么**: 简单可靠的幂等性，不需要外部 dedup 数据库

### macOS-only，不做平台抽象
- **决议**: 不引入 platform interface 层，每个工具一个模块；跨平台支持延后到真有需求再做
- **为什么**: 避免过度抽象。当前用户单平台，YAGNI

### 两层测试
- **决议**: 默认 mock 测试随处可跑；`@pytest.mark.macos` 命中真 EventKit/Vision API；`@pytest.mark.converter` 命中真转换器 CLI
- **为什么**: CI 不需要 macOS 也能跑大部分测试，但保留集成测试入口验证真实行为

### 文件传递处理大内容
- **决议**: `convert_to_markdown` 返回临时文件路径而非 markdown 字符串
- **为什么**: 见 v0.1.3.0 条目（同决策的延伸）

---

## OpenClaw 集成路径（v0.1.0 后期 / 2026-03-25）

- **决议**: claw-ea 作为 OpenClaw **原生插件**而非 MCPorter 桥接
- **为什么**: MCPorter 只是 MCP 服务器测试 CLI，不与 OpenClaw agent 集成；只有原生插件能注册到 agent 工具池
- **机制**: `openclaw-plugin/` 内 TypeScript wrapper 启动 `python -m claw_ea.server` 子进程，通过 MCP JSON-RPC 桥接 stdin/stdout
- **教训**: `server.py` 必须有 `if __name__ == "__main__": main()` 守护，否则 `python -m claw_ea.server` 只导入不启动
