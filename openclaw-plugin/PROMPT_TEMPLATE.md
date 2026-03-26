# claw-ea Prompt Template for OpenClaw

安装 claw-ea 插件后，将以下内容添加到 OpenClaw workspace 的 `AGENTS.md` 和 `TOOLS.md` 中。

---

## AGENTS.md 片段

将以下内容添加到 `~/.openclaw/workspace/AGENTS.md`：

```markdown
## 社媒消息自动处理（claw-ea）

**触发条件**：当用户从飞书/企微/Telegram 转发工作消息时（手术通知、会议安排、文件、截图等），自动使用 claw-ea 工具集处理。不需要触发词，根据消息内容判断。

**处理流程**：
1. **看懂消息**：你自己读文本/看图片，判断消息类别（surgery/meeting/meeting_minutes/task/document/general）
2. **如果有图片且你能看到**：直接读图提取信息。如果你不能看图，调用 `claw_ocr_image` 做 OCR
3. **如果有附件**：调用 `claw_save_attachment` 保存文件
4. **⛔ 如果是非纯文本文件（PDF/Word/Excel/PPT/图片/文本文件）**：**必须**调用 `claw_convert_to_markdown` 将文件转为 Markdown，获得 `md_path`。**绝对不可跳过此步**
   - **PPT 特殊处理**：读取转换后的 Markdown 内容，总结后将摘要写入 `content_data`（不使用 `raw_body_path`）
   - **其他文件**：直接将 `md_path` 传给 `raw_body_path`
5. **创建笔记**（surgery 类别除外，手术安排不创建笔记）：调用 `claw_create_note`，传入 category、title、结构化数据、附件路径。如果第 4 步获得了 `md_path`，传入 `raw_body_path=md_path`
6. **如果有日程/任务**：先展示摘要让用户确认，确认后才调用对应工具
   - **手术安排**：仅调用 `claw_create_calendar_event`（不建笔记、不建提醒）
   - **会议安排**：`claw_create_calendar_event` + `claw_create_reminder`（有用户议程项时）
   - **任务指派**：`claw_create_reminder`

**多条消息关联**：如果用户连续发送多条消息属于同一个事件，合并后一起处理。不同事件按内容语义分开处理。

**不触发 claw-ea 的场景**：闲聊、问答、指令、与工作信息归档无关的对话。
```

---

## TOOLS.md 片段

将以下内容添加到 `~/.openclaw/workspace/TOOLS.md`：

```markdown
### claw-ea（医疗办公自动化 MCP 工具集）

**用途**：自动处理社媒通道收到的工作消息 → 归档到 Obsidian + 日历 + 提醒

**9 个工具**：

| 工具 | 用途 | 自动/需确认 |
|------|------|-------------|
| `claw_save_attachment` | 保存附件，按日期分文件夹。**优先用 file_path** | 自动 |
| `claw_convert_to_markdown` | **非文本文件必须调用**：将文件转为 Markdown 临时文件，返回 `md_path` | 自动 |
| `claw_create_note` | 创建带 frontmatter 的 Obsidian 笔记 | 自动 |
| `claw_create_calendar_event` | 创建 Apple Calendar 事件 | **需用户确认** |
| `claw_create_reminder` | 创建 Apple Reminders 提醒 | **需用户确认** |
| `claw_ocr_image` | 图片 OCR（中英文） | 自动（仅当你不能直接看图时用） |
| `claw_detect_vault` | 扫描系统中的 Obsidian vault | 配置时用 |
| `claw_list_calendars` | 列出日历和提醒列表 | 配置时用 |
| `claw_save_config` | 保存 claw-ea 配置 | 配置时用 |

**消息分类动作表**：

| 类别 | Obsidian 笔记 | 日历事件 | 提醒任务 |
|------|:---:|:---:|:---:|
| surgery | ❌ | ✅ | ❌ |
| meeting | ✅ | ✅ | ✅（有用户议程项时） |
| meeting_minutes | ✅ | ❌ | ✅（用户的 action items） |
| task | ✅ | ❌ | ✅ |
| document | ✅ | ❌ | ❌ |
| general | ✅ | ❌ | ❌ |

**用户姓名匹配**：在排班表和议程中查找用户名及别名（见 `~/.claw-ea/config.yaml` 的 `user` 配置）。

**⛔ 文件转换强制约束（不可跳过）**：

收到非纯文本文件（PDF、Word、Excel、PPT、图片）时，**必须先调用 `claw_convert_to_markdown`** 将文件转为 Markdown，再将返回的 `md_path` 传给 `claw_create_note` 的 `raw_body_path` 参数。**严禁跳过此步骤直接创建笔记**。

PPT 文件特殊处理：转换后由 agent 读取 Markdown 内容并生成详细总结，将总结写入 `content_data`（不使用 `raw_body_path`）。

正确调用顺序：
1. `claw_save_attachment(file_path=...)` → 保存原始文件
2. `claw_convert_to_markdown(file_path=...)` → 获得 `md_path`
3. `claw_create_note(..., raw_body_path=md_path, ...)` → 笔记正文 = 转换后的 Markdown

**审核流程**：笔记和附件直接创建（低风险）。日历和提醒**必须先展示摘要让用户确认**。
```

---

## 推荐安装工具

claw-ea 依赖外部转换器 CLI 将文件转为 Markdown。安装后服务器自动检测（`shutil.which()`）。

### 必装

| 工具 | 用途 | 安装命令 |
|------|------|---------|
| **docling** | 主力转换器，PDF/Word/PPT/Excel/HTML/图片 | `pipx install docling` |
| **markitdown** | 轻量回退，Office 格式 + CSV | `pipx install markitdown` |

### 可选

| 工具 | 用途 | 安装命令 |
|------|------|---------|
| **MinerU** (magic-pdf) | 学术 PDF、复杂公式（LaTeX） | `pipx install magic-pdf` |
| **LM Studio** + glm-OCR | 图片 Vision OCR（需配置 endpoint） | 见 [LM Studio 文档](https://lmstudio.ai) |

### 配置示例

如果安装了可选工具，在 `~/.claw-ea/config.yaml` 中添加：

```yaml
converters:
  lmstudio:
    endpoint: http://localhost:1234/v1
    api_key: "your-token"
    model: "glm-ocr"
    timeout: 120
  routing:
    pdf:
      default: [docling]
      academic: [mineru, docling]
    image:
      default: [lmstudio, docling, vision_ocr]
```
