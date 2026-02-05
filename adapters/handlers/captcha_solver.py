#!/usr/bin/env python3
"""
CAPTCHA Solver Module - BrowserBase Stealth primary, 2captcha fallback.

Usage:
    from adapters.handlers.captcha_solver import CaptchaSolver
    
    solver = CaptchaSolver()
    result = await solver.solve_with_fallback(page)
"""

import asyncio
import os
from typing import Optional
import logging
import aiohttp

logger = logging.getLogger(__name__)


class CaptchaSolver:
    """
    CAPTCHA solving with BrowserBase Stealth as primary, 2captcha as fallback.
    """
    
    def __init__(self):
        self.twocaptcha_key = os.getenv('TWOCAPTCHA_API_KEY')
        self.capsolver_key = os.getenv('CAPSOLVER_API_KEY')
        self.stats = {
            'browserbase_solved': 0,
            'twocaptcha_solved': 0,
            'capsolver_solved': 0,
            'failed': 0,
        }
    
    async def solve_with_fallback(self, page, timeout: int = 45) -> bool:
        """
        CAPTCHA solving cascade:
        1. BrowserBase Stealth (primary)
        2. Capsolver (fallback 1)
        3. 2captcha (fallback 2)
        
        Args:
            page: Playwright page with CAPTCHA
            timeout: Total timeout in seconds
            
        Returns:
            True if CAPTCHA solved, False otherwise
        """
        # Step 1: Wait for BrowserBase automatic solving
        logger.info("[CAPTCHA] Step 1: BrowserBase Stealth...")
        bb_result = await self._wait_browserbase(page, timeout=30)
        
        if bb_result:
            logger.info("[CAPTCHA] ✅ BrowserBase Stealth solved!")
            self.stats['browserbase_solved'] += 1
            return True
        
        # Step 2: Try Capsolver
        if self.capsolver_key:
            logger.info("[CAPTCHA] Step 2: Capsolver...")
            cs_result = await self._solve_capsolver(page)
            
            if cs_result:
                logger.info("[CAPTCHA] ✅ Capsolver solved!")
                self.stats['capsolver_solved'] += 1
                return True
        
        # Step 3: Fall back to 2captcha
        if self.twocaptcha_key and self.twocaptcha_key != 'your_2captcha_key_here':
            logger.info("[CAPTCHA] Step 3: 2captcha...")
            tc_result = await self._solve_twocaptcha(page)
            
            if tc_result:
                logger.info("[CAPTCHA] ✅ 2captcha solved!")
                self.stats['twocaptcha_solved'] += 1
                return True
        else:
            logger.warning("[CAPTCHA] No CAPTCHA solving service configured")
        
        self.stats['failed'] += 1
        return False
    
    async def _wait_browserbase(self, page, timeout: int = 30) -> bool:
        """
        Wait for BrowserBase Stealth to solve CAPTCHA.
        
        BrowserBase emits console messages during solving.
        """
        start_time = asyncio.get_event_loop().time()
        solving_started = False
        
        # Listen for console messages
        def handle_console(msg):
            nonlocal solving_started
            text = msg.text if hasattr(msg, 'text') else str(msg)
            
            if "browserbase-solving-started" in text:
                solving_started = True
                logger.info("[CAPTCHA] BrowserBase solving started")
            elif "browserbase-solving-finished" in text:
                logger.info("[CAPTCHA] BrowserBase solving finished")
        
        page.on("console", handle_console)
        
        try:
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                # Check if CAPTCHA is still present
                captcha_present = await self._check_captcha_exists(page)
                
                if not captcha_present:
                    if solving_started:
                        return True
                    # Might have been solved very quickly or no CAPTCHA
                    return True
                
                await asyncio.sleep(1)
            
            return False
            
        finally:
            try:
                page.remove_listener("console", handle_console)
            except:
                pass
    
    async def _check_captcha_exists(self, page) -> bool:
        """Check if CAPTCHA elements are present."""
        captcha_selectors = [
            'iframe[src*="recaptcha"]',
            'iframe[src*="captcha"]',
            '.g-recaptcha',
            '[data-sitekey]',
            '.captcha',
            '#captcha',
        ]
        
        for selector in captcha_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except:
                continue
        
        return False
    
    async def _solve_twocaptcha(self, page) -> bool:
        """
        Solve CAPTCHA using 2captcha service.
        
        Supports reCAPTCHA v2/v3, hCaptcha, etc.
        """
        if not self.twocaptcha_key:
            return False
        
        try:
            # Detect CAPTCHA type and sitekey
            captcha_info = await self._detect_captcha_type(page)
            
            if not captcha_info:
                logger.warning("[CAPTCHA] Could not detect CAPTCHA type")
                return False
            
            logger.info(f"[CAPTCHA] Detected {captcha_info['type']} with sitekey {captcha_info['sitekey'][:20]}...")
            
            # Submit to 2captcha
            solution = await self._submit_to_twocaptcha(
                captcha_type=captcha_info['type'],
                sitekey=captcha_info['sitekey'],
                pageurl=captcha_info['pageurl']
            )
            
            if solution:
                # Inject solution into page
                await self._inject_solution(page, captcha_info['type'], solution)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[CAPTCHA] 2captcha error: {e}")
            return False
    
    async def _solve_capsolver(self, page) -> bool:
        """
        Solve CAPTCHA using Capsolver service.
        Docs: https://docs.capsolver.com/
        """
        if not self.capsolver_key:
            return False
        
        try:
            # Detect CAPTCHA type
            captcha_info = await self._detect_captcha_type(page)
            if not captcha_info:
                logger.warning("[CAPTCHA] Could not detect CAPTCHA type for Capsolver")
                return False
            
            logger.info(f"[CAPTCHA] Submitting to Capsolver: {captcha_info['type']}")
            
            # Capsolver API endpoint
            api_url = "https://api.capsolver.com/createTask"
            
            # Build task payload
            task_type = {
                'recaptcha_v2': 'ReCaptchaV2TaskProxyless',
                'recaptcha_v3': 'ReCaptchaV3TaskProxyless',
                'hcaptcha': 'HCaptchaTaskProxyless',
            }.get(captcha_info['type'], 'ReCaptchaV2TaskProxyless')
            
            payload = {
                'clientKey': self.capsolver_key,
                'task': {
                    'type': task_type,
                    'websiteURL': captcha_info['pageurl'],
                    'websiteKey': captcha_info['sitekey'],
                }
            }
            
            async with aiohttp.ClientSession() as session:
                # Create task
                async with session.post(api_url, json=payload, timeout=30) as resp:
                    data = await resp.json()
                    
                    if data.get('errorId', 0) != 0:
                        logger.error(f"[CAPTCHA] Capsolver create task failed: {data}")
                        return False
                    
                    task_id = data.get('taskId')
                    logger.info(f"[CAPTCHA] Capsolver task ID: {task_id}")
                
                # Poll for result
                result_url = "https://api.capsolver.com/getTaskResult"
                start_time = asyncio.get_event_loop().time()
                
                while (asyncio.get_event_loop().time() - start_time) < 120:
                    await asyncio.sleep(5)
                    
                    async with session.post(
                        result_url,
                        json={'clientKey': self.capsolver_key, 'taskId': task_id},
                        timeout=30
                    ) as resp:
                        data = await resp.json()
                        
                        if data.get('errorId', 0) != 0:
                            logger.error(f"[CAPTCHA] Capsolver error: {data}")
                            return False
                        
                        status = data.get('status')
                        if status == 'ready':
                            solution = data.get('solution', {}).get('gRecaptchaResponse')
                            if solution:
                                logger.info("[CAPTCHA] Capsolver solution received")
                                await self._inject_solution(page, captcha_info['type'], solution)
                                return True
                        
                        if status == 'processing':
                            continue
                        
                        logger.warning(f"[CAPTCHA] Capsolver unknown status: {status}")
                        return False
            
            logger.warning("[CAPTCHA] Capsolver timeout")
            return False
            
        except Exception as e:
            logger.error(f"[CAPTCHA] Capsolver error: {e}")
            return False
    
    async def _detect_captcha_type(self, page) -> Optional[dict]:
        """Detect CAPTCHA type and extract parameters."""
        info = {'pageurl': page.url}
        
        # Check for reCAPTCHA v2
        recaptcha = await page.locator('.g-recaptcha').first
        if await recaptcha.count() > 0:
            info['type'] = 'recaptcha_v2'
            sitekey = await recaptcha.get_attribute('data-sitekey')
            if sitekey:
                info['sitekey'] = sitekey
                return info
        
        # Check for invisible reCAPTCHA
        recaptcha_v3 = await page.locator('[data-sitekey]').first
        if await recaptcha_v3.count() > 0:
            sitekey = await recaptcha_v3.get_attribute('data-sitekey')
            if sitekey:
                info['type'] = 'recaptcha_v3'
                info['sitekey'] = sitekey
                return info
        
        # Check for hCaptcha
        hcaptcha = await page.locator('.h-captcha').first
        if await hcaptcha.count() > 0:
            sitekey = await hcaptcha.get_attribute('data-sitekey')
            if sitekey:
                info['type'] = 'hcaptcha'
                info['sitekey'] = sitekey
                return info
        
        # Check for iframe-based CAPTCHA
        iframe = await page.locator('iframe[src*="recaptcha/api2"]').first
        if await iframe.count() > 0:
            src = await iframe.get_attribute('src')
            # Extract sitekey from src
            match = __import__('re').search(r'k=([^&]+)', src)
            if match:
                info['type'] = 'recaptcha_v2'
                info['sitekey'] = match.group(1)
                return info
        
        return None
    
    async def _submit_to_twocaptcha(
        self,
        captcha_type: str,
        sitekey: str,
        pageurl: str,
        timeout: int = 120
    ) -> Optional[str]:
        """Submit CAPTCHA to 2captcha and get solution."""
        
        # Map captcha types to 2captcha methods
        method_map = {
            'recaptcha_v2': 'userrecaptcha',
            'recaptcha_v3': 'userrecaptcha',
            'hcaptcha': 'hcaptcha',
        }
        
        method = method_map.get(captcha_type, 'userrecaptcha')
        
        async with aiohttp.ClientSession() as session:
            # Step 1: Submit CAPTCHA
            submit_url = 'http://2captcha.com/in.php'
            params = {
                'key': self.twocaptcha_key,
                'method': method,
                'googlekey': sitekey,
                'pageurl': pageurl,
                'json': 1,
            }
            
            if captcha_type == 'recaptcha_v3':
                params['version'] = 'v3'
            
            try:
                async with session.post(submit_url, data=params, timeout=30) as resp:
                    data = await resp.json()
                    
                    if data.get('status') != 1:
                        logger.error(f"[CAPTCHA] 2captcha submit failed: {data}")
                        return None
                    
                    captcha_id = data.get('request')
                    logger.info(f"[CAPTCHA] 2captcha task ID: {captcha_id}")
            except Exception as e:
                logger.error(f"[CAPTCHA] Submit error: {e}")
                return None
            
            # Step 2: Poll for solution
            result_url = 'http://2captcha.com/res.php'
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(5)
                
                try:
                    async with session.get(
                        result_url,
                        params={
                            'key': self.twocaptcha_key,
                            'action': 'get',
                            'id': captcha_id,
                            'json': 1,
                        },
                        timeout=30
                    ) as resp:
                        data = await resp.json()
                        
                        if data.get('status') == 1:
                            solution = data.get('request')
                            logger.info("[CAPTCHA] 2captcha solution received")
                            return solution
                        
                        if data.get('request') != 'CAPCHA_NOT_READY':
                            logger.error(f"[CAPTCHA] 2captcha error: {data}")
                            return None
                            
                except Exception as e:
                    logger.warning(f"[CAPTCHA] Poll error: {e}")
                    continue
        
        logger.warning("[CAPTCHA] 2captcha timeout")
        return None
    
    async def _inject_solution(self, page, captcha_type: str, solution: str):
        """Inject 2captcha solution into the page."""
        if captcha_type in ['recaptcha_v2', 'recaptcha_v3']:
            # Inject g-recaptcha-response
            await page.evaluate(f'''
                document.getElementById("g-recaptcha-response").innerHTML="{solution}";
            ''')
        
        # Trigger form submission or callback
        await page.evaluate('''
            if (typeof grecaptcha !== 'undefined') {
                grecaptcha.getResponse = function() { return arguments; };
            }
        ''')


# Singleton
_solver = None


def get_captcha_solver() -> CaptchaSolver:
    """Get singleton CAPTCHA solver."""
    global _solver
    if _solver is None:
        _solver = CaptchaSolver()
    return _solver
