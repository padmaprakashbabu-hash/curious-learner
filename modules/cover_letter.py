"""cover_letter.py — Quality: llama-3.3-70b-versatile on-demand (~1,200 tokens/letter)"""
import os, re, logging
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

def _slug(t): return re.sub(r"[^a-z0-9]+","_",(t or "").lower()).strip("_")[:40]

def _build_prompt(job, profile, max_words):
    jd  = (job.get("description") or "")[:2000]
    cur = profile.get("experience",[{}])[0]
    highlights = []
    for exp in profile.get("experience",[])[:3]:
        for h in exp.get("highlights",[])[:2]:
            highlights.append(f"• {h} ({exp.get('title','')} @ {exp.get('company','')})")
    edu = profile.get("education",[{}])[0]
    return "\n".join([
        "You are an expert career coach. Write a tailored, compelling cover letter.",
        "",
        f"CANDIDATE: {profile.get('name','')}",
        f"Current: {cur.get('title','')} at {cur.get('company','')}",
        f"Education: {edu.get('degree','')} from {edu.get('institution','')}",
        f"Key skills: {', '.join(profile.get('core_skills',[])[:8])}",
        f"Key tools: {', '.join(profile.get('tools',[])[:6])}",
        "",
        "STRONGEST ACHIEVEMENTS:",
        "\n".join(highlights[:4]),
        "",
        f"TARGET: {job.get('title')} at {job.get('company')}",
        f"JOB DESCRIPTION:\n{jd}",
        "",
        f"RULES:",
        f"- Max {max_words} words",
        "- Open with the strongest quantified achievement relevant to this role",
        "- Reference specific requirements from the JD by name",
        "- Highlight supply chain + program management expertise",
        "- Professional but warm tone",
        "- Do NOT start with 'Dear Hiring Manager' or 'I am writing'",
        "- Output ONLY the cover letter body, no subject line or headers",
    ])

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=20))
def _call_llm(prompt):
    """Quality model for cover letters — llama-3.3-70b for best output."""
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            r = Groq(api_key=groq_key).chat.completions.create(
                model="llama-3.3-70b-versatile",  # Quality model for cover letters
                messages=[{"role":"user","content":prompt}],
                temperature=0.5, max_tokens=500,
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[CoverLetter] Groq 70b failed: {e}, trying 8b...")
            try:
                from groq import Groq
                r = Groq(api_key=groq_key).chat.completions.create(
                    model="llama-3.1-8b-instant",  # Fallback to 8b
                    messages=[{"role":"user","content":prompt}],
                    temperature=0.5, max_tokens=500,
                )
                return r.choices[0].message.content.strip()
            except Exception as e2:
                logger.warning(f"[CoverLetter] Groq 8b failed: {e2}, trying Gemini...")
    try:
        from google import genai
        c = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return c.models.generate_content(
            model="gemini-2.0-flash", contents=prompt).text.strip()
    except Exception as e:
        raise RuntimeError(f"All LLMs failed: {e}")

def generate_cover_letters(jobs, profile, prefs):
    max_words = prefs.get("apply_settings",{}).get("cover_letter_max_words", 320)
    out_dir = Path("output/cover_letters")
    out_dir.mkdir(parents=True, exist_ok=True)
    suitable = [j for j in jobs if j.get("status") == "suitable"]
    logger.info(f"[CoverLetter] Generating {len(suitable)} letters (quality model)")
    for job in suitable:
        company, title = job.get("company","co"), job.get("title","role")
        try:
            letter = _call_llm(_build_prompt(job, profile, max_words))
            job["cover_letter"] = letter
            fp = out_dir / f"{_slug(company)}_{_slug(title)}.txt"
            fp.write_text(letter, encoding="utf-8")
            logger.info(f"[CoverLetter] OK  {company} — {title} ({len(letter.split())}w)")
        except Exception as e:
            logger.error(f"[CoverLetter] Failed {company}: {e}")
            job["cover_letter"] = ""
    return jobs
