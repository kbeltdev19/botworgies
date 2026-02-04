#!/usr/bin/env python3
"""
Job Description Optimizer - Reduce JD size while preserving key information.

Impact: 30-50% token reduction per tailoring call
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class JDSection:
    """A section of a job description."""
    name: str
    content: str
    priority: int  # Higher = more important


class JobDescriptionOptimizer:
    """
    Reduce JD size while preserving key information for AI processing.
    
    Strategy:
    1. Extract key sections (requirements, responsibilities, about)
    2. Remove fluff and boilerplate
    3. Prioritize requirements section
    4. Truncate to MAX_CHARS
    """
    
    # Maximum characters to send to AI (approx 4 chars per token)
    MAX_CHARS = 3000
    
    # Section priority (higher = more important)
    SECTION_PRIORITY = {
        'requirements': 100,
        'qualifications': 90,
        'responsibilities': 80,
        'role': 70,
        'about': 60,
        'company': 50,
        'benefits': 40,
        'perks': 30,
    }
    
    def optimize(self, job_description: str) -> str:
        """
        Extract relevant sections from JD.
        
        Args:
            job_description: Full job description text
            
        Returns:
            Optimized JD (max MAX_CHARS)
        """
        if not job_description:
            return ""
            
        # If already short enough, return as-is
        if len(job_description) <= self.MAX_CHARS:
            return job_description
        
        # Extract sections
        sections = self._extract_sections(job_description)
        
        # Combine sections by priority
        optimized = self._combine_sections(sections)
        
        return optimized[:self.MAX_CHARS]
    
    def _extract_sections(self, jd: str) -> List[JDSection]:
        """Extract key sections using regex patterns."""
        sections = []
        
        # Pattern groups for each section type
        patterns = {
            'requirements': [
                r'(?:requirements|qualifications|what you.ll need|must have|you should have)\s*[:\-]?\s*(.+?)(?=preferred|nice to have|benefits|about us|what we offer|$)',
                r'(?:you will|you have)\s*[:\-]?\s*(.+?)(?=we offer|about us|$)',
            ],
            'responsibilities': [
                r'(?:responsibilities|what you.ll do|the role|job description|position overview|key duties)\s*[:\-]?\s*(.+?)(?=requirements|qualifications|about us|benefits|$)',
                r'(?:in this role|as a)\s*[:\-]?\s*(.+?)(?=requirements|qualifications|$)',
            ],
            'about': [
                r'(?:about the role|position summary|overview)\s*[:\-]?\s*(.+?)(?=requirements|responsibilities|$)',
            ],
            'company': [
                r'(?:about us|who we are|company overview|about \w+)\s*[:\-]?\s*(.+?)(?=the role|requirements|responsibilities|$)',
            ],
            'benefits': [
                r'(?:benefits|perks|what we offer|compensation)\s*[:\-]?\s*(.+?)(?=about us|apply|$)',
            ]
        }
        
        for section_name, patterns_list in patterns.items():
            for pattern in patterns_list:
                match = re.search(pattern, jd, re.IGNORECASE | re.DOTALL)
                if match:
                    content = self._clean_text(match.group(1))
                    priority = self.SECTION_PRIORITY.get(section_name, 50)
                    
                    sections.append(JDSection(
                        name=section_name,
                        content=content,
                        priority=priority
                    ))
                    break  # Found this section, move to next
        
        # Sort by priority (descending)
        sections.sort(key=lambda s: s.priority, reverse=True)
        
        return sections
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove bullet point markers but keep content
        text = re.sub(r'^[\s•\-\*\+]+', ' ', text, flags=re.MULTILINE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _combine_sections(self, sections: List[JDSection]) -> str:
        """Combine sections with priority."""
        if not sections:
            return ""
        
        parts = []
        total_length = 0
        
        for section in sections:
            # Skip if adding this section would exceed limit
            section_header = f"{section.name.upper()}:"
            section_text = f"{section_header}\n{section.content}\n\n"
            
            if total_length + len(section_text) > self.MAX_CHARS:
                # Try to truncate this section
                remaining = self.MAX_CHARS - total_length - len(section_header) - 10
                if remaining > 100:  # Only add if we can fit meaningful content
                    truncated = section.content[:remaining].rsplit('.', 1)[0] + '.'
                    parts.append(f"{section_header}\n{truncated}")
                break
            
            parts.append(section_text)
            total_length += len(section_text)
        
        return "\n".join(parts)
    
    def extract_keywords(self, job_description: str) -> List[str]:
        """Extract key skills/requirements from JD."""
        optimized = self.optimize(job_description)
        
        # Simple keyword extraction
        keywords = []
        
        # Common skill patterns
        skill_patterns = [
            r'(?:proficiency in|experience with|knowledge of)\s+([\w\s]+?)(?:,|;|\.|\n|$)',
            r'(?:\b\w+\b)\s+(?:required|preferred|mandatory)',
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, optimized, re.IGNORECASE)
            for match in matches:
                keywords.append(match.strip())
        
        # Deduplicate and return
        return list(set(keywords))[:20]
    
    def get_compression_ratio(self, original: str, optimized: str) -> float:
        """Calculate compression ratio."""
        if not original:
            return 1.0
        return len(optimized) / len(original)


# Singleton instance
_optimizer: Optional[JobDescriptionOptimizer] = None


def get_optimizer() -> JobDescriptionOptimizer:
    """Get global optimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = JobDescriptionOptimizer()
    return _optimizer


def optimize_jd(job_description: str) -> str:
    """Convenience function to optimize a job description."""
    return get_optimizer().optimize(job_description)
