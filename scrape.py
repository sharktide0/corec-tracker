"""One check of the CoRec Upper/Lower Gym counts. Appends to docs/log.csv."""
import csv, html, os, re
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

URL = "https://www.purdue.edu/recwell/facility-usage/"
AREAS = ["Upper Gym", "Lower Gym"]
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "log.csv")

BLOCK_RE = re.compile(r'<h5 class="rw-c2c-feed__location--name">(.*?)</h5>(.*?)(?=<div class="rw-c2c-feed__location">|$)', re.S)
CAP_RE = re.compile(r"Capacity:\s*(\d+)\s*/\s*(\d+)\s*//\s*(\d+)%")
UPD_RE = re.compile(r"Last Updated:\s*([^<]+)")


def parse(page_html):
    out = {}
    for name, body in BLOCK_RE.findall(page_html):
        name = html.unescape(name).strip()
        if name not in AREAS:
            continue
        if "Closed Now" in body:
            out[name] = None
            continue
        m = CAP_RE.search(body)
        u = UPD_RE.search(body)
        if m:
            out[name] = (int(m.group(1)), int(m.group(2)), int(m.group(3)), u.group(1).strip() if u else "")
    return out


def site_time(upd, now):
    """'Nov-07 03:32pm' -> '2026-11-07T15:32' (year from now, handles Dec->Jan)."""
    try:
        t = datetime.strptime(f"{now.year} {upd}", "%Y %b-%d %I:%M%p")
        if t.month == 12 and now.month == 1:
            t = t.replace(year=now.year - 1)
        return t.strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return now.strftime("%Y-%m-%dT%H:%M")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36")
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_selector(".rw-c2c-feed__location--name", timeout=90000)
        data = parse(page.content())
        b.close()

    now = datetime.now(ZoneInfo("America/New_York"))
    stamp = now.strftime("%Y-%m-%dT%H:%M")

    # last site_updated already logged for each area
    seen = {}
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            for r in csv.DictReader(f):
                seen[r["area"]] = r["site_updated"]

    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["updated_at", "area", "count", "capacity", "pct", "site_updated", "checked_at"])
        for a in AREAS:
            d = data.get(a)
            if not d:
                print(a, "closed or missing")
                continue
            count, cap, pct, upd = d
            if seen.get(a) == upd:
                print(a, "no new update from Purdue, skipped")
                continue
            w.writerow([site_time(upd, now), a, count, cap, pct, upd, stamp])
            print(a, d)


if __name__ == "__main__":
    main()
