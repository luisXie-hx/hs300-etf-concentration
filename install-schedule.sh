#!/bin/bash
# 安装系统级定时任务（可选）
#
# 平台定时任务（WorkBuddy automation）需要应用处于运行状态才会触发。
# 这个脚本装的是系统级任务：只要电脑开机，每晚 21:30 / 23:30 自动跑，不依赖任何 App。
#
# 用法：  ./install-schedule.sh          安装
#         ./install-schedule.sh remove   卸载

set -e

LABEL="com.luis.hs300etf.update"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUNNER="$HOME/bin/hs300etf-update.sh"
LOG="$HOME/Library/Logs/hs300etf-update.log"
PROJ="/Users/luis/WorkBuddy AI/金融"

# ---------- 卸载 ----------
if [ "$1" = "remove" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  ( crontab -l 2>/dev/null | grep -v "hs300etf-update" ) | crontab - 2>/dev/null || true
  echo "已卸载系统级定时任务。"
  exit 0
fi

# ---------- 准备运行脚本 ----------
mkdir -p "$HOME/bin" "$HOME/Library/Logs"
cat > "$RUNNER" <<EOF
#!/bin/bash
# 本机每日更新：抓数据 → 有实质推进才 commit → 推送到 GitHub
cd "$PROJ" || exit 1
PY="/Users/luis/.workbuddy-ai/binaries/python/versions/3.13.12/bin/python3"
[ -x "\$PY" ] || PY=python3

stamp() {
  "\$PY" - <<'PYEOF'
import json
try:
    d = json.load(open('data/dashboard.json'))
    a = d['rows'][-1]['date']
except Exception:
    a = '-'
try:
    t = json.load(open('data/tri.json'))['series']['hs300tri']
    b = max(t)
except Exception:
    b = '-'
print(a + '|' + b)
PYEOF
}

BEFORE=\$(stamp)
./update.sh || exit 1
AFTER=\$(stamp)
echo "[\$(date '+%F %T')] 数据日 \$BEFORE -> \$AFTER"

if [ "\$BEFORE" = "\$AFTER" ]; then
  echo "数据日未推进，不提交"
  exit 0
fi

git add -A
if git diff --staged --quiet; then
  echo "无变更可提交"
  exit 0
fi

git -c user.name="hs300-local" -c user.email="hs300-local@localhost" \
    commit -q -m "data: 更新至 \$(date +%F)（本机抓取）" || exit 0

if git push origin main --quiet 2>/dev/null; then
  echo "已推送到 GitHub"
  exit 0
fi

echo "push 被拒，rebase 后重试"
git fetch origin main --quiet || true
if git pull --rebase -X ours origin main --quiet; then
  git push origin main --quiet && echo "rebase 后推送成功"
else
  git rebase --abort 2>/dev/null || true
  echo "!! rebase 失败，本地提交保留，请手动处理"
  exit 1
fi
EOF
chmod +x "$RUNNER"
echo "运行脚本： $RUNNER"

# ---------- 优先 launchd ----------
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUNNER</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Hour</key><integer>23</integer><key>Minute</key><integer>30</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
EOF

if launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null; then
  echo "✅ 已通过 launchd 安装：每晚 21:30 / 23:30 自动更新"
  echo "   查看状态： launchctl list | grep hs300etf"
  echo "   查看日志： tail -f \"$LOG\""
  exit 0
fi

# ---------- 回退 cron ----------
rm -f "$PLIST"
if ( crontab -l 2>/dev/null | grep -v "hs300etf-update"; \
     echo "30 21,23 * * * /bin/bash \"$RUNNER\" >> \"$LOG\" 2>&1" ) | crontab - 2>/dev/null; then
  echo "✅ 已通过 cron 安装：每晚 21:30 / 23:30 自动更新"
  echo "   查看： crontab -l"
  echo "   日志： tail -f \"$LOG\""
  exit 0
fi

echo "❌ launchd 与 cron 都安装失败。"
echo "   多半是终端缺少权限。请在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」里"
echo "   给「终端」打开开关后重试。"
exit 1
