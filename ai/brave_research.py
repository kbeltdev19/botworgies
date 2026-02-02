"""
Brave Search Research Agent
Gathers company intelligence for cover letter personalization.
"""

import os
import asyncio
from typing import Optional, List, Dict
import httpx


class BraveResearchAgent:
    """
    Uses Brave Search API to research companies for personalized applications.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
    
    async def search(self, query: str, count: int = 5) -> List[Dict]:
        """Execute a Brave search query."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.base_url,
                headers=self.headers,
                params={"q": query, "count": count}
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return data.get("web", {}).get("results", [])
    
    async def research_company(self, company_name: str) -> Dict:
        """
        Gather comprehensive intel about a company for cover letter personalization.
        """
        # Run searches in parallel
        results = await asyncio.gather(
            self._search_news(company_name),
            self._search_tech_stack(company_name),
            self._search_culture(company_name),
            self._search_recent_funding(company_name),
            return_exceptions=True
        )
        
        return {
            "company": company_name,
            "recent_news": results[0] if not isinstance(results[0], Exception) else [],
            "tech_stack": results[1] if not isinstance(results[1], Exception) else [],
            "culture": results[2] if not isinstance(results[2], Exception) else [],
            "funding": results[3] if not isinstance(results[3], Exception) else [],
            "summary": self._generate_summary(results)
        }
    
    async def _search_news(self, company: str) -> List[Dict]:
        """Find recent news about the company."""
        query = f'"{company}" news announcement 2024 OR 2025'
        results = await self.search(query, count=3)
        
        return [
            {
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "url": r.get("url", ""),
                "age": r.get("age", "")
            }
            for r in results
        ]
    
    async def _search_tech_stack(self, company: str) -> List[str]:
        """Find the company's technology stack."""
        query = f'"{company}" engineering blog OR tech stack OR technology'
        results = await self.search(query, count=3)
        
        # Extract tech mentions from descriptions
        tech_keywords = [
            "python", "java", "javascript", "typescript", "go", "rust",
            "react", "vue", "angular", "node", "django", "flask",
            "aws", "gcp", "azure", "kubernetes", "docker",
            "postgresql", "mysql", "mongodb", "redis",
            "kafka", "rabbitmq", "graphql", "rest api"
        ]
        
        found_tech = set()
        for r in results:
            desc = (r.get("description", "") + r.get("title", "")).lower()
            for tech in tech_keywords:
                if tech in desc:
                    found_tech.add(tech.title())
        
        return list(found_tech)
    
    async def _search_culture(self, company: str) -> Dict:
        """Find info about company culture and values."""
        query = f'"{company}" company culture values mission'
        results = await self.search(query, count=3)
        
        # Look for culture-related content
        culture_keywords = ["mission", "values", "culture", "team", "diversity", "remote"]
        
        culture_info = {
            "values": [],
            "perks": [],
            "remote_friendly": False
        }
        
        for r in results:
            desc = r.get("description", "").lower()
            if "remote" in desc or "hybrid" in desc:
                culture_info["remote_friendly"] = True
            
            # Extract any values mentioned
            if "mission" in desc or "values" in desc:
                culture_info["values"].append(r.get("description", "")[:200])
        
        return culture_info
    
    async def _search_recent_funding(self, company: str) -> Dict:
        """Find recent funding or growth news."""
        query = f'"{company}" funding series raised investment 2024 OR 2025'
        results = await self.search(query, count=2)
        
        for r in results:
            desc = r.get("description", "").lower()
            if "raised" in desc or "funding" in desc or "series" in desc:
                return {
                    "has_recent_funding": True,
                    "details": r.get("description", "")[:300]
                }
        
        return {"has_recent_funding": False, "details": None}
    
    async def find_hiring_manager(self, company: str, role: str) -> Optional[Dict]:
        """
        Attempt to find relevant hiring manager or recruiter on LinkedIn.
        """
        query = f'site:linkedin.com/in "{company}" ("hiring" OR "recruiting" OR "talent") AND ("{role}" OR "engineering")'
        results = await self.search(query, count=5)
        
        recruiter_keywords = ["talent", "recruiting", "recruiter", "hiring", "people", "hr"]
        
        for r in results:
            title = r.get("title", "").lower()
            if any(kw in title for kw in recruiter_keywords):
                # Extract name from LinkedIn title format: "Name - Title - Company | LinkedIn"
                full_title = r.get("title", "")
                name = full_title.split(" - ")[0] if " - " in full_title else full_title.split(" | ")[0]
                
                return {
                    "name": name.strip(),
                    "profile_url": r.get("url", ""),
                    "title": r.get("description", "")[:100]
                }
        
        return None
    
    async def find_job_page(self, company: str) -> Optional[str]:
        """Find the company's careers/jobs page."""
        query = f'"{company}" careers jobs hiring'
        results = await self.search(query, count=5)
        
        career_keywords = ["careers", "jobs", "hiring", "join", "openings"]
        
        for r in results:
            url = r.get("url", "").lower()
            if any(kw in url for kw in career_keywords):
                return r.get("url")
        
        return None
    
    def _generate_summary(self, results: List) -> str:
        """Generate a brief summary for cover letter use."""
        parts = []
        
        # News
        if results[0] and not isinstance(results[0], Exception) and results[0]:
            parts.append(f"Recent news: {results[0][0].get('title', '')}")
        
        # Tech
        if results[1] and not isinstance(results[1], Exception) and results[1]:
            parts.append(f"Tech stack includes: {', '.join(results[1][:5])}")
        
        # Funding
        if results[3] and not isinstance(results[3], Exception):
            if results[3].get("has_recent_funding"):
                parts.append("Recently raised funding")
        
        return " | ".join(parts) if parts else "No specific intel found"


# Test function
async def test_brave():
    agent = BraveResearchAgent()
    
    print("Researching Stripe...")
    intel = await agent.research_company("Stripe")
    
    print(f"\nRecent News: {intel['recent_news']}")
    print(f"Tech Stack: {intel['tech_stack']}")
    print(f"Culture: {intel['culture']}")
    print(f"Funding: {intel['funding']}")
    print(f"\nSummary: {intel['summary']}")
    
    # Find hiring manager
    hm = await agent.find_hiring_manager("Stripe", "software engineer")
    print(f"\nHiring Manager: {hm}")


if __name__ == "__main__":
    asyncio.run(test_brave())
