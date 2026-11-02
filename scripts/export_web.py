#!/usr/bin/env python3
"""把数据集导出为前端可直接 <script> 加载的 data.js"""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

d = json.load(open(os.path.join(DATA, "dashboard.json")))
idx = json.load(open(os.path.join(DATA, "hs300.json")))
rows = d["rows"]
meta = d["meta"]

# 情绪序列（可选：market.json 不存在时前端自动隐藏情绪面板）
mp = os.path.join(DATA, "market.json")
mk = {}
sent = {}
if os.path.exists(mp):
    m = json.load(open(mp))
    mk = {r["date"]: r for r in m.get("rows", [])}
    sent = m.get("sentiment", {}) or {}

def col(key):
    return [mk.get(r["date"], {}).get(key) for r in rows]

codes = [x["code"] for x in meta["top4"]] + \
        [x["code"] for x in meta["sh"] if x["code"] not in [y["code"] for y in meta["top4"]]] + \
        [x["code"] for x in meta["sz"] if x["code"] not in [y["code"] for y in meta["top4"]]]
codes = list(dict.fromkeys(codes))

out = {
    "meta": meta,
    "dates": [r["date"] for r in rows],
    "ratio": [r["ratio"] for r in rows],
    "ratioSh": [r["ratio_sh"] for r in rows],
    "top4": [r["top4"] for r in rows],
    "total": [r["total"] for r in rows],
    "shTotal": [r["sh_total"] for r in rows],
    "szTotal": [r["sz_total"] for r in rows],
    "idx": [idx.get(r["date"]) for r in rows],
    "series": {c: [r["per"].get(c) for r in rows] for c in codes},
    "turnover": col("turnover"),
    "turnoverMa20": col("turnover_ma20"),
    "tmaPct": col("tma_pct"),
    "margin": col("margin"),
    "marginPct": col("margin_pct"),
    "vol20": col("vol20"),
    "volPct": col("vol_pct"),
    "temp": col("temp"),
    "sentiment": sent,
    "latest": rows[-1],
    "prev": rows[-2],
}
# 长期收益对比：沪深300全收益 vs 中证债券型基金（归一化 1000）
tri = None
tp = os.path.join(DATA, "tri.json")
if os.path.exists(tp):
    t = json.load(open(tp))
    s = t.get("series") or {}
    a, b = s.get("hs300tri") or {}, s.get("bondfund") or {}
    if a and b:
        keys = sorted(set(a) & set(b))
        base = "2019-01-02"
        if base not in a:
            base = keys[0]
        ba, bb = a[base], b[base]
        show = [k for k in keys if k >= base]
        # 分年度收益：每年最后交易日 vs 上一年最后交易日
        import collections
        years = collections.OrderedDict()
        for k in keys:
            years.setdefault(k[:4], []).append(k)
        yearly = []
        prev_a = prev_b = None
        for y, ds in years.items():
            last = ds[-1]
            if prev_a is None:
                ra = rb = None
            else:
                ra = round((a[last] / prev_a - 1) * 100, 2)
                rb = round((b[last] / prev_b - 1) * 100, 2)
            if y >= base[:4]:
                yearly.append({"y": y, "hs": ra, "bond": rb})
            prev_a, prev_b = a[last], b[last]
        tri = {
            "base": base,
            "dates": show,
            "hs": [round(a[k] / ba * 1000, 1) for k in show],
            "bond": [round(b[k] / bb * 1000, 1) for k in show],
            "yearly": yearly,
            "meta": t.get("meta") or {},
            "updated": t.get("updated"),
        }
        out["tri"] = tri

js = "window.DASH=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
open(os.path.join(BASE, "data.js"), "w").write(js)
print("data.js", len(js), "bytes, days=", len(rows))
print("codes", len(codes))
print("情绪序列:", "有" if any(out["turnover"]) else "无", "| 温度", sent.get("temp"))
if tri:
    print("长期对比:", len(tri["dates"]), "天", tri["dates"][0], "~", tri["dates"][-1],
          "| 沪深300全收益", tri["hs"][-1], "| 债基", tri["bond"][-1])
else:
    print("长期对比: 无")
