# claw-ea EventKit/TCC 修复 — 测试方案

> 目标：验证 disclaim + 签名 bundle 方案（见 `eventkit-tcc-fix-v3.md`）在三种启动上下文下稳定、
> 免疫 uv 升级、headless 不污染缓存、且不破坏现有功能。
> 运行时落点：`~/.claw-ea/{claw-launcher, claw-ea.app, claw-ea.keychain-db}`；身份 `com.fsh.claw-ea`。

公用环境变量（手动跑链路时用）：
```bash
REPO=/Users/f.sh/Workspace/devs/claw_EA
APP="$HOME/.claw-ea/claw-ea.app"
LAUNCHER="$HOME/.claw-ea/claw-launcher"
CLAWPY="$APP/Contents/MacOS/clawpy"
export PYTHONHOME="$APP/Contents"
export PYTHONPATH="$REPO/src:$REPO/.venv/lib/python3.14/site-packages"
```

---

## T1 冒烟（自动，<1min）— 已通过，可随时复跑

| # | 命令 | 期望 |
|---|---|---|
| T1.1 bundle 完整性 | `bash $REPO/scripts/verify-bundle.sh` | `VERIFY PASS`；DR=`identifier "com.fsh.claw-ea" and certificate leaf`（非 cdhash）；freeze 生效 |
| T1.2 disclaim 归因+授权 | `"$LAUNCHER" "$CLAWPY" -c 'from EventKit import EKEventStore,EKEntityTypeReminder as R; print(EKEventStore.authorizationStatusForEntityType_(R))'` | `3`（已授权 com.fsh.claw-ea） |
| T1.3 MCP 启动握手 | `printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' \| timeout 15 $REPO/run-server.sh 2>/dev/null \| head -c 400` | 返回含 `"serverInfo":{"name":"claw-ea"...}`；stderr 无 PermissionError |
| T1.4 seal 稳定性（回归）| `"$LAUNCHER" "$CLAWPY" /tmp/e2e.py >/dev/null 2>&1; bash $REPO/scripts/verify-bundle.sh \| tail -1` | 运行 clawpy 后再验仍 `VERIFY PASS`（证明运行时不再写 .pyc 破坏签名） |

> **已修坑**：`cp -R` stdlib 后 `.py` mtime 变，运行时 Python 会重编译并写新 `.pyc` 进 bundle、破坏整包签名 seal（`codesign --verify --strict` 报 `a sealed resource is missing or invalid`）。修复：`build-bundle.sh` 签名前先 `compileall` 让 `.pyc` 与拷贝后 `.py` mtime 一致；`run-server.sh` 设 `PYTHONDONTWRITEBYTECODE=1` 兜底。注意：即使 seal 破了，**TCC 仍正常**（TCC 看 clawpy 可执行文件签名，不看 bundle 资源 seal），但仍应保持 seal 干净以便可重新验证。

**通过标准**：四项全绿。任何一项失败→回 `eventkit-tcc-fix-v3.md` §10 退路。

---

## T2 三种启动上下文真实归因（核心，手动 + 日志）

这是方案的真正验收：不同父 app 下 TCC 都应记到 `com.fsh.claw-ea` 并放行。

**通用日志窗口**（每个子用例期间开着，单独终端）：
```bash
log stream --debug --style compact --predicate 'process == "tccd" AND eventMessage CONTAINS "claw-ea"'
```

### T2.1 GUI-Hermes
1. 双击启动 Hermes.app（非从终端起）。
2. 在 Hermes agent 里发：「用 claw-ea 建一条测试提醒：今天 18:00 TCC验收，列表 任务箱」。
3. 观察。

**期望**：
- 提醒出现在 Apple 提醒事项「任务箱」；agent 回报成功，**无 PermissionError**。
- tccd 日志出现 `AttributionChain: responsible={... identifier=com.fsh.claw-ea ...}` 且 `ReqResult(... Allowed ...)`（**不是** `com.nousresearch.hermes`）。

### T2.2 WorkBuddy.app（另一 Electron 实例，同 run-server.sh）
同 T2.1，但在 WorkBuddy.app 里触发。**期望相同**：responsible=com.fsh.claw-ea、Allowed、提醒创建成功。
> 前提：WorkBuddy 需重启过一次以 respawn claw-ea 走新 run-server.sh（旧进程 pid 仍走旧链路）。

### T2.3 cron / 无 GUI（headless 持久性）
在 Hermes/WorkBuddy 内置调度器（`~/.hermes/cron/jobs.json`）加一条 ~2 分钟后触发 claw-ea 建提醒的任务，等它自动跑。
**期望**：headless 下**直接成功、无弹窗**（因 com.fsh.claw-ea 已持久授权 + disclaim 自立）。提醒出现，日志 responsible=com.fsh.claw-ea / Allowed。

**T2 通过标准**：三个上下文都 responsible=com.fsh.claw-ea 且提醒创建成功。

---

## T3 headless 安全闸（防污染）

验证 cron/headless 在**未授权**时只报错退出、绝不主动 request（不会把 com.fsh.claw-ea 写成 denied）。

> ⚠ 破坏性：会清掉 com.fsh.claw-ea 的现有授权，做完需重授权。仅在需要严格验证时做。

```bash
# 1) 清授权 → 回到 notDetermined
tccutil reset Reminders com.fsh.claw-ea 2>/dev/null; tccutil reset Calendar com.fsh.claw-ea 2>/dev/null
# 2) 模拟 headless 工具调用(allow_prompt=False)：应抛错且不弹窗、不写 denied
"$LAUNCHER" "$CLAWPY" -c "
import asyncio; from claw_ea.eventkit_utils import EventKitClient
async def m():
    try:
        await EventKitClient().ensure_reminder_access()  # 默认不弹
        print('FAIL: 未按预期报错')
    except PermissionError as e:
        print('OK 报错未request:', str(e)[:40])
asyncio.run(m())"
# 3) 确认状态仍是 0(notDetermined)，没被污染成 2(denied)
"$LAUNCHER" "$CLAWPY" -c 'from EventKit import EKEventStore,EKEntityTypeReminder as R; print("status", EKEventStore.authorizationStatusForEntityType_(R))'
# 4) 重新授权(GUI 会话)
"$LAUNCHER" "$CLAWPY" -m claw_ea.grant
```
**期望**：步骤2 打印 `OK 报错未request:...`；步骤3 `status 0`（**不是 2**）；步骤4 弹窗→允许→恢复。

---

## T4 uv 升级韧性（DR 与内容解耦 → 授权不丢）

不需真升级 uv，重建 bundle（换二进制内容、同证书同 identifier 重签）即可验证授权是否跨重签存活。

```bash
# 前提：T1/T2 已授权(status=3)
bash $REPO/scripts/build-bundle.sh                       # 重建+重签(clawpy 内容会变)
"$LAUNCHER" "$CLAWPY" -c 'from EventKit import EKEventStore,EKEntityTypeReminder as R; print("重签后 status", EKEventStore.authorizationStatusForEntityType_(R))'
```
**期望**：重签后 `status 3`（授权命中新 clawpy，**未丢**）。这等价于「uv 升级换解释器后重跑 build-bundle.sh，无需重新授权」。

真升级场景（可选）：`uv python upgrade` 后 `uv sync` → `bash scripts/build-bundle.sh` → run-server.sh 的版本校验应通过，status 仍 3。

---

## T5 回归（不破坏现有功能）

```bash
cd $REPO
uv run pytest -q                          # 全量(含 macos 标记，因已授权)
uv run pytest -m "not macos" -q           # 纯逻辑(CI 可跑)
```
**期望**：全绿（基线 122 passed；macos 标记测试现可真跑 EventKit）。

另：在 Hermes 跑一遍现有典型流程（手术提醒 / 会议日历事件 / 文件转 Markdown 归档），确认 calendar/reminder/obsidian 工具都正常——验证改动只动了授权链、没碰业务逻辑。

---

## 验收清单

- [ ] T1 冒烟三项全绿
- [ ] T2.1 GUI-Hermes：responsible=com.fsh.claw-ea + 提醒成功
- [ ] T2.2 WorkBuddy：同上
- [ ] T2.3 cron headless：无弹窗直接成功
- [ ] T3 headless 闸：未授权只报错不污染（可选/破坏性）
- [ ] T4 重签后 status 仍 3（升级韧性）
- [ ] T5 pytest 全绿 + 典型业务流程正常

任一核心项（T2）失败 → 抓 tccd 完整 `AttributionChain` 贴回排查，或转 `eventkit-tcc-fix-v3.md` §10/§11 退路。
