#!/usr/bin/env python3
"""
Email Notification System for Job Applications

Supports:
- SendGrid
- SMTP (Gmail, Outlook, etc.)
- Console output (for testing)

Usage:
    from email_notifications import EmailNotifier
    
    notifier = EmailNotifier()
    await notifier.send_application_confirmation(
        to_email="kle4311@gmail.com",
        job_title="Customer Success Manager",
        company="TechCorp"
    )
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class ApplicationNotification:
    """Represents an application notification"""
    candidate_email: str
    candidate_name: str
    job_title: str
    company: str
    platform: str
    status: str  # "submitted", "failed", "pending"
    timestamp: datetime
    job_url: Optional[str] = None
    error_message: Optional[str] = None


class EmailNotifier:
    """Sends email notifications for job applications"""
    
    def __init__(self):
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.from_email = os.getenv("FROM_EMAIL", "job-applier@notifications.com")
        self.enabled = self._check_config()
        
    def _check_config(self) -> bool:
        """Check if email is configured"""
        if self.sendgrid_api_key:
            return True
        if self.smtp_user and self.smtp_pass:
            return True
        return False
    
    async def send_application_confirmation(self, notification: ApplicationNotification):
        """Send application confirmation email"""
        
        subject = f"✅ Job Application Submitted: {notification.job_title} at {notification.company}"
        
        body = f"""
Hello {notification.candidate_name},

Your job application has been submitted successfully!

📋 APPLICATION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Job Title:    {notification.job_title}
Company:      {notification.company}
Platform:     {notification.platform}
Status:       ✅ SUBMITTED
Date/Time:    {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📧 WHAT HAPPENS NEXT:
• The employer will review your application
• You may receive a confirmation email from {notification.platform}
• Typical response time: 3-5 business days
• Check your spam folder if you don't see responses

📊 CAMPAIGN STATS:
Visit your dashboard to track all applications:
http://localhost:8000/applications

❓ NEED HELP?
Reply to this email if you have questions.

Good luck with your application!

— Job Applier Bot
        """
        
        if not self.enabled:
            # Console output for testing
            print(f"\n{'='*60}")
            print("📧 EMAIL NOTIFICATION (Console Mode)")
            print(f"{'='*60}")
            print(f"To: {notification.candidate_email}")
            print(f"Subject: {subject}")
            print(f"{'='*60}")
            print(body)
            print(f"{'='*60}\n")
            return True
        
        # Try SendGrid first
        if self.sendgrid_api_key:
            return await self._send_sendgrid(notification.candidate_email, subject, body)
        
        # Fallback to SMTP
        return await self._send_smtp(notification.candidate_email, subject, body)
    
    async def send_daily_summary(self, 
                                 to_email: str,
                                 candidate_name: str,
                                 applications_today: int,
                                 successful: int,
                                 failed: int):
        """Send daily summary email"""
        
        subject = f"📊 Daily Job Application Summary - {applications_today} Applications"
        
        body = f"""
Hello {candidate_name},

Here's your daily job application summary:

📈 TODAY'S STATS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Applications:   {applications_today}
✅ Successful:        {successful}
❌ Failed:            {failed}
Success Rate:         {(successful/applications_today*100):.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 KEEP GOING!
You're making great progress on your job search.
Consistency is key - keep applying!

— Job Applier Bot
        """
        
        if not self.enabled:
            print(f"\n📧 DAILY SUMMARY (Console):")
            print(f"To: {to_email}")
            print(f"Applications today: {applications_today}")
            return True
        
        if self.sendgrid_api_key:
            return await self._send_sendgrid(to_email, subject, body)
        
        return await self._send_smtp(to_email, subject, body)
    
    async def _send_sendgrid(self, to_email: str, subject: str, body: str) -> bool:
        """Send via SendGrid API"""
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.sendgrid_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "personalizations": [{
                            "to": [{"email": to_email}]
                        }],
                        "from": {"email": self.from_email, "name": "Job Applier"},
                        "subject": subject,
                        "content": [{
                            "type": "text/plain",
                            "value": body
                        }]
                    },
                    timeout=30.0
                )
                
                if response.status_code == 202:
                    print(f"✅ Email sent to {to_email} via SendGrid")
                    return True
                else:
                    print(f"❌ SendGrid error: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ SendGrid failed: {e}")
            return False
    
    async def _send_smtp(self, to_email: str, subject: str, body: str) -> bool:
        """Send via SMTP"""
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_pass,
                start_tls=True
            )
            
            print(f"✅ Email sent to {to_email} via SMTP")
            return True
            
        except Exception as e:
            print(f"❌ SMTP failed: {e}")
            return False


def setup_email_config():
    """Interactive setup for email configuration"""
    print("\n📧 Email Notification Setup")
    print("="*60)
    print("\nChoose email provider:")
    print("1. SendGrid (recommended)")
    print("2. Gmail SMTP")
    print("3. Other SMTP")
    print("4. Console only (testing)")
    
    choice = input("\nChoice (1-4): ").strip()
    
    env_vars = []
    
    if choice == "1":
        api_key = input("SendGrid API Key: ").strip()
        env_vars.append(f'SENDGRID_API_KEY={api_key}')
        
    elif choice == "2":
        email = input("Gmail address: ").strip()
        password = input("Gmail app password: ").strip()
        env_vars.append(f'SMTP_USER={email}')
        env_vars.append(f'SMTP_PASS={password}')
        env_vars.append('SMTP_HOST=smtp.gmail.com')
        env_vars.append('SMTP_PORT=587')
        
    elif choice == "3":
        host = input("SMTP Host: ").strip()
        port = input("SMTP Port: ").strip()
        user = input("SMTP Username: ").strip()
        password = input("SMTP Password: ").strip()
        env_vars.append(f'SMTP_HOST={host}')
        env_vars.append(f'SMTP_PORT={port}')
        env_vars.append(f'SMTP_USER={user}')
        env_vars.append(f'SMTP_PASS={password}')
    
    from_email = input("From email address [job-applier@notifications.com]: ").strip()
    if from_email:
        env_vars.append(f'FROM_EMAIL={from_email}')
    
    # Save to .env
    env_path = Path(__file__).parent.parent / '.env'
    with open(env_path, 'a') as f:
        f.write('\n# Email Notifications\n')
        for var in env_vars:
            f.write(f'{var}\n')
    
    print(f"\n✅ Configuration saved to {env_path}")
    print("Restart the campaign to use email notifications.\n")


if __name__ == "__main__":
    setup_email_config()
