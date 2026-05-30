import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

TARGET_URL = "https://eldorado.gg/category/roblox"

async def main():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        title = await page.title()
        print(f"Page Title: {title}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
