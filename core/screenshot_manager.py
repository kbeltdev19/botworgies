"""
Centralized Screenshot Management Service

Eliminates duplication of screenshot logic across 20+ adapter files.
Provides consistent naming, metadata tracking, and HTML report generation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

from playwright.async_api import Page


@dataclass
class ScreenshotContext:
    """Context for a screenshot capture."""
    job_id: str
    platform: str
    step: int
    label: str
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Screenshot:
    """Represents a captured screenshot with metadata."""
    path: Path
    context: ScreenshotContext
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    page_content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def filename(self) -> str:
        return self.path.name
    
    @property
    def timestamp(self) -> datetime:
        return self.context.timestamp


@dataclass
class ScreenshotConfig:
    """Configuration for screenshot capture."""
    base_dir: Path
    naming_template: str = "{platform}_{job_id}_step{step:02d}_{label}_{timestamp}.png"
    full_page: bool = True
    element_highlight: bool = False
    create_html_report: bool = True
    max_screenshots: int = 50  # Per application


class ScreenshotManager:
    """
    Centralized screenshot capture and management.
    
    Replaces duplicated screenshot logic in 20+ adapter files.
    Provides consistent naming, metadata tracking, and reporting.
    
    Usage:
        manager = ScreenshotManager(ScreenshotConfig(base_dir=Path("./screenshots")))
        
        # Capture full page
        screenshot = await manager.capture(page, ScreenshotContext(
            job_id="job_123",
            platform="greenhouse",
            step=1,
            label="initial"
        ))
        
        # Capture element
        screenshot = await manager.capture_element(page, "#submit-btn", context)
        
        # Generate report
        report_path = manager.generate_html_report()
    """
    
    def __init__(self, config: ScreenshotConfig):
        self.config = config
        self.captured: List[Screenshot] = []
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create screenshot directories."""
        self.config.base_dir.mkdir(parents=True, exist_ok=True)
        (self.config.base_dir / "full_page").mkdir(exist_ok=True)
        (self.config.base_dir / "elements").mkdir(exist_ok=True)
    
    def _generate_path(self, context: ScreenshotContext, 
                      element_selector: Optional[str] = None) -> Path:
        """Generate screenshot path based on context."""
        timestamp = context.timestamp.strftime("%Y%m%d_%H%M%S")
        
        filename = self.config.naming_template.format(
            platform=context.platform,
            job_id=context.job_id.replace("/", "_"),
            step=context.step,
            label=context.label,
            timestamp=timestamp
        )
        
        if element_selector:
            subdir = "elements"
            filename = filename.replace(".png", f"_{self._sanitize_selector(element_selector)}.png")
        else:
            subdir = "full_page"
        
        return self.config.base_dir / subdir / filename
    
    def _sanitize_selector(self, selector: str) -> str:
        """Sanitize selector for filename."""
        return selector.replace("#", "").replace(".", "_").replace("[", "").replace("]", "")[:30]
    
    async def capture(self, page: Page, context: ScreenshotContext,
                     full_page: Optional[bool] = None) -> Screenshot:
        """
        Capture full page screenshot.
        
        Args:
            page: Playwright page
            context: Screenshot context (job_id, platform, step, label)
            full_page: Override config full_page setting
            
        Returns:
            Screenshot object with metadata
        """
        if len(self.captured) >= self.config.max_screenshots:
            raise RuntimeError(f"Max screenshots ({self.config.max_screenshots}) reached")
        
        path = self._generate_path(context)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        use_full_page = full_page if full_page is not None else self.config.full_page
        
        try:
            await page.screenshot(path=str(path), full_page=use_full_page)
            
            screenshot = Screenshot(
                path=path,
                context=context,
                page_url=page.url,
                page_title=await page.title(),
                metadata={"full_page": use_full_page}
            )
            
            self.captured.append(screenshot)
            return screenshot
            
        except Exception as e:
            # Fallback: try without full_page
            if use_full_page:
                await page.screenshot(path=str(path))
                return Screenshot(path=path, context=context, metadata={"fallback": True})
            raise
    
    async def capture_element(self, page: Page, selector: str, 
                             context: ScreenshotContext) -> Optional[Screenshot]:
        """
        Capture screenshot of specific element.
        
        Args:
            page: Playwright page
            selector: Element selector
            context: Screenshot context
            
        Returns:
            Screenshot object or None if element not found
        """
        try:
            element = page.locator(selector).first
            
            if await element.count() == 0:
                return None
            
            path = self._generate_path(context, selector)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            await element.screenshot(path=str(path))
            
            screenshot = Screenshot(
                path=path,
                context=context,
                page_url=page.url,
                page_title=await page.title(),
                metadata={"element_selector": selector}
            )
            
            self.captured.append(screenshot)
            return screenshot
            
        except Exception as e:
            return None
    
    async def capture_on_error(self, page: Page, 
                              context: ScreenshotContext) -> Screenshot:
        """Capture screenshot when error occurs."""
        error_context = ScreenshotContext(
            job_id=context.job_id,
            platform=context.platform,
            step=context.step,
            label=f"{context.label}_ERROR",
            timestamp=datetime.now()
        )
        return await self.capture(page, error_context, full_page=True)
    
    def get_timeline(self) -> List[Screenshot]:
        """Get all captured screenshots in chronological order."""
        return sorted(self.captured, key=lambda s: s.timestamp)
    
    def get_by_step(self, step: int) -> List[Screenshot]:
        """Get screenshots for a specific step."""
        return [s for s in self.captured if s.context.step == step]
    
    def get_by_label(self, label: str) -> List[Screenshot]:
        """Get screenshots with specific label."""
        return [s for s in self.captured if label in s.context.label]
    
    def generate_html_report(self, title: str = "Application Screenshot Report") -> Path:
        """
        Generate HTML report with all screenshots.
        
        Returns:
            Path to generated HTML file
        """
        if not self.config.create_html_report:
            return None
        
        report_path = self.config.base_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .timeline {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .screenshot {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .screenshot-header {{
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .screenshot-step {{
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .screenshot-label {{
            font-size: 16px;
            font-weight: 600;
            color: #212529;
            margin-top: 5px;
        }}
        .screenshot-meta {{
            font-size: 12px;
            color: #6c757d;
            margin-top: 5px;
        }}
        .screenshot-img {{
            max-width: 100%;
            height: auto;
            display: block;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .stat {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: 700;
            color: #212529;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6c757d;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{len(self.captured)}</div>
                <div class="stat-label">Screenshots</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(set(s.context.platform for s in self.captured))}</div>
                <div class="stat-label">Platforms</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(set(s.context.job_id for s in self.captured))}</div>
                <div class="stat-label">Jobs</div>
            </div>
        </div>
    </div>
    
    <div class="timeline">
"""
        
        # Add each screenshot
        for screenshot in self.get_timeline():
            relative_path = screenshot.path.relative_to(self.config.base_dir)
            
            html += f"""
        <div class="screenshot">
            <div class="screenshot-header">
                <div class="screenshot-step">Step {screenshot.context.step}</div>
                <div class="screenshot-label">{screenshot.context.label}</div>
                <div class="screenshot-meta">
                    {screenshot.context.platform} | {screenshot.timestamp.strftime('%H:%M:%S')}
                    {f"| {screenshot.page_title[:50]}" if screenshot.page_title else ""}
                </div>
            </div>
            <img class="screenshot-img" src="{relative_path}" alt="{screenshot.context.label}" />
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        
        report_path.write_text(html, encoding='utf-8')
        return report_path
    
    def export_json(self, path: Optional[Path] = None) -> Path:
        """Export screenshot metadata to JSON."""
        if path is None:
            path = self.config.base_dir / f"screenshots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            "config": {
                "base_dir": str(self.config.base_dir),
                "full_page": self.config.full_page,
            },
            "screenshots": [
                {
                    "path": str(s.path),
                    "filename": s.filename,
                    "platform": s.context.platform,
                    "job_id": s.context.job_id,
                    "step": s.context.step,
                    "label": s.context.label,
                    "timestamp": s.timestamp.isoformat(),
                    "page_url": s.page_url,
                    "page_title": s.page_title,
                    "metadata": s.metadata,
                }
                for s in self.get_timeline()
            ]
        }
        
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        return path
    
    def clear(self):
        """Clear captured screenshots list."""
        self.captured = []


# Convenience function for quick usage
async def capture_application_screenshots(
    page: Page,
    job_id: str,
    platform: str,
    base_dir: Path = Path("./screenshots")
) -> ScreenshotManager:
    """
    Quick screenshot capture for an application.
    
    Usage:
        manager = await capture_application_screenshots(page, "job_123", "greenhouse")
        await manager.capture(page, ScreenshotContext(...))
    """
    config = ScreenshotConfig(base_dir=base_dir)
    return ScreenshotManager(config)
