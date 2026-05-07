# claw-ea Prompt Template for OpenClaw

> **给安装 agent 的指令：这一步是强制的，不可跳过。**
> claw-ea 的工作流规则（Capture-First v2：原文优先、category/type 分层、
> 文件必须转 Markdown、时间字段置信度自评、多消息合并策略等）
> 全部定义在下面的 AGENTS.md 和 TOOLS.md 片段中。如果不写入 workspace，
> claw-ea 的工具虽然能调用，但 agent 不知道正确的调用顺序和分类规则，
> 会导致手术安排被错误归档、文件内容丢失、idea 未进入创意池等问题。
>
> **执行方法：** 读取下面两个代码块的完整内容，分别追加写入到
> `~/.openclaw/workspace/AGENTS.md` 和 `~/.openclaw/workspace/TOOLS.md` 末尾。
> 如果文件中已有 `## 社媒消息自动处理（claw-ea）` 或 `### claw-ea` 段落，替换为下面的新版本。
> 写入后用 `cat` 确认内容正确。

---

## AGENTS.md 片段

**必须**写入 `~/.openclaw/workspace/AGENTS.md`（追加或替换已有的 claw-ea 段落）：

```markdown
## 社媒消息自动处理（claw-ea）

**触发条件**：当用户从飞书/企微/Telegram 转发工作消息时（手术通知、会议安排、文件、
截图、想法灵感、评审报告等），自动使用 claw-ea 工具集处理。不需要触发词，根据消息内容判断。

**Capture-First 核心原则**：原文零损失优先。你的职责是识别 + 分类 + 路由，
不要改写或摘要原文内容。文件正文通过 raw_body_path（MinerU 转换输出）原样落地。

**处理流程**：

1. **看懂消息**：你直接读文本/图片（你有多模态能力，不需要 OCR 兜底工具）

2. **分类判定**：输出两个字段：
   - `type`（qp 命名空间，必填）：meeting_minutes | document | idea | review | writing
   - `category`（claw-ea 业务细分，必填）：surgery | meeting | task | document | raw_thought | review

   映射（category → type）：
   meeting → meeting_minutes | surgery → document | task → document
   | document → document | raw_thought → idea | review → review

3. **时间抽取 + 置信度自评**（Q1）：
   只抽取有明确表达的时间（"明天下午3点"、"5/8 14:00"）。
   能 100% 锁定为 ISO 时间戳时才传 start_time 给 create_calendar_event。
   含糊表达（"下周"、"过几天"、"有空的时候"）→ 不自动建事件，提示用户补充时间地点。

4. **多消息合并**（Q4）：
   默认：同 sender + 5 分钟内连续消息 → 合并为一个 session 处理。
   用户覆盖：群里发 "/split" 或 "分开处理" → 逐条独立 capture。

5. **如果有附件**：调用 `claw_save_attachment` 保存文件。

6. **⛔ 文件转换（不可跳过）**：所有非纯文本文件（PDF/Word/Excel/PPT/图片/纯文本）
   → **必须**调用 `claw_convert_to_markdown` 获得 `md_path`。
   MinerU 已设为默认转换器（不需要传 hint），docling 为自动回退。
   - **PPT**：agent 读取转换后 Markdown 内容并总结，总结写入 content_data
     （不使用 raw_body_path）
   - **其他文件**：直接将 `md_path` 传给 raw_body_path

7. **创建笔记**（surgery 类别除外——手术不建笔记）：
   调用 `claw_create_note`，传入：
   - 必填：`category`、`title`（消息首句前 30 字）、`content_data`、`raw_body_path=md_path`
   - 推荐：`type`（不传则自动从 category 推导）、`source_channel`、`message_ts`、`project`
   - 文件类：`converter_used`（mineru 或其他）、`attachment_paths`

8. **idea 类异步调研**（Q2/Q3）：
   当 type=idea 时：
   - 原文通过 raw_body_path 写入创意池（`idea_stage="raw"`、`idea_topics=[...]`），不阻塞 capture 流程
   - 笔记写入成功后，尝试创建 OpenClaw cron 延迟调研任务：
     ```bash
     openclaw cron add \
       --name "claw-ea-idea-{note_id}" \
       --at +2min \
       --delete-after-run \
       --session main \
       --system-event "对笔记 <note_path> 做 AI 调研补充：web_search + 本地 vault MCP 检索，结果追加到 '## AI 调研补充' 段（区分'本地关联'和'外部检索'两类来源），完成后更新 frontmatter 的 processed_by_ai=true, idea_stage=enriched" \
       --timeout 120000 \
       --thinking low
     ```
   - cron 创建成功后告知用户："想法已归档到创意池（自动调研已排队，约 2 分钟后补充）"
   - **cron 创建失败时**（非交互环境等）：降级为路径 C 兜底——
     告知用户："想法已归档到创意池。需要我对这个想法做 AI 调研补充吗？"（用户 `/research` 手动触发）
   - cron 触发时 agent 收到 system-event → 读笔记 → 检索 → 追加补充段 →
     更新 frontmatter: `processed_by_ai: true`, `idea_stage: enriched`

9. **如果有日程/任务**：先展示摘要让用户确认，确认后调用对应工具：
   - **手术安排**：仅调用 `claw_create_reminder`（不建笔记、不建日历事件）。
   - **会议安排**：`claw_create_calendar_event` + `claw_create_reminder`
     （有用户议程项时）
   - **任务指派**：`claw_create_reminder`

10. **删除操作**：先向用户确认要删除的条目 →
    调用 `claw_delete_calendar_event(event_id=...)` 或
    `claw_delete_reminder(reminder_id=...)`。
    event_id / reminder_id 来自创建时的返回值。

**不触发 claw-ea 的场景**：闲聊、问答、指令、与工作信息归档无关的对话。
```

---

## TOOLS.md 片段

**必须**写入 `~/.openclaw/workspace/TOOLS.md`（追加或替换已有的 claw-ea 段落）：

```markdown
### claw-ea（医疗办公自动化 MCP 工具集）

**用途**：Capture-First v2 工作流——自动处理社媒通道消息 → 归档到 Obsidian + 日历 + 提醒

**11 个工具**：

| 工具 | 用途 | 自动/需确认 |
|------|------|-------------|
| `claw_save_attachment` | 保存附件，按日期分文件夹。**优先用 file_path** | 自动 |
| `claw_convert_to_markdown` | **非文本文件必须调用**：MinerU 默认转换器，返回 `md_path`。无需传 hint | 自动 |
| `claw_create_note` | 创建 Capture-First v2 笔记（§4 frontmatter schema，raw-body dedup） | 自动 |
| `claw_create_calendar_event` | 创建 Apple Calendar 事件（含 15 分钟提醒） | **需用户确认** |
| `claw_delete_calendar_event` | 按 event_id 删除日历事件 | **需用户确认** |
| `claw_create_reminder` | 创建 Apple Reminders 提醒 | **需用户确认** |
| `claw_delete_reminder` | 按 reminder_id 删除提醒 | **需用户确认** |
| `claw_ocr_image` | 图片 OCR（中英文）。**不再在 capture 流程自动调用**——agent 多模态直接读图 | 手动/备用 |
| `claw_detect_vault` | 扫描系统中的 Obsidian vault | 配置时用 |
| `claw_list_calendars` | 列出日历和提醒列表 | 配置时用 |
| `claw_save_config` | 保存 claw-ea 配置 | 配置时用 |

**claw_create_note v2 关键参数**：

| 参数 | 必填 | 说明 |
|------|:--:|------|
| `category` | ✅ | claw-ea 业务细分：surgery / meeting / task / document / raw_thought / review |
| `title` | ✅ | 自动生成：消息首句前 30 字 |
| `content_data` | ✅ | 业务字段（patient, procedure, surgeon, summary 等） |
| `raw_body_path` | ✅ | convert_to_markdown 返回的 md_path。文件内容直接成为笔记正文 |
| `attachment_paths` | — | save_attachment 返回的路径列表 |
| `type` | — | qp 命名空间，不传时从 category 自动推导 |
| `source_channel` | — | feishu / wecom / telegram / tui |
| `source_message_id` | — | 渠道消息 ID，防重 + 溯源 |
| `message_ts` | — | 消息原始时间（ISO 8601） |
| `project` | — | Obsidian wikilink，如 `[[项目名]]` |
| `converter_used` | — | 转换器名称（mineru, docling 等），写入 verbatim header |
| `idea_stage` | — | 仅 type=idea：raw / enriched / framed |
| `idea_topics` | — | 仅 type=idea：调研维度标签列表 |
| `related_event_id` | — | 关联的日历事件 ID |
| `related_reminder_id` | — | 关联的提醒 ID |

**category → type 映射表**（§4.1）：

| category | type | qp 路由 |
|----------|------|---------|
| meeting | meeting_minutes | 📋 会议纪要编译 → `02_Projects/[项目]/` |
| surgery | document | 🟢/🟡 直接归档（提醒事项承载） |
| task | document | 🟢/🟡 直接归档 |
| document | document | 🟢/🟡 直接归档 |
| raw_thought | idea | Route 9 → `05_创意池/` |
| review | review | 🔴 评审编译 → `06_评审知识库/` |

**消息分类动作表**：

| category | Obsidian 笔记 | 日历事件 | 提醒任务 |
|----------|:---:|:---:|:---:|
| surgery | ❌ | ❌ | ✅ |
| meeting | ✅ | ✅ | ✅（有用户议程项时） |
| meeting_minutes | ✅ | ❌ | ✅（用户的 action items） |
| task | ✅ | ❌ | ✅ |
| document | ✅ | ❌ | ❌ |
| raw_thought | ✅ | ❌ | ❌ |
| review | ✅ | ❌ | ❌ |

**raw_thought（idea）自动异步调研**：
写入创意池笔记后，agent 自动通过 `openclaw cron add --at +2min --delete-after-run`
创建一次性延迟调研任务。2 分钟后 agent 收到 system-event，独立执行 web_search +
本地 vault 检索，结果追加到 `## AI 调研补充` 段，完成后更新 frontmatter
（`processed_by_ai: true`, `idea_stage: enriched`）。如 cron 不可用则提示用户
手动 `/research` 触发。

**用户姓名匹配**：在排班表和议程中查找用户名及别名
（见 `~/.claw-ea/config.yaml` 的 `user` 配置）。

**⛔ 文件转换约束**：
收到非纯文本文件时，**必须先调用 `claw_convert_to_markdown`**（MinerU 默认，
自动 fallback 到 docling），获得 `md_path` 后传入 `claw_create_note` 的
`raw_body_path` 参数。**严禁跳过此步骤直接创建笔记**。

正确调用顺序：
1. `claw_save_attachment(file_path=...)` → 保存原始文件
2. `claw_convert_to_markdown(file_path=...)` → 获得 `md_path`
3. `claw_create_note(..., raw_body_path=md_path, converter_used="mineru")` → verbatim body

**审核流程**：笔记和附件直接创建（低风险）。日历和提醒**必须先展示摘要让用户确认**。
```

---

## 推荐安装工具

claw-ea 依赖外部转换器 CLI 将文件转为 Markdown。安装后服务器自动检测（`shutil.which()`）。

### 必装

| 工具 | 用途 | 安装命令 |
|------|------|---------|
| **MinerU** | 主力转换器（PDF/Word/PPT/Excel/图片）。v3.1.6+ 多格式支持 | `pipx install mineru` |
| **docling** | 回退转换器，MinerU 不可用时自动切换 | `pipx install docling` |
| **markitdown** | 轻量回退，Office 格式 + CSV | `pipx install markitdown` |

### 可选

| 工具 | 用途 | 安装命令 |
|------|------|---------|
| **LM Studio** + glm-OCR | 图片 Vision OCR（需配置 endpoint） | 见 [LM Studio 文档](https://lmstudio.ai) |

### 配置示例

```yaml
converters:
  lmstudio:
    endpoint: http://localhost:1234/v1
    api_key: "your-token"
    model: "glm-ocr"
    timeout: 120
  routing:
    pdf: [mineru, docling]
    docx: [mineru, docling, markitdown]
    pptx: [mineru, docling, markitdown]
    xlsx: [mineru, docling, markitdown]
    csv: [markitdown]
    html: [docling, markitdown]
    image: [lmstudio, mineru, docling, vision_ocr]
```
