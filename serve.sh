#!/bin/bash
# 手机查看：在局域网内启动服务，手机连同一 WiFi 扫码或输入地址即可
cd "$(dirname "$0")"
PY="/Users/luis/.workbuddy-ai/binaries/python/versions/3.13.12/bin/python3"
PORT="${1:-8899}"

IP=$(ipconfig getifaddr en0 2>/dev/null)
[ -z "$IP" ] && IP=$(ipconfig getifaddr en1 2>/dev/null)
[ -z "$IP" ] && IP=$(ifconfig | awk '/inet 192\.|inet 10\.|inet 172\./{print $2; exit}')

if [ -z "$IP" ]; then
  echo "未检测到局域网 IP，请确认已连接 WiFi。"
  exit 1
fi

# 端口被占用则自动顺延
while lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  echo "端口 $PORT 已被占用，尝试 $((PORT+1))"
  PORT=$((PORT+1))
done

URL="http://$IP:$PORT/index.html"

echo ""
echo "  手机访问地址： $URL"
echo "  （手机需与本机连同一个 WiFi）"
echo ""
/Users/luis/.workbuddy-ai/binaries/python/envs/default/bin/python - "$URL" <<'EOF'
import sys, qrcode
qr = qrcode.QRCode(border=1, box_size=1)
qr.add_data(sys.argv[1]); qr.make()
qr.print_ascii(invert=True)
EOF
echo ""
echo "  按 Ctrl+C 停止服务"
echo ""
$PY -m http.server "$PORT" --bind 0.0.0.0
