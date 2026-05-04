"""
date_filter.py — Filters jobs by date, title relevance, and IST-compatible location.
Keeps: India, Bangalore, Remote (global), Remote UK/EU/ME/APAC.
Rejects: Remote US/Americas, other Indian cities (Chennai, Hyderabad etc).
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

RELEVANT_TITLE_KEYWORDS = [
    "program manager","programme manager","project manager","project lead",
    "product manager","product lead","senior pm","sr pm","principal pm",
    "technical program","tpm","operations manager","operations lead",
    "supply chain","logistics manager","delivery manager","engagement manager",
    "portfolio manager","business analyst","business program","strategy manager",
    "strategy lead","consulting manager","solutions manager","scrum master",
    "agile coach","transformation manager",
]

# IST ± 4 hours: UK(UTC+0), EU(UTC+1-2), ME/UAE(UTC+4), APAC, India
IST_COMPATIBLE_REGIONS = [
    "india","bangalore","bengaluru","karnataka",
    "remote, in","remote, india","remote, uk","remote, gb","remote, eu","remote, europe",
    "remote, uae","remote, middle east","remote, apac","remote, asia","remote, singapore",
    "remote, australia","remote, global","worldwide","global","anywhere",
]

# US states and non-compatible locations
REJECT_LOCATIONS = [
    # US remote (10.5-13.5h behind IST — no viable overlap)
    "remote, us","remote, ca","remote, ny","remote, tx","remote, wa","remote, fl",
    "remote, il","remote, ga","remote, ma","remote, co","remote, or","remote, nc",
    "remote, va","remote, az","remote, nj","remote, oh","remote, pa","remote, mi",
    # US cities
    "new york","san francisco","los angeles","seattle","chicago","boston","austin",
    "dallas","atlanta","denver","phoenix","san jose","san diego","portland",
    "morris, nj","long beach","fremont, ca",
    # Indian cities (not Bangalore)
    "kochi","ernakulam","kerala","trivandrum","thiruvananthapuram","thrissur",
    "chennai","hyderabad","pune","mumbai","delhi","noida","gurgaon","gurugram",
    "kolkata","ahmedabad","jaipur","nagpur","surat",
    # Americas (not IST compatible)
    "toronto","vancouver","montreal","remote, canada","remote, brazil","remote, mexico",
    "remote, latam","buenos aires",
]

# US timezone keywords in job descriptions
US_TZ_KEYWORDS = [
    "pst","est","cst","mst","pacific time","eastern time","central time","mountain time",
    "us time zone","us time","north america only","must be us","united states based",
    "us-based","us based",
]


def _is_title_relevant(title):
    t = (title or "").lower()
    return any(kw in t for kw in RELEVANT_TITLE_KEYWORDS)


def _is_location_compatible(job, prefs):
    """Returns True if job is accessible from Bangalore in IST ± 4h buffer."""
    location = (job.get("location") or "").lower().strip()
    desc     = (job.get("description") or "")[:600].lower()

    # Empty location = assume global/flexible, keep
    if not location or location in ("n/a", "not specified", ""):
        return True

    # Explicitly IST-compatible regions
    if any(k in location for k in IST_COMPATIBLE_REGIONS):
        return True

    # Plain "remote" with no qualifier = global remote, keep
    if location.strip() in ("remote", "remote / work from home", "remote / wfh", "work from home"):
        return True

    # Check reject list
    if any(r in location for r in REJECT_LOCATIONS):
        # Last chance: description explicitly mentions India/APAC/global
        if any(kw in desc for kw in ["india", "apac", "asia pacific", "global remote", "worldwide", "bengaluru"]):
            return True
        logger.debug(f"[Filter] Rejected location: {location}")
        return False

    # "Remote" with unknown qualifier — check description for US timezone hints
    if "remote" in location:
        if any(kw in desc for kw in US_TZ_KEYWORDS):
            logger.debug(f"[Filter] Remote job with US timezone requirement: {location}")
            return False
        return True  # Remote without US hints = keep

    # Unknown — be permissive
    return True


def filter_jobs(jobs, prefs):
    """Returns (passed, rejected). Applies all filters including IST location check."""
    max_age = prefs.get("job_preferences", {}).get("max_job_age_days", 10)
    exc_kw  = [k.lower() for k in prefs.get("excluded_keywords", [])]
    exc_cos = [c.lower() for c in prefs.get("excluded_companies", [])]

    logger.info(f"Starting filter on {len(jobs)} jobs")
    passed, rejected = [], []
    seen = set()

    for job in jobs:
        url     = (job.get("job_url") or "").strip()
        title   = job.get("title", "") or ""
        company = (job.get("company") or "").lower()
        desc    = (job.get("description") or "").lower()
        t_lower = title.lower()

        if not url:
            job["filter_reason"] = "empty_url"; rejected.append(job); continue
        if url in seen:
            job["filter_reason"] = "duplicate_url"; rejected.append(job); continue
        seen.add(url)

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

        if any(kw in t_lower or kw in desc for kw in exc_kw):
            job["filter_reason"] = "excluded_keyword"; rejected.append(job); continue
        if company in exc_cos:
            job["filter_reason"] = "excluded_company"; rejected.append(job); continue
        if not _is_title_relevant(title):
            job["filter_reason"] = f"irrelevant_title: {title[:60]}"
            rejected.append(job); continue
        if not _is_location_compatible(job, prefs):
            job["filter_reason"] = f"timezone_incompatible: {job.get('location','')}"
            rejected.append(job); continue

        passed.append(job)

    reasons = {}
    for j in rejected:
        r = j.get("filter_reason","?").split(":")[0]
        reasons[r] = reasons.get(r, 0) + 1
    logger.info(f"Filter: {len(passed)} passed, {len(rejected)} rejected — {reasons}")
    return passed, rejected
