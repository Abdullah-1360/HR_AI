"""
app/ai/agents/anonymizer_agent.py
DEI Blind Resume Screening Agent.
Redacts PII (Personally Identifiable Information) and demographic indicators
from a ParsedResume object prior to candidate evaluation.
"""
import copy
import logging
from typing import Optional
from app.ai.schemas.resume_schemas import ParsedResume, Education, WorkExperience

logger = logging.getLogger(__name__)


def anonymize_parsed_resume(
    resume: ParsedResume,
    candidate_index_id: Optional[str] = None,
) -> ParsedResume:
    """
    Sanitize and anonymize a ParsedResume instance for DEI blind screening.

    Redacts:
      - Full Name → Candidate-X / Anonymous Candidate
      - Email / Phone / Address / Location
      - LinkedIn / GitHub social links
      - Specific company names → Generic Industry Employer
      - University names → Accredited Institution

    Preserves:
      - Technical and domain skills
      - Years of experience
      - Roles, degrees, certifications, and project descriptions

    Returns:
        A sanitized ParsedResume instance.
    """
    anon_resume = copy.deepcopy(resume)

    candidate_label = f"Candidate-{candidate_index_id[:8]}" if candidate_index_id else "Anonymous Candidate"

    # Redact PII fields
    anon_resume.name = candidate_label
    anon_resume.email = "dei-redacted@privacy.internal"
    anon_resume.phone = "[REDACTED]"
    anon_resume.location = "Region Redacted (DEI Blind Mode)"
    anon_resume.linkedin = None
    anon_resume.github = None

    # Sanitize Education (Keep degree, sanitize institution name)
    sanitized_education = []
    for edu in anon_resume.education:
        sanitized_education.append(
            Education(
                degree=edu.degree,
                institution="Accredited Academic Institution",
                year=edu.year,
            )
        )
    anon_resume.education = sanitized_education

    # Sanitize Work Experience (Keep role & skills, sanitize specific company name)
    sanitized_history = []
    for work in anon_resume.work_history:
        sanitized_history.append(
            WorkExperience(
                company="Enterprise Employer",
                role=work.role,
                duration=work.duration,
                highlights=work.highlights,
            )
        )
    anon_resume.work_history = sanitized_history

    logger.info("anonymizer_agent.anonymized_success label=%s", candidate_label)
    return anon_resume
