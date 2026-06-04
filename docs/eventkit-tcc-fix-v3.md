# claw-ea EventKit/TCC 授权稳定化 — v3.1 执行方案

> 状态：定稿待执行。v3.1 并入 codex 独立 review 的全部修正，并把两个未经 spike 证明的推断
> 降级为**执行期阻塞验证门**（§8 Gate A/B）。环境：macOS 26.5.1 / Apple Silicon / uv cpython-3.14.3。
>
> **v3 → v3.1 变更摘要**：① 签**整个 .app**（seal Info.plist），非只签内层 clawpy；② 加 headless
> 首授权闸（notDetermined + 非 GUI → 拒绝 request，防污染 TCC 缓存为 deny）；③ `PYTHONHOME` 锁
> stdlib + build 后实测 `sys.base_prefix`；④ run-server.sh 动态推导 py 版本 + 校验 site-packages；
> ⑤ 修 build-cert.sh 的 key-partition-list 密码 bug；⑥ 清 `com.apple.quarantine`；⑦ EventKit
> callback 暴露 error；⑧ 去掉 `LSBackgroundOnly`；⑨ 两道 GUI 阻塞验证门。

---

## 1. 问题与根因（已确诊）

**现象**：claw-ea 由 Hermes 拉起时，EKEventStore 请求 Calendar/Reminders 在 GUI-Hermes / 内置 cron 下抛 `PermissionError`；手动给 uv 解释器授权升级后即失效。

**根因（实测闭环）**：

1. TCC 把 EventKit 访问记在 **responsible 进程 = 启动链顶端 GUI app**，不看实际调用的 python 叶子签名。
   - Ghostty 终端起的 Hermes → responsible=`com.mitchellh.ghostty`（已授权）→ 能用。
   - GUI 双击 `Hermes.app` / 内置 cron → responsible=`com.nousresearch.hermes`，**无 usage 串、无法弹窗、未授权** → `PermissionError`。
2. uv 解释器 ad-hoc 签名（`Identifier=-`），DR 退化为 `cdhash`；升级换 patch → 路径与 cdhash 同变 → 授权失效。

**结论**：单独「签 python」无效（TCC 不评估 accessing 叶子）；必须让 claw-ea 进程**自立为 responsible**，并携带稳定签名身份 + usage 串。

---

## 2. 已验证的承重机制（spike 证据）

| # | 假设 | 验证 | 结果 |
|---|---|---|---|
| 1 | 当前解释器 DR=cdhash，升级即变 | `codesign -d -r-` | `designated => cdhash H"cd0f…"` ✅ |
| 2 | TCC 记 responsible(顶层GUI app) | `log stream` 抓 `AttributionChain` | `Resp:{com.mitchellh.ghostty}` ✅ |
| 3 | Hermes.app 无 usage 串 | PlistBuddy | 三 key 全 `Does Not Exist` ✅ |
| 4 | **disclaim 把 responsible 夺到叶子** | C launcher + `authorizationStatus` | 无=3 / 有=**0** ✅ |
| 5 | 自签名→稳定 DR(identifier+cert)，与内容解耦 | 两不同 cdhash 同证书签名 | 两者同一 DR ✅ |
| 6 | 不开 hardened runtime 可载未签名 .so | 跑签名副本 import pyobjc | `EventKit ok` ✅ |
| 7 | cp uv python 需 lib 同置(`@executable_path/../lib`) | 直接跑崩 → symlink 修好 | ✅ |
| 8 | run-server.sh 字面量 `\$PYTHONPATH` / `readlink -f` 不可靠 | 读码 | ✅ |

## 2b. **未经 spike 证明的推断（必须执行期验证，见 §8 Gate A/B）**

| 编号 | 推断 | 风险 | 验证门 |
|---|---|---|---|
| INF-1 | TCC 会把 self-responsible 的 `Contents/MacOS/clawpy` 反解为 `claw-ea.app` 并读其 Info.plist usage 串、按 `com.fsh.claw-ea` 持久化 | bundle attribution 对 `posix_spawn`(非 LaunchServices) Mach-O 非公开稳定行为 | **Gate A** |
| INF-2 | 后台 `posix_spawn` 进程首次 `requestFullAccess*` 能弹出系统授权框 | 可能静默 deny 并**污染缓存**；headless cron 抢先触发更危险 | **Gate B** + headless 闸(§5.6) |
| INF-3 | disclaim 在 `Hermes→sh→launcher→clawpy` 整条链生效（spike 只测了终端直起） | 多层父进程理论上不改 spawnattr 效果，但私有 API 需实证 | **Gate A** |

---

## 3. 目标架构

```
Hermes(任意启动) → run-server.sh → claw-launcher(disclaim) → claw-ea.app/Contents/MacOS/clawpy -m claw_ea.server
                                          │ posix_spawn 继承 fd(stdio 不断)
                                          └ responsibility_spawnattrs_setdisclaim(attr,1)
                                            → clawpy self-responsible
                                            → TCC 读 claw-ea.app 的 bundle 身份(整包签名 + usage 串)
```

clawpy = uv python 的**冻结副本**（≈47MB：stdlib 30M + libpython 17M），置 `~/.claw-ea/`，不入 git。整个 `.app` 用稳定自签名证书**整包签名**（seal Info.plist）。

---

## 4. 交付物

```
~/.claw-ea/                              # 运行时根（已有 config.yaml）
├── claw-launcher                        # C disclaim 启动器
└── claw-ea.app/Contents/
    ├── Info.plist                       # CFBundleIdentifier + usage 串（整包签名 seal）
    ├── MacOS/clawpy                     # 冻结 python 副本
    └── lib/{libpython3.14.dylib, python3.14/}   # clawpy 的 ../lib 依赖

claw_EA/ (仓库)
├── scripts/{launcher.c, Info.plist, build-cert.sh, build-bundle.sh, verify-bundle.sh}
├── run-server.sh                        # 改写
└── src/claw_ea/
    ├── eventkit_utils.py                # 状态闸 + full-access API + 暴露 error
    └── grant.py                         # 新增：唯一允许弹窗的 GUI 首授权入口
```

---

## 5. 文件内容

### 5.1 `scripts/launcher.c`

```c
// claw-launcher: 用私有 API responsibility_spawnattrs_setdisclaim 让被 spawn 的子进程
// 成为自己的 TCC responsible 进程，同时继承 fd 保 stdio。用法: claw-launcher <prog> [args...]
#include <stdio.h>
#include <stdlib.h>
#include <spawn.h>
#include <dlfcn.h>
#include <sys/wait.h>

extern char **environ;
typedef int (*disclaim_fn)(posix_spawnattr_t *, int);

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: claw-launcher <prog> [args...]\n"); return 2; }
    posix_spawnattr_t attr;
    posix_spawnattr_init(&attr);
    disclaim_fn disclaim = (disclaim_fn)dlsym(RTLD_DEFAULT, "responsibility_spawnattrs_setdisclaim");
    if (!disclaim) { fprintf(stderr, "[claw-launcher] disclaim symbol missing\n"); return 3; }
    disclaim(&attr, 1);
    pid_t pid;
    int sp = posix_spawn(&pid, argv[1], NULL, &attr, &argv[1], environ);
    if (sp != 0) { fprintf(stderr, "[claw-launcher] posix_spawn rc=%d\n", sp); return 4; }
    int status;
    waitpid(pid, &status, 0);
    posix_spawnattr_destroy(&attr);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
```
编译（`cc` 在交互 shell 可能被 gsd 包装污染，用绝对路径）：
```bash
/usr/bin/clang -O2 -o ~/.claw-ea/claw-launcher scripts/launcher.c
```

### 5.2 `scripts/Info.plist`

> 去掉了 `LSBackgroundOnly`（对首授权弹窗是负资产）。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>            <string>com.fsh.claw-ea</string>
    <key>CFBundleName</key>                  <string>claw-ea</string>
    <key>CFBundleExecutable</key>            <string>clawpy</string>
    <key>CFBundlePackageType</key>           <string>APPL</string>
    <key>CFBundleInfoDictionaryVersion</key> <string>6.0</string>
    <key>CFBundleShortVersionString</key>    <string>1.0</string>
    <key>NSRemindersFullAccessUsageDescription</key>
        <string>claw-ea 将工作消息中的提醒事项归档到 Apple 提醒事项。</string>
    <key>NSCalendarsFullAccessUsageDescription</key>
        <string>claw-ea 将会议日程写入 Apple 日历。</string>
</dict>
</plist>
```

### 5.3 `scripts/build-cert.sh`（一次性自签名证书）

> 首选 Keychain Access GUI（坑最少）：钥匙串访问 → 证书助理 → 创建证书 → 名 `claw-ea-codesign`，
> 类型「自签名根」+「代码签名」，勾「覆盖默认值」默认到底。下面 CLI 版已修 v3 的 partition-list 密码 bug。

```bash
#!/bin/bash
set -euo pipefail
CN=claw-ea-codesign
LOGIN_KC="$HOME/Library/Keychains/login.keychain-db"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/cert.conf" <<'EOF'
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = claw-ea-codesign
[ext]
keyUsage = critical, digitalSignature
extendedKeyUsage = critical, codeSigning
basicConstraints = critical, CA:false
EOF
# 系统为 LibreSSL：勿加 -legacy；导出必须带非空密码（空密码 security import 静默失败）
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout "$WORK/key.pem" -out "$WORK/cert.pem" -config "$WORK/cert.conf"
openssl pkcs12 -export -inkey "$WORK/key.pem" -in "$WORK/cert.pem" -out "$WORK/id.p12" -passout pass:clawcert
security import "$WORK/id.p12" -k "$LOGIN_KC" -P clawcert -T /usr/bin/codesign

# 关键修正：set-key-partition-list 的 -k 要的是「登录钥匙串密码」，不是路径。
# 不硬编码密码；改为放过它——首次 codesign 用此私钥时会弹一次「codesign 想使用密钥」，
# 点「始终允许」即永久授权。若需 headless 无人值守重签，再手动:
#   security set-key-partition-list -S apple-tool:,apple: -s -k <你的登录密码> "$LOGIN_KC"
echo "证书已导入 login keychain。"
echo "验证存在（注意 find-identity -v 看不到未受信自签名身份，属正常）："
echo "  security find-certificate -c $CN \"$LOGIN_KC\" >/dev/null && echo FOUND"
echo "首次 build-bundle 签名时若弹「codesign 想使用密钥」→ 点『始终允许』。"
```

### 5.4 `scripts/build-bundle.sh`（构建/重建 + 整包签名 + 清 quarantine）

```bash
#!/bin/bash
set -euo pipefail
APP="$HOME/.claw-ea/claw-ea.app"
VENV_PY="/Users/f.sh/Workspace/devs/claw_EA/.venv/bin/python"
IDENTITY=claw-ea-codesign
BUNDLE_ID=com.fsh.claw-ea
PLIST_SRC="/Users/f.sh/Workspace/devs/claw_EA/scripts/Info.plist"

# 路径 guard：防 rm -rf 误删
case "$APP" in "$HOME/.claw-ea/claw-ea.app") : ;; *) echo "APP 路径异常，拒绝: $APP"; exit 1;; esac

# macOS readlink -f 不可靠 → 用 python realpath
REAL_PY="$(/usr/bin/python3 -c "import os;print(os.path.realpath('$VENV_PY'))")"
PY_PREFIX="$(dirname "$(dirname "$REAL_PY")")"
PY_VER="$(basename "$REAL_PY" | sed 's/^python//')"   # 3.14
echo "源解释器 $REAL_PY (py$PY_VER)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/lib"
cp "$REAL_PY" "$APP/Contents/MacOS/clawpy"
cp "$PY_PREFIX/lib/libpython${PY_VER}.dylib" "$APP/Contents/lib/"
cp -R "$PY_PREFIX/lib/python${PY_VER}" "$APP/Contents/lib/python${PY_VER}"
cp "$PLIST_SRC" "$APP/Contents/Info.plist"

# 清 quarantine（拷贝可能带 xattr，Gatekeeper 会卡）
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

# 整包签名：seal Info.plist + nested code。--deep 对自签名本地包可接受。
# 不加 --options runtime（hardened runtime 会触发库校验，未签名 .so 崩）。
codesign --force --deep --identifier "$BUNDLE_ID" --sign "$IDENTITY" "$APP"

echo "=== 验证（也可单独跑 verify-bundle.sh）==="
"/Users/f.sh/Workspace/devs/claw_EA/scripts/verify-bundle.sh"
```

### 5.5 `scripts/verify-bundle.sh`（build 后硬验证）

```bash
#!/bin/bash
set -uo pipefail
APP="$HOME/.claw-ea/claw-ea.app"
CLAWPY="$APP/Contents/MacOS/clawpy"
fail=0

echo "--- 1. bundle 签名 & sealed Info.plist ---"
codesign --verify --strict --deep --verbose=2 "$APP" 2>&1 | tail -3 || fail=1
codesign -dvvv "$APP" 2>&1 | grep -E 'Identifier=|Authority=' | head

echo "--- 2. DR 与内容解耦（应为 identifier+cert，非 cdhash）---"
codesign -d -r- "$APP" 2>&1 | grep designated
codesign -d -r- "$APP" 2>&1 | grep -qi 'cdhash' && { echo "!! DR 退回 cdhash，方案前提破"; fail=1; }

echo "--- 3. bundle id 可被读到 ---"
/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist"

echo "--- 4. clawpy 能跑且 stdlib 指向 bundle 内（freeze 生效）---"
export PYTHONHOME="$APP/Contents"
"$CLAWPY" -c "import sys, sysconfig
print('version', sys.version.split()[0])
print('base_prefix', sys.base_prefix)
print('stdlib', sysconfig.get_path('stdlib'))
assert sys.base_prefix.startswith('$APP/Contents'), 'base_prefix 未指向 bundle，freeze 失效'
print('OK freeze')" || fail=1

[ "$fail" = 0 ] && echo "VERIFY PASS" || { echo "VERIFY FAIL"; exit 1; }
```

### 5.6 `src/claw_ea/eventkit_utils.py`（状态闸 + full-access API + 暴露 error）

`_request_access` 改 full-access API；新增 `_ensure_access` 状态闸：**默认不弹窗**，notDetermined 且非 GUI 授权模式时直接报错退出（绝不 headless request，防污染 TCC 缓存）。

```python
    async def ensure_calendar_access(self, allow_prompt: bool = False) -> None:
        await self._ensure_access(EKEntityTypeEvent, "Calendar", "Calendars", allow_prompt)

    async def ensure_reminder_access(self, allow_prompt: bool = False) -> None:
        await self._ensure_access(EKEntityTypeReminder, "Reminders", "Reminders", allow_prompt)

    async def _ensure_access(self, entity_type, label, pane, allow_prompt):
        st = EKEventStore.authorizationStatusForEntityType_(entity_type)
        if st in (3, 4):            # fullAccess / writeOnly → 可用
            return
        if st == 0:                 # notDetermined
            if not allow_prompt:
                raise PermissionError(
                    f"{label} 尚未授权。请在图形登录会话运行一次性授权："
                    f"`python -m claw_ea.grant`。为避免污染 TCC 缓存，headless 下拒绝主动请求。"
                )
            granted, error = await self._request_access(entity_type)
            if not granted:
                raise PermissionError(f"{label} 授权弹窗被拒：{error}")
            return
        raise PermissionError(      # denied / restricted
            f"{label} 访问被拒。请在 系统设置 › 隐私与安全性 › {pane} 开启后重跑授权。(status={st})"
        )

    async def _request_access(self, entity_type):
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        def callback(granted, error):
            loop.call_soon_threadsafe(future.set_result, (granted, error))
        if entity_type == EKEntityTypeEvent:
            self.store.requestFullAccessToEventsWithCompletion_(callback)
        else:
            self.store.requestFullAccessToRemindersWithCompletion_(callback)
        return await future
```
> 调用方（calendar.py / reminder.py）保持调 `ensure_*_access()`（默认 `allow_prompt=False`）。

### 5.7 `src/claw_ea/grant.py`（新增：唯一允许弹窗的 GUI 首授权入口）

```python
"""一次性 GUI 授权入口：仅此处允许触发 TCC 弹窗。必须在图形登录会话运行。"""
import asyncio
from claw_ea.eventkit_utils import EventKitClient

async def main():
    c = EventKitClient()
    await c.ensure_reminder_access(allow_prompt=True)
    await c.ensure_calendar_access(allow_prompt=True)
    print("授权完成。之后 Ghostty/GUI-Hermes/cron 均直接可用。")

if __name__ == "__main__":
    asyncio.run(main())
```

### 5.8 `run-server.sh`（改写：修 bug + 走 launcher + 动态版本 + PYTHONHOME）

```bash
#!/bin/bash
set -euo pipefail
REPO=/Users/f.sh/Workspace/devs/claw_EA
APP="$HOME/.claw-ea/claw-ea.app"
LAUNCHER="$HOME/.claw-ea/claw-launcher"
CLAWPY="$APP/Contents/MacOS/clawpy"

[ -x "$LAUNCHER" ] || { echo "缺 $LAUNCHER" >&2; exit 1; }
[ -x "$CLAWPY" ]   || { echo "缺 $CLAWPY（先跑 build-bundle.sh）" >&2; exit 1; }

# 动态推导 clawpy 版本，校验 venv site-packages 匹配（防 minor 升级 ABI 错配）
PYVER="$("$CLAWPY" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
SITE="$REPO/.venv/lib/python$PYVER/site-packages"
[ -d "$SITE" ] || { echo "site-packages 不匹配：$SITE 不存在（clawpy=py$PYVER，重建 bundle 或同步 venv）" >&2; exit 1; }

cd "$REPO"
export PYTHONHOME="$APP/Contents"                       # 锁 stdlib 在 bundle 内
export PYTHONPATH="$REPO/src:$SITE${PYTHONPATH:+:$PYTHONPATH}"
exec "$LAUNCHER" "$CLAWPY" -m claw_ea.server
```

---

## 6. 首次授权（实现后，GUI 会话一次）

```bash
# 必须图形登录会话（终端 ! 前缀亦可）。仅此命令允许弹窗。
cd /Users/f.sh/Workspace/devs/claw_EA
export PYTHONHOME="$HOME/.claw-ea/claw-ea.app/Contents"
export PYTHONPATH="$PWD/src:$PWD/.venv/lib/python3.14/site-packages"
"$HOME/.claw-ea/claw-launcher" "$HOME/.claw-ea/claw-ea.app/Contents/MacOS/clawpy" -m claw_ea.grant
```
应弹系统授权框；点允许后，授权按 `com.fsh.claw-ea` 写入 TCC。

---

## 7. 升级 / 维护

- **uv 例行 `uv sync`**：不影响 bundle（clawpy 冻结副本）。无需动作。
- **故意升级 python**：重跑 `build-bundle.sh`（重建 + 整包重签）。DR 与内容解耦（§2 #5）→ 旧授权自动命中新 clawpy，**无需重授权**。若 minor 升级（3.14→3.15），`run-server.sh` 的 site-packages 校验会拦下提醒同步 venv。
- 证书 `claw-ea-codesign` 长期留 login keychain，勿删。

---

## 8. 执行顺序（带验证门，含两道 GUI 阻塞门）

1. `scripts/launcher.c` → 编译到 `~/.claw-ea/claw-launcher`。验证：`./claw-launcher /bin/echo ok` 打印 ok。
2. `scripts/build-cert.sh`。验证：`security find-certificate -c claw-ea-codesign ~/Library/Keychains/login.keychain-db` 有输出。
3. `scripts/Info.plist` + `build-bundle.sh` + `verify-bundle.sh`。**门**：`verify-bundle.sh` 输出 `VERIFY PASS`（含 DR 非 cdhash + freeze 生效）。首次签名弹「codesign 想用密钥」→「始终允许」。
4. 改 `eventkit_utils.py` + 新增 `grant.py`。验证：`uv run pytest -m "not macos"` 全绿。
5. 改 `run-server.sh`。验证：手动 `./run-server.sh` 起 MCP server，stdio 无错。
6. **🚦 Gate A（阻塞，验 INF-1 + INF-3）**：开 `log stream --debug --predicate 'process=="tccd"'`，在 **GUI 双击启动的 Hermes** 里触发一次 claw-ea 提醒，看 `AttributionChain` 的 `responsible=` 是否为 **`com.fsh.claw-ea`**（而非 `com.nousresearch.hermes`）。
   - ✅ 是 → bundle attribution + 整链 disclaim 成立，继续。
   - ❌ 否（仍 Hermes / 仍 cdhash）→ **停**。bundle attribution 不被 TCC 认；转 §10 退路或 §11 Swift .app/XPC。
7. **🚦 Gate B（阻塞，验 INF-2）**：§6 首授权命令在 GUI 跑。
   - ✅ 弹窗出现 + 点允许 + `authorizationStatus`→3 → 持久化成立。
   - ❌ 无弹窗 / 静默 deny → **停**。先 `tccutil reset Reminders; tccutil reset Calendar` 清掉可能被污染的记录，再转 §10 退路。
8. 端到端：GUI-Hermes 建提醒成功无 PermissionError；内置 cron 触发一次也成功。
9. 回归：`uv run pytest`（含 macos 标记）全绿。

> headless 安全：§5.6 的状态闸保证即使 cron 抢先跑，notDetermined 下也只报错退出、**绝不 request**，不会把 `com.fsh.claw-ea` 污染成 deny。首授权只能由 §6 的 GUI 命令（`allow_prompt=True`）完成。

---

## 9. 回滚

- bundle/launcher：`rm -rf ~/.claw-ea/claw-ea.app ~/.claw-ea/claw-launcher`；`run-server.sh` git revert。
- 证书：Keychain Access 删 `claw-ea-codesign`（或 `security delete-identity -c claw-ea-codesign`）。
- TCC：`tccutil reset Reminders` / `tccutil reset Calendar`（**清该类全部 app 授权，慎用**）。
- 代码：`eventkit_utils.py` / `grant.py` git revert。

---

## 10. 若 Gate A/B 失败的退路

- **Gate A 失败（bundle attribution 不成立）**：clawpy self-responsible 但 TCC 未按 bundle 记账 → 说明非 LS 启动的 posix_spawn Mach-O 拿不到 bundle 身份。退路：把首授权与运行都改为经 **LaunchServices 启动的已签 .app**（`open -b com.fsh.claw-ea`），但这会切断 stdio → 需配合 XPC/socket 把 MCP 流量从 .app 桥回 Hermes（即 §11 路线）。
- **Gate B 失败（无弹窗/静默 deny）**：先 `tccutil reset` 清污染。退路：用一个带窗口的最小 `.app`（同 `com.fsh.claw-ea`）双击取首授权，授权落到同 bundle id，再由 clawpy 复用。

---

## 11. 备选方案（已评估）

- **Swift/ObjC EventKit helper**：仅当做成**完整签名 `.app` / XPC service + LaunchServices 启动 + seal Info.plist**，才比 v3.1 低风险——消灭 python freeze / rpath / stdlib getpath / venv ABI / 未签名 pyobjc .so 全部问题；python 只通过 IPC 调它。代价：写 Swift helper（create/delete reminder+event、list calendars）+ 重写 5 个工具模块为 IPC。**若 Gate A 失败，这是首选退路**。
- 纯 Swift CLI 被 shell-out（不走 LS/disclaim）：❌ 仍继承 Hermes responsible。
- 签 uv 解释器（v2）：❌ TCC 不评估 accessing 叶子。
- 授权 Hermes.app：❌ 无 usage 串无法 grant，更新即失效。
- 写 TCC.db / MDM PPPC：❌ SIP/脆弱/仅托管机现实。
```

---

## 12. 仍存的已知不确定性（诚实标注）

- INF-1/2/3 在 Gate A/B 通过前仍是推断；v3.1 的价值是**把它们前置成低成本阻塞门**，失败有明确退路（§10/§11），不会在错误前提上继续盖楼。
- `--deep` 签名 Apple 已不推荐用于分发（本地自签名包可接受）；若将来要分发需改 Developer ID + notarization。
- bundle 内 stdlib `.so` 由整包签名一并签；若数量导致签名过慢，可评估只签 clawpy+libpython 并验证 TCC 是否仍认（属 Gate A 范畴）。
