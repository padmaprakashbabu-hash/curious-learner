"""scorer.py — Google Gemini scorer (google-genai SDK, rate-limit safe)"""
import os, json, time, logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _build_prompt(job: dict, profile: dict) -> str:
    jd     = (job.get("description") or "")[:3000]
    skills = ", ".join(profile.get("core_skills", []))
    tools  = ", ".join(profile.get("tools", []))
    roles  = ", ".join(profile.get("target_roles", []))
    return (
        "You are an expert recruiter. Score job suitability 0-100 for this candidate.\n\n"
        "CANDIDATE:\n"
        f"- Name: {profile.get(chr(39)+'name'+chr(39))}\n"
        f"- Experience: {profile.get(chr(39)+'total_experience_years'+chr(39), 10)} years\n"
        f"- Target Roles: {roles}\n"
        f"- Skills: {skills}\n"
        f"- Tools: {tools}\n"
        f"- Summary: {profile.get(chr(39)+'summary'+chr(39), chr(39)+chr(39))}\n\n"
        "JOB:\n"
        f"- Title: {job.get(chr(39)+'title'+chr(39))}\n"
        f"- Company: {job.get(chr(39)+'company'+chr(39))}\n"
        f"- Location: {job.get(chr(39)+'location'+chr(39))}\n"
        f"- Salary: {job.get(chr(39)+'salary_text'+chr(39), chr(39)+'Not stated'+chr(39))}\n"
        f"- Description: {jd}\n\n"
        "Scoring: 90-100=perfect, 75-89=strong, 65-74=good, below 65=skip.\n"
        "Respond with ONLY valid JSON (no markdown):\n"
        '{"score": <int>, "reason": "<one sentence>"}'
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=65, max=130))
def _call_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        contents=prompt
    )
    return response.text


def _parse(raw: str) -> tuple:
    try:
        clean = raw.strip()
        for fence in ("```json", "```"):
            if clean.startswith(fence):
                clean = clean[len(fence):]
        clean = clean.rstrip("`").strip()
        d = json.loads(clean)
        return max(0, min(100, int(d.get("score", 0)))), str(d.get("reason", ""))
    except Exception as e:
        logger.warning(f"[Scorer] Parse error: {e} | raw={raw[:80]}")
        return 0, "parse error"


def score_jobs(jobs: list, profile: dict, prefs: dict) -> list:
    threshold = int(os.getenv("MIN_SUITABILITY_SCORE",
                   prefs.get("job_preferences", {}).get("min_suitability_score", 65)))
    to_score = [j for j in jobs if j.get("status") == "found"]
    logger.info(f"[Scorer] Scoring {len(to_score)} jobs (threshold={threshold}, ~{len(to_score)*5}s)")

    for i, job in enumerate(to_score):
        try:
            score, reason = _parse(_call_gemini(_build_prompt(job, profile)))
            job["score"]        = score
            job["score_reason"] = reason
            job["status"]       = "suitable" if score >= threshold else "skipped"
            icon = "OK " if job["status"] == "suitable" else "   "
            logger.info(f"[Scorer] {icon} {job.get(chr(39)+'company'+chr(39),chr(39)+'?'+chr(39))} — {job.get(chr(39)+'title'+chr(39),chr(39)+'?'+chr(39))}: {score}/100 — {reason}")
        except Exception as e:
            logger.error(f"[Scorer] Failed {job.get(chr(39)+'company'+chr(39))}: {e}")
            job["score"], job["score_reason"], job["status"] = 0, str(e), "skipped"
        time.sleep(5)  # 12 req/min — safely under Gemini free tier 15 RPM

    suitable = sum(1 for j in to_score if j.get("status") == "suitable")
    logger.info(f"[Scorer] Done — {suitable}/{len(to_score)} suitable")
    return jobs
