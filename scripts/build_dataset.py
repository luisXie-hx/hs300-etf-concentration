#!/usr/bin/env python3
"""合并沪市日频 + 深市季报(锚点插值)，计算头部4只沪深300ETF份额占比

数据口径：
- 沪市：上交所每日披露的 ETF 总份额（TOT_VOL），真实日频值
- 深市：交易所不提供历史日频，使用基金季报"期末总份额"作为锚点，
        锚点之间按交易日线性插值；最后一个锚点为当日实时份额快照
"""
import json, os, datetime as dt
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

SH = {
    "510300": "华泰柏瑞沪深300ETF", "510310": "易方达沪深300ETF", "510320": "中金沪深300ETF",
    "510330": "华夏沪深300ETF", "510350": "工银瑞信沪深300ETF", "510360": "广发沪深300ETF",
    "510370": "兴业沪深300ETF", "510380": "国寿安保沪深300ETF", "510390": "平安沪深300ETF",
    "515130": "博时沪深300ETF", "515310": "汇添富沪深300ETF", "515330": "天弘沪深300ETF",
    "515350": "民生加银沪深300ETF", "515360": "方正富邦沪深300ETF", "515380": "泰康沪深300ETF",
    "515390": "华安沪深300ETF", "515660": "国泰沪深300ETF", "561930": "招商沪深300ETF",
    "563520": "永赢沪深300ETF",
}
SZ = {
    "159919": "嘉实沪深300ETF", "159925": "南方沪深300ETF", "159300": "富国沪深300ETF",
    "159330": "东财沪深300ETF", "159393": "万家沪深300ETF", "159673": "鹏华沪深300ETF",
}
TOP4 = ["510300", "510310", "510330", "159919"]


def load():
    sse = json.load(open(os.path.join(DATA, "sse_shares.json")))
    szq = json.load(open(os.path.join(DATA, "sz_quarterly.json")))
    snap = {}
    p = os.path.join(DATA, "snapshot.json")
    if os.path.exists(p):
        snap = json.load(open(p))
    return sse, szq, snap


def clean_dates(sse):
    """丢弃交易所尚未披露的最后一个交易日（空数据，或与前一交易日完全相同）"""
    ds = sorted(sse)
    while len(ds) >= 2:
        if not sse[ds[-1]]:
            ds.pop()
            continue
        a, b = sse[ds[-1]], sse[ds[-2]]
        common = set(a) & set(b)
        if common and all(abs(a[k] - b[k]) < 1e-6 for k in common):
            ds.pop()
        else:
            break
    return ds


def sz_series(anchors, dates):
    """锚点间按交易日线性插值"""
    pts = sorted((d, float(v)) for d, v in anchors.items())
    if not pts:
        return {}
    out = {}
    for d in dates:
        if d < pts[0][0]:
            continue
        prev = pts[0]
        nxt = None
        for p in pts:
            if p[0] <= d:
                prev = p
            else:
                nxt = p
                break
        if nxt is None:
            out[d] = prev[1]
            continue
        # 在 prev 与 nxt 之间按自然日占比插值
        d0 = dt.date.fromisoformat(prev[0])
        d1 = dt.date.fromisoformat(nxt[0])
        dx = dt.date.fromisoformat(d)
        w = (dx - d0).days / max((d1 - d0).days, 1)
        out[d] = round(prev[1] + (nxt[1] - prev[1]) * w, 4)
    return out


def main():
    sse, szq, snap = load()
    dates = clean_dates(sse)
    last = dates[-1]

    # 深市锚点：季报 + 历史日频快照 + 当日快照
    hist_path = os.path.join(DATA, "sz_snapshots.json")
    szsnap = json.load(open(hist_path)) if os.path.exists(hist_path) else {}

    sz_daily = {}
    for code, series in szq.items():
        anchors = {d: v for d, v in series.items() if d <= last}
        for d, vals in szsnap.items():
            if d <= last and vals.get(code):
                anchors[d] = vals[code]
        if snap.get(code):
            anchors[last] = snap[code]
        sz_daily[code] = sz_series(anchors, dates)

    rows = []
    for d in dates:
        per = {}
        total = 0.0
        for code in SH:
            v = sse[d].get(code)
            if v is None:
                continue
            x = round(v / 1e4, 4)
            per[code] = x
            total += x
        for code in SZ:
            x = sz_daily.get(code, {}).get(d)
            if x is None:
                continue
            per[code] = x
            total += x
        top = sum(per.get(c, 0) for c in TOP4)
        sh_total = sum(per.get(c, 0) for c in SH)
        sh_top = sum(per.get(c, 0) for c in ["510300", "510310", "510330"])
        rows.append({
            "date": d,
            "top4": round(top, 3),
            "total": round(total, 3),
            "ratio": round(top / total * 100, 3) if total else None,
            "ratio_sh": round(sh_top / sh_total * 100, 3) if sh_total else None,
            "sh_total": round(sh_total, 3),
            "sz_total": round(total - sh_total, 3),
            "per": per,
        })

    out = {
        "meta": {
            "generated": dt.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M"),
            "range": [rows[0]["date"], rows[-1]["date"]],
            "days": len(rows),
            "top4": [{"code": c, "name": SH.get(c) or SZ.get(c)} for c in TOP4],
            "sh": [{"code": c, "name": n} for c, n in SH.items()],
            "sz": [{"code": c, "name": n} for c, n in SZ.items()],
            "note": "沪市为交易所每日披露份额（真实日频）；深市为基金季报期末份额锚点间按交易日线性插值，"
                    "末端锚点为当日实时快照。份额单位：亿份。",
        },
        "rows": rows,
    }
    json.dump(out, open(os.path.join(DATA, "dashboard.json"), "w"), ensure_ascii=False)
    print(f"rows={len(rows)} {rows[0]['date']} ~ {rows[-1]['date']}")
    step = max(1, len(rows) // 14)
    for r in rows[::step] + [rows[-1]]:
        print(f"  {r['date']}  top4={r['top4']:7.1f} total={r['total']:7.1f} "
              f"ratio={r['ratio']:5.2f}%  sh_ratio={r['ratio_sh']:5.2f}%")


if __name__ == "__main__":
    main()
