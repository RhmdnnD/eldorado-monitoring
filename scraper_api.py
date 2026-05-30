import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None

import asyncio, time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import database

BASE_URL = "https://www.eldorado.gg"
ROBLOX_GAME_ID = "70"
ITEM_GAME_ID = "TULIS_ANGKA_YANG_ANDA_TEMUKAN_DI_SINI"
PAGE_SIZE = 50

def extract_listing(r: dict, default_cat: str) -> dict:
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
        "category": default_cat,
    }

async def fetch_flexible_offers(page, category: str, game_id: str, max_pages: int = 5) -> list[dict]:
    results = []
    base = f"{BASE_URL}/api/flexibleOffers?pageSize={PAGE_SIZE}&category={category}&gameId={game_id}"
    for idx in range(1, max_pages + 1):
        resp = await page.request.get(f"{base}&pageIndex={idx}")
        data = await resp.json()
        if not isinstance(data, dict) or not data.get("results"):
            break
        batch = [extract_listing(r, category) for r in data["results"]]
        results.extend(batch)
        print(f"  Page {idx}/{data.get('totalPages')}: +{len(batch)} (total {len(results)})")
        if idx >= data.get("totalPages", 1):
            break
        await asyncio.sleep(0.5)
    return results

async def fetch_predefined_offers(page, category: str) -> list[dict]:
    url = f"{BASE_URL}/api/predefinedOffers/game?pageSize=50&category={category}&gameId={ROBLOX_GAME_ID}"
    resp = await page.request.get(url)
    data = await resp.json()
    if not isinstance(data, dict) or not data.get("results"):
        return []
    return [extract_listing(r, category) for r in data["results"]]

async def scrape_roblox():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        await page.goto(f"{BASE_URL}/category/roblox", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        print("Session established (Cloudflare bypassed)")

        all_data = {"accounts": [], "items": [], "robux": []}

        print("\n--- Roblox Accounts ---")
        all_data["accounts"] = await fetch_flexible_offers(page, "Account", ROBLOX_GAME_ID)

        print("\n--- Roblox Items ---")
        all_data["items"] = await fetch_flexible_offers(page, "Item", ITEM_GAME_ID)

        print("\n--- Roblox Robux ---")
        all_data["robux"] = await fetch_predefined_offers(page, "Currency")
        if all_data["robux"]:
            print(f"  Got {len(all_data['robux'])} offers")

        await browser.close()
        return all_data

def main():
    database.setup()
    t0 = time.time()
    data = asyncio.run(scrape_roblox())
    elapsed = time.time() - t0

    if data.get("accounts"):
        database.save_listings(data["accounts"], "Account")
    if data.get("items"):
        database.save_listings(data["items"], "Item")
    if data.get("robux"):
        database.save_listings(data["robux"], "Currency")

    print(f"\n=== Summary ===")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Accounts: {len(data.get('accounts', []))} listings")
    print(f"Items:    {len(data.get('items', []))} listings")
    print(f"Robux:    {len(data.get('robux', []))} listings")

if __name__ == "__main__":
    main()
