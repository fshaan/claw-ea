---
title: claw-ea Capture-First 重设计
date: 2026-04-30
author: 陕飞
status: draft (讨论中)
supersedes: 现有 PROMPT_TEMPLATE.md 的 LLM-as-extractor 范式
---

# claw-ea Capture-First 重设计

> 本文档是讨论载体，**不是已批准的设计**。所有"决议"都标记为 `[待讨论]` 或 `[已共识]`，
> 用于驱动下一步的 spec / plan 流程。

---

## 1. 背景与触发原因

### 现状痛点
- 实际使用中频繁产生**几乎空白的 md 文件**：frontmatter 有 category，body 只有占位符
- 根本原因：当前架构让 LLM 同时承担"识别 + 分类 + 字段提取"三件事，提取环节最易失败
- LLM 拿不准时倾向于留空，结果是"原文丢了，提取也没成功"——双重信息损失

### 设计目标
1. **原文零损失**：用户发送的原始消息和文件，必须 100% 可恢复
2. **职责重划**：LLM 只做识别+分类（路由器），不做内容创作（不修改原文）
3. **想法增值**：对"想法类"消息允许 AI 主动调研补充，但必须与原文视觉分离
4. **下游友好**：与 my2nd-brain 清盘流程明确契约，frontmatter 字段足够清盘决策使用

---

## 2. 核心原则 [已共识]

| # | 原则 | 含义 |
|---|---|---|
| P1 | Capture First, Process Later | 先保原文，再考虑 AI 处理 |
| P2 | LLM-as-Router, not Extractor | LLM 输出仅 `{category, action_set}`，不输出 content_data |
| P3 | Verbatim by Default | 文本/图片消息原样落地，AI 不改写 |
| P4 | AI 调研补充必须可识别 | 双段结构 + 视觉分离 + 来源标注 |
| P5 | 确定性工具优先 | 文件转 MD 用 MinerU/docling，不用 LLM 描述文件内容 |

---

## 3. 目标架构

```
┌─ 入口 ──────────────────────────────────────────────────┐
│  TUI / 社媒 channel → 消息 + 附件                       │
└──────────────┬──────────────────────────────────────────┘
               ▼
┌─ Agent LLM 层（最小职责）─────────────────────────────┐
│  ① 识别：message_type / attachment_types               │
│  ② 分类：work / idea  →  唯一输出                      │
│     work 子类：surgery / meeting / task / document    │
│     idea 子类：raw_thought                             │
└──────────────┬─────────────────────────────────────────┘
               ▼
┌─ 确定性归档管道（无 AI 创作）──────────────────────────┐
│                                                        │
│  分支 A：text + image                                  │
│    → 聚合成 session MD（原文 verbatim + 图 wiki-link）│
│                                                        │
│  分支 B：file (PDF/docx/pptx/xlsx)                    │
│    → 原件入 attachments/                              │
│    → MinerU/docling 转 MD 作主记录入 inbox/           │
│    → wiki-link 关联                                    │
│                                                        │
│  分支 C：category=idea                                 │
│    → 原文先入创意池（不阻塞）                          │
│    → 异步触发 AI 调研，结果作为 supplement 段补全      │
└──────────────┬─────────────────────────────────────────┘
               ▼
        Obsidian vault（含 lifecycle frontmatter）
               │
               ▼
        my2nd-brain 清盘（按 status 推进，外部流程）
```

---

## 4. Frontmatter Schema [已和 my2nd-brain qp skill 对齐 — 2026-05-06 翻转]

> **设计原则**：claw-ea 直接写 qp v1.5.0 路由命名空间内的 `type` 值，qp 一行规则不加。
> claw-ea 业务细分降级为 `category` 子字段，qp 不读，仅 claw-ea 自身用于决定要不要建日历/提醒。

```yaml
---
# 来源元数据（capture 阶段必填）
source: claw-ea                       # 标识来源工具（qp 不依赖此字段路由）
source_channel: feishu | wecom | telegram | tui   # 渠道
source_message_id: <channel-msg-id>   # 防重 + 溯源（如果可得）
message_ts: 2026-04-29T10:30:00       # 消息原始时间（语义锚点）
ingested_at: 2026-04-30T15:00:00      # claw-ea 处理时间

# 分类(qp 路由命名空间,MUST 写其一)
type: meeting_minutes | document | idea | review | writing
title: "自动生成:消息首句前30字"        # qp 展示用

# claw-ea 业务细分(qp 不读,claw-ea 自用)
category: surgery | meeting | task | document | raw_thought | review

# 项目归属（选填，有则 qp 自动归入 🟢 高置信组）
project: "[[项目名]]"                  # Obsidian wikilink

# 生命周期
status: inbox                         # claw-ea 始终写 inbox；qp 移动文件后位置即状态
processed_by_ai: false                # 是否已做 idea 调研补充

# 关联
attachments: [99_Attachments/2026/04/30/手术通知.pdf]
related_event_id: <calendar-event-id> # 反查日历
related_reminder_id: <reminder-id>    # 反查提醒

# 想法专用字段（仅 type=idea）
idea_stage: raw | enriched | framed   # 调研成熟度
idea_topics: [obsidian, agent-design] # 调研维度（用于检索）

tags: [...]
---
```

### 4.1 claw-ea category → qp type 映射表（MUST）

| 业务场景 | claw-ea 写入 `category` | claw-ea 写入 `type` | qp 落地路由 |
|---|---|---|---|
| 会议通知/纪要 | `meeting` | `meeting_minutes` | 📋 会议纪要编译 → `02_Projects/[项目]/` |
| 手术通知 | `surgery` | `document` | 🟢/🟡 直接归档（依赖日历事件,不入纪要流程）|
| 任务/待办 | `task` | `document` | 🟢/🟡 直接归档 |
| 一般文档 | `document` | `document` | 🟢/🟡 直接归档 |
| 想法/灵感 | `raw_thought` | `idea` | Route 9 → `05_创意池/` |
| 评审报告 | `review` | `review` | 🔴 评审编译 → `06_评审知识库/` |

---

## 5. 笔记 Body 模板

### 5.1 work / 文本+图片
```markdown
# {自动生成 title：取消息首句前 30 字}

## 消息记录

**[14:23] 用户**：明天 9 点手术室准备...

**[14:24] 用户**：![[2026-04-30-术前检查单.jpg]]

**[14:25] 用户**：注意准备 X 器械

## 附件
- [[2026-04-30-术前检查单.jpg]]
```

### 5.2 work / 文件归档
```markdown
# {文件名}

> **原始文件**：[[手术通知.pdf]]（已归档于 attachments/2026/04/30/）
> **转换工具**：mineru / docling
> **转换时间**：2026-04-30T15:01:00

---

{MinerU/docling 输出的 MD 全文}

---

## 用户消息（如有）
> 转发时附带的文字：...
```

### 5.3 idea / 双段结构
```markdown
# {取首句}

## 原始想法（用户原文，AI 不得修改）

> 今天看到一篇关于 X 的论文，觉得 Y 方向有意思，可以联想到我之前在 Z 上的工作...

---

## AI 调研补充
> 生成时间：2026-04-30T15:05:00
> 信息来源：web_search + 本地知识库
> ⚠️ 仅供参考，可能含错误

### 相关概念
- ...

### 已有研究
- ...

### 可能延伸方向
- ...
```

---

## 6. 行为变更对照表

| 维度 | 现状 | 重设计后 |
|---|---|---|
| LLM 输出 | category + content_data（多字段）+ title + attendees + ... | **仅 `{type, category, action_set}`**（type 落 qp 命名空间, category 为 claw-ea 业务细分,见 §4.1） |
| 笔记 body 来源 | 模板渲染 content_data 字段 | **原文 verbatim 或转换器输出** |
| 文本消息归档 | 提取摘要塞进 `summary` 字段 | **原文加时间戳塞进 `## 消息记录`** |
| 图片归档 | OCR 后塞 body | **直接 wiki-link 嵌入**，OCR 仅作可选索引字段 |
| PDF 归档 | docling 转换（mineru 不可达） | **routing 接通 mineru，按学术/普通分流** |
| 想法归档 | 走 `general` 类，无特殊处理 | **独立 idea 类 + 异步 AI 调研补充** |
| 去重 hash | hash(content_data) | **hash(raw_text + sorted(attachment_hashes))** |
| 多消息合并 | agent 自由判断 | 待讨论：自动 5min 窗口 vs 显式触发 |
| 日历时间字段 | LLM 从原文抽取 | **待讨论**：用户口述补 vs 极简抽取 |

---

## 7. 决策点 [全部已决议 — 2026-05-06]

> Q1-Q8 全部收敛完成。下一步进入 spec-phase（formal SPEC.md）或直接 plan。

### Q5：与 my2nd-brain 的清盘契约？ [已决议 — 2026-05-06 翻转 v2]

**决议（v2 翻转）**：claw-ea 直接写 qp v1.5.0 路由表能消费的 `type` 值，**qp 不加任何来源专属规则**。

**翻转原因**：
- 2026-04-30 v1 决议要求 qp 新增 2-3 行 `source: claw-ea` 识别规则。
- 2026-05-06 复核 qp v1.5.0 SKILL.md 后发现 qp 修正后**未加该规则**（也不应加——让 qp 维护来源特殊分支不健康）。
- qp 路由是**字段值驱动**（`type: meeting_minutes / review / writing / idea / document`），不是来源驱动。
- claw-ea 写入 qp 命名空间的字段值即可，qp 一行不改。

**核心洞察（保留）**：qp 是"位置驱动"而非"状态机驱动"——文件从 `01_Inbox/` 移动到目标目录即视为清盘完成。claw-ea 无需维护复杂的 `status` 状态机。

**契约**（详见 §4 Frontmatter Schema 和 §4.1 映射表）：
- `type` MUST 落在 qp 命名空间：`meeting_minutes | document | idea | review | writing`
- `category` 是 claw-ea 业务细分（surgery / meeting / task / document / raw_thought / review），qp 不读
- `source: claw-ea` 仅为溯源标记，不参与路由
- 有 `project:` 时 qp 自动归入 🟢 高置信组（qp v1.5.0 §1.3）

**qp 侧需要的改动**：**0 行**。qp v1.5.0 现有规则即可消费。

**status 字段**：claw-ea 始终写 `status: inbox`。qp 移动文件后位置即状态，无需改 status。

**文件命名**：claw-ea 保持 `{date}-{category}-{hash[:8]}.md`，qp 在 §3.2.4 清盘时按人类可读格式重命名。两阶段互不干扰。

**遗留映射边界 case**：
- `category: surgery` → `type: document`：手术通知不走 qp 会议纪要编译流程（surgery 走日历事件承载，归档时按普通 document 处理）。**待 Q1 时间字段决议后再确认细节。**
- `category: review` → `type: review`：极少见场景（评审报告通过社媒群转发），如出现走 qp 评审编译含脱敏。

### Q1：日历/提醒的时间字段如何获取？ [已决议 — B 极简抽取 + 抓不到走 A]

**决议**：保留极简时间抽取（明确表达如 "明天下午 3 点"、"5/8 14:00"），抽不到则不自动建事件，agent 提示用户口述时间地点后再建。

**实施细节**：
- agent prompt 写入"时间抽取置信度自评"逻辑：能 100% 锁定 ISO 时间戳才传 `start_time` 给 `create_calendar_event`，否则跳过自动建事件、附上"请补充时间地点"提示给用户。
- 不引入新工具——抽取仍由 agent LLM 完成，置信度由 agent 自评。
- 与 surgery 边界 case 对齐：surgery 通知通常含明确手术时间（"明日 9:00 主刀 X 患者"），命中极简抽取；抽不到时按 Q5 v2 翻转的 `category: surgery → type: document` 直接归档不建事件。

### Q2：想法调研动作的范围？ [已决议 — B 异步]

**决议**：原文先入创意池（不阻塞），后台触发 AI 调研后追加 `## AI 调研补充` 段。

**实施细节**：
- `processed_by_ai: false` 初始写入；调研完成后 update 为 `true` + `idea_stage: enriched`。
- 异步触发机制：暂以 agent 自身后台轮询 / 或 OpenClaw 工作流定时器。**具体实现待 spec-phase 确定**（涉及到 OpenClaw 是否提供后台任务原语）。
- 失败容错：调研失败不阻塞原文落地，frontmatter 留 `processed_by_ai: false`，下次手动 `/research` 重试。

### Q3：调研信息来源？ [已决议 — 本地 + web 混合]

**决议**：本地 obsidian vault 检索 + web_search 联合，两者结果合并写入 supplement 段。

**实施细节**：
- 本地检索：用现有 vault MCP server 的 search（grep/embedding，待评估）。
- web 检索：复用 OpenClaw 自带的 web_search / `last30days` 等工具。
- supplement 段必须区分两类来源：`### 本地关联（vault）` / `### 外部检索（web）`，避免混淆 vault 已有论点和外部新信息。

### Q4：多消息合并策略？ [已决议 — C 混合]

**决议**：默认自动（同 sender + 5min 窗口连续消息 → 合并），用户可在 capture 前用"分开处理"指令显式覆盖。

**实施细节**：
- 现有 agent prompt "Consecutive messages about the same event → merge before processing" 保留并细化为 "5 分钟窗口内同 sender 连续消息默认合并"。
- 用户覆盖语义：用户在群里发 "claw 分开处理" / "/split" 等明确指令 → agent 跳过合并、逐条 capture。
- 合并后的 dedup hash：按 §6 行为变更对照表 → `hash(merged_raw_text + sorted(attachment_hashes))`。

### Q5：与 my2nd-brain 的清盘契约？ [已决议 — 见上方 v2 翻转]

详见本节顶部"Q5"块。

### Q6：图片 OCR 默认开关？ [已决议 — A 默认关]

**决议**：默认关闭 `ocr_image` 自动调用。原图通过 wiki-link 嵌入笔记，搜索靠肉眼 + agent 多模态 LLM 直接读图。

**实施细节**：
- 移除 agent prompt 中"agent 看不见图就调 ocr_image"的兜底分支——这是 v1 的兼容遗物，OpenClaw agent 已具多模态能力。
- `ocr_image` MCP 工具保留但**不再在 capture 流程被自动调用**，仅作为用户显式触发或未来可配置开关。
- `ocr_text` frontmatter 字段废弃（不再写入）。

### Q7：存量"几乎空白"笔记如何处理？ [已决议 — B 标 legacy + 移 _legacy/]

**决议**：一次性迁移脚本扫描 obsidian inbox，对"几乎空白"笔记（body < 50 字符且无附件 wiki-link）加 frontmatter `legacy: true`，mv 到 `_legacy/` 子目录。

**实施细节**：
- 判定阈值：`body 去除 frontmatter / 注释后 strip().len() < 50` 且 `attachments: []` 或字段缺失。
- 脚本路径：`scripts/migrate_legacy_inbox.py`（一次性，不入主代码库 src/）。
- frontmatter 增加 `legacy: true` + `legacy_reason: empty_body`，便于后续若发现误判可恢复。
- qp 路由：qp v1.5.0 §1.2 Route 11（无归档价值）已能处理 `_legacy/` 下条目；或 agent.md 是否需要新增 `_legacy/` 路径白名单**留作 my2nd-brain 侧的小协调，不阻塞**。

### Q8：转换器 routing 策略？ [已决议 — 统一用 MinerU]

**决议**：取消 academic vs default 双链路，所有 PDF / docx / pptx / xlsx / 图片都默认走 MinerU 3.1.6（已升级为多格式解析器）。docling 降级为 fallback（仅 MinerU 失败时尝试）。

**实施细节**：
- `converters.py` `DEFAULT_ROUTING` 简化为单链路：`{format: [mineru, docling, lmstudio?, passthrough]}`。
- agent prompt 移除 hint 参数——`convert_to_markdown` 调用不再传 hint。
- `is_usable()` 质量检查保留，MinerU 输出不可用时自动 fallback 到 docling。
- **影响面**：
  - converters.py 简化 ~30-50 行（删除 routing 表的 `academic` 分支）
  - converter.py MCP wrapper 移除 hint 参数
  - openclaw-plugin/PROMPT_TEMPLATE.md 移除"判定学术/行政传 hint"指引
  - 测试：原 `@pytest.mark.converter` 测试需更新断言

---

## 8. 显式 Out of Scope（不在本次重设计内）

- 失败回滚 / 事务边界（半成品状态目前可口头修正，先不做）
- LLM 微调 / 自定义模型（agent 用 OpenClaw 自带的就够）
- 跨设备同步（Obsidian 自身已有方案）
- 实时通知（推送到 Slack / WeChat）

---

## 9. 改造影响面

| 文件 | 改动类型 | 工作量估计 |
|---|---|---|
| `openclaw-plugin/PROMPT_TEMPLATE.md` | 重写 AGENTS.md / TOOLS.md 片段 | 中 |
| `src/claw_ea/tools/obsidian.py` | 新增 raw-text body 模式 + 双段 idea 模式 + frontmatter schema | 中 |
| `src/claw_ea/tools/converter.py` | 新增 idea 类调研动作（可选异步） | 大（涉及新工具） |
| `src/claw_ea/converters.py` | DEFAULT_ROUTING 加 mineru 分支 | 小 |
| `src/claw_ea/config.py` | 新增 idea-pool 配置 + my2nd-brain 契约字段 | 小 |
| `~/.claw-ea/config.yaml` | 用户配置补全（categories / converters.routing） | 小 |
| `tests/` | 新增 verbatim / dedup-by-raw / idea-supplement 测试 | 中 |
| 存量笔记迁移脚本 | 一次性 | 小 |

---

## 10. 下一步

本文档以现状（截至 2026-04-30）讨论结果为输入，作为后续 spec / plan 阶段的起点。
建议路径见同目录下的 `discussion-tooling-recommendation.md`（如生成）。
