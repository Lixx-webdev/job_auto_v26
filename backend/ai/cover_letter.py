"""
AI Cover Letter Generator — creates a tailored cover letter using Gemini.
"""

import logging
from backend.ai.client import WRITING_MODEL as MODEL, get_client

logger = logging.getLogger(__name__)

_COVER_LETTER_PROMPT_TEMPLATE = """\
Write a professional, tailored cover letter for the job application below.

## Candidate Profile
- Name: {name}
- Email: {email}
- Phone: {phone}
- Skills: {skills}
- Summary: {summary}
- Key Experience:
{experience}

## Job Details
- Role: {job_title}
- Company: {company}
- Location: {location}
- Description:
{job_description}

## Instructions
- Length: 400–500 words
- Tone: Professional yet warm and human — not stiff or robotic
- Structure: Opening hook → 2–3 body paragraphs → confident closing
- Mention the specific role title and company name naturally
- Highlight 2–3 skills from the candidate's profile that directly match the job
- Show genuine interest in the company's mission or product
- Do NOT start with "I am writing to express my interest"
- Do NOT use clichés like "dynamic", "synergy", "passionate about", "results-driven"
- Address hiring team as "Hiring Team" unless a name is provided
- End with a confident call-to-action requesting an interview
- Return ONLY the cover letter text, no metadata, no subject line, no extra commentary
"""


async def generate_cover_letter(job: dict, profile: dict) -> str:
    """Generate a tailored cover letter for a job.

    Args:
        job: Job details dict (title, company, location, description, etc.).
        profile: Parsed user profile dict.

    Returns:
        Cover letter as a plain string. Returns an empty string on failure.
    """
    try:
        skills = profile.get("skills", [])
        skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)

        experience = profile.get("experience", [])
        exp_lines = []
        for exp in experience[:3]:  # top 3 most recent roles
            if isinstance(exp, dict):
                exp_lines.append(
                    f"  - {exp.get('title', '')} at {exp.get('company', '')} "
                    f"({exp.get('duration', '')}): {exp.get('description', '')}"
                )
        experience_str = "\n".join(exp_lines) if exp_lines else "Not provided"

        prompt = _COVER_LETTER_PROMPT_TEMPLATE.format(
            name=profile.get("name", "Candidate"),
            email=profile.get("email", ""),
            phone=profile.get("phone", ""),
            skills=skills_str or "Not provided",
            summary=profile.get("summary", "Not provided"),
            experience=experience_str,
            job_title=job.get("title", "the role"),
            company=job.get("company", "your company"),
            location=job.get("location", "India / Remote"),
            job_description=job.get("description", ""),
        )

        client = get_client()
        interaction = client.interactions.create(
            model=MODEL,
            input=prompt,
            store=False,
        )

        return interaction.output_text.strip()

    except Exception as exc:
        logger.error("generate_cover_letter: unexpected error: %s", exc)
        return ""
