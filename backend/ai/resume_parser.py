"""
AI Resume Parser — extracts structured profile data from raw resume text using Gemini.
"""

import json
import logging
from backend.ai.client import MODEL, get_client

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are a precise resume parser. Extract structured information from resume text "
    "and return it as valid JSON only. Do not add commentary or markdown."
)

_PARSE_PROMPT_TEMPLATE = """\
Parse the following resume text and extract structured information.

## Resume Text
{raw_text}

## Output Format
Return a JSON object with exactly these keys:
{{
  "name": "<full name as string>",
  "email": "<email address or empty string>",
  "phone": "<phone number or empty string>",
  "linkedin_url": "<LinkedIn profile URL or empty string>",
  "github_url": "<GitHub profile URL or empty string>",
  "portfolio_url": "<personal website / portfolio URL or empty string>",
  "skills": ["<skill1>", "<skill2>", ...],
  "experience": [
    {{
      "title": "<job title>",
      "company": "<company name>",
      "duration": "<e.g. Jan 2021 – Mar 2023>",
      "description": "<brief description of responsibilities/achievements>"
    }}
  ],
  "education": [
    {{
      "degree": "<degree name and field>",
      "institution": "<university or college name>",
      "year": "<graduation year or year range>"
    }}
  ],
  "summary": "<professional summary or objective, 2-4 sentences>"
}}

Rules:
- Use empty string "" for missing scalar fields
- Use empty list [] for missing list fields
- Infer reasonable values where clearly implied; do not hallucinate data
- Return ONLY the JSON object
"""

_DEFAULT_PROFILE: dict = {
    "name": "",
    "email": "",
    "phone": "",
    "linkedin_url": "",
    "github_url": "",
    "portfolio_url": "",
    "skills": [],
    "experience": [],
    "education": [],
    "summary": "",
}


async def parse_resume_text(raw_text: str) -> dict:
    """Parse raw resume text into a structured profile dict.

    Args:
        raw_text: Plain text extracted from a PDF resume.

    Returns:
        Structured profile dict. Falls back to _DEFAULT_PROFILE on parse error.
    """
    if not raw_text or not raw_text.strip():
        logger.warning("parse_resume_text: empty input, returning default profile")
        return dict(_DEFAULT_PROFILE)

    try:
        prompt = _PARSE_PROMPT_TEMPLATE.format(raw_text=raw_text)

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

        # Build a clean, validated output merging with defaults
        profile = dict(_DEFAULT_PROFILE)
        profile["name"] = str(result.get("name", ""))
        profile["email"] = str(result.get("email", ""))
        profile["phone"] = str(result.get("phone", ""))
        profile["linkedin_url"] = str(result.get("linkedin_url", ""))
        profile["github_url"] = str(result.get("github_url", ""))
        profile["portfolio_url"] = str(result.get("portfolio_url", ""))
        profile["summary"] = str(result.get("summary", ""))

        skills = result.get("skills", [])
        profile["skills"] = skills if isinstance(skills, list) else []

        experience = result.get("experience", [])
        profile["experience"] = (
            [
                {
                    "title": str(e.get("title", "")),
                    "company": str(e.get("company", "")),
                    "duration": str(e.get("duration", "")),
                    "description": str(e.get("description", "")),
                }
                for e in experience
                if isinstance(e, dict)
            ]
            if isinstance(experience, list)
            else []
        )

        education = result.get("education", [])
        profile["education"] = (
            [
                {
                    "degree": str(e.get("degree", "")),
                    "institution": str(e.get("institution", "")),
                    "year": str(e.get("year", "")),
                }
                for e in education
                if isinstance(e, dict)
            ]
            if isinstance(education, list)
            else []
        )

        return profile

    except json.JSONDecodeError as exc:
        logger.warning("parse_resume_text: JSON parse error: %s", exc)
        return dict(_DEFAULT_PROFILE)
    except Exception as exc:
        logger.error("parse_resume_text: unexpected error: %s", exc)
        return dict(_DEFAULT_PROFILE)
