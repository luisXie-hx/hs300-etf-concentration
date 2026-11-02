#!/bin/bash
# 每日更新：抓取沪深300ETF 份额 + 市场情绪指标 → 重建数据集 → 导出前端数据
# 建议在交易日 21:00 之后运行（交易所份额已披露、两融余额已更新）
set -e
cd "$(dirname "$0")"
PY="/Users/luis/.workbuddy-ai/binaries/python/versions/3.13.12/bin/python3"

echo "== [1/8] 沪市日频份额（上交所） =="
$PY scripts/fetch_sse_shares.py

echo "== [2/8] 深市季报份额 =="
$PY scripts/fetch_sz_quarterly.py || echo "  ⚠ 深市季报抓取失败，沿用已有数据"

echo "== [3/8] 当日份额快照 =="
$PY scripts/fetch_snapshot.py || echo "  ⚠ 当日快照抓取失败，沿用已有数据"

echo "== [4/8] 市场情绪原始数据（成交额 / 两融 / 指数） =="
$PY scripts/fetch_market.py || echo "  ⚠ 情绪数据抓取失败，沿用已有数据"

echo "== [5/8] 市场情绪指标计算 =="
$PY scripts/build_market.py || echo "  ⚠ 情绪指标计算失败，沿用已有数据"

echo "== [6/8] 长期收益对比（沪深300全收益 / 债券型基金） =="
$PY scripts/fetch_tri.py || echo "  ⚠ 长期对比抓取失败，沿用已有数据"

echo "== [7/8] 合并计算 =="
$PY scripts/build_dataset.py

echo "== [8/8] 导出前端数据 =="
$PY scripts/export_web.py

echo "完成：打开 index.html 查看"
