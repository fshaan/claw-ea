# TODOS

## ✅ 已完成 — Capture-First v2 重设计 (2026-05-06)

> 设计源: `docs/design/2026-04-30-capture-first-redesign.md`
> 决议日期: Q5 翻转 2026-05-06；Q1-Q4/Q6-Q8 收敛 2026-05-06
> 实施日期: 2026-05-06，PR-1 → PR-5 + Spike 全部完成
> 测试: 122 passed

### PR-1: converters.py routing 简化 ✅
- **What:** 删除 `DEFAULT_ROUTING` 嵌套 dict，拍平为 `{ext: chain}`；`dispatch()` 移除 hint；`convert_mineru` docstring 改为 "Default for all PDF/document conversions"
- **Scope:** `src/claw_ea/converters.py` + `src/claw_ea/config.py` 类型注解
- **Why:** Q8 决议——MinerU 3.1.6 已扩展为多格式解析器

### PR-2: convert_to_markdown MCP wrapper 移除 hint ✅
- **What:** `src/claw_ea/tools/converter.py` MCP tool schema 删除 hint 参数 + docstring
- **Depends on:** PR-1
- **Why:** dispatch 已无 hint 入参，wrapper 同步

### PR-3: obsidian.py §4 frontmatter + verbatim body + idea 双段 ✅
- **What:** `_render_frontmatter` 重写为 §4 schema（source/type/category/status/ingested_at...）；新增 `_render_verbatim_header`（§5.2）+ `_render_idea_body`（§5.3）；dedup hash 翻转到 raw_body 内容 + attachment
- **Scope:** `src/claw_ea/tools/obsidian.py`（+247/-93）
- **Why:** Q5 (qp 命名空间) + capture-first 原则

### PR-4: agent prompt 重写 ✅
- **What:** PROMPT_TEMPLATE.md 全面重写（AGENTS.md 10 步 v2 流程 + TOOLS.md v2 参数表 + §4.1 映射表）；tools.ts 移除 hint + 新增 10 个 v2 参数；CLAUDE.md config/AGENTS 段同步
- **Depends on:** PR-1+2+3
- **Why:** Q1/Q2/Q3/Q4/Q6/Q8 决议落地到 agent 行为

### PR-5: scripts/migrate_legacy_inbox.py 一次性迁移 ✅
- **What:** 扫 inbox，body < 50 字符且无附件 → 加 `legacy: true` + `legacy_reason: empty_body`，mv 到 `_legacy/`。`--apply` 执行，默认 dry-run。
- **Tests:** `tests/test_migrate_legacy.py`（18 tests: strip_markdown / is_legacy / parse_note / E2E）
- **Why:** Q7 决议

### PR-6: tests 补全（含在 PR-3 + PR-5 中）
- 7 个新增 obsidian 测试（verbatim header / idea dual-section / dedup-by-raw / type auto-derive / optional fields）
- 18 个迁移脚本测试

### Spike: OpenClaw 后台任务原语调研 ✅
- **结论:** ✅ 路径 B 完全可行——OpenClaw 内置 cron scheduler（`croner` v10.0.1）
- **推荐:** B + C 混合（cron one-shot 延迟任务 + 用户 /research 兜底）
- **文档:** `docs/spikes/2026-05-06-openclaw-background-tasks.md`

### 下一步: PR-7 — cron-based idea async research
- 在 agent prompt 中加入自动 `openclaw cron add --at +2min` 创建逻辑
- 调研 system-event 触发后 agent 的笔记修改流程
- 如 cron 不可用则回退到 C（用户 `/research` 兜底）

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
