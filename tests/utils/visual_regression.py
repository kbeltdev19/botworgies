"""
Visual Regression Testing Helpers

Utilities for capturing, comparing, and analyzing screenshots
during E2E testing.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

try:
    from PIL import Image, ImageChops
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageChops = None


@dataclass
class ScreenshotComparison:
    """Result of comparing two screenshots."""
    baseline_path: str
    current_path: str
    diff_path: Optional[str]
    similarity_score: float  # 0.0 to 1.0
    differences_found: bool
    diff_pixels: int
    total_pixels: int
    metadata: Dict[str, Any]


@dataclass
class FormFieldState:
    """State of a form field at a point in time."""
    selector: str
    field_type: str
    label: str
    value: str
    is_filled: bool
    is_visible: bool
    is_required: bool
    is_valid: bool
    timestamp: str


class VisualRegressionHelper:
    """Helper class for visual regression testing."""
    
    def __init__(self, baseline_dir: str = "/tmp/baselines", 
                 output_dir: str = "/tmp/visual_diffs"):
        self.baseline_dir = Path(baseline_dir)
        self.output_dir = Path(output_dir)
        self.screenshot_history: List[Dict] = []
        
        # Create directories
        self.baseline_dir.mkdir(exist_ok=True, parents=True)
        self.output_dir.mkdir(exist_ok=True, parents=True)
    
    async def capture_form_state(self, page, step_name: str) -> Dict:
        """
        Capture both screenshot and form data at current state.
        
        Returns dict with:
        - screenshot_path
        - form_fields
        - page_title
        - url
        - timestamp
        """
        timestamp = datetime.now().isoformat()
        
        # Capture screenshot
        screenshot_filename = f"{step_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path = self.output_dir / screenshot_filename
        
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            screenshot_path = None
        
        # Capture form data
        form_data = await page.evaluate("""
            () => {
                const fields = [];
                const inputs = document.querySelectorAll('input, select, textarea');
                
                inputs.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const label = document.querySelector(`label[for="${el.id}"]`) ||
                                 el.closest('label') ||
                                 el.previousElementSibling;
                    
                    fields.push({
                        selector: el.id ? `#${el.id}` : el.name ? `[name="${el.name}"]` : el.tagName,
                        tag: el.tagName.toLowerCase(),
                        type: el.type,
                        name: el.name,
                        id: el.id,
                        label: label ? label.textContent.trim() : '',
                        value: el.value,
                        placeholder: el.placeholder,
                        is_filled: el.value.length > 0,
                        is_visible: el.offsetParent !== null,
                        is_required: el.required,
                        is_valid: el.checkValidity(),
                        bounding_box: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }
                    });
                });
                
                return {
                    fields: fields,
                    title: document.title,
                    url: window.location.href,
                    timestamp: new Date().toISOString()
                };
            }
        """)
        
        state = {
            "step_name": step_name,
            "screenshot_path": str(screenshot_path) if screenshot_path else None,
            "form_fields": form_data.get("fields", []),
            "page_title": form_data.get("title", ""),
            "url": form_data.get("url", ""),
            "timestamp": timestamp
        }
        
        self.screenshot_history.append(state)
        return state
    
    def compare_screenshots(self, baseline_path: str, current_path: str,
                           threshold: float = 0.95) -> ScreenshotComparison:
        """
        Compare two screenshots and return similarity metrics.
        
        Args:
            baseline_path: Path to baseline screenshot
            current_path: Path to current screenshot
            threshold: Similarity threshold (0.0-1.0)
        
        Returns:
            ScreenshotComparison object
        """
        if not PIL_AVAILABLE:
            return ScreenshotComparison(
                baseline_path=baseline_path,
                current_path=current_path,
                diff_path=None,
                similarity_score=0.0,
                differences_found=True,
                diff_pixels=0,
                total_pixels=0,
                metadata={"error": "PIL not available"}
            )
        
        try:
            # Load images
            baseline = Image.open(baseline_path).convert('RGB')
            current = Image.open(current_path).convert('RGB')
            
            # Ensure same size
            if baseline.size != current.size:
                current = current.resize(baseline.size)
            
            # Calculate diff
            diff = ImageChops.difference(baseline, current)
            
            # Count different pixels
            diff_pixels = 0
            total_pixels = baseline.size[0] * baseline.size[1]
            
            # Get bounding box of differences
            diff_bbox = diff.getbbox()
            
            if diff_bbox:
                # Calculate diff pixels
                diff_data = list(diff.getdata())
                diff_pixels = sum(1 for pixel in diff_data if pixel != (0, 0, 0))
                
                # Create diff visualization
                diff_path = self.output_dir / f"diff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                
                # Highlight differences in red
                diff_highlight = diff.copy()
                diff_highlight = diff_highlight.convert('RGBA')
                pixels = diff_highlight.load()
                
                for i in range(diff_highlight.size[0]):
                    for j in range(diff_highlight.size[1]):
                        if pixels[i, j] != (0, 0, 0, 255):
                            pixels[i, j] = (255, 0, 0, 128)
                
                # Overlay on current image
                overlay = Image.blend(current.convert('RGBA'), diff_highlight, 0.5)
                overlay.save(diff_path)
                
                differences_found = True
            else:
                diff_path = None
                diff_pixels = 0
                differences_found = False
            
            # Calculate similarity score
            similarity = 1.0 - (diff_pixels / total_pixels)
            
            return ScreenshotComparison(
                baseline_path=baseline_path,
                current_path=current_path,
                diff_path=str(diff_path) if diff_path else None,
                similarity_score=similarity,
                differences_found=differences_found and similarity < threshold,
                diff_pixels=diff_pixels,
                total_pixels=total_pixels,
                metadata={
                    "threshold": threshold,
                    "diff_bbox": diff_bbox
                }
            )
            
        except Exception as e:
            return ScreenshotComparison(
                baseline_path=baseline_path,
                current_path=current_path,
                diff_path=None,
                similarity_score=0.0,
                differences_found=True,
                diff_pixels=0,
                total_pixels=0,
                metadata={"error": str(e)}
            )
    
    def compare_form_states(self, state1: Dict, state2: Dict) -> List[Dict]:
        """
        Compare two form states and return differences.
        
        Returns list of differences with:
        - field selector
        - property that changed
        - old value
        - new value
        """
        differences = []
        
        fields1 = {f["selector"]: f for f in state1.get("form_fields", [])}
        fields2 = {f["selector"]: f for f in state2.get("form_fields", [])}
        
        # Check for new fields
        for selector, field2 in fields2.items():
            if selector not in fields1:
                differences.append({
                    "type": "added",
                    "selector": selector,
                    "field": field2
                })
            else:
                field1 = fields1[selector]
                # Check for changes
                for prop in ["value", "is_filled", "is_visible", "is_valid"]:
                    if field1.get(prop) != field2.get(prop):
                        differences.append({
                            "type": "changed",
                            "selector": selector,
                            "property": prop,
                            "old_value": field1.get(prop),
                            "new_value": field2.get(prop)
                        })
        
        # Check for removed fields
        for selector, field1 in fields1.items():
            if selector not in fields2:
                differences.append({
                    "type": "removed",
                    "selector": selector,
                    "field": field1
                })
        
        return differences
    
    def generate_visual_report(self, output_path: Optional[str] = None) -> str:
        """Generate HTML report of all captured states and comparisons."""
        if output_path is None:
            output_path = self.output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Visual Regression Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .step { border: 1px solid #ddd; margin: 20px 0; padding: 15px; }
        .step-header { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
        .screenshot { max-width: 100%; border: 1px solid #ccc; }
        .field-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .field-table th, .field-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .field-table th { background-color: #f2f2f2; }
        .filled { background-color: #d4edda; }
        .empty { background-color: #f8d7da; }
        .comparison { display: flex; gap: 20px; }
        .comparison img { max-width: 48%; }
    </style>
</head>
<body>
    <h1>Visual Regression Report</h1>
    <p>Generated: {}</p>
""".format(datetime.now().isoformat())
        
        for i, state in enumerate(self.screenshot_history):
            html += f"""
    <div class="step">
        <div class="step-header">Step {i+1}: {state['step_name']}</div>
        <p>URL: {state['url']}</p>
        <p>Title: {state['page_title']}</p>
        <p>Timestamp: {state['timestamp']}</p>
"""
            
            if state.get('screenshot_path'):
                html += f'<img class="screenshot" src="{state["screenshot_path"]}" /><br>'
            
            # Add form fields table
            if state.get('form_fields'):
                html += """
        <table class="field-table">
            <tr>
                <th>Field</th>
                <th>Type</th>
                <th>Label</th>
                <th>Value</th>
                <th>Filled</th>
                <th>Valid</th>
            </tr>
"""
                for field in state['form_fields']:
                    filled_class = 'filled' if field.get('is_filled') else 'empty'
                    html += f"""
            <tr class="{filled_class}">
                <td>{field.get('selector', '')}</td>
                <td>{field.get('type', field.get('tag', ''))}</td>
                <td>{field.get('label', '')}</td>
                <td>{field.get('value', '')[:50]}</td>
                <td>{'Yes' if field.get('is_filled') else 'No'}</td>
                <td>{'Yes' if field.get('is_valid') else 'No'}</td>
            </tr>
"""
                html += "</table>"
            
            html += "</div>"
        
        html += """
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        return str(output_path)
    
    def save_baseline(self, screenshot_path: str, name: str):
        """Save a screenshot as a new baseline."""
        baseline_path = self.baseline_dir / f"{name}.png"
        
        if PIL_AVAILABLE:
            img = Image.open(screenshot_path)
            img.save(baseline_path)
        else:
            import shutil
            shutil.copy(screenshot_path, baseline_path)
        
        return str(baseline_path)
    
    def load_baseline(self, name: str) -> Optional[str]:
        """Load path to baseline screenshot if it exists."""
        baseline_path = self.baseline_dir / f"{name}.png"
        if baseline_path.exists():
            return str(baseline_path)
        return None


class FormProgressTracker:
    """Track progress through multi-step forms."""
    
    def __init__(self):
        self.steps: List[Dict] = []
        self.current_step = 0
    
    async def record_step(self, page, step_name: str, action: str):
        """Record a step in the form process."""
        # Get current URL and title
        url = page.url
        title = await page.title()
        
        step = {
            "step_number": self.current_step,
            "step_name": step_name,
            "action": action,
            "url": url,
            "title": title,
            "timestamp": datetime.now().isoformat()
        }
        
        self.steps.append(step)
        self.current_step += 1
        return step
    
    def get_progress(self) -> Dict:
        """Get current progress summary."""
        return {
            "total_steps": len(self.steps),
            "current_step": self.current_step,
            "steps": self.steps,
            "is_complete": False  # Would be set based on success detection
        }
    
    def export_json(self, path: str):
        """Export progress to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.get_progress(), f, indent=2)


# Fuzzy matching utilities
def fuzzy_match_text(expected: str, actual: str, threshold: float = 0.8) -> Tuple[bool, float]:
    """
    Fuzzy match two strings.
    
    Returns:
        (is_match, similarity_score)
    """
    matcher = SequenceMatcher(None, expected.lower(), actual.lower())
    ratio = matcher.ratio()
    return ratio >= threshold, ratio


def find_best_match(target: str, candidates: List[str], threshold: float = 0.6) -> Optional[str]:
    """Find the best fuzzy match from a list of candidates."""
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        score = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    
    return best_match


# Element detection helpers
async def detect_elements_by_text(page, text: str, element_type: str = "*") -> List[Dict]:
    """
    Find elements containing specific text.
    
    Returns list of elements with:
    - selector
    - text content
    - bounding box
    """
    elements = await page.evaluate(f"""
        () => {{
            const results = [];
            const elements = document.querySelectorAll('{element_type}');
            
            elements.forEach(el => {{
                if (el.textContent.toLowerCase().includes('{text.lower()}')) {{
                    const rect = el.getBoundingClientRect();
                    results.push({{
                        tag: el.tagName.toLowerCase(),
                        id: el.id,
                        class: el.className,
                        text: el.textContent.trim().substring(0, 100),
                        selector: el.id ? `#${{el.id}}` : 
                                 el.className ? `.${{el.className.split(' ')[0]}}` : 
                                 el.tagName.toLowerCase(),
                        bounding_box: {{
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }}
                    }});
                }}
            }});
            
            return results;
        }}
    """)
    
    return elements


async def wait_for_visual_stability(page, timeout: int = 5000, check_interval: int = 500) -> bool:
    """
    Wait for page to become visually stable (no major changes).
    
    Useful for ensuring animations complete before taking screenshots.
    """
    import asyncio
    
    start_time = asyncio.get_event_loop().time()
    last_hash = None
    stable_count = 0
    
    while (asyncio.get_event_loop().time() - start_time) * 1000 < timeout:
        # Get screenshot hash
        screenshot = await page.screenshot()
        current_hash = hash(screenshot)
        
        if current_hash == last_hash:
            stable_count += 1
            if stable_count >= 2:  # Stable for 2 checks
                return True
        else:
            stable_count = 0
        
        last_hash = current_hash
        await asyncio.sleep(check_interval / 1000)
    
    return False  # Timeout


# Export utilities
__all__ = [
    'VisualRegressionHelper',
    'FormProgressTracker',
    'ScreenshotComparison',
    'FormFieldState',
    'fuzzy_match_text',
    'find_best_match',
    'detect_elements_by_text',
    'wait_for_visual_stability',
]
