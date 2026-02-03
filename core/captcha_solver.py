import asyncio
import aiohttp
import os
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from playwright.async_api import async_playwright

class CaptchaSolver:
    def __init__(self):
        self.twocaptcha_api_key = os.getenv("TWOCAPTCHA_API_KEY")
        self.anticaptcha_api_key = os.getenv("ANTICAPTCHA_API_KEY")
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.solver = None

    async def detect_captcha(self, page):
        await page.wait_for_selector("iframe[src*='google.com/recaptcha/api2']")
        return True

    async def solve_recaptcha_v2(self, sitekey: str, page_url: str) -> Optional[str]:
        return await self.solve_captcha(sitekey, page_url, "recaptcha")

    async def solve_hcaptcha(self, sitekey: str, page_url: str) -> Optional[str]:
        return await self.solve_captcha(sitekey, page_url, "hcaptcha")

    async def solve_image_captcha(self, base64_image: str) -> Optional[str]:
        return await self.solve_captcha(base64_image, "", "image")

    async def solve_captcha(self, sitekey_or_base64: str, page_url: str, captcha_type: str) -> Optional[str]:
        async with aiohttp.ClientSession() as session:
            try:
                if captcha_type == "recaptcha" or captcha_type == "hcaptcha":
                    response = await self.send_request(session, "post", self.solver + f"?key={self.solver_api_key}&method={captcha_type}&sitekey={sitekey_or_base64}&pageurl={page_url}")
                elif captcha_type == "image":
                    response = await self.send_request(session, "post", self.solver + f"?key={self.solver_api_key}&method=imagetotext&body={sitekey_or_base64}")
                else:
                    raise ValueError("Invalid captcha type")

                response_json = await response.json()
                if response_json["status"] == 1:
                    return response_json["request"]
                else:
                    raise Exception("Failed to solve captcha")
            except Exception as e:
                print(f"Error with {self.solver}, trying {self.fallback_solver}")
                self.solver = self.fallback_solver
                self.solver_api_key = self.fallback_solver_api_key
                return await self.solve_captcha(sitekey_or_base64, page_url, captcha_type)

    async def send_request(self, session, method, url, data=None):
        async with session.request(method, url, data=data) as response:
            return response

    async def solve(self, captcha_type, sitekey_or_base64, page_url):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self.solve_captcha, sitekey_or_base64, page_url, captcha_type)

    def use_twocaptcha(self):
        self.solver = "http://2captcha.com/in.php"
        self.fallback_solver = "http://anti-captcha.com/"
        self.solver_api_key = self.twocaptcha_api_key
        self.fallback_solver_api_key = self.anticaptcha_api_key

    def use_anticaptcha(self):
        self.solver = "http://api.anti-captcha.com/in.php"
        self.fallback_solver = "http://2captcha.com/in.php"
        self.solver_api_key = self.anticaptcha_api_key
        self.fallback_solver_api_key = self.twocaptcha_api_key

async def main():
    solver = CaptchaSolver()
    solver.use_twocaptcha()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://example.com")
        if await solver.detect_captcha(page):
            token = await solver.solve_recaptcha_v2("your_sitekey", "https://example.com")
            print(token)
        await browser.close()

asyncio.run(main())