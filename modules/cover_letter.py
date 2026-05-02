"""cover_letter.py — Google Gemini cover letter generator (google-genai SDK)"""
import os, re, logging
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (t or "").lower()).strip("_")[:40]


def _build_prompt(job: dict, profile: dict, max_words: int) -> str:
    jd = (job.get("description") or "")[:3000]
    highlights = []
    for exp in profile.get("experience", [])[:3]:
        for h in exp.get("highlights", [])[:2]:
            highlights.append(f"- {h} ({exp['title']} @ {exp['company']})")
    skills = ", ".join(profile.get("core_skills", [])[:8])
    edu    = profile.get("education", [{}])[0]
    cur    = profile.get("experience", [{}])[0]

    return "\n".join([
        "You are an expert career coach for tech industry applications.",
        "Write a tailored cover letter for this specific job.\n",
        f"CANDIDATE: {profile.get('name')}",
        f"Role: {cur.get('title','')} at {cur.get('company','')}",
        f"Experience: {profile.get('total_experience_years',10)} years",
        f"Education: {edu.get('degree','')} from {edu.get('institution','')}",
        f"Skills: {skills}\n",
        "KEY ACHIEVEMENTS:",
        "\n".join(highlights),
        f"\nJOB: {job.get('title')} at {job.get('company')}",
        f"DESCRIPTION: {jd}\n",
        "RULES:",
        f"- Max {max_words} words",
        "- Lead with strongest quantified achievement relevant to this role",
        "- Reference specific details from the job description",
        "- Highlight supply chain + program management expertise",
        "- No 'Dear Hiring Manager' opener, no headers, no subject line",
        "- Output ONLY the cover letter body text",
    ])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
def _call_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        contents=prompt
    )
    return response.text.strip()


def generate_cover_letters(jobs: list, profile: dict, prefs: dict) -> list:
    max_words = prefs.get("apply_settings", {}).get("cover_letter_max_words", 350)
    out_dir   = Path("output/cover_letters")
    out_dir.mkdir(parents=True, exist_ok=True)

    suitable = [j for j in jobs if j.get("status") == "suitable"]
    logger.info(f"[CoverLetter] Generating {len(suitable)} letters...")

    for job in suitable:
        company = job.get("company", "co")
        title   = job.get("title",   "role")
        try:
            letter = _call_gemini(_build_prompt(job, profile, max_words))
            job["cover_letter"] = letter
            fp = out_dir / f"{_slug(company)}_{_slug(title)}.txt"
            fp.write_text(letter, encoding="utf-8")
            logger.info(f"[CoverLetter] OK  {company} — {title} ({len(letter.split())} words)")
        except Exception as e:
            logger.error(f"[CoverLetter] Failed {company}: {e}")
            job["cover_letter"] = ""

    logger.info(f"[CoverLetter] Done — {len(suitable)} letters")
    return jobs
