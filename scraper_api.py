import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None

import asyncio, time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import database

BASE_URL = "https://www.eldorado.gg"
ROBLOX_GAME_ID = "70"

FORCE_TARGET_GAMES = [
    "Fisch", 
    "Blade Ball",
    "Dress To Impress"
]

def extract_listing(r: dict, default_cat: str, source_game: str = "") -> dict:
    o = r.get("offer", {})
    u = r.get("user", {})
    info = r.get("userOrderInfo", {})
    
    title = o.get("offerTitle") or "Unknown"
    if source_game:
        title = f"[{source_game}] {title}"

    return {
        "id": o.get("id"),
        "title": title,
        "price_usd": o.get("pricePerUnitInUSD", {}).get("amount"),
        "seller": u.get("username"),
        "seller_id": u.get("id"),
        "quantity": o.get("quantity"),
        "total_orders": info.get("totalOrdersFromUser"),
        "is_verified": u.get("isVerifiedSeller"),
        "category": default_cat
    }

async def fetch_flexible_offers(page, category: str, game_id: str) -> list[dict]:
    url = f"{BASE_URL}/api/flexibleOffers?pageSize=50&category={category}&gameId={game_id}"
    resp = await page.request.get(url)
    data = await resp.json()
    if not isinstance(data, dict) or not data.get("results"):
        return []
    return [extract_listing(r, category) for r in data["results"]]

async def fetch_predefined_offers(page, category: str, game_id: str) -> list[dict]:
    url = f"{BASE_URL}/api/predefinedOffers/game?pageSize=50&category={category}&gameId={game_id}"
    resp = await page.request.get(url)
    data = await resp.json()
    if not isinstance(data, dict) or not data.get("results"):
        return []
    return [extract_listing(r, category) for r in data["results"]]

async def auto_discover_roblox_games(page) -> dict[str, str]:
    resp = await page.request.get(f"{BASE_URL}/api/library?locale=en-US")
    library = await resp.json()
    
    seen = {}
    if isinstance(library, list):
        for entry in library:
            name = entry.get("menuGameTitle") or entry.get("gameName") or ""
            group = entry.get("gameGroup")

            is_roblox_group = (group == "Roblox")
            is_forced = any(forced.lower() in name.lower() for forced in FORCE_TARGET_GAMES)

            if not (is_roblox_group or is_forced):
                continue
                
            if name.lower() in ["roblox", ""]:
                continue
                
            seo_url = entry.get("seoUrl")
            if not seo_url:
                seo_url = name.lower().replace(" ", "-").replace("'", "")
            
            seen[name] = seo_url
                
    print(f"  [RADAR AKTIF] Ditemukan {len(seen)} game (Otomatis + Paksaan)!")
    return seen

async def fetch_items_via_intercept(page, game_name: str, seo_url: str) -> list[dict]:
    url = f"{BASE_URL}/games/{seo_url}"
    captured_items = []

    async def intercept_response(response):
        if "api" in response.url.lower() and response.request.method == "GET":
            try:
                data = await response.json()
                if isinstance(data, dict) and "results" in data:
                    if len(data["results"]) > 0 and "offer" in data["results"][0]:
                        batch = [extract_listing(r, "Item", game_name) for r in data["results"]]
                        captured_items.extend(batch)
                        print(f"      [HIT] Disadap +{len(batch)} item! (Total sementara: {len(captured_items)})")
            except:
                pass

    page.on("response", intercept_response)
    print(f"    Membuka: {url}")
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        previous_height = await page.evaluate("document.body.scrollHeight")
        stuck_counter = 0
        
        while True:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2.5) 
            
            new_height = await page.evaluate("document.body.scrollHeight")
            
            if new_height == previous_height:
                stuck_counter += 1
                if stuck_counter >= 2:
                    print("      [INFO] Sudah mencapai dasar halaman.")
                    break
            else:
                stuck_counter = 0
                previous_height = new_height
            
    except Exception as e:
        print(f"      [SKIP] Halaman tidak valid atau timeout.")

    page.remove_listener("response", intercept_response)
    
    unique_items = {item["id"]: item for item in captured_items if item.get("id")}
    hasil_akhir = list(unique_items.values())
    print(f"    -> TOTAL Item {game_name} yang disadap: {len(hasil_akhir)}")
    return hasil_akhir

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

        print("\n--- Auto-Discovering Roblox Games ---")
        game_urls = await auto_discover_roblox_games(page)

        print("\n--- Scraping Items (DOM Interceptor) ---")
        all_game_items = []
        for game_name, seo_url in game_urls.items():
            print(f"\n  [{game_name}]")
            items = await fetch_items_via_intercept(page, game_name, seo_url)
            all_game_items.extend(items)
            
        all_data["items"] = all_game_items

        print("\n--- Roblox Robux ---")
        all_data["robux"] = await fetch_predefined_offers(page, "Currency", ROBLOX_GAME_ID)

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

    database.export_dashboard_json()
    summary = database.get_date_summary()
    print(f"\nDatabase: {summary['total']} total records for {summary['date']}")

if __name__ == "__main__":
    main()