#!/bin/bash
# 每日更新：抓取沪深300ETF 份额 → 重建数据集 → 导出前端数据
# 建议在交易日 18:00 之后运行（交易所份额已披露、基金净值已更新）
set -e
cd "$(dirname "$0")"
PY="/Users/luis/.workbuddy-ai/binaries/python/versions/3.13.12/bin/python3"

echo "== [1/5] 沪市日频份额（上交所） =="
$PY scripts/fetch_sse_shares.py

echo "== [2/5] 深市季报份额 =="
$PY scripts/fetch_sz_quarterly.py || echo "  ⚠ 深市季报抓取失败，沿用已有数据"

echo "== [3/5] 当日份额快照 =="
$PY scripts/fetch_snapshot.py || echo "  ⚠ 当日快照抓取失败，沿用已有数据"

echo "== [4/5] 合并计算 =="
$PY scripts/build_dataset.py

echo "== [5/5] 导出前端数据 =="
$PY scripts/export_web.py

echo "完成：打开 index.html 查看"
