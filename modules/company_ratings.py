"""company_ratings.py — AmbitionBox + Glassdoor rating fetcher with DB cache."""
import logging, requests, sqlite3, time
logger = logging.getLogger(__name__)

def get_glassdoor_rating(company_name, db_path="data/jobs.db"):
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE IF NOT EXISTS company_ratings (company TEXT PRIMARY KEY, glassdoor_rating REAL, checked_at TEXT)")
    con.commit()
    row = con.execute("SELECT glassdoor_rating FROM company_ratings WHERE company=?", (company_name.lower(),)).fetchone()
    con.close()
    if row is not None:
        return row[0]
    rating = _fetch_rating(company_name)
    time.sleep(0.3)
    con = sqlite3.connect(db_path)
    from datetime import datetime, timezone
    con.execute("INSERT OR REPLACE INTO company_ratings VALUES (?,?,?)", (company_name.lower(), rating, datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()
    return rating

def _fetch_rating(company_name):
    hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "Accept": "application/json"}
    # Try AmbitionBox (India-focused)
    try:
        r = requests.get("https://www.ambitionbox.com/api/v2/companies/search", params={"query": company_name, "mode": "list"}, headers={**hdrs, "Referer": "https://www.ambitionbox.com/"}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            cos = data.get("data", data if isinstance(data, list) else [])
            for co in (cos[:3] if isinstance(cos, list) else []):
                rating = co.get("overallRating") or co.get("companyRating") or co.get("rating")
                if rating:
                    return float(rating)
    except Exception:
        pass
    # Fallback: Glassdoor India
    try:
        r = requests.get("https://www.glassdoor.co.in/api/employer/find", params={"query": company_name, "maxEmployers": 2, "location": "", "locationId": 0, "version": 2}, headers={**hdrs, "Referer": "https://www.glassdoor.co.in/"}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            employers = data if isinstance(data, list) else data.get("employers", [])
            for emp in employers[:2]:
                rating = emp.get("overallRating") or emp.get("rating")
                if rating:
                    return float(rating)
    except Exception:
        pass
    return None

def enrich_with_ratings(jobs, min_rating, db_path="data/jobs.db"):
    if not min_rating:
        return jobs
    companies = list({j.get("company", "") for j in jobs if j and j.get("company")})
    logger.info(f"[Glassdoor] Fetching ratings for {len(companies)} companies (min: {min_rating})")
    for company in companies:
        rating = get_glassdoor_rating(company, db_path)
        if rating is not None:
            logger.info(f"[Glassdoor] {company}: {rating}/5.0")
    filtered, rejected = [], []
    for job in jobs:
        if not job:
            continue
        company = job.get("company", "")
        rating = get_glassdoor_rating(company, db_path)
        job["glassdoor_rating"] = rating
        if rating is not None and rating < min_rating:
            job["filter_reason"] = f"glassdoor_rating_{rating:.1f}"
            rejected.append(job)
        else:
            filtered.append(job)
    logger.info(f"[Glassdoor] Kept {len(filtered)} | Filtered {len(rejected)}")
    return filtered + rejected

def filter_by_rating(jobs, min_rating):
    if not min_rating:
        return jobs, []
    passed, rejected = [], []
    for job in jobs:
        if not job:
            continue
        rating = job.get("glassdoor_rating")
        if rating is not None and rating < min_rating:
            rejected.append(job)
        else:
            passed.append(job)
    return passed, rejected
