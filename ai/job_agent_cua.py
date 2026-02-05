#!/usr/bin/env python3
"""
Job Agent CUA (Computer Use Agent) - Autonomous job application agent.

Inspired by BrowserBase + Stagehand Agent pattern:
- Uses vision (Kimi) + DOM analysis for form understanding
- Executes high-level tasks like "apply for this job"
- Handles complex multi-step forms autonomously
- Provides detailed action history and verification
"""

import asyncio
import base64
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import os
import aiohttp
from pathlib import Path

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the agent can take."""
    GOTO = "goto"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    UPLOAD = "upload"
    SCROLL = "scroll"
    WAIT = "wait"
    EXTRACT = "extract"
    THINK = "think"
    SUBMIT = "submit"


@dataclass
class AgentAction:
    """A single action taken by the agent."""
    action_type: ActionType
    description: str
    selector: str = ""
    value: str = ""
    coordinates: Optional[Tuple[int, int]] = None
    success: bool = False
    error: Optional[str] = None
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None


@dataclass
class AgentResult:
    """Result of agent execution."""
    success: bool
    message: str
    actions: List[AgentAction] = field(default_factory=list)
    completed: bool = False
    confirmation_id: Optional[str] = None
    error: Optional[str] = None
    final_url: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'completed': self.completed,
            'message': self.message,
            'confirmation_id': self.confirmation_id,
            'error': self.error,
            'final_url': self.final_url,
            'action_count': len(self.actions),
        }


class JobAgentCUA:
    """
    Computer Use Agent for job applications.
    
    Uses Kimi Vision to:
    1. Analyze page screenshots
    2. Plan actions (click, type, select)
    3. Execute actions with verification
    4. Handle errors and retry
    """
    
    def __init__(self, model: str = "moonshot-v1-8k-vision-preview"):
        self.model = model
        self.api_key = os.getenv('MOONSHOT_API_KEY')
        self.base_url = "https://api.moonshot.ai/v1"
        self.max_steps = 25
        
    async def initialize(self):
        """Initialize API key."""
        if not self.api_key:
            from dotenv import load_dotenv
            load_dotenv()
            self.api_key = os.getenv('MOONSHOT_API_KEY')
    
    async def execute(
        self,
        page,
        instruction: str,
        profile: Dict[str, Any],
        resume_path: str,
        max_steps: int = 25
    ) -> AgentResult:
        """
        Execute a high-level instruction like "apply for this job".
        
        Args:
            page: Playwright page
            instruction: High-level goal (e.g., "apply for this job")
            profile: User profile data
            resume_path: Path to resume PDF
            max_steps: Maximum steps to take
        
        Returns:
            AgentResult with success status and action history
        """
        result = AgentResult(
            success=False,
            message="",
            actions=[],
            completed=False
        )
        
        self.max_steps = max_steps
        initial_url = page.url
        
        logger.info(f"[Agent] Starting task: {instruction}")
        logger.info(f"[Agent] Initial URL: {initial_url}")
        
        try:
            for step in range(max_steps):
                logger.info(f"\n[Agent] Step {step + 1}/{max_steps}")
                
                # Take screenshot
                screenshot = await self._take_screenshot(page)
                
                # Get AI decision
                decision = await self._get_ai_decision(
                    screenshot=screenshot,
                    instruction=instruction,
                    profile=profile,
                    action_history=result.actions,
                    current_url=page.url
                )
                
                logger.info(f"[Agent] AI Decision: {decision.get('action', 'unknown')}")
                
                # Execute action
                action_result = await self._execute_action(
                    page=page,
                    decision=decision,
                    profile=profile,
                    resume_path=resume_path
                )
                
                result.actions.append(action_result)
                
                if not action_result.success:
                    logger.warning(f"[Agent] Action failed: {action_result.error}")
                
                # Check if task is complete
                if decision.get('task_complete', False):
                    logger.info("[Agent] Task marked as complete by AI")
                    result.completed = True
                    break
                
                # Small delay between actions
                await asyncio.sleep(1)
            
            # Verify completion
            verification = await self._verify_completion(page, initial_url, instruction)
            result.success = verification['success']
            result.message = verification['message']
            result.confirmation_id = verification.get('confirmation_id')
            result.final_url = page.url
            result.error = verification.get('error')
            
            logger.info(f"\n[Agent] Final Result: {result.success}")
            logger.info(f"[Agent] Message: {result.message}")
            
        except Exception as e:
            logger.error(f"[Agent] Execution error: {e}")
            result.error = str(e)
        
        return result
    
    async def _take_screenshot(self, page) -> bytes:
        """Take screenshot of current page."""
        return await page.screenshot(type='png', full_page=False)
    
    async def _get_ai_decision(
        self,
        screenshot: bytes,
        instruction: str,
        profile: Dict,
        action_history: List[AgentAction],
        current_url: str
    ) -> Dict:
        """
        Get AI decision on next action based on screenshot.
        
        Uses Kimi Vision to analyze the page and decide what to do next.
        """
        image_base64 = base64.b64encode(screenshot).decode('utf-8')
        
        # Build action history summary
        history_summary = ""
        if action_history:
            recent = action_history[-5:]  # Last 5 actions
            history_summary = "Recent actions:\n" + "\n".join([
                f"- {a.action_type.value}: {a.description} ({'✓' if a.success else '✗'})"
                for a in recent
            ])
        
        prompt = f"""You are an AI agent applying for jobs. Analyze the current page and decide the next action.

TASK: {instruction}

USER PROFILE:
- Name: {profile.get('first_name', '')} {profile.get('last_name', '')}
- Email: {profile.get('email', '')}
- Phone: {profile.get('phone', '')}
- Location: {profile.get('city', '')}, {profile.get('state', '')}

CURRENT URL: {current_url}

{history_summary}

Look at the screenshot and decide:
1. What is the current state of the page?
2. What needs to be done next?
3. Which specific element should be interacted with?

Respond in JSON format:
{{
    "observation": "What you see on the page",
    "thought": "Your reasoning about what to do",
    "action": "One of: goto, click, type, select, upload, scroll, wait, extract, submit, complete",
    "target": "CSS selector or description of target element",
    "value": "Value to type or select (if applicable)",
    "task_complete": false,
    "reason": "Why you chose this action"
}}

If the application appears to be successfully submitted (confirmation page, thank you message), set task_complete to true.
"""
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                                    {"type": "text", "text": prompt}
                                ]
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1500
                    }
                ) as response:
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    
                    # Extract JSON from response
                    try:
                        # Try to parse JSON directly
                        decision = json.loads(content)
                    except:
                        # Try to extract JSON from markdown
                        if '```json' in content:
                            json_str = content.split('```json')[1].split('```')[0]
                            decision = json.loads(json_str)
                        elif '```' in content:
                            json_str = content.split('```')[1].split('```')[0]
                            decision = json.loads(json_str)
                        else:
                            # Fallback
                            decision = {
                                "observation": "Failed to parse response",
                                "thought": content[:200],
                                "action": "wait",
                                "target": "",
                                "value": "",
                                "task_complete": False,
                                "reason": "Parse error"
                            }
                    
                    return decision
                    
        except Exception as e:
            logger.error(f"[Agent] AI decision error: {e}")
            return {
                "action": "wait",
                "task_complete": False,
                "reason": f"Error: {e}"
            }
    
    async def _execute_action(
        self,
        page,
        decision: Dict,
        profile: Dict,
        resume_path: str
    ) -> AgentAction:
        """Execute the decided action."""
        action_type_str = decision.get('action', 'wait').lower()
        target = decision.get('target', '')
        value = decision.get('value', '')
        
        # Map action string to ActionType
        action_map = {
            'goto': ActionType.GOTO,
            'click': ActionType.CLICK,
            'type': ActionType.TYPE,
            'select': ActionType.SELECT,
            'upload': ActionType.UPLOAD,
            'scroll': ActionType.SCROLL,
            'wait': ActionType.WAIT,
            'extract': ActionType.EXTRACT,
            'submit': ActionType.SUBMIT,
            'complete': ActionType.THINK,
        }
        
        action_type = action_map.get(action_type_str, ActionType.WAIT)
        
        action = AgentAction(
            action_type=action_type,
            description=decision.get('thought', 'No description'),
            selector=target,
            value=value
        )
        
        try:
            if action_type == ActionType.GOTO:
                await page.goto(value, wait_until='domcontentloaded')
                action.success = True
                
            elif action_type == ActionType.CLICK:
                # Try multiple selector strategies
                selectors = [target] if target.startswith('#') or target.startswith('.') or target.startswith('[') else [
                    f'text="{target}"',
                    f'button:has-text("{target}")',
                    f'a:has-text("{target}")',
                    target,
                ]
                
                for sel in selectors:
                    try:
                        elem = page.locator(sel).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.click()
                            action.success = True
                            break
                    except:
                        continue
                
                if not action.success:
                    action.error = f"Could not find element: {target}"
                    
            elif action_type == ActionType.TYPE:
                # Determine what to type based on field
                if 'name' in target.lower() and 'first' in target.lower():
                    value = profile.get('first_name', '')
                elif 'name' in target.lower() and ('last' in target.lower() or 'sur' in target.lower()):
                    value = profile.get('last_name', '')
                elif 'email' in target.lower():
                    value = profile.get('email', '')
                elif 'phone' in target.lower() or 'mobile' in target.lower():
                    value = profile.get('phone', '')
                
                selectors = [target] if target.startswith('#') or target.startswith('.') else [
                    f'input[name*="{target}" i]',
                    f'input[placeholder*="{target}" i]',
                    f'#{target}',
                ]
                
                for sel in selectors:
                    try:
                        elem = page.locator(sel).first
                        if await elem.count() > 0:
                            await elem.fill(value)
                            action.success = True
                            action.value = value
                            break
                    except:
                        continue
                
                if not action.success:
                    action.error = f"Could not find input: {target}"
                    
            elif action_type == ActionType.SELECT:
                selectors = [
                    f'select[name*="{target}" i]',
                    f'#{target}',
                ]
                
                for sel in selectors:
                    try:
                        elem = page.locator(sel).first
                        if await elem.count() > 0:
                            await elem.select_option(label=value)
                            action.success = True
                            break
                    except:
                        continue
                
                if not action.success:
                    action.error = f"Could not select: {target}"
                    
            elif action_type == ActionType.UPLOAD:
                if os.path.exists(resume_path):
                    selectors = [
                        'input[type="file"][accept*=".pdf"]',
                        'input[type="file"]',
                    ]
                    
                    for sel in selectors:
                        try:
                            elem = page.locator(sel).first
                            if await elem.count() > 0:
                                await elem.set_input_files(resume_path)
                                action.success = True
                                action.value = resume_path
                                break
                        except:
                            continue
                
                if not action.success:
                    action.error = "Could not upload file"
                    
            elif action_type == ActionType.SUBMIT:
                selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Submit")',
                    'button:has-text("Apply")',
                ]
                
                for sel in selectors:
                    try:
                        elem = page.locator(sel).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.click()
                            action.success = True
                            break
                    except:
                        continue
                
                if not action.success:
                    action.error = "Could not find submit button"
                    
            elif action_type == ActionType.WAIT:
                await asyncio.sleep(2)
                action.success = True
                
            elif action_type == ActionType.SCROLL:
                await page.evaluate('window.scrollBy(0, 500)')
                action.success = True
                
            else:
                action.success = True  # THINK actions are always "successful"
                
        except Exception as e:
            action.error = str(e)
            action.success = False
        
        return action
    
    async def _verify_completion(
        self,
        page,
        initial_url: str,
        instruction: str
    ) -> Dict:
        """
        Verify that the task was completed successfully.
        
        Checks:
        1. URL changed from initial
        2. Success indicators in content
        3. No error messages visible
        """
        result = {
            'success': False,
            'message': '',
            'confirmation_id': None,
            'error': None
        }
        
        current_url = page.url
        content = await page.content()
        title = await page.title()
        
        # Check for success indicators
        success_patterns = [
            'thank you',
            'application received',
            'application submitted',
            'successfully submitted',
            'we have received',
            'confirmation',
            'your application',
        ]
        
        found_success = any(p in content.lower() for p in success_patterns)
        
        # Check for error indicators
        error_patterns = [
            'error',
            'required field',
            'please fix',
            'invalid',
            'failed',
        ]
        
        found_error = any(p in content.lower() for p in error_patterns)
        
        # URL changed
        url_changed = current_url != initial_url
        
        # Determine result
        if found_success and not found_error:
            result['success'] = True
            result['message'] = 'Application appears to be submitted successfully'
            
            # Try to extract confirmation number
            import re
            conf_match = re.search(r'confirmation[\s#:]+([A-Z0-9\-]+)', content, re.I)
            if conf_match:
                result['confirmation_id'] = conf_match.group(1)
        elif found_error:
            result['success'] = False
            result['error'] = 'Form has validation errors or submission failed'
            result['message'] = 'Application submission failed'
        elif url_changed:
            result['success'] = True
            result['message'] = f'Page navigated to: {current_url}'
        else:
            result['success'] = False
            result['error'] = 'No confirmation or navigation detected'
            result['message'] = 'Unable to verify successful submission'
        
        return result


# Test function
async def test_agent():
    """Test the CUA agent."""
    import yaml
    from adapters.handlers.browser_manager import BrowserManager
    
    # Load profile
    with open('campaigns/profiles/kevin_beltran.yaml') as f:
        profile = yaml.safe_load(f)
    
    browser = BrowserManager(headless=False)
    _, page = await browser.create_context()
    
    # Test job
    job_url = "https://grnh.se/5dqpfgbb6us"
    
    print(f"Testing CUA Agent on: {job_url}")
    
    await page.goto(job_url, wait_until='networkidle')
    await asyncio.sleep(2)
    
    agent = JobAgentCUA()
    await agent.initialize()
    
    result = await agent.execute(
        page=page,
        instruction="Apply for this ServiceNow Developer job. Fill all required fields including name, email, phone, and upload resume.",
        profile=profile,
        resume_path='Test Resumes/Kevin_Beltran_Resume.pdf',
        max_steps=20
    )
    
    print(f"\nResult: {result.to_dict()}")
    
    await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(test_agent())
