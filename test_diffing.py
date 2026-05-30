"""Insert simulated yesterday data to test the best-seller diffing logic."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import database, datetime, sqlite3

yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

with database.get_connection() as conn:
    today_records = conn.execute(
        "SELECT * FROM listings WHERE scraped_date = ? LIMIT 10",
        (datetime.date.today().isoformat(),)
    ).fetchall()

    for rec in today_records:
        old_qty = rec["quantity"] + (hash(rec["listing_id"]) % 10 + 1)
        conn.execute("""
            INSERT INTO listings
                (listing_id, title, category, price_usd, seller,
                 quantity, total_orders, is_verified, scraped_date, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec["listing_id"], rec["title"], rec["category"],
            rec["price_usd"], rec["seller"],
            old_qty, rec["total_orders"], rec["is_verified"],
            yesterday, rec["scraped_at"],
        ))

print(f"Inserted 10 simulated yesterday records ({yesterday})")

best = database.get_best_sellers()
for r in best:
    title = (r["title"] or "")[:40]
    print(f"  Sold {r['units_sold']:>3}: {title}")
print(f"Total best sellers found: {len(best)}")
