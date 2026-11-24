import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            args=["--disable-crash-reporter", "--disable-breakpad"],
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 1400}, device_scale_factor=1)
        await page.goto("http://127.0.0.1:8502/", wait_until="domcontentloaded", timeout=30000)
        await page.get_by_text("Season-to-variety picker", exact=True).click()
        await page.get_by_text("Find the Best Onion & Garlic Variety for Your Season").wait_for(timeout=30000)
        await page.wait_for_timeout(1500)
        await page.screenshot(path="docs/screenshots/checkpoint-2.png", full_page=True)
        print("captured", await page.title())
        await browser.close()

asyncio.run(main())
