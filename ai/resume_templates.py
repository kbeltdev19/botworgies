#!/usr/bin/env python3
"""
Resume Tailoring Templates - Pre-tailored templates for common roles.

Impact: Instant tailoring (free) vs AI call ($0.01-0.05)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re


@dataclass
class ResumeTemplate:
    """A pre-tailored resume template."""
    role_type: str
    keywords: List[str]
    summary_template: str
    skills_highlight: List[str]
    experience_bullets: List[str]
    certifications: List[str]


# Pre-defined templates for common roles
RESUME_TEMPLATES = {
    'software_engineer': ResumeTemplate(
        role_type='Software Engineer',
        keywords=[
            'Python', 'JavaScript', 'TypeScript', 'React', 'Node.js',
            'API Development', 'Cloud', 'AWS', 'Docker', 'Kubernetes',
            'Microservices', 'CI/CD', 'Git', 'Agile', 'Scrum'
        ],
        summary_template='''Results-driven Software Engineer with {years}+ years of experience designing, developing, and deploying scalable applications. 
Proficient in full-stack development with expertise in {primary_stack}. 
Strong track record of delivering high-quality code and collaborating with cross-functional teams to drive product success.''',
        skills_highlight=[
            'Full-Stack Development',
            'Cloud Architecture (AWS/GCP)',
            'API Design & Development',
            'Database Design & Optimization',
            'DevOps & CI/CD',
        ],
        experience_bullets=[
            'Developed and maintained {scale} applications serving {users} users',
            'Reduced system latency by {percentage}% through performance optimization',
            'Led migration to microservices architecture, improving scalability',
            'Implemented CI/CD pipelines reducing deployment time by {percentage}%',
        ],
        certifications=['AWS Solutions Architect', 'Certified Kubernetes Administrator']
    ),
    
    'product_manager': ResumeTemplate(
        role_type='Product Manager',
        keywords=[
            'Product Strategy', 'Agile', 'Scrum', 'User Research',
            'Roadmap', 'KPIs', 'A/B Testing', 'Data Analysis',
            'Stakeholder Management', 'JIRA', 'Confluence'
        ],
        summary_template='''Strategic Product Manager with {years}+ years of experience driving product development from conception to launch. 
Proven ability to translate customer needs into actionable product requirements and deliver measurable business results. 
Expert in agile methodologies and cross-functional team leadership.''',
        skills_highlight=[
            'Product Strategy & Roadmapping',
            'User Research & Analytics',
            'Agile & Scrum Leadership',
            'Data-Driven Decision Making',
            'Stakeholder Management',
        ],
        experience_bullets=[
            'Launched {product_count} products generating ${revenue}M in revenue',
            'Increased user engagement by {percentage}% through feature optimization',
            'Managed product roadmap for team of {team_size} engineers',
            'Conducted {research_count} user research studies informing product decisions',
        ],
        certifications=['Certified Scrum Product Owner (CSPO)', 'Pragmatic Marketing Certified']
    ),
    
    'customer_success': ResumeTemplate(
        role_type='Customer Success Manager',
        keywords=[
            'Customer Retention', 'SaaS', 'Account Management', 'Onboarding',
            'NPS', 'Churn Reduction', 'Upselling', 'CRM', 'Salesforce',
            'Customer Journey', 'QBR', 'Expansion'
        ],
        summary_template='''Customer-focused professional with {years}+ years of experience driving customer success and retention in SaaS environments. 
Proven track record of building strong client relationships, reducing churn, and identifying expansion opportunities. 
Passionate about helping customers achieve their business goals.''',
        skills_highlight=[
            'Customer Retention & Growth',
            'SaaS Account Management',
            'Onboarding & Training',
            'CRM Administration (Salesforce)',
            'Data-Driven Customer Insights',
        ],
        experience_bullets=[
            'Managed {account_count} enterprise accounts with {retention}% retention rate',
            'Reduced churn by {percentage}% through proactive engagement strategies',
            'Achieved {percentage}% upsell rate by identifying expansion opportunities',
            'Conducted quarterly business reviews with C-level executives',
        ],
        certifications=['Customer Success Manager Certification', 'Salesforce Certified Administrator']
    ),
    
    'account_manager': ResumeTemplate(
        role_type='Account Manager',
        keywords=[
            'Account Management', 'B2B Sales', 'Relationship Building',
            'Revenue Growth', 'Contract Negotiation', 'CRM',
            'Pipeline Management', 'Forecasting', 'Cross-selling'
        ],
        summary_template='''Results-driven Account Manager with {years}+ years of B2B sales experience and a proven record of exceeding revenue targets. 
Skilled in building long-term client relationships, negotiating contracts, and identifying growth opportunities. 
Adept at managing complex sales cycles and collaborating with internal teams.''',
        skills_highlight=[
            'Strategic Account Management',
            'B2B Sales & Negotiation',
            'Revenue Growth & Expansion',
            'CRM & Pipeline Management',
            'Cross-functional Collaboration',
        ],
        experience_bullets=[
            'Grew account portfolio by {percentage}% year-over-year',
            'Exceeded sales quota by {percentage}% for {consecutive} consecutive quarters',
            'Managed {account_count} key accounts with ${revenue}M annual contract value',
            'Negotiated {contract_count} enterprise contracts worth ${value}M',
        ],
        certifications=['Certified Professional Sales Person (CPSP)', 'SPIN Selling Certified']
    ),
    
    'sales_development': ResumeTemplate(
        role_type='Sales Development Representative',
        keywords=[
            'Lead Generation', 'Cold Calling', 'Email Outreach',
            'LinkedIn Sales Navigator', 'CRM', 'Salesforce',
            'Pipeline Building', 'B2B Sales', 'Qualification'
        ],
        summary_template='''Energetic Sales Development Representative with {years}+ years of experience in B2B lead generation and pipeline building. 
Proven ability to identify and qualify prospects, conduct effective outreach, and set qualified meetings. 
Track record of exceeding activity and quota targets.''',
        skills_highlight=[
            'Lead Generation & Prospecting',
            'Cold Calling & Email Outreach',
            'CRM Management (Salesforce)',
            'Sales Pipeline Development',
            'B2B Qualification (BANT/MEDDIC)',
        ],
        experience_bullets=[
            'Generated {lead_count} qualified leads per month, exceeding target by {percentage}%',
            'Achieved {percentage}% connect rate through personalized outreach',
            'Booked {meeting_count} meetings per month for Account Executives',
            'Built pipeline worth ${pipeline}M through proactive prospecting',
        ],
        certifications=['Certified Inside Sales Professional', 'Salesforce Certified Administrator']
    ),
    
    'servicenow': ResumeTemplate(
        role_type='ServiceNow Consultant',
        keywords=[
            'ServiceNow', 'ITSM', 'ITIL', 'CMDB', 'Workflow',
            'Scripting', 'JavaScript', 'Business Rules', 'UI Policies',
            'Integration', 'API', 'HRSD', 'CSM'
        ],
        summary_template='''Certified ServiceNow professional with {years}+ years of experience implementing and optimizing ITSM solutions. 
Expert in ServiceNow platform configuration, workflow automation, and integrations. 
Strong understanding of ITIL best practices and experience across multiple ServiceNow modules.''',
        skills_highlight=[
            'ServiceNow Platform Implementation',
            'ITSM/ITIL Best Practices',
            'Workflow Automation & Scripting',
            'CMDB & Asset Management',
            'Integration Development',
        ],
        experience_bullets=[
            'Implemented ServiceNow ITSM for {user_count} users across {department_count} departments',
            'Automated {process_count} workflows reducing ticket resolution time by {percentage}%',
            'Developed {script_count} custom business rules and script includes',
            'Led CMDB data migration with {accuracy}% data accuracy',
        ],
        certifications=['ServiceNow Certified System Administrator', 'ITIL Foundation', 'ServiceNow Certified Application Developer']
    ),
    
    'business_analyst': ResumeTemplate(
        role_type='Business Analyst',
        keywords=[
            'Requirements Gathering', 'Process Analysis', 'Data Analysis',
            'SQL', 'Excel', 'Tableau', 'Power BI', 'Agile',
            'User Stories', 'JIRA', 'Confluence', 'Documentation'
        ],
        summary_template='''Analytical Business Analyst with {years}+ years of experience translating business needs into technical requirements. 
Proficient in process analysis, data visualization, and stakeholder communication. 
Track record of delivering process improvements and data-driven insights.''',
        skills_highlight=[
            'Requirements Elicitation & Documentation',
            'Process Analysis & Improvement',
            'Data Analysis & Visualization',
            'SQL & Database Querying',
            'Agile Methodologies',
        ],
        experience_bullets=[
            'Gathered and documented {req_count} business requirements for {project_count} projects',
            'Improved process efficiency by {percentage}% through workflow optimization',
            'Created {dashboard_count} dashboards providing real-time business insights',
            'Facilitated {workshop_count} requirements workshops with stakeholders',
        ],
        certifications=['Certified Business Analysis Professional (CBAP)', 'PMI Professional in Business Analysis (PMI-PBA)']
    ),
}


class ResumeTemplateManager:
    """Manage resume tailoring with templates."""
    
    def __init__(self):
        self.templates = RESUME_TEMPLATES
    
    def detect_role_type(self, job_title: str) -> Optional[str]:
        """Detect role type from job title."""
        title_lower = job_title.lower()
        
        # Role detection patterns
        patterns = {
            'software_engineer': ['engineer', 'developer', 'programmer', 'software'],
            'product_manager': ['product manager', 'pm', 'product owner'],
            'customer_success': ['customer success', 'client success', 'csm'],
            'account_manager': ['account manager', 'account executive', 'ae'],
            'sales_development': ['sdr', 'sales development', 'bdr', 'business development'],
            'servicenow': ['servicenow', 'service now'],
            'business_analyst': ['business analyst', 'ba', 'systems analyst'],
        }
        
        for role_type, keywords in patterns.items():
            if any(kw in title_lower for kw in keywords):
                return role_type
        
        return None
    
    def apply_template(
        self,
        base_resume: str,
        template_key: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Apply template to resume.
        
        Args:
            base_resume: Original resume text
            template_key: Key from RESUME_TEMPLATES
            variables: Variables to substitute in template
            
        Returns:
            Tailored resume text
        """
        if template_key not in self.templates:
            return base_resume
        
        template = self.templates[template_key]
        vars = variables or {}
        
        # Default variables
        defaults = {
            'years': '5',
            'primary_stack': 'modern web technologies',
            'percentage': '25',
        }
        defaults.update(vars)
        
        # Build tailored sections
        summary = template.summary_template.format(**defaults)
        
        skills = ', '.join(template.skills_highlight[:5])
        
        experience = '\n'.join([
            f'• {bullet.format(**defaults)}'
            for bullet in template.experience_bullets[:3]
        ])
        
        # Combine into resume
        tailored = f"""{summary}

CORE COMPETENCIES:
{skills}

KEY ACHIEVEMENTS:
{experience}

---
{base_resume}"""
        
        return tailored
    
    def get_tailored_resume(
        self,
        base_resume: str,
        job_title: str,
        job_description: str = "",
        use_ai_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Get resume tailored for job.
        
        Returns:
            Dict with 'resume', 'method', 'template_used'
        """
        # Detect role type
        template_key = self.detect_role_type(job_title)
        
        if template_key and template_key in self.templates:
            # Use template (instant, free)
            tailored = self.apply_template(base_resume, template_key)
            return {
                'resume': tailored,
                'method': 'template',
                'template_used': template_key,
                'cost': 0,
            }
        
        # Fall back to AI if allowed
        if use_ai_fallback:
            return {
                'resume': base_resume,  # Placeholder - would call AI
                'method': 'ai',
                'template_used': None,
                'cost': 0.03,  # Estimated cost
            }
        
        # Return original
        return {
            'resume': base_resume,
            'method': 'original',
            'template_used': None,
            'cost': 0,
        }
    
    def get_template_for_role(self, role_type: str) -> Optional[ResumeTemplate]:
        """Get template by role type."""
        return self.templates.get(role_type)
    
    def list_available_templates(self) -> List[str]:
        """List all available template keys."""
        return list(self.templates.keys())


# Singleton instance
_manager: Optional[ResumeTemplateManager] = None


def get_template_manager() -> ResumeTemplateManager:
    """Get global template manager."""
    global _manager
    if _manager is None:
        _manager = ResumeTemplateManager()
    return _manager


def get_tailored_resume(
    base_resume: str,
    job_title: str,
    job_description: str = ""
) -> Dict[str, Any]:
    """Convenience function to get tailored resume."""
    return get_template_manager().get_tailored_resume(
        base_resume, job_title, job_description
    )
