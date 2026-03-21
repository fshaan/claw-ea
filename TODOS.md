# TODOS

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
