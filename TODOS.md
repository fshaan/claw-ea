# TODOS

## 进行中 — Capture-First v2 重设计

> 设计源: `docs/design/2026-04-30-capture-first-redesign.md`
> 决议日期: Q5 翻转 2026-05-06；Q1-Q4/Q6-Q8 收敛 2026-05-06
> 拆分原则: 单一职责 PR、独立可 revert、按依赖顺序

### PR-1: converters.py routing 简化（破冰）
- **What:** 删除 `DEFAULT_ROUTING` 嵌套 dict 中的 `academic` 分支，拍平为 `{ext: chain}` 一层；`dispatch()` 移除 hint 参数
- **Scope:** 仅 `src/claw_ea/converters.py`，约 15 行改动 + docstring 更新（`_run_mineru` 不再描述 "Specialty: academic papers"）
- **Why:** Q8 决议——MinerU 3.1.6 已扩展为多格式解析器，不再需要分流
- **Validates:** 现有 `@pytest.mark.converter` 测试 + 新增"无 hint 也能转换 PDF"测试

### PR-2: convert_to_markdown MCP wrapper 移除 hint
- **What:** `src/claw_ea/tools/converter.py` 的 MCP tool schema 删除 hint 参数
- **Depends on:** PR-1
- **Why:** dispatch 已无 hint 入参，wrapper 同步

### PR-3: obsidian.py raw-text body + 双段 idea + frontmatter schema
- **What:** `create_obsidian_note` 支持 verbatim mode（不渲染 content_data，直接写原文 + 时间戳）；新增 idea 类双段结构；frontmatter 改为 §4 schema
- **Scope:** `src/claw_ea/tools/obsidian.py`、新增模板文件
- **Why:** Q5 (qp 命名空间) + capture-first 原则
- **Validates:** 新增 verbatim / dedup-by-raw 测试

### PR-4: agent prompt 重写
- **What:** `openclaw-plugin/PROMPT_TEMPLATE.md`、`AGENTS.md`、`TOOLS.md` 改写：移除 hint 指引（Q8）、移除 OCR 兜底（Q6）、加时间字段置信度自评（Q1）、加多消息 5min 合并 + /split 覆盖（Q4）、加 idea 异步调研触发逻辑（Q2/Q3）
- **Depends on:** PR-1+2+3
- **Why:** 决议落地到 agent 行为

### PR-5: scripts/migrate_legacy_inbox.py 一次性迁移
- **What:** 扫 obsidian inbox，body < 50 字符且无附件 → 加 `legacy: true` + `legacy_reason: empty_body`，mv 到 `_legacy/`
- **Depends on:** PR-3 (frontmatter schema 稳定)
- **Why:** Q7 决议
- **Note:** 一次性脚本，不入主代码库 src/

### PR-6: tests 补 verbatim / dedup-by-raw / idea-supplement
- **Depends on:** PR-3+4
- **Why:** 新行为需要测试覆盖

### Spike: OpenClaw 后台任务原语调研
- **What:** Q2 异步调研机制依赖 OpenClaw 是否提供后台任务/定时器原语
- **Why:** 决议是"异步"，但实施路径未定（agent 自身轮询 vs OpenClaw 工作流定时器 vs 用户 /research 显式触发兜底）
- **Output:** spike 文档说明可行性 + 推荐实施路径，再进入 PR-7
- **Status:** Q2 决议已写"具体实现待 spec-phase 确定"，本 spike 替代 spec

---

## Deferred — Post-MVP

### 笔记模板可配置化
- **What:** 支持用户自定义 Obsidian 笔记模板（Jinja2 或类似）
- **Why:** 不同科室/用户可能需要不同的 frontmatter 字段和笔记结构
- **Pros:** 提升灵活性，适应更多场景
- **Cons:** 增加复杂度，可能过早
- **Context:** 设计文档 Open Question #3。先用硬编码模板上线，收集真实用户反馈后再决定
- **Depends on:** 核心工作流跑通后
- **Added:** 2026-03-21 /plan-eng-review

### 交接班报告生成
- **What:** 新增 generate_handoff_report tool，汇总一天的信息生成交接班报告
- **Why:** 用户选定的 10x 版本目标，日常工作中耗时最多的任务之一
- **Pros:** 用户价值极高
- **Cons:** 需要 Obsidian 笔记的查询/汇总能力，可能需要新 tool（如 query_obsidian_notes）
- **Context:** 设计文档 Next Steps 第 7 步
- **Depends on:** create_obsidian_note 稳定运行
- **Added:** 2026-03-21 /plan-eng-review
