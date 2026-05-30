import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def main():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        await page.goto("https://eldorado.gg/category/roblox", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # Find max pageSize
        for size in [5, 10, 20, 50, 40, 30, 25]:
            url = f"https://www.eldorado.gg/api/flexibleOffers?pageSize={size}&category=Account&gameId=70"
            resp = await page.request.get(url)
            data = await resp.json()
            if isinstance(data, dict) and "results" in data:
                n = len(data["results"])
                print(f"pageSize={size}: OK, got {n} results, totalRecords={data.get('recordCount')}")
            else:
                print(f"pageSize={size}: FAIL - {data}")

        # Test with pageSize=20 and pageIndex
        print("\n--- Testing pagination ---")
        for p_idx in [1, 2, 3]:
            url = f"https://www.eldorado.gg/api/flexibleOffers?pageSize=20&category=Account&gameId=70&pageIndex={p_idx}"
            resp = await page.request.get(url)
            data = await resp.json()
            if isinstance(data, dict) and data.get("results"):
                ids = [r["offer"]["id"] for r in data["results"]]
                titles = [r["offer"]["offerTitle"] for r in data["results"]]
                print(f"  Page {p_idx}: {len(ids)} items, records={data.get('recordCount')}, pages={data.get('totalPages')}")
                print(f"    IDs: {ids}")
                print(f"    Titles: {titles[:3]}...")
            else:
                print(f"  Page {p_idx}: FAIL - {data}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
