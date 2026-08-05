"""
app/ai/prompts/interview_prompts.py
Prompt templates for the Interview Generation Agent.
"""
from langchain_core.prompts import ChatPromptTemplate

INTERVIEW_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a principal engineer and experienced technical interviewer.
Your task is to generate a comprehensive interview pack for a specific (job, candidate) pair.

Guidelines:
- Technical questions should be directly relevant to the job's required skills and responsibilities.
- Behavioral questions should use the STAR framework and target the seniority level.
- Scenario questions should reflect realistic on-the-job situations.
- Include system design questions for senior/lead roles only.
- For each question, describe what an ideal answer looks like.
- Suggest 1–2 follow-up probing questions per main question.
- The evaluation rubric should give clear hire/no-hire signals per category.""",
    ),
    (
        "human",
        """Generate a comprehensive interview pack for the following position and candidate.

── JOB ───────────────────────────────────────────────
Title: {job_title}
Seniority: {seniority}
Required Skills: {required_skills}
Key Responsibilities: {responsibilities}

── CANDIDATE ─────────────────────────────────────────
Name: {candidate_name}
Experience: {experience_years} years
Skills: {candidate_skills}
Identified Strengths: {strengths}
Areas to Probe: {probe_areas}
─────────────────────────────────────────────────────

Generate a full interview pack with technical, behavioral, and scenario questions.""",
    ),
])
