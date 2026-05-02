"""
SQLite database wrapper for the job search agent.

Manages persistent storage of jobs and run statistics.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any


logger = logging.getLogger(__name__)


class JobDatabase:
    """SQLite database wrapper for job search agent."""

    def __init__(self, db_path: str = "data/jobs.db") -> None:
        """
        Initialize database connection and create tables if needed.

        Args:
            db_path: Path to SQLite database file (created if doesn't exist).
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Database initialized at {self.db_path}")

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()

        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                job_url TEXT UNIQUE NOT NULL,
                apply_url TEXT,
                apply_email TEXT,
                description TEXT,
                date_posted TEXT,
                salary_text TEXT,
                source TEXT,
                score REAL,
                cover_letter TEXT,
                status TEXT,
                apply_platform TEXT,
                applied_at TEXT,
                fetched_at TEXT,
                filter_reason TEXT
            )
        """)

        # Runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT,
                jobs_fetched INT,
                jobs_passed_filter INT,
                jobs_scored INT,
                jobs_suitable INT,
                jobs_applied INT,
                jobs_action_required INT,
                jobs_skipped INT
            )
        """)

        self.conn.commit()
        logger.debug("Tables created or verified")

    def save_jobs(self, jobs: list[dict]) -> int:
        """
        Insert jobs into database, skipping duplicates by job_url.

        Args:
            jobs: List of job dictionaries.

        Returns:
            Count of jobs successfully inserted.
        """
        cursor = self.conn.cursor()
        inserted = 0

        for job in jobs:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO jobs (
                        title, company, location, job_url, apply_url, apply_email,
                        description, date_posted, salary_text, source, score,
                        cover_letter, status, apply_platform, applied_at, fetched_at,
                        filter_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.get("title"),
                    job.get("company"),
                    job.get("location"),
                    job.get("job_url"),
                    job.get("apply_url"),
                    job.get("apply_email"),
                    job.get("description"),
                    job.get("date_posted"),
                    job.get("salary_text"),
                    job.get("source"),
                    job.get("score"),
                    job.get("cover_letter"),
                    job.get("status"),
                    job.get("apply_platform"),
                    job.get("applied_at"),
                    job.get("fetched_at", datetime.now().isoformat()),
                    job.get("filter_reason"),
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Failed to insert job {job.get('job_url')}: {e}")

        self.conn.commit()
        logger.info(f"Saved {inserted} new jobs to database")
        return inserted

    def update_job(self, job_url: str, **kwargs) -> None:
        """
        Update job fields by job_url.

        Args:
            job_url: URL of job to update.
            **kwargs: Field names and values to update.
        """
        if not kwargs:
            return

        cursor = self.conn.cursor()
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [job_url]

        try:
            cursor.execute(f"UPDATE jobs SET {fields} WHERE job_url = ?", values)
            self.conn.commit()
            logger.debug(f"Updated job {job_url} with {len(kwargs)} fields")
        except sqlite3.Error as e:
            logger.error(f"Failed to update job {job_url}: {e}")

    def get_jobs(self, status: Optional[str] = None) -> list[dict]:
        """
        Fetch jobs, optionally filtered by status.

        Args:
            status: Filter by status (e.g., 'applied', 'pending'). If None, fetch all.

        Returns:
            List of job dictionaries.
        """
        cursor = self.conn.cursor()

        if status:
            cursor.execute("SELECT * FROM jobs WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT * FROM jobs")

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_all_jobs(self) -> list[dict]:
        """
        Fetch all jobs for dashboard.

        Returns:
            List of all job dictionaries.
        """
        return self.get_jobs(status=None)

    def job_exists(self, job_url: str) -> bool:
        """
        Check if job already exists by job_url.

        Args:
            job_url: URL to check.

        Returns:
            True if job exists, False otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM jobs WHERE job_url = ?", (job_url,))
        return cursor.fetchone() is not None

    def save_run(self, run_data: dict) -> int:
        """
        Save a run record with statistics.

        Args:
            run_data: Dictionary with keys like jobs_fetched, jobs_passed_filter, etc.

        Returns:
            run_id of the inserted record.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO runs (
                    run_date, jobs_fetched, jobs_passed_filter, jobs_scored,
                    jobs_suitable, jobs_applied, jobs_action_required, jobs_skipped
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_data.get("run_date", datetime.now().isoformat()),
                run_data.get("jobs_fetched", 0),
                run_data.get("jobs_passed_filter", 0),
                run_data.get("jobs_scored", 0),
                run_data.get("jobs_suitable", 0),
                run_data.get("jobs_applied", 0),
                run_data.get("jobs_action_required", 0),
                run_data.get("jobs_skipped", 0),
            ))
            self.conn.commit()
            run_id = cursor.lastrowid
            logger.info(f"Saved run record with id {run_id}")
            return run_id
        except sqlite3.Error as e:
            logger.error(f"Failed to save run: {e}")
            return -1

    def get_stats(self) -> dict:
        """
        Get job statistics grouped by status for dashboard.

        Returns:
            Dictionary with counts per status and total.
        """
        cursor = self.conn.cursor()

        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM jobs
            GROUP BY status
        """)
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Total
        cursor.execute("SELECT COUNT(*) FROM jobs")
        total = cursor.fetchone()[0]

        stats = {
            "total": total,
            "by_status": status_counts,
        }
        logger.debug(f"Stats: {stats}")
        return stats

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
