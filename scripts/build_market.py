#!/usr/bin/env python3
"""由原始数据计算大盘状态指标

维度：量能 / 价格位置 / 趋势 / 资金（两融） / 波动
输出 data/market.json 供前端渲染
"""
import json, os, math
from statistics import mean, pstdev

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")


def pct_rank(series, v):
    """v 在 series 中的百分位（0-100）"""
    if not series or v is None:
        return None
    n = sum(1 for x in series if x <= v)
    return round(n / len(series) * 100, 1)


def ma(arr, n):
    if len(arr) < n:
        return None
    return sum(arr[-n:]) / n


def main():
    raw = json.load(open(os.path.join(DATA, "market_raw.json")))
    hs = raw["index"]["hs300"]["series"]
    sse = raw["index"]["sse"]["series"]
    szse = raw["index"]["szse"]["series"]
    dates = sorted(hs)

    closes = [hs[d]["close"] for d in dates]
    turnover_raw = raw.get("turnover") or {}
    margin = raw.get("margin") or {}

    rows = []
    for i, d in enumerate(dates):
        c = closes[i]
        t = turnover_raw.get(d)
        turnover = round(t / 1e8, 1) if t else None
        m = margin.get(d)
        # 两市成交量（亿手）：腾讯成交量单位为手
        v_sse = sse.get(d, {}).get("vol")
        v_szse = szse.get(d, {}).get("vol")
        volume = round((v_sse + v_szse) / 1e8, 3) if (v_sse and v_szse) else None
        rows.append({
            "date": d,
            "close": round(c, 2),
            "turnover": turnover,
            "volume": volume,
            "margin": round(m["total"] / 1e8, 1) if m else None,
            "margin_fin": round(m["fin"] / 1e8, 1) if m else None,
        })

    # 20 日均成交额
    tvals = [r["turnover"] for r in rows]
    for i, r in enumerate(rows):
        seg = [x for x in tvals[max(0, i - 19):i + 1] if x]
        r["turnover_ma20"] = round(mean(seg), 1) if len(seg) >= 10 else None

    # 逐日派生：波动率、各指标 5 年滚动分位、情绪温度
    def roll_vol(i):
        if i < 20:
            return None
        seg = [closes[j] / closes[j - 1] - 1 for j in range(i - 19, i + 1)]
        return round(pstdev(seg) * math.sqrt(252) * 100, 2)

    tma_hist, m_hist, v_hist = [], [], []
    for i, r in enumerate(rows):
        r["vol20"] = roll_vol(i)

        if r["turnover_ma20"]:
            tma_hist.append(r["turnover_ma20"])
            r["tma_pct"] = pct_rank(tma_hist, r["turnover_ma20"])
        else:
            r["tma_pct"] = None

        if r["margin"]:
            m_hist.append(r["margin"])
            r["margin_pct"] = pct_rank(m_hist, r["margin"])
        else:
            r["margin_pct"] = None

        if r["vol20"]:
            v_hist.append(r["vol20"])
            r["vol_pct"] = pct_rank(v_hist, r["vol20"])
        else:
            r["vol_pct"] = None

        r["ret20"] = round((closes[i] / closes[i - 20] - 1) * 100, 2) if i >= 20 else None

        # 情绪温度：量能 40% + 杠杆 30% + 波动 30%（波动反向，越平静越偏热）
        parts = []
        if r["tma_pct"] is not None:
            parts.append((r["tma_pct"], 0.4))
        if r["margin_pct"] is not None:
            parts.append((r["margin_pct"], 0.3))
        if r["vol_pct"] is not None:
            parts.append((100 - r["vol_pct"], 0.3))
        if parts:
            w = sum(p[1] for p in parts)
            r["temp"] = round(sum(p[0] * p[1] for p in parts) / w, 1)
        else:
            r["temp"] = None

    # 以"最后一个各指标齐全"的交易日为基准（成交额/两融披露晚于指数）
    idx = max((i for i, r in enumerate(rows)
               if r["turnover"] is not None and r["margin"] is not None),
              default=len(rows) - 1)
    last = rows[idx]

    # ---- 量能 ----
    tma_series = [r["turnover_ma20"] for r in rows[:idx + 1] if r["turnover_ma20"]]
    cur_tma = last["turnover_ma20"]
    tma_pct = pct_rank(tma_series, cur_tma) if cur_tma else None

    # ---- 价格 ----
    ma20 = ma(closes, 20)
    ma60 = ma(closes, 60)
    hi250 = max(closes[max(0, idx - 249):idx + 1])
    drawdown = (last["close"] / hi250 - 1) * 100
    ret20 = (last["close"] / closes[idx - 20] - 1) * 100 if idx >= 20 else None
    ret5 = (last["close"] / closes[idx - 5] - 1) * 100 if idx >= 5 else None

    # ---- 波动 ----
    rets = []
    for i in range(max(1, idx - 19), idx + 1):
        rets.append(closes[i] / closes[i - 1] - 1)
    vol20 = pstdev(rets) * math.sqrt(252) * 100 if len(rets) >= 10 else None
    vol_series = []
    for i in range(60, idx + 1):
        seg = [closes[j] / closes[j - 1] - 1 for j in range(i - 19, i + 1)]
        vol_series.append(pstdev(seg) * math.sqrt(252) * 100)
    vol_pct = pct_rank(vol_series, vol20) if vol20 else None

    # ---- 两融 ----
    mvals = [r["margin"] for r in rows if r["margin"]]
    cur_m = last["margin"]
    m_pct = pct_rank(mvals, cur_m) if cur_m else None
    m_chg5 = None
    if cur_m and idx >= 5 and rows[idx - 5]["margin"]:
        m_chg5 = cur_m - rows[idx - 5]["margin"]
    m_chg20 = None
    if cur_m and idx >= 20 and rows[idx - 20]["margin"]:
        m_chg20 = cur_m - rows[idx - 20]["margin"]

    # ---- 状态合成 ----
    if tma_pct is not None:
        vol_state = "放量" if tma_pct >= 70 else ("缩量" if tma_pct <= 30 else "量能中性")
    else:
        vol_state = "量能未知"

    if ret20 is not None:
        if ret20 >= 3:
            price_state = "上涨"
        elif ret20 <= -3:
            price_state = "下跌"
        else:
            price_state = "震荡"
    else:
        price_state = "震荡"

    if ma20 and ma60:
        if last["close"] > ma20 > ma60:
            trend = "多头排列"
        elif last["close"] < ma20 < ma60:
            trend = "空头排列"
        else:
            trend = "均线缠绕"
    else:
        trend = "—"

    if drawdown >= -5:
        pos = "接近高位"
    elif drawdown >= -15:
        pos = "中位回调"
    else:
        pos = "深度回撤"

    headline = f"{vol_state} · {price_state} · {pos}"

    out = {
        "meta": {
            "date": last["date"],
            "generated": raw.get("generated") or "",
            "turnover_src": raw.get("turnover_src"),
            "turnover_days": len([r for r in rows if r["turnover"]]),
            "note": "指数、两融、成交额均为完整 5 年日频；成交额采用沪市+深市全市场口径。"
        },
        "headline": headline,
        "state": {
            "vol": vol_state, "price": price_state, "trend": trend, "pos": pos
        },
        "cards": {
            "turnover": {
                "label": "两市成交额（20日均）",
                "value": round(cur_tma, 0) if cur_tma else None,
                "unit": "亿元",
                "pct": tma_pct,
                "sub": f"当日 {last['turnover']:.0f} 亿" if last["turnover"] else "—"
            },
            "index": {
                "label": "沪深300",
                "value": last["close"],
                "unit": "",
                "pct": None,
                "sub": f"20日 {ret20:+.2f}%" if ret20 is not None else "—"
            },
            "drawdown": {
                "label": "距250日高点",
                "value": round(drawdown, 1),
                "unit": "%",
                "pct": None,
                "sub": f"高点 {hi250:.0f}"
            },
            "trend": {
                "label": "均线位置",
                "value": trend,
                "unit": "",
                "pct": None,
                "sub": f"MA20 {ma20:.0f} / MA60 {ma60:.0f}" if ma20 and ma60 else "—"
            },
            "margin": {
                "label": "两融余额",
                "value": cur_m,
                "unit": "亿元",
                "pct": m_pct,
                "sub": f"5日 {m_chg5:+.0f} 亿" if m_chg5 is not None else "—"
            },
            "vol20": {
                "label": "20日年化波动率",
                "value": round(vol20, 1) if vol20 else None,
                "unit": "%",
                "pct": vol_pct,
                "sub": "历史分位 " + (f"{vol_pct:.0f}%" if vol_pct else "—")
            },
            "temp": {
                "label": "情绪温度",
                "value": last.get("temp"),
                "unit": "/100",
                "pct": last.get("temp"),
                "sub": "量能40% + 杠杆30% + 波动30%"
            }
        },
        "sentiment": {
            "temp": last.get("temp"),
            "turnover_pct": last.get("tma_pct"),
            "margin_pct": last.get("margin_pct"),
            "vol_pct": last.get("vol_pct"),
            "turnover_ma20": last.get("turnover_ma20"),
            "turnover": last.get("turnover"),
            "margin": last.get("margin"),
            "vol20": last.get("vol20"),
        },
        "rows": rows,
    }

    json.dump(out, open(os.path.join(DATA, "market.json"), "w"), ensure_ascii=False)
    js = "window.MARKET=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(os.path.join(BASE, "market_data.js"), "w").write(js)
    print("状态:", headline)
    print("趋势:", trend, "| 回撤:", f"{drawdown:.1f}%", "| 波动:", f"{vol20:.1f}%")
    print("量能分位:", tma_pct, "| 两融:", cur_m, "亿 (分位", m_pct, ")")
    print("rows:", len(rows))


if __name__ == "__main__":
    main()
