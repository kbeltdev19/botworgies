"""
Dynamic Company Discovery - Find companies using specific ATS platforms.

Since there's no public directory, we use multiple strategies:
1. Curated lists (growing over time)
2. Industry categorization
3. Company size tiers
4. User-added companies
"""

from typing import List, Set, Dict, Optional
from dataclasses import dataclass
import aiohttp
import asyncio
import json
import os


@dataclass
class Company:
    """Company with ATS information."""
    name: str
    slug: str  # URL-friendly name
    ats: str  # 'greenhouse', 'lever', 'ashby', etc.
    industry: str = "tech"
    size: str = "startup"  # startup, growth, enterprise
    verified: bool = True


class CompanyDiscovery:
    """
    Discovers and manages companies across different ATS platforms.
    
    Features:
    - Curated lists by industry/size
    - Verifies if company still uses the ATS
    - Persists discovered companies
    - Expands list over time
    """
    
    # Curated company lists by ATS
    GREENHOUSE_COMPANIES = {
        # Tech Giants
        "enterprise": [
            "stripe", "airbnb", "netflix", "coinbase", "doordash",
            "instacart", "pinterest", "twitch", "lyft", "snap",
            "dropbox", "cloudflare", "datadog", "mongodb", "elastic",
            "confluent", "hashicorp", "snowflake", "databricks", "palantir",
        ],
        # Growth Stage
        "growth": [
            "figma", "notion", "plaid", "brex", "ramp",
            "gusto", "lattice", "retool", "vercel", "linear",
            "mercury", "rippling", "anduril", "scale", "anthropic",
            "airtable", "webflow", "loom", "miro", "zapier",
            "deel", "remote", "oyster", "papaya", "velocity",
            "maven", "replit", "railway", "render", "fly",
            "supabase", "planetscale", "neon", "turso", "upstash",
        ],
        # Startups
        "startup": [
            "raycast", "arc", "perplexity", "cursor", "v0",
            "cal", "dub", "resend", "trigger", "inngest",
            "highlight", "axiom", "baselime", "checkly", "grafbase",
            "convex", "liveblocks", "partykit", "electric-sql", "drizzle",
        ],
        # AI/ML Focused
        "ai": [
            "anthropic", "openai", "cohere", "huggingface", "replicate",
            "modal", "anyscale", "weights-biases", "labelbox", "scale",
            "together", "mistral", "perplexity", "character", "inflection",
        ],
        # Fintech
        "fintech": [
            "stripe", "plaid", "brex", "ramp", "mercury",
            "square", "affirm", "chime", "robinhood", "coinbase",
            "kraken", "gemini", "anchorage", "fireblocks", "chainalysis",
        ],
        # Developer Tools
        "devtools": [
            "vercel", "netlify", "railway", "render", "fly",
            "supabase", "planetscale", "prisma", "hasura", "grafbase",
            "github", "gitlab", "bitbucket", "sourcegraph", "linear",
            "sentry", "datadog", "newrelic", "pagerduty", "opsgenie",
        ],
    }
    
    LEVER_COMPANIES = {
        "growth": [
            "notion", "figma", "loom", "pitch", "raycast",
            "height", "cal", "vitally", "mercury", "brex",
            "rippling", "retool", "webflow", "airtable", "miro",
        ],
        "startup": [
            "linear", "railway", "render", "supabase", "convex",
            "trigger", "resend", "dub", "cal", "paperplane",
        ],
    }
    
    ASHBY_COMPANIES = {
        "growth": [
            "notion", "ramp", "deel", "remote", "lattice",
            "gusto", "rippling", "finch", "merge", "plaid",
        ],
    }
    
    def __init__(self, cache_path: str = None):
        self.cache_path = cache_path or "/tmp/company_cache.json"
        self.verified_companies: Dict[str, List[Company]] = {
            "greenhouse": [],
            "lever": [],
            "ashby": [],
        }
        self._load_cache()
    
    def _load_cache(self):
        """Load cached company data."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path) as f:
                    data = json.load(f)
                    # Convert back to Company objects
                    for ats, companies in data.items():
                        self.verified_companies[ats] = [
                            Company(**c) for c in companies
                        ]
            except Exception:
                pass
    
    def _save_cache(self):
        """Save company data to cache."""
        try:
            data = {}
            for ats, companies in self.verified_companies.items():
                data[ats] = [
                    {
                        "name": c.name,
                        "slug": c.slug,
                        "ats": c.ats,
                        "industry": c.industry,
                        "size": c.size,
                        "verified": c.verified,
                    }
                    for c in companies
                ]
            with open(self.cache_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
    
    def get_companies(
        self,
        ats: str,
        industries: List[str] = None,
        sizes: List[str] = None,
        limit: int = None
    ) -> List[str]:
        """
        Get company slugs for a specific ATS.
        
        Args:
            ats: 'greenhouse', 'lever', or 'ashby'
            industries: Filter by industry ['ai', 'fintech', 'devtools', etc.]
            sizes: Filter by size ['startup', 'growth', 'enterprise']
            limit: Max companies to return
        
        Returns:
            List of company slugs
        """
        companies = set()
        
        if ats == "greenhouse":
            source = self.GREENHOUSE_COMPANIES
        elif ats == "lever":
            source = self.LEVER_COMPANIES
        elif ats == "ashby":
            source = self.ASHBY_COMPANIES
        else:
            return []
        
        # Collect from selected categories
        categories = []
        
        if industries:
            categories.extend(industries)
        if sizes:
            categories.extend(sizes)
        
        if not categories:
            # Use all categories
            categories = list(source.keys())
        
        for category in categories:
            if category in source:
                companies.update(source[category])
        
        result = list(companies)
        
        if limit:
            result = result[:limit]
        
        return result
    
    async def verify_company(self, slug: str, ats: str) -> bool:
        """
        Verify that a company still uses the specified ATS.
        
        Args:
            slug: Company slug (e.g., 'stripe')
            ats: ATS platform ('greenhouse', 'lever', 'ashby')
        
        Returns:
            True if company uses the ATS
        """
        try:
            async with aiohttp.ClientSession() as session:
                if ats == "greenhouse":
                    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
                elif ats == "lever":
                    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
                elif ats == "ashby":
                    url = f"https://jobs.ashbyhq.com/{slug}"
                else:
                    return False
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
                    
        except Exception:
            return False
    
    async def discover_and_verify(
        self,
        ats: str,
        industries: List[str] = None,
        sizes: List[str] = None,
        max_companies: int = 50
    ) -> List[str]:
        """
        Get companies and verify they're still using the ATS.
        
        Returns only verified companies.
        """
        candidates = self.get_companies(ats, industries, sizes, limit=max_companies * 2)
        
        verified = []
        semaphore = asyncio.Semaphore(10)  # Limit concurrent checks
        
        async def check(slug):
            async with semaphore:
                if await self.verify_company(slug, ats):
                    return slug
                return None
        
        results = await asyncio.gather(*[check(s) for s in candidates])
        verified = [r for r in results if r]
        
        return verified[:max_companies]
    
    def add_company(self, slug: str, ats: str, industry: str = "tech", size: str = "startup"):
        """Add a new company to the discovery list."""
        company = Company(
            name=slug.replace("-", " ").title(),
            slug=slug,
            ats=ats,
            industry=industry,
            size=size,
            verified=False  # Will be verified on next search
        )
        self.verified_companies[ats].append(company)
        self._save_cache()
    
    def get_all_companies_flat(self) -> Dict[str, List[str]]:
        """Get all companies as flat lists by ATS."""
        return {
            "greenhouse": self.get_companies("greenhouse"),
            "lever": self.get_companies("lever"),
            "ashby": self.get_companies("ashby"),
        }


# Convenience function
def get_default_companies(ats: str, limit: int = 50) -> List[str]:
    """Quick access to company list."""
    discovery = CompanyDiscovery()
    return discovery.get_companies(ats, limit=limit)


async def test_discovery():
    """Test company discovery."""
    discovery = CompanyDiscovery()
    
    print("=== Greenhouse Companies ===")
    companies = discovery.get_companies("greenhouse", industries=["ai", "fintech"])
    print(f"AI + Fintech: {len(companies)} companies")
    print(f"Sample: {companies[:10]}")
    
    print("\n=== Verifying Companies ===")
    verified = await discovery.discover_and_verify("greenhouse", sizes=["startup"], max_companies=10)
    print(f"Verified startups: {verified}")


if __name__ == "__main__":
    asyncio.run(test_discovery())
