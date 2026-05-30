import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

TARGET_URL = "https://eldorado.gg/category/roblox"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await stealth_async(page)
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        title = await page.title()
        print(f"Page Title: {title}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
