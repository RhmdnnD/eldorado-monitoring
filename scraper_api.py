import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None

import asyncio, time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import database

BASE_URL = "https://www.eldorado.gg"
ROBLOX_GAME_ID = "70"

# Daftar Game yang ingin dilacak Item-nya
TARGET_ROBLOX_GAMES = [
    "Blox Fruits",
    "Adopt Me",
    "Pet Simulator 99",
    "Murder Mystery 2",
    "Anime Defenders",
]

def extract_listing(r: dict, default_cat: str, source_game: str = "") -> dict:
    o = r.get("offer", {})
    u = r.get("user", {})
    info = r.get("userOrderInfo", {})
    
    title = o.get("offerTitle") or "Unknown"
    # Modifikasi: Tambahkan tag nama game di judul agar rapi di Dashboard Vercel
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
    # Jalur cepat khusus untuk Account
    url = f"{BASE_URL}/api/flexibleOffers?pageSize=50&category={category}&gameId={game_id}"
    resp = await page.request.get(url)
    data = await resp.json()
    if not isinstance(data, dict) or not data.get("results"):
        return []
    return [extract_listing(r, category) for r in data["results"]]

async def fetch_predefined_offers(page, category: str, game_id: str) -> list[dict]:
    # Jalur cepat khusus untuk Robux
    url = f"{BASE_URL}/api/predefinedOffers/game?pageSize=50&category={category}&gameId={game_id}"
    resp = await page.request.get(url)
    data = await resp.json()
    if not isinstance(data, dict) or not data.get("results"):
        return []
    return [extract_listing(r, category) for r in data["results"]]

async def auto_discover_urls(page, game_names: list[str]) -> dict[str, str]:
    # Langkah 1: Membaca direktori Eldorado untuk menemukan URL kategori
    resp = await page.request.get(f"{BASE_URL}/api/library?locale=en-US")
    library = await resp.json()
    
    seen = {}
    if isinstance(library, list):
        for entry in library:
            if entry.get("gameGroup") != "Roblox":
                continue
            
            name = entry.get("menuGameTitle") or entry.get("gameName") or ""
            
            if name in game_names:
                # Coba ambil URL dari API. Jika kosong, kita rakit sendiri!
                seo_url = entry.get("seoUrl")
                if not seo_url:
                    # Mengubah "Blox Fruits" menjadi "blox-fruits"
                    seo_url = name.lower().replace(" ", "-").replace("'", "")
                
                seen[name] = seo_url
                
    print(f"  Discovered {len(seen)} category URLs: {seen}")
    return seen
    # Langkah 1: Membaca direktori Eldorado untuk menemukan URL kategori
    resp = await page.request.get(f"{BASE_URL}/api/library?locale=en-US")
    library = await resp.json()
    
    seen = {}
    if isinstance(library, list):
        for entry in library:
            if entry.get("gameGroup") != "Roblox":
                continue
            name = entry.get("menuGameTitle") or entry.get("gameName") or ""
            seo_url = entry.get("seoUrl")
            if name in game_names and seo_url:
                seen[name] = seo_url
                
    print(f"  Discovered {len(seen)} category URLs.")
    return seen

async def fetch_items_via_intercept(page, game_name: str, seo_url: str) -> list[dict]:
    # Langkah 2: Teknik Interceptor! Membuka halaman dan menyadap API.
    url = f"{BASE_URL}/games/{seo_url}"
    captured_items = []

    async def intercept_response(response):
        # Mencegat semua lalu lintas API di balik layar
        if "api" in response.url.lower() and response.request.method == "GET":
            try:
                data = await response.json()
                # Ciri-ciri balasan API yang berisi daftar jualan
                if isinstance(data, dict) and "results" in data:
                    if len(data["results"]) > 0 and "offer" in data["results"][0]:
                        batch = [extract_listing(r, "Item", game_name) for r in data["results"]]
                        captured_items.extend(batch)
                        print(f"      [HIT] Disadap {len(batch)} item dari lalu lintas tersembunyi!")
            except:
                pass

    # Pasang alat penyadap
    page.on("response", intercept_response)
    
    print(f"    Membuka halaman web: {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    
    # Scroll layar ke bawah untuk memancing server mengirimkan data item
    await page.evaluate("window.scrollTo(0, 1000)")
    await asyncio.sleep(4) # Tunggu loading jaringan selesai

    # Lepas alat penyadap
    page.remove_listener("response", intercept_response)
    
    # Filter duplikat (berjaga-jaga jika API dipanggil 2x oleh web)
    unique_items = {item["id"]: item for item in captured_items if item.get("id")}
    return list(unique_items.values())

async def scrape_roblox():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        await page.goto(f"{BASE_URL}/category/roblox", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        print("Session established (Cloudflare bypassed)")

        all_data = {"accounts": [], "items": [], "robux": []}

        # --- 1) ACCOUNTS ---
        print("\n--- Roblox Accounts ---")
        all_data["accounts"] = await fetch_flexible_offers(page, "Account", ROBLOX_GAME_ID)
        print(f"  Got {len(all_data['accounts'])} accounts")

        # --- 2) URL DISCOVERY ---
        print("\n--- Auto-Discovering Category URLs ---")
        game_urls = await auto_discover_urls(page, TARGET_ROBLOX_GAMES)

        # --- 3) ITEMS (INTERCEPTOR) ---
        print("\n--- Roblox Items (DOM Interceptor) ---")
        all_game_items = []
        for game_name, seo_url in game_urls.items():
            print(f"\n  [{game_name}]")
            items = await fetch_items_via_intercept(page, game_name, seo_url)
            all_game_items.extend(items)
        all_data["items"] = all_game_items

        # --- 4) ROBUX ---
        print("\n--- Roblox Robux ---")
        all_data["robux"] = await fetch_predefined_offers(page, "Currency", ROBLOX_GAME_ID)
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
    print(f"Items:    {len(data.get('items', []))} listings (across {len(TARGET_ROBLOX_GAMES)} games)")
    print(f"Robux:    {len(data.get('robux', []))} listings")

if __name__ == "__main__":
    main()