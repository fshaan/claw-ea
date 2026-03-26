# Design: claw-ea 行为约束增强 + 纯文本支持 + Prompt 模板

Generated on 2026-03-26
Branch: feat/md-first
Status: DRAFT

## Problem Statement

在实际使用 claw-ea 过程中发现三个问题：

1. **LLM 跳过文件转换**：agent 经常跳过 `convert_to_markdown` 步骤，直接调用 `create_obsidian_note`，导致笔记正文为空或仅包含 wikilink，文件内容无法在 Obsidian 中搜索
2. **手术安排动作过重**：手术排班只需要创建提醒任务，不需要 Obsidian 笔记和日历事件
3. **纯文本文件不支持**：`.txt` 等纯文本文件无法通过 `convert_to_markdown` 管道，dispatch() 会抛 ValueError
4. **PPT 需要总结**：PPT 幻灯片原文转换后信息碎片化，应由 agent 总结后写入笔记
5. **Word 全文写入**：Word 文档与 PDF 一样，全文转 MD 后写入笔记

## 文件处理策略总结

| 文件类型 | 转换方式 | 写入笔记方式 |
|----------|----------|-------------|
| PDF | convert_to_markdown → md_path | raw_body_path=md_path（全文） |
| Word (.docx) | convert_to_markdown → md_path | raw_body_path=md_path（全文） |
| Excel (.xlsx) | convert_to_markdown → md_path | raw_body_path=md_path（全文） |
| PPT (.pptx) | convert_to_markdown → agent 读取 md → 总结 | content_data 含 summary（不用 raw_body_path） |
| 图片 | convert_to_markdown → md_path | raw_body_path=md_path（OCR 全文） |
| 纯文本 (.txt/.md/.rst/.log) | convert_to_markdown(passthrough) → md_path | raw_body_path=md_path（全文） |

## 消息分类动作表

| 类别 | Obsidian 笔记 | 日历事件 | 提醒任务 |
|------|:---:|:---:|:---:|
| surgery | ❌ | ❌ | ✅ |
| meeting | ✅ | ✅ | ✅（有用户议程项时） |
| meeting_minutes | ✅ | ❌ | ✅（用户的 action items） |
| task | ✅ | ❌ | ✅ |
| document | ✅ | ❌ | ❌ |
| general | ✅ | ❌ | ❌ |

## 方案设计

### 方案 A：MCP tool description 内嵌约束（核心，自动生效）

将关键行为约束写进 MCP tool 的 description 字符串。任何 MCP 客户端（OpenClaw、Claude Desktop、Cursor）在发现工具时都能读到，无需额外配置。

**约束分配原则**：每个工具只写该工具自身的关键约束，1-2 句话，不重复完整工作流。

#### convert_to_markdown — 加入首行约束

```
IMPORTANT: MUST be called for ALL files (including text) before creating Obsidian notes.
For PPT files: agent should read the converted markdown, summarize it, then pass the
summary to create_obsidian_note via content_data (do NOT use raw_body_path for PPT).
```

#### create_obsidian_note — 加入首行约束

```
IMPORTANT: For files (PDF/Word/Excel/images/text), raw_body_path MUST be the md_path
from convert_to_markdown. Never skip the conversion step.
Do NOT create notes for surgery category — use create_reminder only.
```

#### create_calendar_event — 末尾追加

```
Note: Do NOT use for surgery schedules — use create_reminder instead.
```

#### create_reminder — 末尾追加

```
For surgery schedules: this is the primary action (no calendar event, no note).
```

### 方案 B：随项目附带 Prompt 模板

新建 `openclaw-plugin/PROMPT_TEMPLATE.md`，包含：

1. **AGENTS.md 片段**：完整 6 步处理流程 + PPT 分支 + surgery 例外 + ⛔不可跳过约束
2. **TOOLS.md 片段**：9 个工具表 + 分类动作表 + 审核流程 + 文件转换强制约束段落
3. **推荐安装工具**：
   - `docling`（主力转换器，PDF/Word/PPT/Excel/HTML/图片）：`pipx install docling`
   - `markitdown`（轻量回退，Office/CSV）：`pipx install markitdown`
   - 可选：MinerU `magic-pdf`（学术 PDF + 公式）、LM Studio + glm-OCR（图片 OCR）

### 代码修改：passthrough 转换器

在 `converters.py` 中添加 passthrough 转换器，处理纯文本文件：

```python
_PLAINTEXT_EXTENSIONS = {".txt", ".md", ".rst", ".log"}

def convert_passthrough(file_path: Path) -> str:
    """Read plaintext file and return content as-is."""
    return file_path.read_text(encoding="utf-8")
```

- 在 DEFAULT_ROUTING 中注册
- 在 _get_available_check 中返回 True（始终可用）
- 在 _run_converter 中调用

## 涉及文件

| 文件 | 改动 |
|------|------|
| `src/claw_ea/converters.py` | 添加 passthrough 转换器 + 路由 |
| `src/claw_ea/tools/converter.py` | 增强 docstring |
| `src/claw_ea/tools/obsidian.py` | 增强 docstring |
| `src/claw_ea/tools/calendar.py` | 增强 docstring |
| `src/claw_ea/tools/reminder.py` | 增强 docstring |
| `openclaw-plugin/src/tools.ts` | 同步 4 个 description |
| `openclaw-plugin/PROMPT_TEMPLATE.md` | **新建**：Prompt 模板 |
| `tests/test_converters.py` | 添加 passthrough 测试 |
| `~/.openclaw/workspace/AGENTS.md` | 补充 PPT 流程 + surgery 仅提醒 |
| `~/.openclaw/workspace/TOOLS.md` | 补充 PPT 说明 |

## 风险评估

- **description 长度**：每个工具增加 1-2 句，远在 MCP 描述常规范围内
- **空 .txt 文件**：空内容会被 `is_usable()` 拒绝，dispatch 返回 fallback warning，行为合理
- **.md 文件经 passthrough**：已是 Markdown，passthrough 读取后写入临时文件，保持管道统一
- **PPT 总结需 agent 读取 md**：会消耗 agent context，但 PPT 转换结果通常较短（幻灯片要点），可接受
