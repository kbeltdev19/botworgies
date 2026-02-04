#!/usr/bin/env python3
"""
Smart Resume Manager - Manage multiple resume versions.

Part of UX improvements for tailored applications.
"""

import os
import hashlib
from typing import Dict, Optional, List
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResumeVersion:
    """A tailored resume version."""
    role_type: str
    path: str
    created_at: str
    file_hash: str


class ResumeManager:
    """
    Manage multiple tailored resume versions.
    
    Features:
    - Create tailored versions for different role types
    - Cache versions to avoid regeneration
    - Track which version was used for which application
    """
    
    def __init__(self, base_resume_path: str, cache_dir: str = "data/resumes/tailored"):
        self.base_path = Path(base_resume_path)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.versions: Dict[str, ResumeVersion] = {}
        self._load_existing_versions()
    
    def _load_existing_versions(self):
        """Load existing tailored versions from cache."""
        if not self.cache_dir.exists():
            return
        
        for file in self.cache_dir.glob("tailored_*.pdf"):
            role_type = file.stem.replace("tailored_", "")
            file_hash = self._hash_file(file)
            
            from datetime import datetime
            self.versions[role_type] = ResumeVersion(
                role_type=role_type,
                path=str(file),
                created_at=datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                file_hash=file_hash
            )
        
        if self.versions:
            logger.info(f"[ResumeManager] Loaded {len(self.versions)} cached versions")
    
    def _hash_file(self, path: Path) -> str:
        """Hash file contents for change detection."""
        try:
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except:
            return ""
    
    async def get_or_create_version(self, role_type: str) -> str:
        """
        Get tailored resume for role type, creating if needed.
        
        Args:
            role_type: Type of role (software_engineer, customer_success, etc.)
            
        Returns:
            Path to tailored resume
        """
        # Check if we have a cached version
        if role_type in self.versions:
            version = self.versions[role_type]
            # Verify file still exists and matches hash
            if Path(version.path).exists():
                current_hash = self._hash_file(Path(version.path))
                if current_hash == version.file_hash:
                    logger.debug(f"[ResumeManager] Using cached {role_type} version")
                    return version.path
        
        # Create new version
        return await self._create_tailored_version(role_type)
    
    async def _create_tailored_version(self, role_type: str) -> str:
        """Create AI-tailored resume for role type."""
        from ai.resume_templates import get_template_manager
        
        logger.info(f"[ResumeManager] Creating tailored version for {role_type}")
        
        # Read base resume
        resume_text = await self._read_resume(self.base_path)
        
        # Apply template
        template_manager = get_template_manager()
        result = template_manager.get_tailored_resume(
            resume_text,
            role_type.replace('_', ' ').title(),
            use_ai_fallback=False  # Use templates first
        )
        
        # Save tailored version
        output_path = self.cache_dir / f"tailored_{role_type}.pdf"
        await self._save_resume(result['resume'], output_path)
        
        # Cache version
        from datetime import datetime
        self.versions[role_type] = ResumeVersion(
            role_type=role_type,
            path=str(output_path),
            created_at=datetime.now().isoformat(),
            file_hash=self._hash_file(output_path)
        )
        
        return str(output_path)
    
    async def _read_resume(self, path: Path) -> str:
        """Read resume file (PDF or text)."""
        if path.suffix.lower() == '.pdf':
            # Use existing PDF extraction
            try:
                import PyPDF2
                with open(path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    return text
            except Exception as e:
                logger.error(f"[ResumeManager] Failed to read PDF: {e}")
                return ""
        else:
            # Text file
            with open(path, 'r') as f:
                return f.read()
    
    async def _save_resume(self, content: str, path: Path):
        """Save resume content (as text for now)."""
        # For now, save as text. In production, convert to PDF
        text_path = path.with_suffix('.txt')
        with open(text_path, 'w') as f:
            f.write(content)
        
        # Copy base PDF as placeholder
        if self.base_path.exists() and not path.exists():
            import shutil
            shutil.copy(self.base_path, path)
    
    def get_version_for_job(self, job_title: str) -> str:
        """
        Get appropriate resume version for job title.
        
        Args:
            job_title: Job title
            
        Returns:
            Path to best resume version
        """
        from ai.resume_templates import get_template_manager
        
        # Detect role type from job title
        template_manager = get_template_manager()
        role_type = template_manager.detect_role_type(job_title)
        
        if role_type and role_type in self.versions:
            return self.versions[role_type].path
        
        # Fall back to base resume
        return str(self.base_path)
    
    def list_versions(self) -> List[Dict]:
        """List all available versions."""
        return [
            {
                'role_type': v.role_type,
                'path': v.path,
                'created_at': v.created_at,
            }
            for v in self.versions.values()
        ]
    
    def clear_cache(self):
        """Clear all tailored versions."""
        for version in self.versions.values():
            try:
                Path(version.path).unlink(missing_ok=True)
                # Also delete text version
                Path(version.path).with_suffix('.txt').unlink(missing_ok=True)
            except:
                pass
        
        self.versions.clear()
        logger.info("[ResumeManager] Cache cleared")
    
    def get_stats(self) -> Dict:
        """Get manager statistics."""
        return {
            'cached_versions': len(self.versions),
            'cache_dir': str(self.cache_dir),
            'base_resume': str(self.base_path),
            'versions': self.list_versions(),
        }


# Singleton
_manager: Optional[ResumeManager] = None


def get_resume_manager(base_resume_path: Optional[str] = None) -> ResumeManager:
    """Get global resume manager."""
    global _manager
    if _manager is None:
        if base_resume_path is None:
            raise ValueError("base_resume_path required for first initialization")
        _manager = ResumeManager(base_resume_path)
    return _manager
