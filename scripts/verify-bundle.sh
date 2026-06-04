#!/bin/bash
# build 后硬验证：bundle 签名 seal、DR 非 cdhash、bundle id 可读、clawpy 跑且 stdlib 在 bundle 内。
set -uo pipefail
APP="$HOME/.claw-ea/claw-ea.app"
CLAWPY="$APP/Contents/MacOS/clawpy"
fail=0

echo "--- 1. bundle 签名 & sealed Info.plist ---"
codesign --verify --strict --deep --verbose=2 "$APP" 2>&1 | tail -3 || fail=1
codesign -dvvv "$APP" 2>&1 | grep -E 'Identifier=|Authority=' | head

echo "--- 2. DR 与内容解耦(应为 identifier+cert，非 cdhash) ---"
codesign -d -r- "$APP" 2>&1 | grep designated
if codesign -d -r- "$APP" 2>&1 | grep -qi 'cdhash'; then echo "!! DR 退回 cdhash，方案前提破"; fail=1; fi

echo "--- 3. bundle id 可读 ---"
/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist"

echo "--- 4. clawpy 能跑且 stdlib 指向 bundle 内(freeze 生效) ---"
export PYTHONHOME="$APP/Contents"
"$CLAWPY" -c "import sys, sysconfig
print('version', sys.version.split()[0])
print('base_prefix', sys.base_prefix)
print('stdlib', sysconfig.get_path('stdlib'))
assert sys.base_prefix.startswith('$APP/Contents'), 'base_prefix 未指向 bundle，freeze 失效'
print('OK freeze')" || fail=1

if [ "$fail" = 0 ]; then echo "VERIFY PASS"; else echo "VERIFY FAIL"; exit 1; fi
