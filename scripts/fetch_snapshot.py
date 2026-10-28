#!/usr/bin/env python3
"""抓取沪深300ETF 当日总份额快照（东财 f84，与交易所口径一致）

同时把每日快照沉淀进 sz_snapshots.json，使深市份额逐步由"季报插值"转为"真实日频"。
"""
import json, os, sys, time, datetime as dt
from zoneinfo import ZoneInfo
import re
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
SH = ["510300","510310","510320","510330","510350","510360","510370","510380","510390",
      "515130","515310","515330","515350","515360","515380","515390","515660","561930","563520"]
SZ = ["159919","159925","159300","159330","159393","159673"]
HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
       "Referer": "https://quote.eastmoney.com/"}
SZSE_HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "http://www.szse.cn/"}


def get(secid):
    u = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f58,f84,f116"
    for _ in range(3):
        try:
            req = urllib.request.Request(u, headers=HDR)
            d = json.loads(urllib.request.urlopen(req, timeout=15).read())["data"]
            if not d or not d.get("f84"):
                return None
            return round(d["f84"] / 1e8, 4)
        except Exception:
            time.sleep(1.2)
    return None


def get_szse(code):
    """深交所 ETF 列表的 dqgm 字段即当日总份额（单位万份），作为东财的备用源"""
    u = ("http://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON"
         f"&CATALOGID=1945&TABKEY=tab1&txtQueryKeyAndJC={code}")
    for _ in range(2):
        try:
            req = urllib.request.Request(u, headers=SZSE_HDR)
            d = json.loads(urllib.request.urlopen(req, timeout=20).read())
            for x in d[0]["data"]:
                c = re.sub("<[^>]+>", "", x.get("sys_key", "")).strip()
                if c == code and x.get("dqgm"):
                    return round(float(x["dqgm"].replace(",", "")) / 1e4, 4)
        except Exception:
            time.sleep(1.0)
    return None


def latest_trade_date():
    """以沪市 510300 的交易所份额是否已更新来判断最新交易日"""
    p = os.path.join(DATA, "sse_shares.json")
    if not os.path.exists(p):
        return None
    sse = json.load(open(p))
    for d in sorted(sse, reverse=True):
        if sse[d]:
            return d
    return None


if __name__ == "__main__":
    out = {}
    for c in SZ:
        v = get("0." + c)
        if v:
            out[c] = v
        time.sleep(0.15)

    # 东财失败的，用深交所补齐
    missing = [c for c in SZ if c not in out]
    if missing:
        print(f"东财缺失 {len(missing)} 只，尝试深交所备用源：{missing}")
        for c in missing:
            v = get_szse(c)
            if v:
                out[c] = v
            time.sleep(0.3)

    if not out:
        print("东财接口无返回（可能被限流），保留原有快照")
        sys.exit(1)

    json.dump(out, open(os.path.join(DATA, "snapshot.json"), "w"), ensure_ascii=False, indent=1)

    # 仅在"当日数据已由交易所披露"且已收盘时归档，保证锚点值与该交易日严格对应
    now = dt.datetime.now(ZoneInfo("Asia/Shanghai"))
    today = now.date().isoformat()
    hist_path = os.path.join(DATA, "sz_snapshots.json")
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else {}
    td = latest_trade_date()
    closed = now.hour > 15 or (now.hour == 15 and now.minute >= 30)
    if td and closed and td == today:
        hist[td] = dict(out)
        json.dump(hist, open(hist_path, "w"), ensure_ascii=False, indent=1)
        print(f"已记录 {td} 深市收盘快照，累计 {len(hist)} 个交易日")
    elif td:
        print(f"最新交易日 {td} 尚未披露或未收盘（当前 {now.strftime('%H:%M')}），"
              f"本次仅更新当日快照，不写入历史")

    print(f"snapshot {len(out)} 只（深市）")
    for c in ["159919", "159925", "159673"]:
        print(f"  {c}: {out.get(c)} 亿份")
