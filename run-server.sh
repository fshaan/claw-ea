#!/bin/bash
# claw-ea MCP server 启动器。
# 经 claw-launcher(disclaim) 拉起 bundle 内冻结的 clawpy，使其自立为 TCC responsible 进程，
# 从而读 claw-ea.app 的稳定签名身份 + usage 串(Ghostty/GUI-Hermes/cron 归因一致)。
set -euo pipefail
REPO=/Users/f.sh/Workspace/devs/claw_EA
APP="$HOME/.claw-ea/claw-ea.app"
LAUNCHER="$HOME/.claw-ea/claw-launcher"
CLAWPY="$APP/Contents/MacOS/clawpy"

[ -x "$LAUNCHER" ] || { echo "缺 $LAUNCHER(先编译 scripts/launcher.c)" >&2; exit 1; }
[ -x "$CLAWPY" ]   || { echo "缺 $CLAWPY(先跑 scripts/build-bundle.sh)" >&2; exit 1; }

# 动态推导 clawpy 版本，校验 venv site-packages 匹配(防 minor 升级 ABI 错配)
PYVER="$("$CLAWPY" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
SITE="$REPO/.venv/lib/python$PYVER/site-packages"
[ -d "$SITE" ] || { echo "site-packages 不匹配：$SITE 不存在(clawpy=py$PYVER，重建 bundle 或同步 venv)" >&2; exit 1; }

cd "$REPO"
export PYTHONHOME="$APP/Contents"                       # 锁 stdlib 在 bundle 内
export PYTHONPATH="$REPO/src:$SITE${PYTHONPATH:+:$PYTHONPATH}"
exec "$LAUNCHER" "$CLAWPY" -m claw_ea.server
