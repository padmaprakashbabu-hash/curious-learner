"""
date_filter.py — Filters jobs by date, title relevance, and location.
Keeps: Remote, Bengaluru/Bangalore hybrid, India-wide, Worldwide.
Drops: Other Indian cities unless job description mentions remote/hybrid.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

RELEVANT_TITLE_KEYWORDS = [
    "program manager", "programme manager", "project manager", "project lead",
    "product manager", "product lead", "senior pm", "sr pm", "principal pm",
    "technical program", "tpm", "operations manager", "operations lead",
    "supply chain", "logistics manager", "delivery manager", "engagement manager",
    "portfolio manager", "business analyst", "business program", "strategy manager",
    "strategy lead", "consulting manager", "solutions manager", "scrum master",
    "agile coach", "transformation manager",
]


def _is_title_relevant(title):
    t = (title or "").lower()
    return any(kw in t for kw in RELEVANT_TITLE_KEYWORDS)


def _is_location_ok(job, prefs):
    """
    Returns True if job is remote, Bengaluru hybrid, India-wide, or worldwide.
    Rejects jobs in other specific Indian cities unless description mentions remote/hybrid.
    """
    location = (job.get("location") or "").lower()
    desc     = (job.get("description") or "").lower()
    title    = (job.get("title") or "").lower()

    allowed  = prefs.get("job_preferences", {}).get("allowed_locations", [
        "remote", "work from home", "wfh", "anywhere", "worldwide", "global",
        "india", "bangalore", "bengaluru", "karnataka", "hybrid"
    ])
    rejected_cities = prefs.get("job_preferences", {}).get("rejected_cities", [
        "mumbai", "delhi", "noida", "gurgaon", "gurugram", "hyderabad",
        "chennai", "pune", "kolkata", "ahmedabad", "jaipur"
    ])

    # Empty location → assume remote/flexible, keep
    if not location or location in ("", "n/a", "not specified"):
        return True

    # Explicitly allowed location keywords
    if any(kw in location for kw in allowed):
        return True

    # Worldwide / remote explicitly in title or description
    if any(kw in title for kw in ["remote", "work from home", "wfh"]):
        return True
    if any(kw in desc[:500] for kw in ["fully remote", "100% remote", "work from home",
                                        "remote position", "remote role", "remote opportunity",
                                        "work remotely", "wfh", "remote-first"]):
        return True

    # In a rejected city BUT description says hybrid/remote → borderline keep
    if any(city in location for city in rejected_cities):
        if any(kw in desc[:500] for kw in ["hybrid", "remote", "flexible"]):
            return True  # hybrid role in another city — Priyanka can decide
        return False  # fully on-site in another city

    # Unknown location → be permissive, keep
    return True


def filter_jobs(jobs, prefs):
    """Returns (passed, rejected). Filters by URL, dedup, date, title, location."""
    max_age    = prefs.get("job_preferences", {}).get("max_job_age_days", 10)
    exc_kw     = [k.lower() for k in prefs.get("excluded_keywords", [])]
    exc_cos    = [c.lower() for c in prefs.get("excluded_companies", [])]

    logger.info(f"Starting filter on {len(jobs)} jobs")
    logger.info(f"  Max age: {max_age} days | Excluded kw: {len(exc_kw)}")

    passed, rejected = [], []
    seen = set()

    for job in jobs:
        url     = (job.get("job_url") or "").strip()
        title   = job.get("title", "") or ""
        company = (job.get("company") or "").lower()
        desc    = (job.get("description") or "").lower()
        t_lower = title.lower()

        # 1. Empty URL
        if not url:
            job["filter_reason"] = "empty_url"; rejected.append(job); continue

        # 2. Dedup
        if url in seen:
            job["filter_reason"] = "duplicate_url"; rejected.append(job); continue
        seen.add(url)

        # 3. Date
        date_str = job.get("date_posted")
        if not date_str:
            job["filter_reason"] = "unknown_date"; rejected.append(job); continue
        try:
            posted = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - posted).days
            if age > max_age:
                job["filter_reason"] = f"too_old_{age}_days"; rejected.append(job); continue
        except Exception:
            job["filter_reason"] = "invalid_date_format"; rejected.append(job); continue

        # 4. Excluded keywords
        if any(kw in t_lower or kw in desc for kw in exc_kw):
            job["filter_reason"] = "excluded_keyword"; rejected.append(job); continue

        # 5. Excluded companies
        if company in exc_cos:
            job["filter_reason"] = "excluded_company"; rejected.append(job); continue

        # 6. Title relevance
        if not _is_title_relevant(title):
            job["filter_reason"] = f"irrelevant_title: {title[:60]}"
            rejected.append(job); continue

        # 7. Location filter (remote / Bengaluru hybrid only)
        if not _is_location_ok(job, prefs):
            loc = job.get("location", "")
            job["filter_reason"] = f"wrong_location: {loc}"
            rejected.append(job); continue

        passed.append(job)

    reasons = {}
    for j in rejected:
        r = j.get("filter_reason","?").split(":")[0].split("_")[0] \
            if "irrelevant" not in j.get("filter_reason","") \
            and "wrong" not in j.get("filter_reason","") \
            else j.get("filter_reason","?").split(":")[0]
        reasons[r] = reasons.get(r, 0) + 1

    logger.info(f"Filter complete: {len(passed)} passed, {len(rejected)} rejected")
    logger.info(f"  Rejections: {dict(sorted(reasons.items(), key=lambda x:-x[1]))}")
    return passed, rejected
