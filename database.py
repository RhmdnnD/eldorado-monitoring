import sqlite3, datetime, json
from pathlib import Path

DB_PATH = Path(__file__).parent / "eldorado.db"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def setup():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                title TEXT,
                category TEXT,
                price_usd REAL,
                seller TEXT,
                quantity INTEGER,
                total_orders INTEGER,
                is_verified INTEGER DEFAULT 0,
                scraped_date TEXT NOT NULL,
                scraped_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_listings_id_date
            ON listings(listing_id, scraped_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_listings_date
            ON listings(scraped_date)
        """)

def save_listings(records: list[dict], category: str):
    today = datetime.date.today().isoformat()
    now = datetime.datetime.utcnow().isoformat()
    with get_connection() as conn:
        rows = [
            (
                r["id"],
                r.get("title", ""),
                category,
                r.get("price_usd") or r.get("price_per_unit_usd"),
                r.get("seller"),
                r.get("quantity", 0),
                r.get("total_orders"),
                1 if r.get("is_verified") else 0,
                today,
                now,
            )
            for r in records
        ]
        conn.executemany("""
            INSERT OR REPLACE INTO listings
                (listing_id, title, category, price_usd, seller,
                 quantity, total_orders, is_verified, scraped_date, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        print(f"  Saved {len(rows)} {category} records to database")

def get_best_sellers(limit: int = 50) -> list[dict]: # Limit diubah ke 50
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                MAX(t.listing_id) AS listing_id,
                t.title,
                MAX(t.category) AS category,
                MAX(t.seller) AS seller,
                SUM(t.quantity) AS qty_today,
                SUM(y.quantity) AS qty_yesterday,
                SUM(y.quantity - t.quantity) AS units_sold
            FROM listings t
            JOIN listings y
                ON t.listing_id = y.listing_id
                AND y.scraped_date = ?
            WHERE t.scraped_date = ?
              AND y.quantity > t.quantity
              AND t.title NOT GLOB '*[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]*'
            GROUP BY t.title
            ORDER BY units_sold DESC
            LIMIT ?
        """, (yesterday, today, limit)).fetchall()
    return [dict(r) for r in rows]
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                MAX(t.listing_id) AS listing_id,
                t.title,
                MAX(t.category) AS category,
                MAX(t.seller) AS seller,
                SUM(t.quantity) AS qty_today,
                SUM(y.quantity) AS qty_yesterday,
                SUM(y.quantity - t.quantity) AS units_sold
            FROM listings t
            JOIN listings y
                ON t.listing_id = y.listing_id
                AND y.scraped_date = ?
            WHERE t.scraped_date = ?
              AND y.quantity > t.quantity
              AND t.title NOT GLOB '*[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]*'
            GROUP BY t.title
            ORDER BY units_sold DESC
            LIMIT ?
        """, (yesterday, today, limit)).fetchall()
    return [dict(r) for r in rows]

def export_dashboard_json(limit: int = 50):
    best = get_best_sellers(limit)
    summary = get_date_summary()
    payload = {
        "updated_at": datetime.datetime.utcnow().isoformat(),
        "date": summary["date"],
        "total_records": summary["total"],
        "best_sellers": best,
    }
    path = Path(__file__).parent / "dashboard.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Exported {len(best)} best sellers to dashboard.json")

def get_date_summary(date: str | None = None) -> dict:
    date = date or datetime.date.today().isoformat()
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM listings WHERE scraped_date = ?", (date,)
        ).fetchone()["c"]
        accounts = conn.execute(
            "SELECT COUNT(*) AS c FROM listings WHERE scraped_date = ? AND category = 'Account'", (date,)
        ).fetchone()["c"]
        items = conn.execute( # Tambahan untuk menghitung Item
            "SELECT COUNT(*) AS c FROM listings WHERE scraped_date = ? AND category = 'Item'", (date,)
        ).fetchone()["c"]
        robux = conn.execute(
            "SELECT COUNT(*) AS c FROM listings WHERE scraped_date = ? AND category = 'Currency'", (date,)
        ).fetchone()["c"]
    return {"date": date, "total": total, "accounts": accounts, "items": items, "robux": robux}
