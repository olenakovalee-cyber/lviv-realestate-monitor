from __future__ import annotations
import requests

def send_message(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }, timeout=20)
    r.raise_for_status()
    return r.json()

def format_event(kind: str, listing: dict) -> str:
    title = listing.get("title") or "(без назви)"
    locality = listing.get("locality") or ""
    price = listing.get("price")
    currency = listing.get("currency") or ""
    price_text = f"{price:,.0f} {currency}" if isinstance(price, (int, float)) else "ціна не вказана"

    prefix = {
        "new": "🆕 Нова пропозиція",
        "price": "💰 Зміна ціни",
        "gone": "⚠️ Оголошення зникло",
    }.get(kind, "🏠 Подія")

    return f"{prefix}\n{title}\n{locality}\n{price_text}"
