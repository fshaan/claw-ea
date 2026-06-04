#!/bin/bash
# 一次性建自签名 code-signing 证书 claw-ea-codesign，放入【专用 keychain】(非 login)，
# 以便 headless 无人值守签名/重签。passphrase 存 ~/.claw-ea/.keychain-pass (600，仓库外不入 git)。
# 已规避 v3 两个坑：空密码 p12 静默失败；set-key-partition-list 的 -k 误传路径。
# (备选：也可用 Keychain Access GUI 建同名证书进 login keychain，再改 build-bundle.sh 的 KC 指向。)
set -euo pipefail
CN=claw-ea-codesign
HOME_DIR="$HOME/.claw-ea"
KC="$HOME_DIR/claw-ea.keychain-db"
PASS_FILE="$HOME_DIR/.keychain-pass"
mkdir -p "$HOME_DIR"

if [ -f "$PASS_FILE" ] && security find-certificate -c "$CN" "$KC" >/dev/null 2>&1; then
  echo "✓ 证书 $CN 已在专用 keychain，跳过。"; exit 0
fi

# 随机 passphrase，600，仓库外
if [ ! -f "$PASS_FILE" ]; then
  ( umask 077; openssl rand -hex 24 > "$PASS_FILE" ); chmod 600 "$PASS_FILE"
fi
KCPASS="$(cat "$PASS_FILE")"

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
# 系统为 LibreSSL：勿加 -legacy；p12 导出必须带非空密码(空密码 security import 静默失败)
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout "$WORK/key.pem" -out "$WORK/cert.pem" -config "$WORK/cert.conf"
openssl pkcs12 -export -inkey "$WORK/key.pem" -in "$WORK/cert.pem" \
  -out "$WORK/id.p12" -passout pass:clawcert

security delete-keychain "$KC" 2>/dev/null || true
security create-keychain -p "$KCPASS" "$KC"
security set-keychain-settings "$KC"                 # 不自动锁
security unlock-keychain -p "$KCPASS" "$KC"
security import "$WORK/id.p12" -k "$KC" -P clawcert -T /usr/bin/codesign
# 关键：-k 要 keychain 密码(此处是我们自设的专用 keychain 密码，已知) → headless 可无交互签名
security set-key-partition-list -S apple-tool:,apple: -s -k "$KCPASS" "$KC" >/dev/null

echo "✓ 专用 keychain + 证书就绪：$KC"
echo "  passphrase: $PASS_FILE (600，仓库外)"
security find-certificate -c "$CN" "$KC" >/dev/null && echo "  FOUND $CN"
