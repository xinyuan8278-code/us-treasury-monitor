# -*- coding: utf-8 -*-
"""
抓取美国财政部 Daily Treasury Par Yield Curve Rates (CMT)，生成站点数据层 data.js。

数据源（不变）：https://home.treasury.gov/resource-center/data-chart-center/interest-rates
    type=daily_treasury_yield_curve，官方 CSV 视图

产物（结构不变）：data.js → window.TREASURY_DATA = { meta, latest, history }

用法：
    python fetch_us_treasury.py                 # 抓当年（必要时补上年）并写 data.js
    python fetch_us_treasury.py --keep-baseline # 仅校验，不覆盖 data.js

只用标准库，无第三方依赖。
"""

import argparse
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)

OUT_PATH = "data.js"

# 站点上的收款期限（与页面一致：5Y / 10Y / 20Y）
COL_5Y = "5 Yr"
COL_10Y = "10 Yr"
COL_20Y = "20 Yr"

HISTORY_LEN = 60  # 页面图表展示的近 60 个交易日

SCHEDULE_TEXT = "每周一、周三、周五 09:30（北京时间）自动更新"


def beijing_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def fetch_year(year: int) -> list:
    """抓取某一年的日频收益率，返回 [(date, {5y,10y,20y})]，按日期升序。"""
    url = CSV_URL.format(year=year)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; us-treasury-monitor/1.0)",
            "Accept": "text/csv,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(raw))
    rows = []
    for r in reader:
        date_s = (r.get("Date") or "").strip()
        if not date_s:
            continue
        try:
            d = datetime.strptime(date_s, "%m/%d/%Y").date()
        except ValueError:
            continue
        vals = {}
        ok = True
        for key, col in (("y5", COL_5Y), ("y10", COL_10Y), ("y20", COL_20Y)):
            cell = (r.get(col) or "").strip()
            if cell in ("", "N/A"):
                ok = False
                break
            vals[key] = round(float(cell), 2)
        if ok:
            rows.append((d, vals))
    rows.sort(key=lambda x: x[0])
    return rows


def load_rows() -> list:
    now = beijing_now()
    rows = []
    try:
        rows = fetch_year(now.year)
    except Exception as e:  # 当年文件在极早期可能为空
        print(f"提示：抓取 {now.year} 年数据失败（{e}），尝试上一年", file=sys.stderr)
    if len(rows) < HISTORY_LEN:
        try:
            prev = fetch_year(now.year - 1)
            merged = {d: v for d, v in prev}
            merged.update({d: v for d, v in rows})
            rows = sorted(merged.items(), key=lambda x: x[0])
        except Exception as e:
            print(f"提示：补抓上一年失败（{e}）", file=sys.stderr)
    return [{"date": d, "y5": v["y5"], "y10": v["y10"], "y20": v["y20"]} for d, v in rows]


def bp(a: float, b: float) -> int:
    """a - b，换算为整数 bp。"""
    return int(round((a - b) * 100))


def build_payload(rows: list) -> dict:
    if len(rows) < 6:
        raise RuntimeError(f"可用交易日不足（{len(rows)}），无法计算 5 日前对比")

    window = rows[-HISTORY_LEN:]
    history = [
        {
            "date": r["date"].isoformat(),
            "y5": r["y5"],
            "y10": r["y10"],
            "y20": r["y20"],
            "spread": bp(r["y20"], r["y10"]),  # 20Y-10Y，单位 bp
        }
        for r in window
    ]

    cur = window[-1]
    prev = window[-2]
    five = window[-6]

    spread = bp(cur["y20"], cur["y10"])
    spread10_5 = bp(cur["y10"], cur["y5"])
    spread20_5 = bp(cur["y20"], cur["y5"])

    latest = {
        "date": cur["date"].isoformat(),
        "y5": cur["y5"],
        "y10": cur["y10"],
        "y20": cur["y20"],
        "spreadBp": spread,
        "spread10_5Bp": spread10_5,
        "spread20_5Bp": spread20_5,
        "dY5Bp": bp(cur["y5"], prev["y5"]),
        "dY10Bp": bp(cur["y10"], prev["y10"]),
        "dY20Bp": bp(cur["y20"], prev["y20"]),
        "dSpreadBp": spread - bp(prev["y20"], prev["y10"]),
        "dSpread10_5Bp": spread10_5 - bp(prev["y10"], prev["y5"]),
        "dSpread20_5Bp": spread20_5 - bp(prev["y20"], prev["y5"]),
        "w5Y5Bp": bp(cur["y5"], five["y5"]),
        "w5Y10Bp": bp(cur["y10"], five["y10"]),
        "w5Y20Bp": bp(cur["y20"], five["y20"]),
        "w5SpreadBp": spread - bp(five["y20"], five["y10"]),
        "prevDate": prev["date"].isoformat(),
        "fiveAgoDate": five["date"].isoformat(),
    }

    meta = {
        "title": "美债 5Y / 10Y / 20Y 收益率监控",
        "subtitle": "固收投资经理 · 每日监控仪表盘",
        "sourceName": "U.S. Department of the Treasury — Daily Treasury Par Yield Curve Rates (CMT)",
        "sourceUrl": (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            f"TextView?type=daily_treasury_yield_curve&field_tdr_date_value={cur['date'].year}"
        ),
        "generatedAt": beijing_now().strftime("%Y-%m-%d %H:%M"),
        "schedule": SCHEDULE_TEXT,
        "unit": "percent",
        "spreadUnit": "bp",
    }

    return {"meta": meta, "latest": latest, "history": history}


def render(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return "/* 由 fetch_us_treasury.py 自动生成，请勿手工编辑 */\nwindow.TREASURY_DATA = " + body + ";\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-baseline", action="store_true", help="只校验不写文件")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    rows = load_rows()
    print(f"拿到 {len(rows)} 个交易日，最新 {rows[-1]['date']}")
    payload = build_payload(rows)
    text = render(payload)
    print(f"最新交易日 {payload['latest']['date']}："
          f"5Y {payload['latest']['y5']}% 10Y {payload['latest']['y10']}% 20Y {payload['latest']['y20']}% "
          f"（20Y-10Y {payload['latest']['spreadBp']} bp）")

    if args.keep_baseline:
        print("仅校验模式，未写文件")
        return
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"已写入 {args.out}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
