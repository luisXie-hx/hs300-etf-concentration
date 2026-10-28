#!/bin/bash
# 安装系统级定时任务（可选）
#
# 平台定时任务（WorkBuddy automation）需要应用处于运行状态才会触发。
# 这个脚本装的是系统级任务：只要电脑开机，每晚 19:00 / 22:00 自动跑，不依赖任何 App。
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
cd "$PROJ" || exit 1
./update.sh
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
    <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
EOF

if launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null; then
  echo "✅ 已通过 launchd 安装：每晚 19:00 / 22:00 自动更新"
  echo "   查看状态： launchctl list | grep hs300etf"
  echo "   查看日志： tail -f \"$LOG\""
  exit 0
fi

# ---------- 回退 cron ----------
rm -f "$PLIST"
if ( crontab -l 2>/dev/null | grep -v "hs300etf-update"; \
     echo "0 19,22 * * * /bin/bash \"$RUNNER\" >> \"$LOG\" 2>&1" ) | crontab - 2>/dev/null; then
  echo "✅ 已通过 cron 安装：每晚 19:00 / 22:00 自动更新"
  echo "   查看： crontab -l"
  echo "   日志： tail -f \"$LOG\""
  exit 0
fi

echo "❌ launchd 与 cron 都安装失败。"
echo "   多半是终端缺少权限。请在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」里"
echo "   给「终端」打开开关后重试。"
exit 1
