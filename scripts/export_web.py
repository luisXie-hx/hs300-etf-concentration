#!/usr/bin/env python3
"""把数据集导出为前端可直接 <script> 加载的 data.js"""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

d = json.load(open(os.path.join(DATA, "dashboard.json")))
idx = json.load(open(os.path.join(DATA, "hs300.json")))
rows = d["rows"]
meta = d["meta"]

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
    "latest": rows[-1],
    "prev": rows[-2],
}
js = "window.DASH=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
open(os.path.join(BASE, "data.js"), "w").write(js)
print("data.js", len(js), "bytes, days=", len(rows))
print("codes", len(codes))
