#!/bin/bash
# 构建/重建 claw-ea.app：冻结 uv python 副本 + libpython + stdlib，写 Info.plist，整包签名，清 quarantine。
set -euo pipefail
APP="$HOME/.claw-ea/claw-ea.app"
VENV_PY="/Users/f.sh/Workspace/devs/claw_EA/.venv/bin/python"
IDENTITY=claw-ea-codesign
BUNDLE_ID=com.fsh.claw-ea
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/Info.plist"

# 路径 guard：防 rm -rf 误删
case "$APP" in "$HOME/.claw-ea/claw-ea.app") : ;; *) echo "APP 路径异常，拒绝: $APP"; exit 1;; esac
[ -f "$PLIST_SRC" ] || { echo "缺 $PLIST_SRC"; exit 1; }

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

# 清 quarantine(拷贝可能带 xattr，Gatekeeper 会卡)
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

# 整包签名：seal Info.plist + nested code。--deep 对自签名本地包可接受。
# 不加 --options runtime(hardened runtime 会触发库校验，未签名 .so 崩)。
codesign --force --deep --identifier "$BUNDLE_ID" --sign "$IDENTITY" "$APP"

echo "=== 验证 ==="
"$SCRIPT_DIR/verify-bundle.sh"
