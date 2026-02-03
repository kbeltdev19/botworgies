import asyncio
from playwright.async_api import async_playwright
from asyncio import Semaphore

class BrowserPool:
    def __init__(self, max_browsers=10, memory_limit=500):
        self.max_browsers = max_browsers
        self.memory_limit = memory_limit
        self.semaphore = Semaphore(max_browsers)
        self.browsers = []
        self.loop = asyncio.get_event_loop()

    async def acquire(self):
        async with self.semaphore:
            if not self.browsers:
                browser = await self._create_browser()
                self.browsers.append(browser)
            else:
                browser = self.browsers.pop(0)
            return browser

    async def release(self, browser):
        async with self.semaphore:
            self.browsers.append(browser)

    async def _create_browser(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--single-process', f'--max-old-space-size={self.memory_limit}']
            )
            return browser

    async def _health_check(self):
        while True:
            await asyncio.sleep(60)
            for i, browser in enumerate(self.browsers):
                if not browser.contexts:
                    await self._restart_browser(browser)

    async def _restart_browser(self, browser):
        await browser.close()
        new_browser = await self._create_browser()
        self.browsers[self.browsers.index(browser)] = new_browser

    async def run(self):
        await self._health_check()
        await self._cleanup()

    async def _cleanup(self):
        for browser in self.browsers:
            await browser.close()
        await self.semaphore.release(self.max_browsers)

    def shutdown(self):
        self.loop.create_task(self._cleanup())
        self.loop.stop()
        self.loop.close()

# Usage example
if __name__ == "__main__":
    pool = BrowserPool()

    async def main():
        async with pool.acquire() as browser:
            # Use the browser instance
            pass

    pool.loop.create_task(pool.run())
    pool.loop.run_until_complete(main())
    pool.shutdown()