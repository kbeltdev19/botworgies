#!/usr/bin/env python3
"""
Job Agent CUA (Computer Use Agent) - Autonomous job application agent.

Now powered by BrowserBase Stagehand:
- Uses Stagehand's AI-powered act/extract/observe primitives
- Executes high-level tasks like "apply for this job"
- Handles complex multi-step forms autonomously
- Integrates with BrowserBase for stealth browsing

Requires:
    pip install stagehand-py browserbase
    
Environment Variables:
    BROWSERBASE_API_KEY - Your BrowserBase API key
    BROWSERBASE_PROJECT_ID - Your BrowserBase project ID
    MODEL_API_KEY - Your OpenAI/Anthropic API key
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from core.browser import Stagehand, StagehandConfig, StagehandAgent
    from stagehand.schemas import AgentConfig, AgentExecuteOptions, AgentProvider
    STAGEHAND_AVAILABLE = True
except ImportError:
    STAGEHAND_AVAILABLE = False
    logging.warning("stagehand-py not installed. Run: pip install stagehand-py")

logger = logging.getLogger(__name__)


@dataclass
class AgentAction:
    """A single action taken by the agent (for compatibility)."""
    action_type: str
    description: str
    selector: str = ""
    value: str = ""
    success: bool = False
    error: Optional[str] = None
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


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
    raw_result: Any = None
    
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
    Computer Use Agent for job applications - Powered by Stagehand.
    
    This agent uses BrowserBase Stagehand to:
    1. Navigate to job postings
    2. Extract job details using AI
    3. Fill application forms autonomously
    4. Submit applications
    
    Stagehand primitives used:
    - page.goto(): Navigate to URLs
    - page.act(): Execute natural language actions
    - page.extract(): Extract structured data
    - page.observe(): Find elements
    - agent.execute(): Run autonomous multi-step tasks
    
    Example:
        agent = JobAgentCUA()
        await agent.initialize()
        
        result = await agent.execute(
            page=stagehand_page,
            instruction="Apply for this job",
            profile=user_profile,
            resume_path="/path/to/resume.pdf"
        )
        
        print(result.to_dict())
    """
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize the Job Agent.
        
        Args:
            model: LLM model to use (gpt-4o, claude-3-5-sonnet, etc.)
        """
        self.model = model
        self.max_steps = 25
        self.stagehand = None
        
    async def initialize(self):
        """Initialize the agent with Stagehand if available."""
        if not STAGEHAND_AVAILABLE:
            raise ImportError(
                "Stagehand is not installed. "
                "Run: pip install stagehand-py browserbase"
            )
    
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
        
        Uses Stagehand's AI-powered primitives to complete the task.
        
        Args:
            page: Stagehand page object (from stagehand.page)
            instruction: High-level goal (e.g., "apply for this job")
            profile: User profile data with name, email, phone, etc.
            resume_path: Path to resume PDF
            max_steps: Maximum steps to take
        
        Returns:
            AgentResult with success status and action history
        """
        self.max_steps = max_steps
        initial_url = page.url
        
        logger.info(f"[JobAgentCUA] Starting: {instruction}")
        logger.info(f"[JobAgentCUA] URL: {initial_url}")
        
        result = AgentResult(
            success=False,
            message="",
            completed=False
        )
        
        try:
            # First, extract job details to understand what we're applying for
            logger.info("[JobAgentCUA] Extracting job details...")
            job_details = await page.extract(
                instruction="Extract the job title, company name, and key requirements"
            )
            logger.info(f"[JobAgentCUA] Job details: {job_details}")
            
            # Look for the apply button/link
            logger.info("[JobAgentCUA] Looking for apply button...")
            observe_result = await page.observe(
                instruction="Find the apply button or link to start the application"
            )
            
            if observe_result and len(observe_result) > 0:
                # Click the apply button using Stagehand act
                action = observe_result[0]
                logger.info(f"[JobAgentCUA] Clicking: {action.get('description', 'apply button')}")
                await page.act(action)
            else:
                # Try to find any application-related button
                await page.act("click the apply button or link to start application")
            
            # Wait for form to load
            await asyncio.sleep(2)
            
            # Fill in the application form using Stagehand agent
            logger.info("[JobAgentCUA] Filling application form...")
            
            # Build profile context
            profile_context = f"""
Name: {profile.get('first_name', '')} {profile.get('last_name', '')}
Email: {profile.get('email', '')}
Phone: {profile.get('phone', '')}
Location: {profile.get('city', '')}, {profile.get('state', '')}
LinkedIn: {profile.get('linkedin_url', '')}
"""
            
            # Use Stagehand's act to fill form fields
            await page.act(f"Fill the first name field with: {profile.get('first_name', '')}")
            await page.act(f"Fill the last name field with: {profile.get('last_name', '')}")
            await page.act(f"Fill the email field with: {profile.get('email', '')}")
            await page.act(f"Fill the phone field with: {profile.get('phone', '')}")
            
            # Upload resume
            if resume_path and Path(resume_path).exists():
                logger.info(f"[JobAgentCUA] Uploading resume: {resume_path}")
                await page.act(f"Upload the resume file from {resume_path}")
            
            # Look for and fill any other required fields
            logger.info("[JobAgentCUA] Checking for additional required fields...")
            
            # Extract form fields to see what's left
            form_info = await page.extract(
                instruction="List all required form fields that are empty or need to be filled"
            )
            logger.info(f"[JobAgentCUA] Remaining fields: {form_info}")
            
            # Submit the application
            logger.info("[JobAgentCUA] Submitting application...")
            await page.act("click the submit button or final submit button to complete the application")
            
            # Wait for confirmation
            await asyncio.sleep(3)
            
            # Verify submission
            current_url = page.url
            content = await page.content()
            
            # Check for success indicators
            success_indicators = [
                "thank you", "application submitted", "successfully submitted",
                "we have received", "confirmation", "your application"
            ]
            
            found_success = any(ind in content.lower() for ind in success_indicators)
            
            # Look for confirmation number
            import re
            conf_match = re.search(r'confirmation[\s#:]+([A-Z0-9\-]+)', content, re.I)
            confirmation_id = conf_match.group(1) if conf_match else None
            
            result.success = found_success
            result.completed = True
            result.final_url = current_url
            result.confirmation_id = confirmation_id
            
            if found_success:
                result.message = "Application submitted successfully"
                logger.info(f"[JobAgentCUA] ✅ Success! Confirmation: {confirmation_id}")
            else:
                result.message = "Application may have been submitted (verification inconclusive)"
                logger.warning("[JobAgentCUA] ⚠️ Could not verify successful submission")
            
        except Exception as e:
            logger.error(f"[JobAgentCUA] Error: {e}")
            result.error = str(e)
            result.message = f"Application failed: {e}"
        
        return result
    
    async def apply_with_agent(
        self,
        job_url: str,
        profile: Dict[str, Any],
        resume_path: str,
        cover_letter: Optional[str] = None
    ) -> AgentResult:
        """
        Apply for a job using Stagehand's autonomous agent.
        
        This uses the full Stagehand agent for complex multi-step applications.
        Uses existing MOONSHOT_API_KEY and BROWSERBASE_API_KEY from environment.
        
        Args:
            job_url: URL of the job posting
            profile: User profile data
            resume_path: Path to resume PDF
            cover_letter: Optional cover letter text
            
        Returns:
            AgentResult
        """
        import os
        
        logger.info(f"[JobAgentCUA] Using Stagehand Agent for: {job_url}")
        
        # Initialize Stagehand with existing API keys
        config = StagehandConfig(
            env="BROWSERBASE",
            api_key=os.getenv("BROWSERBASE_API_KEY"),
            project_id=os.getenv("BROWSERBASE_PROJECT_ID"),
            model_name=self.model,
            model_client_options={"apiKey": os.getenv("MOONSHOT_API_KEY")}
        )
        
        stagehand = Stagehand(config=config)
        await stagehand.init()
        
        try:
            # Navigate to job
            await stagehand.page.goto(job_url)
            
            # Configure the agent
            profile_str = json.dumps(profile, indent=2)
            
            agent_config = AgentConfig(
                provider=AgentProvider.OPENAI,
                model=self.model,
                instructions=f"""You are a job application assistant.

User Profile:
{profile_str}

Resume Path: {resume_path}

Your task is to:
1. Review the job posting
2. Click to apply
3. Fill all required fields with the user's information
4. Upload the resume
5. Answer any screening questions truthfully
6. Submit the application

Be thorough and accurate."""
            )
            
            execute_options = AgentExecuteOptions(
                instruction="Apply for this job completely and accurately. Fill all required fields and submit.",
                max_steps=self.max_steps,
                auto_screenshot=True
            )
            
            # Execute the agent
            agent_result = await stagehand.agent.execute(agent_config, execute_options)
            
            # Convert to our AgentResult format
            result = AgentResult(
                success=getattr(agent_result, 'success', True),
                message=getattr(agent_result, 'message', 'Application completed'),
                confirmation_id=None,
                final_url=stagehand.page.url,
                raw_result=agent_result
            )
            
            # Try to extract confirmation number
            content = await stagehand.page.content()
            import re
            conf_match = re.search(r'confirmation[\s#:]+([A-Z0-9\-]+)', content, re.I)
            if conf_match:
                result.confirmation_id = conf_match.group(1)
            
            return result
            
        finally:
            await stagehand.close()


# Test function
async def test_agent():
    """Test the CUA agent with Stagehand."""
    import yaml
    
    if not STAGEHAND_AVAILABLE:
        print("Stagehand not installed. Run: pip install stagehand-py")
        return
    
    # Load profile
    profile_path = Path('campaigns/profiles/kevin_beltran.yaml')
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}")
        return
    
    with open(profile_path) as f:
        profile = yaml.safe_load(f)
    
    # Test job
    job_url = "https://example.com/job-posting"
    
    print(f"Testing JobAgentCUA with Stagehand")
    print(f"Profile: {profile.get('first_name')} {profile.get('last_name')}")
    
    agent = JobAgentCUA()
    await agent.initialize()
    
    # Use the full agent approach
    result = await agent.apply_with_agent(
        job_url=job_url,
        profile=profile,
        resume_path='Test Resumes/Kevin_Beltran_Resume.pdf'
    )
    
    print(f"\nResult: {result.to_dict()}")


if __name__ == "__main__":
    asyncio.run(test_agent())
