"""
tests/unit/test_phase2.py
Unit tests for Phase 2 features:
- DEI Blind Resume Screening Anonymization Agent
- LangGraph HITL approval state transitions
"""
import unittest
from app.ai.schemas.resume_schemas import ParsedResume, Education, WorkExperience
from app.ai.agents.anonymizer_agent import anonymize_parsed_resume
from app.ai.workflows.hiring_graph import route_after_approval, END


class TestPhase2(unittest.TestCase):
    def test_dei_anonymizer_strips_pii(self):
        original = ParsedResume(
            name="John Doe",
            email="john.doe@university.edu",
            phone="+1-555-0199",
            location="San Francisco, CA",
            linkedin="https://linkedin.com/in/johndoe",
            github="https://github.com/johndoe",
            skills=["Python", "PostgreSQL", "Docker"],
            experience_years=5,
            work_history=[
                WorkExperience(
                    company="Google Inc.",
                    role="Senior Backend Engineer",
                    duration="2020 - Present",
                    highlights=["Built high throughput API"],
                )
            ],
            education=[
                Education(
                    degree="B.S. Computer Science",
                    institution="Stanford University",
                    year=2019,
                )
            ],
        )

        anonymized = anonymize_parsed_resume(original, candidate_index_id="12345678-uuid")

        # Verify PII is redacted
        self.assertEqual(anonymized.name, "Candidate-12345678")
        self.assertEqual(anonymized.email, "dei-redacted@privacy.internal")
        self.assertEqual(anonymized.phone, "[REDACTED]")
        self.assertIsNone(anonymized.linkedin)
        self.assertIsNone(anonymized.github)

        # Verify institutions and company names are sanitized
        self.assertEqual(anonymized.education[0].institution, "Accredited Academic Institution")
        self.assertEqual(anonymized.education[0].degree, "B.S. Computer Science")  # degree preserved
        self.assertEqual(anonymized.work_history[0].company, "Enterprise Employer")
        self.assertEqual(anonymized.work_history[0].role, "Senior Backend Engineer")  # role preserved

        # Verify skills are preserved
        self.assertEqual(anonymized.skills, ["Python", "PostgreSQL", "Docker"])
        self.assertEqual(anonymized.experience_years, 5)

    def test_hitl_approval_routing(self):
        approved_state = {"approval_status": "APPROVED"}
        rejected_state = {"approval_status": "REJECTED"}
        pending_state = {"approval_status": "PENDING_APPROVAL"}

        self.assertEqual(route_after_approval(approved_state), "interview_pack_node")
        self.assertEqual(route_after_approval(rejected_state), END)
        self.assertEqual(route_after_approval(pending_state), END)


if __name__ == "__main__":
    unittest.main()
