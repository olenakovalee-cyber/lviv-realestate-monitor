from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_site TEXT,
    title TEXT,
    description TEXT,
    locality TEXT,
    region TEXT,
    address TEXT,
    price REAL,
    currency TEXT,
    rooms REAL,
    property_type TEXT,
    classification TEXT,
    url TEXT,
    latitude REAL,
    longitude REAL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_price REAL,
    last_currency TEXT,
    missing_scans INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    title TEXT,
    price REAL,
    currency TEXT,
    classification TEXT,
    locality TEXT,
    url TEXT
);

CREATE TABLE IF NOT EXISTS scan_runs (
    scan_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    pages_requested INTEGER DEFAULT 0,
    listings_found INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    baseline INTEGER DEFAULT 0
);
"""

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class Database:
    def __init__(self, path: str = "data/market.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def get(self, source: str, source_id: str):
        return self.conn.execute(
            "SELECT * FROM listings WHERE source=? AND source_id=?",
            (source, source_id),
        ).fetchone()

    def upsert_observation(self, scan_id: str, listing: dict):
        now = now_iso()
        old = self.get(listing["source"], listing["source_id"])
        if old is None:
            self.conn.execute("""
                INSERT INTO listings (
                    source, source_id, source_site, title, description,
                    locality, region, address, price, currency, rooms,
                    property_type, classification, url, latitude, longitude,
                    first_seen, last_seen, last_price, last_currency,
                    missing_scans, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'active')
            """, (
                listing["source"], listing["source_id"], listing.get("source_site"),
                listing.get("title"), listing.get("description"),
                listing.get("locality"), listing.get("region"), listing.get("address"),
                listing.get("price"), listing.get("currency"), listing.get("rooms"),
                listing.get("property_type"), listing.get("classification"),
                listing.get("url"), listing.get("latitude"), listing.get("longitude"),
                now, now, listing.get("price"), listing.get("currency"),
            ))
        else:
            self.conn.execute("""
                UPDATE listings
                SET title=?, description=?, locality=?, region=?, address=?,
                    price=?, currency=?, rooms=?, property_type=?, classification=?,
                    url=?, latitude=?, longitude=?, last_seen=?,
                    last_price=?, last_currency=?, missing_scans=0, status='active'
                WHERE source=? AND source_id=?
            """, (
                listing.get("title"), listing.get("description"),
                listing.get("locality"), listing.get("region"), listing.get("address"),
                listing.get("price"), listing.get("currency"), listing.get("rooms"),
                listing.get("property_type"), listing.get("classification"),
                listing.get("url"), listing.get("latitude"), listing.get("longitude"),
                now, listing.get("price"), listing.get("currency"),
                listing["source"], listing["source_id"],
            ))

        self.conn.execute("""
            INSERT INTO observations
            (scan_id, source, source_id, observed_at, title, price, currency,
             classification, locality, url)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            scan_id, listing["source"], listing["source_id"], now,
            listing.get("title"), listing.get("price"), listing.get("currency"),
            listing.get("classification"), listing.get("locality"), listing.get("url"),
        ))
        self.conn.commit()
        return old

    def mark_missing(self, source: str, seen_ids: set[str], required: int):
        rows = self.conn.execute(
            "SELECT * FROM listings WHERE source=? AND status='active'", (source,)
        ).fetchall()
        gone = []
        for row in rows:
            if row["source_id"] in seen_ids:
                continue
            n = row["missing_scans"] + 1
            status = "active"
            if n >= required:
                status = "gone"
                gone.append(row)
            self.conn.execute(
                "UPDATE listings SET missing_scans=?, status=? WHERE source=? AND source_id=?",
                (n, status, source, row["source_id"]),
            )
        self.conn.commit()
        return gone

    def start_scan(self, scan_id: str):
        self.conn.execute(
            "INSERT INTO scan_runs(scan_id, started_at) VALUES (?,?)",
            (scan_id, now_iso())
        )
        self.conn.commit()

    def finish_scan(self, scan_id: str, pages: int, found: int, errors: int, baseline: bool):
        self.conn.execute("""
            UPDATE scan_runs
            SET finished_at=?, pages_requested=?, listings_found=?, errors=?, baseline=?
            WHERE scan_id=?
        """, (now_iso(), pages, found, errors, int(baseline), scan_id))
        self.conn.commit()
