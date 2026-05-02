"""main.py — Job Search Agent: Find & Prepare, then launch Web UI for approval"""
import sys, os, json, argparse, logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.job_fetcher   import fetch_all_jobs
from modules.date_filter   import filter_jobs
from modules.scorer        import score_jobs
from modules.company_ratings import enrich_with_ratings, filter_by_rating
from modules.cover_letter  import generate_cover_letters
from modules.resume_tailor import tailor_resumes
from modules.dashboard     import generate_dashboard, save_dashboard
from modules.db            import JobDatabase


def setup_logging():
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    fh = RotatingFileHandler(logs_dir / "agent.log", maxBytes=5*1024*1024, backupCount=3)
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt); ch.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(ch)
    return logger


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def run_pipeline():
    """Steps 1-4: Fetch, filter, score, tailor. Populates DB. Then launches web UI."""
    logger = logging.getLogger(__name__)
    load_dotenv()

    logger.info("=" * 60)
    logger.info("=== Job Search Agent — Find & Prepare ===")
    logger.info("=" * 60)

    config_dir = project_root / "config"
    profile    = load_json(config_dir / "profile.json")
    prefs      = load_json(config_dir / "preferences.json")

    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    db = JobDatabase(str(data_dir / "jobs.db"))

    # 1. Fetch
    logger.info("[1/4] Fetching jobs across all boards...")
    raw_jobs = fetch_all_jobs(profile, prefs)
    logger.info(f"      {len(raw_jobs)} raw listings found")

    # 2. Filter & dedup
    logger.info("[2/4] Filtering & deduplicating...")
    passed, rejected = filter_jobs(raw_jobs, prefs)
    logger.info(f"      {len(passed)} passed | {len(rejected)} filtered out")
    new_count = db.save_jobs(passed)
    logger.info(f"      {new_count} new jobs saved to DB")

    # 3. Score & rank
    logger.info("[3/4] Scoring with Gemini...")
    jobs_to_score = db.get_jobs(status="found")
    if jobs_to_score:
        scored = score_jobs(jobs_to_score, profile, prefs)
        for j in scored:
            db.update_job(j["job_url"], status=j["status"],
                          score=j.get("score", 0),
                          score_reason=j.get("score_reason", ""))

    # Enrich with Glassdoor ratings and filter low-rated companies
    min_rating = prefs.get('job_preferences',{}).get('min_glassdoor_rating',0)
    if min_rating:
        all_found = db.get_jobs(status='suitable')
        enriched  = enrich_with_ratings(all_found, min_rating, str(data_dir/'jobs.db'))
        for j in (x for x in enriched if x):
            db.update_job(j['job_url'], glassdoor_rating=j.get('glassdoor_rating'))
            reason = j.get('filter_reason') or ''
            if reason.startswith('glassdoor'):
                db.update_job(j['job_url'], status='skipped', score_reason=reason)
    suitable = sorted(db.get_jobs(status="suitable"),
                      key=lambda j: j.get("score") or 0, reverse=True)
    logger.info(f"      {len(suitable)} suitable jobs (score >= {prefs['job_preferences']['min_suitability_score']})")

    if not suitable:
        logger.info("No suitable jobs found this run.")
    else:
        # 4. Tailor resume + cover letter
        logger.info(f"[4/4] Generating {len(suitable)} cover letters (resumes tailored on-demand)...")
        # Tailoring moved to on-demand in /api/apply — runs only for approved jobs
    # suitable = tailor_resumes(suitable, profile, prefs)
        suitable = generate_cover_letters(suitable, profile, prefs)
        for j in suitable:
            db.update_job(j["job_url"],
                          tailored_resume_path=j.get("tailored_resume_path", ""),
                          cover_letter=j.get("cover_letter", ""))
        logger.info(f"      Done — {len(suitable)} ready for review")

    # Refresh dashboard before launching UI
    all_jobs    = db.get_all_jobs()
    stats       = db.get_stats()
    run_history = db.get_run_history(days=14) if hasattr(db, "get_run_history") else []
    html        = generate_dashboard(all_jobs, stats, run_history)
    save_dashboard(html, str(project_root / "dashboard" / "index.html"))

    logger.info("=" * 60)
    logger.info(f"Pipeline done. Launching web UI for you to review & apply...")
    logger.info("=" * 60)

    # Launch web UI
    from app import run_server
    run_server(port=8080, open_browser_auto=True)


def main():
    parser = argparse.ArgumentParser(description="Job Search Agent")
    parser.add_argument("--find", action="store_true",
                        help="Find & prepare jobs, then open web UI to review & apply")
    parser.add_argument("--ui", action="store_true",
                        help="Open web UI only (skip pipeline, use existing DB)")
    args = parser.parse_args()

    setup_logging()

    if args.find:
        run_pipeline()
    elif args.ui:
        load_dotenv()
        print("\n  Opening web UI with existing jobs from DB...")
        from app import run_server
        run_server(port=8080, open_browser_auto=True)
    else:
        parser.print_help()
        print("\nUsage:")
        print("  python3.11 main.py --find    # Full run: find jobs → prepare → review UI")
        print("  python3.11 main.py --ui      # Just open the UI (jobs already in DB)\n")


if __name__ == "__main__":
    main()
