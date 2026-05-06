# Spike: OpenClaw 后台任务/定时器原语调研

**日期**: 2026-05-06
**目的**: Q2 决议——idea 异步调研机制的工程可行性
**结论**: ✅ 路径 B（OpenClaw Cron）完全可行

---

## 发现

OpenClaw 2026.3.24 内置两套调度原语，互补使用：

### 1. Heartbeat（心跳轮询）

- **机制**: Agent 周期性收到 heartbeat poll，按 `HEARTBEAT.md` 清单执行
- **触发**: Gateway 定时向 agent 发送心跳 prompt
- **适用**: 批量定期检查（inbox + calendar + notifications 合并到一个 heartbeat）
- **精度**: ~30 分钟级别，允许漂移
- **实现**: 文件驱动——`HEARTBEAT.md` + `memory/heartbeat-state.json`

### 2. Cron（Gateway 调度器）

- **机制**: Gateway 内置 cron scheduler，底层用 `croner` 库（v10.0.1）
- **CLI**: `openclaw cron add|list|edit|rm|enable|disable|run|runs|status`
- **精度**: 秒级（支持 6-field cron 表达式）
- **实现**: Gateway 级别独立调度，不依赖 agent session 存活

**关键能力**:

| 参数 | 值 | 用途 |
|------|-----|------|
| `--at <when>` | ISO 时间或 `+duration` | 一次性延迟任务（如 `+5min`） |
| `--every <duration>` | `10m`, `1h`, `6h` | 周期性任务 |
| `--cron <expr>` | 5/6-field cron | 精确重复调度 |
| `--message <text>` | 任意 prompt | agent 执行的指令 |
| `--session main` | main/isolated | 路由到主 session |
| `--delete-after-run` | bool | 一次性任务自动清理 |
| `--system-event <text>` | 系统事件 | 不新建 session，注入当前 session |
| `--timeout` | ms | 任务超时 |
| `--model` | model alias | 独立 model 选择 |
| `--thinking` | off/minimal/low/medium/high/xhigh | 独立 thinking 级别 |

---

## 三种实施路径分析

### 路径 A: Agent 自身轮询

agent 创建 idea 笔记后不立即结束，sleep 后继续做调研。

- ❌ 阻塞 agent session，用户体验差
- ❌ 调研失败影响主流程
- ❌ 不推荐

### 路径 B: OpenClaw Cron（推荐）

agent 创建 idea 笔记后，用 `openclaw cron add` 创建一个 one-shot 延迟任务：

```bash
openclaw cron add \
  --name "claw-ea-idea-research-<hash>" \
  --at +2min \
  --delete-after-run \
  --session main \
  --system-event "对笔记 <note_path> 做 AI 调研补充：web_search + 本地 vault 检索，结果追加到 '## AI 调研补充' 段，更新 frontmatter 的 processed_by_ai=true, idea_stage=enriched" \
  --timeout 120000 \
  --thinking low
```

- ✅ 独立调度，不阻塞 capture 流程
- ✅ 原生支持 one-shot + 自动清理
- ✅ 精度到秒
- ✅ 可指定独立 model/thinking level（调研用更轻量配置）
- ⚠️ 需要 agent 能调用 `openclaw cron add` CLI（bash 工具或 OpenClaw 自身 tool）

### 路径 C: 用户显式触发（兜底）

agent 提示"需要我做调研吗？"，用户回 `/research`。

- ✅ 可靠，不依赖任何基础设施
- ❌ 手动，不是真正的异步
- ✅ 作为 B 的 fallback

---

## 推荐方案: B + C 混合

```
idea capture 流程:
1. agent 写入 idea 笔记（processed_by_ai: false, idea_stage: raw）
2. agent 尝试创建 cron 延迟任务（路径 B）
3. 如果 cron 创建失败（非交互环境等），提示用户备选（路径 C）
4. cron 触发时：agent 收到 system-event → 读笔记 → 检索 → 追加补充段
5. 更新 frontmatter: processed_by_ai: true, idea_stage: enriched
```

## 尚需验证

1. `openclaw cron add` 是否可以从 agent tool 中调用（agent 是否有 bash 执行权）
2. `--system-event` 注入后 agent 是否能正确定位并修改已有笔记
3. cron scheduler 的可靠性（Gateway 重启后 pending 任务是否保留）

## 实施优先级

- **PR-4 已完成**: agent prompt 包含路径 C 兜底（提示用户 `/research`）
- **PR-7 应包含**: agent prompt 加入路径 B 自动 cron 创建逻辑 + 对应的 OpenClaw cron 命令模板
- **后续**: 实际使用中观察 cron 可靠性，如不稳定则回退到纯 C

## 参考

- OpenClaw AGENTS.md heartbeat/cron 使用指南（`~/.openclaw/workspace/AGENTS.md`）
- `openclaw cron add --help` 完整参数列表
- `croner` v10.0.1 (npm dependency of openclaw 2026.3.24)
- 设计文档 Q2 决议：`docs/design/2026-04-30-capture-first-redesign.md`
