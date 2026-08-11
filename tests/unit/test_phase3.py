"""
tests/unit/test_phase3.py
Unit tests for Phase 3 features:
- Self-hosted Open-Source ATS Webhook signature & payload verification
- AI Audio Pre-Screening questions generator
"""
import unittest
from app.api.v1.webhooks import verify_hmac_signature
from app.ai.schemas.job_schemas import ParsedJob
from app.ai.agents.audio_agent import generate_audio_screening_session


class TestPhase3(unittest.TestCase):
    def test_verify_hmac_signature(self):
        payload = b'{"action":"candidate_applied"}'
        secret = "super_secret_key"
        import hmac, hashlib
        valid_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        self.assertTrue(verify_hmac_signature(payload, secret, valid_sig))
        self.assertFalse(verify_hmac_signature(payload, secret, "invalid_sig"))

    def test_audio_screening_question_generator(self):
        import asyncio
        parsed_job = ParsedJob(
            title="Senior Python Architect",
            required_skills=["Python", "FastAPI", "PostgreSQL"],
            preferred_skills=["Docker", "Kubernetes"],
            experience_years_min=5,
            seniority="Senior",
            responsibilities=["Build high throughput microservices"],
        )

        questions = asyncio.run(generate_audio_screening_session(parsed_job))
        self.assertTrue(len(questions) >= 4)
        self.assertIn("Senior Python Architect", questions[0])


if __name__ == "__main__":
    unittest.main()
