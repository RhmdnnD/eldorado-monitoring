import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None

import asyncio, json, time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import database

BASE_URL = "https://www.eldorado.gg"
ROBLOX_GAME_ID = "70"
PAGE_SIZE = 50

def extract_account(r: dict) -> dict:
    o = r["offer"]
    u = r.get("user", {})
    info = r.get("userOrderInfo", {})
    return {
        "id": o.get("id"),
        "title": o.get("offerTitle"),
        "price_usd": o.get("pricePerUnitInUSD", {}).get("amount"),
        "seller": u.get("username"),
        "seller_id": u.get("id"),
        "quantity": o.get("quantity"),
        "total_orders": info.get("totalOrdersFromUser"),
        "is_verified": u.get("isVerifiedSeller"),
        "category": "Account",
    }

def extract_robux(r: dict) -> dict:
    o = r["offer"]
    u = r.get("user", {})
    return {
        "id": o.get("id"),
        "price_per_unit_usd": o.get("pricePerUnitInUSD", {}).get("amount"),
        "seller": u.get("username"),
        "seller_id": u.get("id"),
        "quantity": o.get("quantity"),
        "unit_system": o.get("unitSystem"),
        "total_orders": r.get("userOrderInfo", {}).get("totalOrdersFromUser"),
        "is_verified": u.get("isVerifiedSeller"),
        "category": "Currency",
    }

def print_best_sellers():
    best = database.get_best_sellers()
    if not best:
        print("\n  No best-seller data yet (need 2+ days of records)")
        return
    print("\n  " + "="*70)
    print(f"  {'Rank':<6} {'Title':<36} {'Sold':>8} {'Category':<12}")
    print("  " + "-"*70)
    for i, r in enumerate(best, 1):
        title = (r["title"] or "")[:34]
        units = r["units_sold"]
        print(f"  {i:<6} {title:<36} {units:>8} {r['category']:<12}")
    print("  " + "="*70)

async def fetch_flexible_offers(page, category: str, max_pages: int = 5) -> list[dict]:
    results = []
    base = f"{BASE_URL}/api/flexibleOffers?pageSize={PAGE_SIZE}&category={category}&gameId={ROBLOX_GAME_ID}"
    for idx in range(1, max_pages + 1):
        resp = await page.request.get(f"{base}&pageIndex={idx}")
        data = await resp.json()
        if not isinstance(data, dict) or not data.get("results"):
            break
        batch = [extract_account(r) for r in data["results"]]
        results.extend(batch)
        print(f"  Page {idx}/{data.get('totalPages')}: +{len(batch)} (total {len(results)})")
        if idx >= data.get("totalPages", 1):
            break
        await asyncio.sleep(0.5)
    return results

async def scrape_roblox():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        await page.goto(f"{BASE_URL}/category/roblox", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        print("Session established (Cloudflare bypassed)")

        all_data = {}

        # 1) Accounts
        print("\n--- Roblox Accounts ---")
        all_data["accounts"] = await fetch_flexible_offers(page, "Account")

        # 2) Robux (Currency) via predefinedOffers
        print("\n--- Roblox Robux ---")
        robux_url = f"{BASE_URL}/api/predefinedOffers/game?pageSize=50&category=Currency&gameId={ROBLOX_GAME_ID}"
        resp = await page.request.get(robux_url)
        data = await resp.json()
        if isinstance(data, dict) and data.get("results"):
            all_data["robux"] = [extract_robux(r) for r in data["results"]]
            print(f"  Got {len(all_data['robux'])} offers")
        else:
            all_data["robux"] = []
            print(f"  No results (response: {str(data)[:200]})")

        await browser.close()
        return all_data

def main():
    database.setup()
    t0 = time.time()
    data = asyncio.run(scrape_roblox())
    elapsed = time.time() - t0

    if data.get("accounts"):
        database.save_listings(data["accounts"], "Account")
    if data.get("robux"):
        database.save_listings(data["robux"], "Currency")

    print(f"\n=== Summary ===")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Accounts: {len(data.get('accounts', []))} listings")
    print(f"Robux:    {len(data.get('robux', []))} listings")

    print(f"\n=== Daily Best Sellers (Qty Delta) ===")
    print_best_sellers()

    summary = database.get_date_summary()
    print(f"\nDatabase: {summary['total']} total records for {summary['date']}")

if __name__ == "__main__":
    main()
