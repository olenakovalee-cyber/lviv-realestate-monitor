from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlencode, urlparse, parse_qs, urlunparse

import requests
from bs4 import BeautifulSoup

SOURCE = "lun"

@dataclass
class Listing:
    source: str
    source_id: str
    source_site: str | None
    title: str | None
    description: str | None
    locality: str | None
    region: str | None
    address: str | None
    price: float | None
    currency: str | None
    rooms: float | None
    property_type: str | None
    classification: str
    url: str | None
    latitude: float | None
    longitude: float | None

    def dict(self):
        return asdict(self)

def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _classification(title: str, description: str, structured_type: str) -> str:
    text = f"{title or ''} {description or ''}".lower()
    excluded = [
        "таунхаус", "таунхаус", "townhouse", "дуплекс", "duplex",
        "частина будинку", "частина дома", "квартира", "кімната",
        "земельна ділянка", "земельна ділянка",
    ]
    if any(x in text for x in excluded):
        return "excluded"

    # Schema.org SingleFamilyResidence is a useful positive signal,
    # but text is kept because LUN's broad "houses" result can contain
    # mixed property formats.
    if "SingleFamilyResidence" in structured_type or "будинок" in text or "дом" in text:
        return "detached"

    return "uncertain"

def _page_id(card) -> tuple[str | None, str | None]:
    for node in card.find_all(attrs={"data-event-options": True}):
        raw = node.get("data-event-options", "")
        m = re.search(r"(?:^|\|)site:([^|]+)", raw)
        site = m.group(1) if m else None
        m = re.search(r"(?:^|\|)page_id:(\d+)", raw)
        if m:
            return m.group(1), site
    return None, None

def _page_url(base: str, page: int, param: str) -> str:
    parts = list(urlparse(base))
    q = parse_qs(parts[4], keep_blank_values=True)
    q[param] = [str(page)]
    parts[4] = urlencode(q, doseq=True)
    return urlunparse(parts)

class LUNPageSource:
    def __init__(self, base_url: str, page_param: str = "page", timeout: int = 30):
        self.base_url = base_url
        self.page_param = page_param
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LvivRealEstateMonitor/0.1 (+personal market research bot)"
        })

    def fetch(self, page: int = 1) -> tuple[list[dict], int]:
        url = self.base_url if page == 1 else _page_url(self.base_url, page, self.page_param)
        r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        return parse_html(r.text)

def parse_html(html: str) -> tuple[list[dict], int]:
    soup = BeautifulSoup(html, "html.parser")

    total = 0
    schema = soup.find("script", id="schema-real-estate", type="application/ld+json")
    schema_items = []
    if schema and schema.string:
        try:
            data = json.loads(schema.string)
            total = int(data.get("numberOfItems") or data.get("offers", {}).get("offerCount") or 0)
            schema_items = [x.get("item", {}) for x in data.get("itemListElement", [])]
        except Exception:
            pass

    cards = soup.select('[data-testid="realty-card-container"]')
    listings = []

    for idx, card in enumerate(cards):
        item = schema_items[idx] if idx < len(schema_items) else {}
        page_id, site = _page_id(card)

        if not page_id:
            continue

        address_obj = item.get("address") or {}
        geo = item.get("geo") or {}
        offers = item.get("offers") or {}

        title = item.get("name")
        desc = item.get("description")
        structured_type = " ".join(item.get("@type", []) if isinstance(item.get("@type"), list) else [str(item.get("@type", ""))])

        address = address_obj.get("streetAddress")
        locality = address_obj.get("addressLocality")
        region = address_obj.get("addressRegion")

        listing = Listing(
            source=SOURCE,
            source_id=f"{site or 'lun'}:{page_id}",
            source_site=site,
            title=title,
            description=desc,
            locality=locality,
            region=region,
            address=address,
            price=_float(offers.get("price")),
            currency=offers.get("priceCurrency"),
            rooms=_float(item.get("numberOfRooms")),
            property_type=structured_type or None,
            classification=_classification(title or "", desc or "", structured_type),
            url=None,
            latitude=_float(geo.get("latitude")),
            longitude=_float(geo.get("longitude")),
        )
        listings.append(listing.dict())

    return listings, total
