from __future__ import annotations

import asyncio
from typing import Callable

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from lun import parse_html

async def scrape_lun_with_browser(
    url: str,
    max_pages: int = 0,
    timeout_ms: int = 45_000,
    on_page: Callable[[int, list[dict], int], None] | None = None,
) -> tuple[list[dict], int]:
    """Scrape LUN's JavaScript-driven pagination with a real browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1200},
            user_agent="LvivRealEstateMonitor/0.2",
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)

        all_listings, seen = [], set()
        page_number, reported_total = 1, 0

        while True:
            html = await page.content()
            listings, reported_total = parse_html(html)

            new_count = 0
            for listing in listings:
                if listing["source_id"] not in seen:
                    seen.add(listing["source_id"])
                    all_listings.append(listing)
                    new_count += 1

            if on_page:
                on_page(page_number, listings, reported_total)

            print(
                f"LUN page {page_number}: {len(listings)} cards, "
                f"{new_count} new, {len(all_listings)} unique, "
                f"reported total {reported_total}"
            )

            if max_pages and page_number >= max_pages:
                break

            pagination = page.locator('div[class*="pagination"]').last
            buttons = pagination.locator("button")
            count = await buttons.count()
            if count < 3:
                break

            next_button = buttons.nth(count - 1)
            if await next_button.is_disabled():
                break

            before = [x["source_id"] for x in listings[:3]]
            await next_button.click()

            try:
                await page.wait_for_function(
                    """before => {
                        const cards = document.querySelectorAll(
                            '[data-testid="realty-card-container"]'
                        );
                        if (!cards.length) return false;
                        const attrs = Array.from(cards)
                          .slice(0, 3)
                          .map(c => Array.from(c.querySelectorAll('[data-event-options]'))
                          .map(x => x.getAttribute('data-event-options') || '').join('|'));
                        return attrs.join('|') !== before.join('|');
                    }""",
                    arg=before,
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                break

            page_number += 1

        await browser.close()
        return all_listings, reported_total


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://lun.ua/sale/lviv/houses")
    ap.add_argument("--max-pages", type=int, default=3)
    args = ap.parse_args()
    asyncio.run(scrape_lun_with_browser(args.url, args.max_pages))
