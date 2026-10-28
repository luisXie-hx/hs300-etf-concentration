#!/usr/bin/env python3
"""抓取上交所 ETF 每日总份额 (TOT_VOL, 单位: 万份)"""
import json, os, time, sys, datetime as _dt
from zoneinfo import ZoneInfo
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "sse_shares.json")
EMPTY = os.path.join(os.path.dirname(__file__), "..", "data", "sse_empty_days.json")
URL = ("http://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L"
       "&STAT_DATE={d}")
HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
       "Referer": "http://www.sse.com.cn/"}


def get_trade_dates():
    """按工作日生成候选日期（交易所接口对非交易日返回空，自动跳过）

    东财日K单次最多返回约 500 条，无法用于 5 年日历，故直接用工作日序列。
    """
    start = _dt.date(2021, 9, 1)
    end = _dt.datetime.now(ZoneInfo("Asia/Shanghai")).date()
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += _dt.timedelta(days=1)
    return out


def fetch(date):
    req = urllib.request.Request(URL.format(d=date), headers=HDR)
    for _ in range(3):
        try:
            raw = urllib.request.urlopen(req, timeout=25).read()
            d = json.loads(raw)
            return {x["SEC_CODE"]: float(x["TOT_VOL"]) for x in d.get("result") or []}
        except Exception:
            time.sleep(1.5)
    return None


def main():
    dates = get_trade_dates()
    print(f"交易日数 {len(dates)}: {dates[0]} ~ {dates[-1]}", flush=True)
    store = {}
    if os.path.exists(OUT):
        store = json.load(open(OUT))
    # 已确认无数据的日期（节假日），不再重复探测；最近 3 天除外（数据可能延迟披露）
    empty = set(json.load(open(EMPTY))) if os.path.exists(EMPTY) else set()
    cutoff = (_dt.datetime.now(ZoneInfo("Asia/Shanghai")).date()
              - _dt.timedelta(days=3)).isoformat()
    todo = [d for d in dates if d not in store and d not in empty]
    print(f"待抓取 {len(todo)} 天（已跳过 {len(empty)} 个非交易日）", flush=True)

    for i, d in enumerate(todo):
        r = fetch(d)
        if r is None:
            print(f"  FAIL {d} 网络异常，下次重试", flush=True)
            continue
        if not r:
            if d < cutoff:
                empty.add(d)
            print(f"  SKIP {d} (无数据)", flush=True)
            continue
        store[d] = r
        if i % 20 == 0:
            print(f"  [{i+1}/{len(todo)}] {d} n={len(r)}", flush=True)
            json.dump(store, open(OUT, "w"))
        time.sleep(0.22)

    json.dump(store, open(OUT, "w"))
    json.dump(sorted(empty), open(EMPTY, "w"))
    print("DONE days=", len(store), " empty=", len(empty), flush=True)


if __name__ == "__main__":
    main()
