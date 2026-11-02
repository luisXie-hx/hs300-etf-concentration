#!/usr/bin/env python3
"""抓取「沪深300全收益 vs 债券基金」长期收益对比序列

数据源：
- 沪深300全收益指数 H00300.CSI：中证指数官网 index-perf 接口（免费日频）
- 中证债券型基金指数 H11023：同上

说明：
- 中证官网有 WAF 限流，连续请求会返回 403，故带指数退避重试；
  全部重试失败时沿用 data/tri.json 已有序列，不破坏历史数据。
- 中证接口对节假日会返回"前一交易日收盘价但日期记为节假日"的伪数据，
  因此以东方财富 000300 日线的真实交易日集合为日历做过滤。
"""
import json, os, time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(DATA, "tri.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

START = "2018-01-01"
END = "2035-12-31"

# 展示名 / 中证代码 / 颜色由前端决定，这里只存代码与序列
SERIES = {
    "hs300tri": {"code": "H00300", "name": "沪深300全收益"},
    "bondfund": {"code": "H11023", "name": "中证债券型基金"},
}


def _get(url, headers, timeout=30, retry=5, backoff=(4, 10, 25, 45, 70)):
    """带指数退避的 GET；中证 WAF 限流时 403，需要等待后重试"""
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            if i < retry - 1:
                time.sleep(backoff[min(i, len(backoff) - 1)])
    print(f"    FAIL {last}")
    return None


def parse_date(dt):
    """中证接口的 tradeDate 格式不统一：可能是 20180102 / 2018-01-02 / 2018-1-2"""
    if not dt:
        return None
    s = str(dt).strip()
    if "-" in s:
        p = [x for x in s.split("-") if x != ""]
        if len(p) != 3:
            return None
        y, m, d = p
    else:
        s = s.replace("/", "")
        if len(s) != 8:
            return None
        y, m, d = s[:4], s[4:6], s[6:8]
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def fetch_csi(code):
    """中证指数官网日线：返回 {YYYY-MM-DD: close}"""
    u = ("https://www.csindex.com.cn/csindex-home/perf/index-perf?"
         f"indexCode={code}&startDate={START}&endDate={END}")
    raw = _get(u, {
        "User-Agent": UA,
        "Referer": "https://www.csindex.com.cn/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except Exception:
        return None
    if d.get("code") != "200":
        print(f"    {code} 返回 {d.get('code')} {d.get('msg')}")
        return None
    out = {}
    for x in d.get("data") or []:
        key, c = parse_date(x.get("tradeDate")), x.get("close")
        if not key or c is None:
            continue
        out[key] = float(c)
    return out or None


def clean(d):
    """中证接口会把「请求起始日之前最后一个收盘」当作第一条返回，
    日期标成 startDate、数值与真正的首个交易日相同。这里剔除这条伪数据，
    并兜底过滤周末（接口正常时不产生）。"""
    if not d:
        return d
    import datetime as _dt
    ks = sorted(d)
    if len(ks) >= 2 and d[ks[0]] == d[ks[1]]:
        d.pop(ks[0], None)
    return {k: v for k, v in d.items()
            if _dt.date(*map(int, k.split("-"))).weekday() < 5}


def main():
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT)).get("series") or {}
        except Exception:
            prev = {}

    series = {}
    for key, info in SERIES.items():
        d = fetch_csi(info["code"])
        if not d:
            if prev.get(key):
                print(f"{info['name']}: 抓取失败，沿用已有 {len(prev[key])} 天")
                series[key] = prev[key]
            else:
                print(f"{info['name']}: 抓取失败且无历史数据")
            continue
        filtered = clean(d)
        if not filtered:
            print(f"{info['name']}: 过滤后为空，沿用已有数据")
            if prev.get(key):
                series[key] = prev[key]
            continue
        ks = sorted(filtered)
        print(f"{info['name']}({info['code']}): {len(filtered)} 天  "
              f"{ks[0]} ~ {ks[-1]}  最新 {filtered[ks[-1]]}")
        series[key] = filtered
        time.sleep(2.0)

    if not series:
        print("全部失败，不写文件")
        return

    # 只保留两条序列都有的日期，避免前端错位
    if len(series) == 2:
        common = set(series["hs300tri"]) & set(series["bondfund"])
        if common:
            for k in series:
                series[k] = {d: v for d, v in series[k].items() if d in common}
            print(f"对齐后共同交易日: {len(common)} 天")

    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "meta": {
            "hs300tri": {"code": "H00300", "name": "沪深300全收益指数",
                         "note": "中证指数官网，含分红再投"},
            "bondfund": {"code": "H11023", "name": "中证债券型基金指数",
                         "note": "Wind 885007（混合债券型二级）的免费替代，口径更宽，含纯债基金"},
        },
        "series": series,
    }
    json.dump(out, open(OUT, "w"), ensure_ascii=False)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
