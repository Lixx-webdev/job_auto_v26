"""Resume PDF -> structured profile.json.

Usage:  python -m backend.profile.parser path/to/resume.pdf
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from pdfminer.high_level import extract_text

from backend.ai.resume_parser import parse_resume_text

PROFILE_PATH = Path(__file__).with_name("profile.json")


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"{PROFILE_PATH} not found. Run: python -m backend.profile.parser <resume.pdf>"
        )
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


async def build_profile(resume_pdf: str) -> dict:
    text = extract_text(resume_pdf)
    profile = await parse_resume_text(text)
    profile["resume_path"] = str(Path(resume_pdf).resolve())
    profile["raw_text"] = text
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    return profile


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m backend.profile.parser <resume.pdf>")
    p = asyncio.run(build_profile(sys.argv[1]))
    print(f"Wrote {PROFILE_PATH} — name={p['name']!r}, {len(p['skills'])} skills. Review and edit it by hand.")
