#!/usr/bin/env python3
"""核实候选 ETF 的跟踪标的（东财基金概况页）"""
import json, re, os, sys, time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CAND = {
    # 沪市：名称含 300
    "510300": "300ETF", "510310": "HS300ETF", "510320": "300中金", "510330": "华夏300",
    "510350": "工银300", "510360": "广发300", "510370": "兴业300", "510380": "国寿300",
    "510390": "平安300", "512530": "300红利", "515130": "HS300E", "515300": "红利300",
    "515310": "添富300", "515330": "天弘300", "515350": "民生300", "515360": "方正300",
    "515380": "泰康300", "515390": "HS300", "515660": "沪深300E", "516040": "现金300",
    "516830": "300ESG", "517030": "HGS300", "517300": "AH300ETF", "560180": "ESG300",
    "560330": "300价值E", "561000": "300指增", "561300": "300增ETF", "561420": "300现金",
    "561690": "质量300", "561930": "招商300", "561990": "300增强", "562070": "300ETF增",
    "562170": "300现金E", "562310": "300成长", "562320": "300价值A", "563520": "300永赢",
    "563960": "300质量",
    # 深市
    "159919": "沪深300ETF嘉实", "159925": "沪深300ETF南方", "159927": "沪深300ETF鹏华",
    "159933": "沪深300ETF国投", "159948": "沪深300ETF", "159300": "沪深300ETF富国",
    "159330": "沪深300ETF东财", "159393": "沪深300ETF万家", "159673": "沪深300ETF鹏华",
    "159238": "沪深300增强ETF景顺", "159510": "沪深300价值ETF华夏", "159523": "沪深300成长ETF华夏",
    "159656": "沪深300成长ETF万家", "159653": "ESG300ETF国联安", "159106": "民企300ETF",
}

HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def probe(code):
    url = f"https://fundf10.eastmoney.com/jbgk_{code}.html"
    try:
        req = urllib.request.Request(url, headers=HDR)
        h = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        t = re.sub(r"<[^>]+>", "|", h)
        t = re.sub(r"\|+", "|", t)
        i = t.find("跟踪标的")
        track = t[i:i + 120].split("|")[1].strip() if i > 0 else ""
        j = t.find("基金类型")
        ftype = t[j:j + 120].split("|")[1].strip() if j > 0 else ""
        k = t.find("基金规模")
        scale = t[k:k + 160].split("|")[1].strip() if k > 0 else ""
        return {"code": code, "track": track, "type": ftype, "scale": scale}
    except Exception as e:
        return {"code": code, "track": "", "type": "", "scale": "", "err": str(e)}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(probe, CAND.keys()))
    out = os.path.join(os.path.dirname(__file__), "..", "data", "etf_meta.json")
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    for r in sorted(res, key=lambda x: x["code"]):
        print(f"{r['code']} | {CAND[r['code']]:<18} | {r['track']:<16} | {r['type']:<10} | {r['scale']}")
