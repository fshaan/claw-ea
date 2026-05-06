# Decisions

> 本文件记录 claw-ea 的产品/架构决策**为什么**这样做。决策按时间倒序排列。
> 决策一旦写入此处，应视为长期生效；如要推翻，新增一条决议引用并解释原因。

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
- **遗留**: 异步触发机制具体实现（agent 轮询 vs OpenClaw 后台任务原语）需先 spike

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
