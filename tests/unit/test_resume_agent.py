"""
tests/unit/test_resume_agent.py
Unit tests for the Resume Parsing Agent and related utilities.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.schemas.resume_schemas import ParsedResume, WorkExperience, Education


def test_parsed_resume_schema_full():
    """ParsedResume schema accepts all fields correctly."""
    resume = ParsedResume(
        name="Jane Doe",
        email="jane@example.com",
        phone="+1-555-0100",
        location="San Francisco, CA",
        linkedin="https://linkedin.com/in/janedoe",
        github="https://github.com/janedoe",
        skills=["Python", "FastAPI", "PostgreSQL", "LangChain"],
        experience_years=7,
        work_history=[
            WorkExperience(
                company="OpenAI",
                role="Senior Engineer",
                duration="2021–2024",
                highlights=["Built RAG pipelines", "Led API redesign"],
            )
        ],
        education=[
            Education(degree="BSc Computer Science", institution="MIT", year=2016)
        ],
        projects=["llm-proxy", "vector-search-lib"],
        certifications=["AWS Solutions Architect"],
        summary="Senior engineer specialising in AI backend systems.",
    )
    assert resume.name == "Jane Doe"
    assert len(resume.skills) == 4
    assert resume.experience_years == 7
    assert resume.work_history[0].company == "OpenAI"
    print(f"  ✅ ParsedResume: full schema validation passed (name={resume.name!r})")


def test_parsed_resume_defaults():
    """ParsedResume minimal fields with all defaults."""
    resume = ParsedResume(name="Unknown", skills=[])
    assert resume.email is None
    assert resume.experience_years == 0
    assert resume.work_history == []
    assert resume.education == []
    assert resume.projects == []
    print("  ✅ ParsedResume: defaults are correct")


def test_pdf_extractor_raises_on_empty_bytes():
    """extract_text_from_bytes raises ValueError on empty/invalid input."""
    from app.utils.pdf_extractor import extract_text_from_bytes
    try:
        extract_text_from_bytes(b"not a pdf")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✅ pdf_extractor: raises ValueError on invalid PDF bytes")


def test_pdf_extractor_raises_on_empty_file():
    """extract_text_from_bytes raises ValueError on empty bytes."""
    from app.utils.pdf_extractor import extract_text_from_bytes
    try:
        extract_text_from_bytes(b"")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✅ pdf_extractor: raises ValueError on empty bytes")


def test_dummy_embedding_dimensions():
    """Dummy embedding returns correct dimension and is a unit vector."""
    import math
    from app.utils.embedder import _dummy_embedding
    embedding = _dummy_embedding("test text", dim=1024)
    assert len(embedding) == 1024
    magnitude = math.sqrt(sum(x ** 2 for x in embedding))
    assert abs(magnitude - 1.0) < 1e-6, f"Not unit vector: magnitude={magnitude}"
    print(f"  ✅ Dummy embedding: 1024-dim unit vector (magnitude={magnitude:.6f})")


def test_dummy_embedding_deterministic():
    """Same text always produces the same dummy embedding."""
    from app.utils.embedder import _dummy_embedding
    e1 = _dummy_embedding("hello world")
    e2 = _dummy_embedding("hello world")
    assert e1 == e2
    print("  ✅ Dummy embedding: deterministic for same input")


if __name__ == "__main__":
    print("\n── Resume Agent Unit Tests ───────────────────────────────────")
    test_parsed_resume_schema_full()
    test_parsed_resume_defaults()
    test_pdf_extractor_raises_on_empty_bytes()
    test_pdf_extractor_raises_on_empty_file()
    test_dummy_embedding_dimensions()
    test_dummy_embedding_deterministic()
    print("── All passed ───────────────────────────────────────────────\n")
