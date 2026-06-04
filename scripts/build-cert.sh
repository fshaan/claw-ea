#!/bin/bash
# 一次性建自签名 code-signing 证书 claw-ea-codesign 进 login keychain。
# 首选 Keychain Access GUI(坑最少)：钥匙串访问 → 证书助理 → 创建证书 →
#   名 claw-ea-codesign，类型「自签名根」+「代码签名」，勾「覆盖默认值」默认到底。
# 下面 CLI 版已规避 v3 的两个坑：空密码 p12 静默失败；set-key-partition-list 的 -k 误传路径。
set -euo pipefail
CN=claw-ea-codesign
LOGIN_KC="$HOME/Library/Keychains/login.keychain-db"

if security find-certificate -c "$CN" "$LOGIN_KC" >/dev/null 2>&1; then
  echo "证书 $CN 已存在，跳过。"; exit 0
fi

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
# 系统为 LibreSSL：勿加 -legacy；导出必须带非空密码(空密码 security import 静默失败)
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout "$WORK/key.pem" -out "$WORK/cert.pem" -config "$WORK/cert.conf"
openssl pkcs12 -export -inkey "$WORK/key.pem" -in "$WORK/cert.pem" \
  -out "$WORK/id.p12" -passout pass:clawcert
security import "$WORK/id.p12" -k "$LOGIN_KC" -P clawcert -T /usr/bin/codesign

echo "✓ 证书 $CN 已导入 login keychain。"
echo "  注意 find-identity -v 看不到未受信自签名身份(正常)；验证存在用:"
echo "    security find-certificate -c $CN \"$LOGIN_KC\" >/dev/null && echo FOUND"
echo "  首次 build-bundle 签名时会弹「codesign 想使用密钥」→ 点『始终允许』(只此一次)。"
echo "  若需 headless 无人值守重签，手动跑(需登录钥匙串密码):"
echo "    security set-key-partition-list -S apple-tool:,apple: -s -k <登录密码> \"$LOGIN_KC\""
