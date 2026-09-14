from __future__ import annotations
import argparse
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from database import Database
from lun import LUNPageSource, parse_html
from lun_browser import scrape_lun_with_browser
from telegram import send_message, format_event

def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixture")
    ap.add_argument("--max-pages", type=int, default=int(os.getenv("MAX_PAGES", "0")))
    args = ap.parse_args()

    base_url = os.getenv("LUN_URL", "https://lun.ua/sale/lviv/houses")
    page_param = os.getenv("PAGE_PARAM", "page")
    timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
    missing_required = int(os.getenv("MISSING_SCANS_REQUIRED", "3"))

    db = Database()
    scan_id = uuid.uuid4().hex[:12]
    db.start_scan(scan_id)

    all_listings = []
    pages = 0
    errors = 0

    if args.fixture:
        html = Path(args.fixture).read_text(encoding="utf-8", errors="ignore")
        listings, total = parse_html(html)
        all_listings.extend(listings)
        pages = 1
        print(f"fixture: {len(listings)} listings; reported total={total}")
    else:
        try:
            all_listings, total = __import__("asyncio").run(
                scrape_lun_with_browser(
                    base_url,
                    max_pages=args.max_pages,
                )
            )
            pages = max(1, (len(all_listings) + 23) // 24) if all_listings else 0
        except Exception as exc:
            errors += 1
            print(f"LUN browser ERROR: {exc}")

    seen_ids = set()
    baseline = True
    events = []

    for listing in all_listings:
        sid = listing["source_id"]
        seen_ids.add(sid)
        old = db.upsert_observation(scan_id, listing)

        if old is None:
            events.append(("new", listing))
            baseline = False
        elif old["status"] == "gone":
            events.append(("new", listing))
            baseline = False
        elif old["price"] != listing.get("price") or old["currency"] != listing.get("currency"):
            events.append(("price", listing))
            baseline = False

    # Only perform missing detection after we have a meaningful complete-ish scan.
    gone = db.mark_missing("lun", seen_ids, missing_required)
    for row in gone:
        events.append(("gone", dict(row)))

    # If this is the very first scan, suppress Telegram event spam.
    if baseline:
        events = []

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not args.dry_run and token and chat_id:
        for kind, listing in events:
            send_message(token, chat_id, format_event(kind, listing))

    db.finish_scan(scan_id, pages, len(all_listings), errors, baseline)

    detached = sum(x.get("classification") == "detached" for x in all_listings)
    excluded = sum(x.get("classification") == "excluded" for x in all_listings)
    uncertain = sum(x.get("classification") == "uncertain" for x in all_listings)

    print(
        f"scan={scan_id} found={len(all_listings)} "
        f"detached={detached} excluded={excluded} uncertain={uncertain} "
        f"events={len(events)} baseline={baseline}"
    )

if __name__ == "__main__":
    main()
