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

# 预编译 .pyc：cp 改了 .py 的 mtime，拷来的旧 .pyc 头里的源 mtime 对不上 → 运行时 Python 会
# 重新编译并写新 .pyc 进 bundle，破坏整包签名 seal(codesign --verify --strict 失败)。
# 先删旧 __pycache__ 再用 bundle 内 clawpy 重新 compileall(.pyc 头记录拷贝后的 .py mtime)，
# 这样运行时 mtime 一致、不再重写。签名放在它之后，把一致的 .pyc 一并 seal。
find "$APP/Contents/lib" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
PYTHONHOME="$APP/Contents" "$APP/Contents/MacOS/clawpy" -m compileall -qq "$APP/Contents/lib/python${PY_VER}" || true

# 清 quarantine(拷贝可能带 xattr，Gatekeeper 会卡)
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

# 专用 keychain(由 build-cert.sh 建)解锁，供 headless 签名
KC="$HOME/.claw-ea/claw-ea.keychain-db"
PASS_FILE="$HOME/.claw-ea/.keychain-pass"
[ -f "$KC" ] && [ -f "$PASS_FILE" ] || { echo "缺专用 keychain，先跑 scripts/build-cert.sh"; exit 1; }
security unlock-keychain -p "$(cat "$PASS_FILE")" "$KC"
# 未受信自签名身份 codesign 按【名字】找不到(同 find-identity -v 隐藏)，须按 SHA1 签；
# 且 codesign 的身份搜索只认【搜索列表】里的 keychain(--keychain 不够)，故临时加入再还原。
SHA1="$(security find-identity "$KC" 2>/dev/null | grep -i "$IDENTITY" | head -1 | awk '{print $2}')"
[ -n "$SHA1" ] || { echo "在 $KC 找不到身份 $IDENTITY"; exit 1; }
ORIG_LIST="$(security list-keychains -d user | sed 's/[\" ]//g' | tr '\n' ' ')"
security list-keychains -d user -s $ORIG_LIST "$KC" >/dev/null 2>&1
restore_kc() { security list-keychains -d user -s $ORIG_LIST >/dev/null 2>&1; }
trap restore_kc EXIT

# 整包签名：seal Info.plist + nested code。--deep 对自签名本地包可接受。
# 不加 --options runtime(hardened runtime 会触发库校验，未签名 .so 崩)。
codesign --force --deep --identifier "$BUNDLE_ID" --sign "$SHA1" "$APP"
restore_kc; trap - EXIT

echo "=== 验证 ==="
"$SCRIPT_DIR/verify-bundle.sh"
