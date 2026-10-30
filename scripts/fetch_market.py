#!/usr/bin/env python3
"""抓取大盘状态所需的原始数据

数据源：
- 指数日线：腾讯（稳定，一次可取 5 年）
- 成交额：东财 K 线 f57（上证综指 1.000001 + 深证综指 0.399106，均为全市场口径）
         → 失败时回退同花顺（仅近期数据）
- 两融余额：东财 datacenter RPTA_RZRQ_LSHJ（全市场合计）

注意：东财指数 K 线的 f57 对沪市综指/深市综指返回的是该交易所全部股票成交额，
而沪深300 等成分指数返回的只是成分股成交额，两者不能混用。
"""
import json, os, re, time, sys
import datetime as dt
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

INDEXES = {
    "hs300": ("sh000300", "沪深300"),
    "sse":   ("sh000001", "上证指数"),
    "szse":  ("sz399001", "深证成指"),
    "cyb":   ("sz399006", "创业板指"),
}


def _get(url, headers, timeout=30, retry=3):
    for _ in range(retry):
        try:
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception:
            time.sleep(1.5)
    return None


def fetch_tx_index(symbol):
    """腾讯日线：[日期, 开, 收, 高, 低, 成交量(手)]"""
    u = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
         f"param={symbol},day,2021-09-01,2030-01-01,1600,qfq")
    raw = _get(u, {"User-Agent": UA})
    if not raw:
        return None
    d = json.loads(raw)
    node = d["data"][list(d["data"].keys())[0]]
    rows = node.get("day") or node.get("qfqday") or []
    out = {}
    for r in rows:
        out[r[0]] = {"close": float(r[2]), "vol": float(r[5])}
    return out


def fetch_em_turnover(secid):
    """东财 K 线：f57 为成交额（元）"""
    u = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
         f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f53,f57"
         "&klt=101&fqt=0&beg=20210901&end=20500101")
    raw = _get(u, {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}, timeout=25, retry=3)
    if not raw:
        return None
    try:
        d = json.loads(raw)["data"]["klines"]
    except Exception:
        return None
    out = {}
    for k in d:
        p = k.split(",")
        try:
            out[p[0]] = float(p[2])
        except (ValueError, IndexError):
            continue
    return out or None


def fetch_ths_turnover(code):
    """同花顺：末段含成交额，字段 [日期,开,高,低,收,成交量,成交额,...]"""
    u = f"https://d.10jqka.com.cn/v6/line/{code}/01/last.js"
    raw = _get(u, {"User-Agent": UA, "Referer": "https://stockpage.10jqka.com.cn/"}, timeout=25, retry=2)
    if not raw:
        return None
    s = raw.decode("utf-8", "ignore")
    m = re.search(r"\((.*)\)\s*;?\s*$", s, re.S)
    if not m:
        return None
    d = json.loads(m.group(1))
    out = {}
    for row in d.get("data", "").split(";"):
        p = row.split(",")
        if len(p) >= 7:
            dt = f"{p[0][:4]}-{p[0][4:6]}-{p[0][6:8]}"
            out[dt] = float(p[6])
    return out or None


def fetch_margin():
    """东财两融历史合计：RZYE 融资余额、RQYE 融券余额（单位元）

    接口单页有上限，需分页抓取。
    """
    out = {}
    for page in range(1, 12):
        u = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
             "reportName=RPTA_RZRQ_LSHJ&columns=ALL&pageSize=500"
             f"&pageNumber={page}"
             "&sortColumns=DIM_DATE&sortTypes=-1&source=WEB"
             "&filter=(DIM_DATE%3E%3D%272021-09-01%27)")
        raw = _get(u, {"User-Agent": UA, "Referer": "https://data.eastmoney.com/"}, timeout=30)
        if not raw:
            break
        d = json.loads(raw)
        rows = (d.get("result") or {}).get("data") or []
        if not rows:
            break
        for x in rows:
            dt = x["DIM_DATE"][:10]
            rz = x.get("RZYE") or 0
            rq = x.get("RQYE") or 0
            out[dt] = {"fin": rz, "short": rq, "total": rz + rq}
        if len(rows) < 500:
            break
        time.sleep(0.4)
    return out or None


def main():
    res = {"index": {}, "turnover": {}, "margin": None}

    for key, (sym, name) in INDEXES.items():
        d = fetch_tx_index(sym)
        if d:
            res["index"][key] = {"name": name, "symbol": sym, "series": d}
            print(f"指数 {name}: {len(d)} 天  {min(d)} ~ {max(d)}")
        else:
            print(f"指数 {name}: FAIL")
        time.sleep(0.5)

    # 成交额：沪市 + 深市全市场口径
    sse_turn = fetch_em_turnover("1.000001")   # 上证综指
    szse_turn = fetch_em_turnover("0.399106")  # 深证综指
    src = "eastmoney"
    if not sse_turn or not szse_turn:
        print("东财成交额不可用，回退同花顺")
        sse_turn = fetch_ths_turnover("hs_1A0001")
        szse_turn = fetch_ths_turnover("hs_399001")
        src = "ths"
    if sse_turn and szse_turn:
        days = sorted(set(sse_turn) & set(szse_turn))
        turn = {d: sse_turn[d] + szse_turn[d] for d in days}
        # 当日未收盘的 K 线是盘中数据，不能写进历史序列
        now = dt.datetime.now()
        today = now.strftime("%Y-%m-%d")
        if turn.get(today) and (now.hour, now.minute) < (15, 5):
            turn.pop(today)
            days = [d for d in days if d != today]
            print(f"  剔除当日未收盘数据 {today}")
        res["turnover"] = turn
        res["turnover_src"] = src
        print(f"两市成交额({src}): {len(days)} 天  {days[0]} ~ {days[-1]}")
    else:
        print("成交额: FAIL")

    m = fetch_margin()
    if m:
        res["margin"] = m
        ks = sorted(m)
        print(f"两融余额: {len(ks)} 天  {ks[0]} ~ {ks[-1]}  最新 {m[ks[-1]]['total']/1e8:.0f} 亿")
    else:
        print("两融: FAIL")

    json.dump(res, open(os.path.join(DATA, "market_raw.json"), "w"), ensure_ascii=False)
    print("saved data/market_raw.json")


if __name__ == "__main__":
    main()
