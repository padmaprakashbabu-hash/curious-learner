"""
date_filter.py — Filters jobs by date, dedup, keywords, and title relevance.
Only passes jobs likely relevant to the user's profile to the scorer.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Titles containing ANY of these are kept for scoring
RELEVANT_TITLE_KEYWORDS = [
    "program manager", "programme manager",
    "project manager", "project lead",
    "product manager", "product lead",
    "senior pm", "sr pm", "principal pm",
    "technical program", "tpm",
    "operations manager", "operations lead",
    "supply chain", "logistics manager",
    "business analyst", "business program",
    "strategy manager", "strategy lead",
    "delivery manager", "engagement manager",
    "portfolio manager", "scrum master",
    "agile coach", "transformation manager",
    "consulting manager", "solutions manager",
]


def _is_title_relevant(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(kw in t for kw in RELEVANT_TITLE_KEYWORDS)


def filter_jobs(jobs: list, prefs: dict) -> tuple:
    """
    Returns (passed, rejected).
    Filters: empty URL → dedup → date → excluded keywords → excluded companies → title relevance.
    """
    max_age     = prefs.get("job_preferences", {}).get("max_job_age_days", 10)
    exc_kw      = [k.lower() for k in prefs.get("excluded_keywords", [])]
    exc_cos     = [c.lower() for c in prefs.get("excluded_companies", [])]

    logger.info(f"Starting filter on {len(jobs)} jobs")
    logger.info(f"  Max age: {max_age} days")
    logger.info(f"  Excluded keywords: {len(exc_kw)}")
    logger.info(f"  Excluded companies: {len(exc_cos)}")

    passed, rejected = [], []
    seen_urls = set()

    for job in jobs:
        url     = (job.get("job_url") or "").strip()
        title   = job.get("title", "") or ""
        company = (job.get("company") or "").lower()
        desc    = (job.get("description") or "").lower()
        t_lower = title.lower()

        # 1. Empty URL
        if not url:
            job["filter_reason"] = "empty_url"
            rejected.append(job)
            continue

        # 2. Dedup
        if url in seen_urls:
            job["filter_reason"] = "duplicate_url"
            rejected.append(job)
            continue
        seen_urls.add(url)

        # 3. Date check
        date_str = job.get("date_posted")
        if not date_str:
            job["filter_reason"] = "unknown_date"
            rejected.append(job)
            continue
        try:
            posted = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - posted).days
            if age > max_age:
                job["filter_reason"] = f"too_old_{age}_days"
                rejected.append(job)
                continue
        except Exception:
            job["filter_reason"] = "invalid_date_format"
            rejected.append(job)
            continue

        # 4. Excluded keywords
        if any(kw in t_lower or kw in desc for kw in exc_kw):
            job["filter_reason"] = "excluded_keyword"
            rejected.append(job)
            continue

        # 5. Excluded companies
        if company in exc_cos:
            job["filter_reason"] = "excluded_company"
            rejected.append(job)
            continue

        # 6. Title relevance — only PM/ops/supply chain titles go to Gemini
        if not _is_title_relevant(title):
            job["filter_reason"] = f"irrelevant_title: {title[:60]}"
            rejected.append(job)
            continue

        passed.append(job)

    # Summary
    reasons = {}
    for j in rejected:
        r = j.get("filter_reason", "unknown").split(":")[0].split("_")[0] if "irrelevant" not in j.get("filter_reason","") else "irrelevant_title"
        reasons[r] = reasons.get(r, 0) + 1

    logger.info(f"Filter complete: {len(passed)} passed, {len(rejected)} rejected")
    logger.info(f"  Rejections: { {k: v for k, v in sorted(reasons.items(), key=lambda x: -x[1])} }")

    return passed, rejected
