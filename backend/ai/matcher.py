"""
AI Job Matcher — scores a job listing against a user profile using Gemini.
"""

import json
import logging
from backend.ai.client import MODEL, get_client

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are a strict but fair job-fit analyst for a software/tech professional in India. "
    "Be concise and return only valid JSON."
)

_SCORE_PROMPT_TEMPLATE = """\
You are evaluating how well a candidate matches a job opening.

## Candidate Profile
- Name: {name}
- Skills: {skills}
- Experience: {experience}
- Education: {education}
- Summary: {summary}

## Job Details
- Title: {job_title}
- Company: {company}
- Description:
{job_description}

## Task
Return a JSON object with exactly these keys:
{{
  "score": <integer 0-100 representing overall fit>,
  "reasons": [<string>, <string>, <string>],
  "red_flags": [<string>, ...],
  "is_match": <boolean — true if score >= 70>
}}

Consider: skill overlap, seniority fit, domain relevance, location compatibility (India / Remote preferred).
Return ONLY the JSON object, no markdown, no extra text.
"""


async def score_job(
    job_description: str,
    job_title: str,
    company: str,
    profile: dict,
) -> dict:
    """Score a job against the user profile.

    Args:
        job_description: Full text of the job description.
        job_title: Title of the role.
        company: Hiring company name.
        profile: Parsed user profile dict (from resume_parser or UserProfile).

    Returns:
        dict with keys: score (int), reasons (list[str]), red_flags (list[str]),
        is_match (bool). Falls back to score=0 on any error.
    """
    _default = {"score": 0, "reasons": [], "red_flags": [], "is_match": False}

    try:
        skills = profile.get("skills", [])
        if isinstance(skills, list):
            skills_str = ", ".join(skills)
        else:
            skills_str = str(skills)

        experience = profile.get("experience", [])
        exp_lines = []
        for exp in experience:
            if isinstance(exp, dict):
                exp_lines.append(
                    f"  - {exp.get('title', '')} at {exp.get('company', '')} "
                    f"({exp.get('duration', '')}): {exp.get('description', '')}"
                )
        experience_str = "\n".join(exp_lines) if exp_lines else "Not provided"

        education = profile.get("education", [])
        edu_lines = []
        for edu in education:
            if isinstance(edu, dict):
                edu_lines.append(
                    f"  - {edu.get('degree', '')} from {edu.get('institution', '')} "
                    f"({edu.get('year', '')})"
                )
        education_str = "\n".join(edu_lines) if edu_lines else "Not provided"

        prompt = _SCORE_PROMPT_TEMPLATE.format(
            name=profile.get("name", "Candidate"),
            skills=skills_str or "Not provided",
            experience=experience_str,
            education=education_str,
            summary=profile.get("summary", "Not provided"),
            job_title=job_title,
            company=company,
            job_description=job_description,
        )

        client = get_client()
        interaction = client.interactions.create(
            model=MODEL,
            input=prompt,
            store=False,
            system_instruction=_SYSTEM_INSTRUCTION,
        )

        raw = interaction.output_text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)

        # Normalise / validate keys
        score = int(result.get("score", 0))
        reasons = result.get("reasons", [])
        red_flags = result.get("red_flags", [])
        is_match = bool(result.get("is_match", score >= 70))

        return {
            "score": score,
            "reasons": reasons if isinstance(reasons, list) else [],
            "red_flags": red_flags if isinstance(red_flags, list) else [],
            "is_match": is_match,
        }

    except json.JSONDecodeError as exc:
        logger.warning("score_job: JSON parse error: %s", exc)
        return _default
    except Exception as exc:
        logger.error("score_job: unexpected error: %s", exc)
        return _default
