"""
Indeed RSS Feed Scraper

Uses Indeed's RSS feeds (zero blocking, high volume)
RSS feeds are specifically designed for aggregation and don't have anti-bot measures.
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote_plus, urlparse, parse_qs
import logging

from . import BaseJobBoardScraper, JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


class IndeedRssScraper(BaseJobBoardScraper):
    """
    Scraper for Indeed using RSS feeds.
    
    RSS feeds are the most reliable way to scrape Indeed:
    - No JavaScript required
    - No rate limiting
    - No CAPTCHAs
    - Returns structured XML
    
    Limitations:
    - Limited to ~20 results per feed
    - Less metadata than full site
    - No salary data in RSS
    """
    
    RSS_BASE = "https://rss.indeed.com/rss"
    
    # RSS namespace
    NS = {'content': 'http://purl.org/rss/1.0/modules/content/'}
    
    def get_default_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0 (compatible; JobBot/1.0)',
            'Accept': 'application/rss+xml, application/xml, text/xml',
        }
        
    def get_ats_type(self, url: str) -> Optional[str]:
        """Indeed jobs use Indeed's internal ATS or redirect externally."""
        if 'indeed.com' in url.lower():
            return 'indeed'
        return None
        
    def _build_rss_url(self, criteria: SearchCriteria) -> str:
        """Build Indeed RSS feed URL."""
        params = []
        
        # Query
        if criteria.query:
            params.append(f"q={quote_plus(criteria.query)}")
            
        # Location
        if criteria.location:
            params.append(f"l={quote_plus(criteria.location)}")
        elif criteria.remote_only:
            params.append(f"l=remote")
            
        # Radius
        if criteria.radius:
            params.append(f"radius={criteria.radius}")
            
        # Posted within
        if criteria.posted_within_days:
            params.append(f"fromage={criteria.posted_within_days}")
            
        # Employment type
        if criteria.employment_type:
            emp_map = {
                'fulltime': 'fulltime',
                'contract': 'contract',
                'parttime': 'parttime',
                'internship': 'internship',
            }
            if criteria.employment_type.lower() in emp_map:
                params.append(f"jt={emp_map[criteria.employment_type.lower()]}")
                
        # Sort by date
        params.append("sort=date")
        
        url = self.RSS_BASE
        if params:
            url += "?" + "&".join(params)
            
        return url
        
    def _parse_rss_date(self, date_str: str) -> Optional[datetime]:
        """Parse RSS date format (RFC 822)."""
        try:
            # Format: Mon, 22 Jan 2024 15:30:00 GMT
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            try:
                # Try without timezone
                return datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            except ValueError:
                return None
                
    def _extract_job_id(self, url: str) -> str:
        """Extract Indeed job ID from URL."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Try various ID patterns
        if 'jk' in params:
            return params['jk'][0]
        
        # Extract from path
        match = re.search(r'jk=([a-f0-9]+)', url)
        if match:
            return match.group(1)
            
        # Use URL hash as fallback
        return hash(url) % 10000000
        
    def _parse_job_from_item(self, item: ET.Element) -> Optional[JobPosting]:
        """Parse a single RSS item into a JobPosting."""
        try:
            # Title format: "Job Title - Company Name"
            title_elem = item.find('title')
            if title_elem is None or not title_elem.text:
                return None
                
            full_title = title_elem.text.strip()
            
            # Split title - format varies
            if ' - ' in full_title:
                parts = full_title.rsplit(' - ', 1)
                title = parts[0].strip()
                company = parts[1].strip()
            else:
                title = full_title
                company = "Unknown"
                
            # Link
            link_elem = item.find('link')
            if link_elem is None or not link_elem.text:
                return None
            url = link_elem.text.strip()
            job_id = self._extract_job_id(url)
            
            # Description
            desc_elem = item.find('description')
            description = desc_elem.text if desc_elem is not None else ""
            
            # Clean HTML from description
            if description:
                description = re.sub(r'<[^>]+>', ' ', description)
                description = re.sub(r'\s+', ' ', description).strip()
                
            # Published date
            date_elem = item.find('pubDate')
            posted_date = None
            if date_elem is not None and date_elem.text:
                posted_date = self._parse_rss_date(date_elem.text)
                
            # Try to extract location from description
            location = "Unknown"
            location_match = re.search(r'in ([^,]+, [A-Z]{2})', description)
            if location_match:
                location = location_match.group(1)
            elif 'remote' in description.lower():
                location = "Remote"
                
            # Detect remote
            remote = 'remote' in title.lower() or 'remote' in location.lower()
            
            # Source attribution
            source_elem = item.find('source')
            if source_elem is not None:
                source_url = source_elem.get('url', '')
            else:
                source_url = url
                
            return JobPosting(
                id=f"indeed_{job_id}",
                title=title,
                company=company,
                location=location,
                description=description[:500],  # RSS description is truncated
                url=url,
                source='indeed_rss',
                posted_date=posted_date,
                remote=remote,
                easy_apply=False,  # RSS doesn't indicate Easy Apply
                apply_url=url,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Indeed RSS item: {e}")
            return None
            
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search Indeed via RSS feed."""
        url = self._build_rss_url(criteria)
        
        try:
            xml_content = await self.fetch_text(url)
            
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Find all items
            channel = root.find('channel')
            if channel is None:
                logger.warning("No channel found in Indeed RSS feed")
                return []
                
            items = channel.findall('item')
            
            jobs = []
            for item in items:
                job = self._parse_job_from_item(item)
                if job:
                    jobs.append(job)
                    
            logger.info(f"Indeed RSS: Found {len(jobs)} jobs")
            return jobs[:criteria.max_results]
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse Indeed RSS XML: {e}")
            return []
        except Exception as e:
            logger.error(f"Indeed RSS search failed: {e}")
            return []


# For testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        criteria = SearchCriteria(
            query="software engineer",
            location="Remote",
            remote_only=True,
            posted_within_days=3,
            max_results=20
        )
        
        async with IndeedRssScraper() as scraper:
            jobs = await scraper.search(criteria)
            print(f"Found {len(jobs)} jobs from Indeed RSS")
            for job in jobs[:5]:
                print(f"\n{job.title} at {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Posted: {job.posted_date}")
                print(f"  Remote: {job.remote}")
                
    asyncio.run(test())
