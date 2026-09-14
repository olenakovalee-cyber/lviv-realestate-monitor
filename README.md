# Lviv Real Estate Monitor — v0.2

This version adds browser-based pagination for LUN.

## Why browser pagination?

The supplied LUN HTML has 24 rendered cards but thousands of total results. Its pagination controls are JavaScript buttons rather than normal links, so a simple `?page=2` request is not reliable.

The new `lun_browser.py` opens the LUN search page with Playwright, clicks the site's Next button, and runs the existing JSON-LD/card parser after every page.

## Test locally

```bash
pip install -r requirements.txt
python -m playwright install chromium
python lun_browser.py --max-pages 3
```

Use a small page count first.

## GitHub Actions

The workflow installs Chromium automatically.

Add these repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Do not put either secret in source code.

## Current status

- LUN structured-data parser: tested against the supplied HTML; 24 rendered listings extracted.
- Stable listing identifier: `site:...|page_id:...`.
- Detached-house classification: included/excluded/uncertain.
- SQLite history: included.
- Telegram event formatting: included.
- JavaScript pagination: implemented with Playwright.
- Full live crawl: not executed from this environment because Python network access is unavailable here.

## Important

A listing disappearing from LUN does not necessarily mean it sold. The database therefore records `gone`, not `sold`.

## Step 1 validation

Fixture regression test:
```bash
python test_fixture.py
```

Live browser smoke test:
```bash
python smoke_live.py
```

A GitHub Actions workflow named **LUN smoke test** is also included and can be run manually.
