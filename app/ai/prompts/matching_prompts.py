"""
app/ai/prompts/matching_prompts.py
Prompt templates for the Candidate Matching Agent.
"""
from langchain_core.prompts import ChatPromptTemplate

CANDIDATE_MATCH_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a senior technical recruiter responsible for evaluating how well a candidate fits a job.
Score the candidate across multiple dimensions (0–100 each).
Be objective and evidence-based — cite specific items from the resume or job description.
Your reasoning should be actionable for the hiring team.
Flag any risks or concerns honestly.""",
    ),
    (
        "human",
        """Evaluate the following candidate against the job requirements.

── JOB DETAILS ──────────────────────────────────────
Title: {job_title}
Required Skills: {required_skills}
Preferred Skills: {preferred_skills}
Experience Required: {experience_years_min}+ years
Seniority Level: {seniority}
Key Responsibilities:
{responsibilities}

── CANDIDATE PROFILE ────────────────────────────────
Name: {candidate_name}
Total Experience: {experience_years} years
Skills: {candidate_skills}
Work History Summary:
{work_history}
Education:
{education}
Notable Projects: {projects}
─────────────────────────────────────────────────────

Please evaluate and return a structured match result with scores, strengths, missing skills, risks, and detailed reasoning.""",
    ),
])
