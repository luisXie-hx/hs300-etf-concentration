#!/usr/bin/env python3
"""抓取深市沪深300ETF 季报份额（交易所不提供深市历史日频，季报为同口径最低频率源）"""
import json, os, re, sys, time
import urllib.request

HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Referer": "https://fundf10.eastmoney.com/"}
SZ = ["159919", "159925", "159300", "159330", "159393", "159673"]
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "sz_quarterly.json")


def fetch(code):
    url = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=gmbd&code={code}"
    req = urllib.request.Request(url, headers=HDR)
    s = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
    i, j = s.find("["), s.rfind("]")
    arr = json.loads(s[i:j + 1])
    out = {}
    for r in arr:
        d, sh = r.get("FSRQ"), r.get("QMZFE")
        if d and sh:
            out[d] = round(float(sh) / 1e8, 4)  # 亿份
    return out


if __name__ == "__main__":
    # 读取已有数据后合并，避免某次网络失败把历史季报清空
    res = {}
    if os.path.exists(OUT):
        try:
            res = json.load(open(OUT))
        except Exception:
            res = {}

    ok = 0
    for c in SZ:
        try:
            res[c] = fetch(c)
            ks = sorted(res[c])
            ok += 1
            print(f"{c}: {len(ks)} 期  {ks[0]} ~ {ks[-1]}  最新 {res[c][ks[-1]]} 亿份")
        except Exception as e:
            print(f"{c}: FAIL {e}（保留原有数据）")
        time.sleep(0.8)

    if ok == 0:
        print("全部失败，不写入文件")
        sys.exit(1)

    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"saved {OUT}（成功 {ok}/{len(SZ)}）")
