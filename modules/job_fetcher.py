"""
job_fetcher.py
Fetches job listings from multiple sources:
  - JobSpy (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs)
  - Remotive API (remote-only free API)
  - Adzuna API (India-focused)
Returns a unified list of Job dicts.
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ─── Unified Job Schema ───────────────────────────────────────────────────────
def make_job(
    title: str,
    company: str,
    location: str,
    job_url: str,
    description: str,
    date_posted: Optional[datetime],
    salary_text: str,
    source: str,
    apply_url: Optional[str] = None,
    apply_email: Optional[str] = None,
) -> dict:
    return {
        "id": None,                  # assigned after dedup
        "title": title,
        "company": company,
        "location": location,
        "job_url": job_url,
        "apply_url": apply_url or job_url,
        "apply_email": apply_email,
        "description": description,
        "date_posted": date_posted.isoformat() if date_posted else None,
        "salary_text": salary_text,
        "source": source,
        "score": None,               # filled by scorer
        "cover_letter": None,        # filled by cover_letter generator
        "status": "found",           # found → suitable → applied / action_required / skipped
        "apply_platform": None,      # greenhouse / lever / email / action_required
        "applied_at": None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── JobSpy Fetcher ───────────────────────────────────────────────────────────
def fetch_via_jobspy(keywords: list[str], prefs: dict) -> list[dict]:
    """Uses python-jobspy to scrape LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google."""
    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.warning("python-jobspy not installed. Run: pip install python-jobspy")
        return []

    sites = prefs["job_boards"]["jobspy"]["sites"]
    results_per = prefs["job_boards"]["jobspy"]["results_per_keyword"]
    jobs = []

    for keyword in keywords:
        logger.info(f"[JobSpy] Searching: '{keyword}'")
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=keyword,
                location="Remote",
                results_wanted=results_per,
                hours_old=prefs["job_preferences"]["max_job_age_days"] * 24,
                country_indeed="India",
                linkedin_fetch_description=True,
            )
            for _, row in df.iterrows():
                date_posted = None
                if row.get("date_posted") and str(row["date_posted"]) != "NaT":
                    try:
                        date_posted = datetime.fromisoformat(str(row["date_posted"]))
                    except Exception:
                        pass

                salary = ""
                if row.get("min_amount") and row.get("max_amount"):
                    currency = row.get("currency", "")
                    salary = f"{currency} {row['min_amount']:,.0f} – {row['max_amount']:,.0f} {row.get('interval', '')}"
                elif row.get("min_amount"):
                    salary = f"{row.get('currency', '')} {row['min_amount']:,.0f}"

                jobs.append(make_job(
                    title=str(row.get("title", "")),
                    company=str(row.get("company", "")),
                    location=str(row.get("location", "Remote")),
                    job_url=str(row.get("job_url", "")),
                    description=str(row.get("description", ""))[:8000],
                    date_posted=date_posted,
                    salary_text=salary,
                    source=str(row.get("site", "jobspy")),
                    apply_url=str(row.get("job_url_direct", row.get("job_url", ""))),
                ))
        except Exception as e:
            logger.error(f"[JobSpy] Error for '{keyword}': {e}")

    logger.info(f"[JobSpy] Total fetched: {len(jobs)}")
    return jobs


# ─── Remotive Fetcher ─────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def fetch_via_remotive(keywords: list[str], prefs: dict) -> list[dict]:
    """Calls Remotive free API — remote-only jobs."""
    base_url = prefs["job_boards"]["remotive"]["base_url"]
    jobs = []
    search_terms = ["program manager", "project manager", "product manager", "senior PM"]

    for term in search_terms:
        try:
            resp = requests.get(base_url, params={"search": term, "limit": 100}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("jobs", []):
                date_posted = None
                try:
                    date_posted = datetime.fromisoformat(item["publication_date"].replace("Z", "+00:00"))
                except Exception:
                    pass

                jobs.append(make_job(
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Worldwide"),
                    job_url=item.get("url", ""),
                    description=item.get("description", "")[:8000],
                    date_posted=date_posted,
                    salary_text=item.get("salary", ""),
                    source="remotive",
                    apply_url=item.get("url", ""),
                ))
        except Exception as e:
            logger.error(f"[Remotive] Error for '{term}': {e}")

    logger.info(f"[Remotive] Total fetched: {len(jobs)}")
    return jobs


# ─── Adzuna Fetcher ───────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def fetch_via_adzuna(keywords: list[str], prefs: dict) -> list[dict]:
    """Calls Adzuna API — India jobs, requires ADZUNA_APP_ID + ADZUNA_APP_KEY."""
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        logger.warning("[Adzuna] Skipped — ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env")
        return []

    base_url = prefs["job_boards"]["adzuna"]["base_url"]
    country = prefs["job_boards"]["adzuna"]["country"]
    jobs = []

    for keyword in ["Senior Program Manager", "Senior Project Manager"]:
        try:
            url = f"{base_url}/{country}/search/1"
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 50,
                "what": keyword,
                "title_only": keyword,
                "content-type": "application/json",
            }
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                date_posted = None
                try:
                    date_posted = datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
                except Exception:
                    pass

                salary = ""
                if item.get("salary_min") and item.get("salary_max"):
                    salary = f"₹ {item['salary_min']:,.0f} – {item['salary_max']:,.0f}"

                jobs.append(make_job(
                    title=item.get("title", ""),
                    company=item.get("company", {}).get("display_name", ""),
                    location=item.get("location", {}).get("display_name", "India"),
                    job_url=item.get("redirect_url", ""),
                    description=item.get("description", "")[:8000],
                    date_posted=date_posted,
                    salary_text=salary,
                    source="adzuna",
                    apply_url=item.get("redirect_url", ""),
                ))
        except Exception as e:
            logger.error(f"[Adzuna] Error for '{keyword}': {e}")

    logger.info(f"[Adzuna] Total fetched: {len(jobs)}")
    return jobs


# ─── Main Entry Point ─────────────────────────────────────────────────────────
def fetch_all_jobs(profile: dict, prefs: dict) -> list[dict]:
    """Fetch from all enabled sources and return combined raw list."""
    keywords = profile.get("keywords_for_search", ["Senior Program Manager remote"])
    all_jobs = []

    if prefs["job_boards"]["jobspy"]["enabled"]:
        all_jobs.extend(fetch_via_jobspy(keywords, prefs))

    if prefs["job_boards"]["remotive"]["enabled"]:
        all_jobs.extend(fetch_via_remotive(keywords, prefs))

    if prefs["job_boards"]["adzuna"]["enabled"]:
        all_jobs.extend(fetch_via_adzuna(keywords, prefs))

    logger.info(f"[Fetcher] Grand total raw jobs: {len(all_jobs)}")
    return all_jobs
