#!/usr/bin/env python3
"""
External URL Extractor - Extract direct ATS URLs from job board listings.

This module navigates to job pages (Indeed, LinkedIn, etc.) and extracts
the actual application URLs (Greenhouse, Lever, Workday, etc.).
"""

import asyncio
import json
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of URL extraction."""
    original_url: str
    external_url: Optional[str]
    platform: str
    success: bool
    error: Optional[str] = None
    extracted_at: datetime = None
    
    def __post_init__(self):
        if self.extracted_at is None:
            self.extracted_at = datetime.now()


class ExternalURLExtractor:
    """
    Extract direct ATS URLs from job board pages.
    
    Supports:
    - Indeed (external apply button)
    - LinkedIn (external apply redirect)
    - ZipRecruiter
    """
    
    # Platform detection patterns
    ATS_PATTERNS = {
        'greenhouse': [
            r'boards\.greenhouse\.io',
            r'greenhouse\.io',
        ],
        'lever': [
            r'jobs\.lever\.co',
            r'lever\.co',
        ],
        'workday': [
            r'myworkdayjobs\.com',
            r'wd\d+\.myworkdayjobs\.com',
        ],
        'ashby': [
            r'jobs\.ashbyhq\.com',
        ],
        'breezy': [
            r'\.breezy\.hr',
        ],
        'smartrecruiters': [
            r'smartrecruiters\.com',
        ],
        'applytojob': [
            r'applytojob\.com',
        ],
        'recruitee': [
            r'recruitee\.com',
        ],
        'jobvite': [
            r'jobvite\.com',
        ],
    }
    
    def __init__(self, max_concurrent: int = 5, headless: bool = True):
        self.max_concurrent = max_concurrent
        self.headless = headless
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    def _detect_platform(self, url: str) -> str:
        """Detect ATS platform from URL."""
        url_lower = url.lower()
        for platform, patterns in self.ATS_PATTERNS.items():
            if any(re.search(p, url_lower) for p in patterns):
                return platform
        return 'unknown'
    
    async def extract_from_indeed(self, job_url: str) -> ExtractionResult:
        """
        Extract external apply URL from Indeed job page.
        
        Strategy:
        1. Navigate to Indeed job page
        2. Click "Apply" button or find external link
        3. Follow redirects to find final ATS URL
        """
        from adapters.handlers.browser_manager import BrowserManager
        
        async with self.semaphore:
            browser = None
            external_url = None
            error = None
            
            try:
                browser = BrowserManager(headless=self.headless)
                context, page = await browser.create_context()
                
                logger.debug(f"[Extractor] Navigating to Indeed: {job_url[:60]}...")
                
                # Navigate to job page
                response = await page.goto(
                    job_url, 
                    wait_until='domcontentloaded',
                    timeout=30000
                )
                
                if not response or response.status >= 400:
                    error = f"Page load failed: {response.status if response else 'no response'}"
                    return ExtractionResult(
                        original_url=job_url,
                        external_url=None,
                        platform='unknown',
                        success=False,
                        error=error
                    )
                
                await asyncio.sleep(2)  # Let page settle
                
                # Strategy 1: Look for direct external apply link
                external_selectors = [
                    # Greenhouse
                    'a[href*="greenhouse.io"]',
                    'a[href*="boards.greenhouse.io"]',
                    # Lever
                    'a[href*="jobs.lever.co"]',
                    'a[href*="lever.co"]',
                    # Workday
                    'a[href*="myworkdayjobs.com"]',
                    # Ashby
                    'a[href*="ashbyhq.com"]',
                    # Breezy
                    'a[href*="breezy.hr"]',
                    # SmartRecruiters
                    'a[href*="smartrecruiters.com"]',
                    # ApplyToJob
                    'a[href*="applytojob.com"]',
                    # General apply links
                    'a:has-text("Apply")',
                    'a:has-text("Apply Now")',
                    'button:has-text("Apply")',
                    'button:has-text("Apply on company site")',
                    '[data-testid="apply-button"]',
                ]
                
                for selector in external_selectors:
                    try:
                        element = page.locator(selector).first
                        if await element.count() > 0 and await element.is_visible():
                            href = await element.get_attribute('href')
                            if href:
                                # Resolve relative URLs
                                if href.startswith('/'):
                                    href = f"https://www.indeed.com{href}"
                                elif href.startswith('http'):
                                    # Check if this is an external ATS URL
                                    platform = self._detect_platform(href)
                                    if platform != 'unknown':
                                        external_url = href
                                        logger.info(f"[Extractor] Found {platform} URL: {href[:60]}...")
                                        break
                                    # Might be redirect, try to follow
                                    external_url = await self._follow_redirect(page, href)
                                    if external_url:
                                        break
                    except Exception as e:
                        logger.debug(f"[Extractor] Selector {selector} failed: {e}")
                        continue
                
                # Strategy 2: Check for apply button that opens external site
                if not external_url:
                    apply_button_selectors = [
                        'button:has-text("Apply on company site")',
                        'a:has-text("Apply on company site")',
                        '.ia-ApplyWithIndeedButton + a',  # Link next to Indeed apply
                    ]
                    
                    for selector in apply_button_selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.count() > 0:
                                href = await element.get_attribute('href')
                                if href:
                                    external_url = await self._follow_redirect(page, href)
                                    if external_url:
                                        break
                        except:
                            continue
                
                # Strategy 3: Look in job description for apply links
                if not external_url:
                    try:
                        # Get page content and search for ATS URLs
                        content = await page.content()
                        for platform, patterns in self.ATS_PATTERNS.items():
                            for pattern in patterns:
                                match = re.search(rf'https?://[^"\s<>]*{pattern}[^"\s<>]*', content)
                                if match:
                                    external_url = match.group(0)
                                    logger.info(f"[Extractor] Found {platform} URL in content: {external_url[:60]}...")
                                    break
                            if external_url:
                                break
                    except Exception as e:
                        logger.debug(f"[Extractor] Content search failed: {e}")
                
                await browser.close()
                
            except Exception as e:
                error = str(e)
                logger.warning(f"[Extractor] Failed to extract from {job_url[:60]}: {e}")
                if browser:
                    try:
                        await browser.close()
                    except:
                        pass
            
            platform = self._detect_platform(external_url) if external_url else 'unknown'
            
            return ExtractionResult(
                original_url=job_url,
                external_url=external_url,
                platform=platform,
                success=external_url is not None,
                error=error
            )
    
    async def _follow_redirect(self, page, url: str) -> Optional[str]:
        """Follow a URL and detect final destination."""
        try:
            # Open in new tab to preserve current page
            new_page = await page.context.new_page()
            
            response = await new_page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)
            
            final_url = new_page.url
            await new_page.close()
            
            # Check if final URL is an ATS
            platform = self._detect_platform(final_url)
            if platform != 'unknown':
                logger.info(f"[Extractor] Redirected to {platform}: {final_url[:60]}...")
                return final_url
            
            return None
            
        except Exception as e:
            logger.debug(f"[Extractor] Redirect follow failed: {e}")
            return None
    
    async def extract_batch(self, job_urls: List[str], source: str = 'indeed') -> List[ExtractionResult]:
        """
        Extract external URLs from a batch of job URLs.
        
        Args:
            job_urls: List of job page URLs
            source: Source platform ('indeed', 'linkedin', etc.)
        
        Returns:
            List of ExtractionResults
        """
        logger.info(f"[Extractor] Processing {len(job_urls)} {source} URLs...")
        
        results = []
        
        if source == 'indeed':
            tasks = [self.extract_from_indeed(url) for url in job_urls]
        else:
            logger.warning(f"[Extractor] Unsupported source: {source}")
            return []
        
        # Process with progress logging
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            
            if completed % 10 == 0:
                successful = sum(1 for r in results if r.success)
                logger.info(f"[Extractor] Progress: {completed}/{len(job_urls)} - {successful} external URLs found")
        
        successful = sum(1 for r in results if r.success)
        logger.info(f"[Extractor] Complete: {successful}/{len(job_urls)} external URLs extracted")
        
        return results
    
    def save_results(self, results: List[ExtractionResult], output_path: str):
        """Save extraction results to JSON."""
        data = {
            'extracted_at': datetime.now().isoformat(),
            'total_processed': len(results),
            'successful': sum(1 for r in results if r.success),
            'by_platform': {},
            'results': [
                {
                    'original_url': r.original_url,
                    'external_url': r.external_url,
                    'platform': r.platform,
                    'success': r.success,
                    'error': r.error,
                    'extracted_at': r.extracted_at.isoformat(),
                }
                for r in results
            ]
        }
        
        # Count by platform
        for r in results:
            if r.success:
                platform = r.platform
                data['by_platform'][platform] = data['by_platform'].get(platform, 0) + 1
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"[Extractor] Saved results to {output_path}")


async def test_extraction():
    """Test the URL extractor."""
    logging.basicConfig(level=logging.INFO)
    
    # Sample Indeed URLs to test
    test_urls = [
        "https://www.indeed.com/viewjob?jk=ea5a8e469824b4d5",
        "https://www.indeed.com/viewjob?jk=a185c2650f9935af",
        "https://www.indeed.com/viewjob?jk=2498b8595832a660",
    ]
    
    extractor = ExternalURLExtractor(max_concurrent=3)
    results = await extractor.extract_batch(test_urls, source='indeed')
    
    print("\nExtraction Results:")
    for result in results:
        status = "✅" if result.success else "❌"
        print(f"{status} {result.original_url[:60]}...")
        if result.success:
            print(f"   → {result.platform}: {result.external_url[:60]}...")
        elif result.error:
            print(f"   Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(test_extraction())
