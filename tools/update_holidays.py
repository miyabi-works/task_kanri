"""Refresh the embedded Japanese holiday data from the Cabinet Office CSV.

Run: python3 tools/update_holidays.py
For an already downloaded CSV: python3 tools/update_holidays.py --csv PATH
Only the JP_HOLIDAY_DATA block in index.html is replaced. No task data is read.
"""

import argparse
import csv
import datetime as dt
import io
import json
from pathlib import Path
import re
import urllib.request

SOURCE_URL = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
START = "// BEGIN OFFICIAL JAPAN HOLIDAYS"
END = "// END OFFICIAL JAPAN HOLIDAYS"


def parse_csv(raw):
    rows = list(csv.reader(io.StringIO(raw.decode("cp932"))))
    if not rows or rows[0] != ["国民の祝日・休日月日", "国民の祝日・休日名称"]:
        raise ValueError("Unexpected official CSV header")
    holidays = []
    for row in rows[1:]:
        if not row:
            continue
        if len(row) != 2 or not row[1].strip():
            raise ValueError("Invalid holiday row")
        day = dt.datetime.strptime(row[0], "%Y/%m/%d").date().isoformat()
        if holidays and day <= holidays[-1][0]:
            raise ValueError("Holiday dates must be unique and ascending")
        holidays.append([day, row[1].strip()])
    if not holidays or holidays[0][0][:4] != "1955":
        raise ValueError("Official historical coverage is missing")
    last_year = int(holidays[-1][0][:4])
    for year in range(1955, last_year + 1):
        count = sum(day.startswith(str(year) + "-") for day, _ in holidays)
        if not 8 <= count <= 25:
            raise ValueError(f"Incomplete or unexpected holiday data for {year}")
    return holidays


def update_html(html, holidays):
    pattern = re.compile(re.escape(START) + r"[\s\S]*?" + re.escape(END))
    if len(pattern.findall(html)) != 1:
        raise ValueError("Expected exactly one holiday data block")
    old = pattern.search(html).group()
    old_last_year = re.search(r'lastYear: (\d+)', old)
    if old_last_year and int(holidays[-1][0][:4]) < int(old_last_year[1]):
        raise ValueError("Refusing to reduce published holiday coverage")
    entries = ",\n".join("    " + json.dumps(row, ensure_ascii=False).replace("<", "\\u003c") for row in holidays)
    block = (f"{START}\n"
             f"// 出典: {SOURCE_URL}（公表済みの日付を使用。推定計算はしない）\n"
             "const JP_HOLIDAY_DATA = {\n"
             f"  firstYear: {int(holidays[0][0][:4])},\n"
             f"  lastYear: {int(holidays[-1][0][:4])},\n"
             f"  days: [\n{entries}\n  ]\n}};\n{END}")
    return pattern.sub(lambda _: block, html)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    raw = args.csv.read_bytes() if args.csv else urllib.request.urlopen(SOURCE_URL, timeout=30).read()
    holidays = parse_csv(raw)
    html_path = Path(__file__).resolve().parents[1] / "index.html"
    html = html_path.read_text(encoding="utf-8")
    updated = update_html(html, holidays)
    if updated != html:
        html_path.write_text(updated, encoding="utf-8")
    print(f"Official holidays: {holidays[0][0][:4]}–{holidays[-1][0][:4]}, {len(holidays)} dates")


if __name__ == "__main__":
    main()
