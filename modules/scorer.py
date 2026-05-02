"""scorer.py — Groq (Llama 3.3 70B) with Gemini fallback"""
import os, json, time, logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

def _build_prompt(job, profile):
    jd     = (job.get("description") or "")[:3000]
    skills = ", ".join(profile.get("core_skills", []))
    roles  = ", ".join(profile.get("target_roles", []))
    return (
        "You are an expert recruiter. Score job suitability 0-100 for this candidate.\n\n"
        f"CANDIDATE: {profile.get('name','')}\n"
        f"Experience: {profile.get('total_experience_years', 10)} years\n"
        f"Target Roles: {roles}\n"
        f"Skills: {skills}\n"
        f"Summary: {profile.get('summary', '')}\n\n"
        f"JOB: {job.get('title')} at {job.get('company')}\n"
        f"Location: {job.get('location')}\n"
        f"Salary: {job.get('salary_text', 'Not stated')}\n"
        f"Description: {jd}\n\n"
        "Score 0-100 (90+=perfect, 75-89=strong, 65-74=good, <65=skip).\n"
        'Respond ONLY with valid JSON: {"score": <int>, "reason": "<one sentence>"}'
    )

@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=10, max=30))
def _call_llm(prompt):
    """Try Groq first, fall back to Gemini."""
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=200,
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning(f"[Scorer] Groq failed ({e}), trying Gemini...")

    # Gemini fallback
    from google import genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"), contents=prompt)
    return response.text

def _parse(raw):
    try:
        clean = raw.strip()
        for f in ("```json", "```"):
            if clean.startswith(f): clean = clean[len(f):]
        clean = clean.rstrip("`").strip()
        d = json.loads(clean)
        return max(0, min(100, int(d.get("score", 0)))), str(d.get("reason", ""))
    except Exception as e:
        logger.warning(f"[Scorer] Parse error: {e}")
        return 0, "parse error"

def score_jobs(jobs, profile, prefs):
    threshold = int(os.getenv("MIN_SUITABILITY_SCORE",
                   prefs.get("job_preferences", {}).get("min_suitability_score", 65)))
    to_score = [j for j in jobs if j.get("status") == "found"]
    logger.info(f"[Scorer] Scoring {len(to_score)} jobs (threshold={threshold})")

    for i, job in enumerate(to_score):
        try:
            score, reason = _parse(_call_llm(_build_prompt(job, profile)))
            job["score"]        = score
            job["score_reason"] = reason
            job["status"]       = "suitable" if score >= threshold else "skipped"
            icon = "OK " if job["status"] == "suitable" else "   "
            logger.info(f"[Scorer] {icon} {job.get('company','?')} — {job.get('title','?')}: {score}/100 — {reason}")
        except Exception as e:
            logger.error(f"[Scorer] Failed {job.get('company')}: {e}")
            job["score"], job["score_reason"], job["status"] = 0, str(e), "skipped"
        time.sleep(2)  # 2s = 30 req/min, safely under Groq free tier

    suitable = sum(1 for j in to_score if j.get("status") == "suitable")
    logger.info(f"[Scorer] Done — {suitable}/{len(to_score)} suitable")
    return jobs
