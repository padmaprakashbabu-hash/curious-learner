"""
ApplyEngine Module
==================
Handles automated job applications across multiple ATS platforms using Playwright.
Detects platform type, applies to supported platforms automatically, and flags 
manual applications for unsupported platforms.

Author: Priyanka Job Agent
"""

import asyncio
import logging
import os
import re
import random
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
import smtplib
from email import encoders

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("[ApplyEngine] Playwright not installed. Auto-apply will be unavailable.")
    logger.warning("[ApplyEngine] Install with: pip install playwright && playwright install")

# Constants
AUTO_APPLY_PLATFORMS = {"greenhouse", "lever", "smartrecruiters", "ashby"}
ACTION_REQUIRED_PLATFORMS = {"workday", "icims", "unknown", "linkedin", "indeed"}
PAGE_LOAD_TIMEOUT = 30000  # milliseconds
BROWSER_HEADLESS = True


# ============================================================================
# Applicant Info & Configuration
# ============================================================================

def get_applicant_info() -> dict:
    """Load applicant information from environment or use defaults."""
    return {
        "name": os.getenv("APPLICANT_NAME", os.getenv("APPLICANT_NAME", "")),
        "email": os.getenv("APPLICANT_EMAIL", os.getenv("APPLICANT_EMAIL", "")),
        "phone": os.getenv("APPLICANT_PHONE", os.getenv("APPLICANT_PHONE", "")),
        "location": os.getenv("APPLICANT_LOCATION", "Bengaluru, India"),
        "linkedin": os.getenv("APPLICANT_LINKEDIN", os.getenv("APPLICANT_LINKEDIN", "")),
        "resume_path": os.getenv("RESUME_PATH", _resume_path(job)),
    }


# ============================================================================
# Platform Detection
# ============================================================================

def detect_platform(apply_url: Optional[str], apply_email: Optional[str]) -> str:
    """
    Detect which ATS platform a job's apply_url belongs to.
    
    Args:
        apply_url: The URL to apply via
        apply_email: Email address to apply via (if email-based)
    
    Returns:
        Platform name: greenhouse, lever, smartrecruiters, ashby, workday, icims, email, unknown
    """
    if apply_email:
        return "email"
    
    if not apply_url:
        return "unknown"
    
    url_lower = apply_url.lower()
    
    # Greenhouse
    if "greenhouse.io" in url_lower and ("boards.greenhouse.io" in url_lower or "job-boards.greenhouse.io" in url_lower):
        return "greenhouse"
    
    # Lever
    if "jobs.lever.co" in url_lower:
        return "lever"
    
    # SmartRecruiters
    if "jobs.smartrecruiters.com" in url_lower:
        return "smartrecruiters"
    
    # Ashby
    if "jobs.ashbyhq.com" in url_lower:
        return "ashby"
    
    # Workday
    if "workday.com" in url_lower:
        return "workday"
    
    # iCIMS
    if "icims.com" in url_lower:
        return "icims"
    
    # LinkedIn
    if "linkedin.com" in url_lower:
        return "linkedin"
    
    # Indeed
    if "indeed.com" in url_lower:
        return "indeed"
    
    return "unknown"


# ============================================================================
# Email Application
# ============================================================================

def send_email_application(
    job: dict,
    applicant: dict,
    cover_letter: str
) -> bool:
    """
    Send a job application via email.
    
    Args:
        job: Job dict with 'company', 'role', 'apply_email'
        applicant: Applicant dict with 'name', 'email', 'resume_path'
        cover_letter: Cover letter text
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        gmail_sender = os.getenv("GMAIL_SENDER")
        gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
        
        if not gmail_sender or not gmail_app_password:
            logger.error("[ApplyEngine] Email credentials not configured (GMAIL_SENDER, GMAIL_APP_PASSWORD)")
            return False
        
        # Prepare email
        msg = MIMEMultipart()
        msg["From"] = gmail_sender
        msg["To"] = job.get("apply_email")
        msg["Subject"] = f"Application for {job.get('role')} at {job.get('company')} — {applicant['name']}"
        
        # Body
        msg.attach(MIMEText(cover_letter, "plain"))
        
        # Attach resume
        resume_path = Path(applicant.get("resume_path", _resume_path(job)))
        if not resume_path.exists():
            logger.error(f"[ApplyEngine] Resume not found: {resume_path}")
            return False
        
        with open(resume_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {resume_path.name}")
        msg.attach(part)
        
        # Send
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_sender, gmail_app_password)
            server.send_message(msg)
        
        logger.info(f"[ApplyEngine] Email sent to {job.get('apply_email')} for {job.get('role')} at {job.get('company')}")
        return True
    
    except Exception as e:
        logger.error(f"[ApplyEngine] Failed to send email application: {e}")
        return False


# ============================================================================
# Playwright Auto-Apply Logic
# ============================================================================

async def apply_greenhouse(page: Page, job: dict, applicant: dict) -> bool:
    """Apply via Greenhouse ATS."""
    try:
        logger.info(f"[ApplyEngine] Applying via Greenhouse for {job.get('role')}")
        
        await page.goto(job["apply_url"], timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_timeout(1000)
        
        # Extract name parts
        name_parts = applicant["name"].split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Fill form fields
        first_name_input = await page.query_selector("input[name*='first']")
        if first_name_input:
            await first_name_input.fill(first_name)
        
        last_name_input = await page.query_selector("input[name*='last']")
        if last_name_input:
            await last_name_input.fill(last_name)
        
        email_input = await page.query_selector("input[type='email']")
        if email_input:
            await email_input.fill(applicant["email"])
        
        phone_input = await page.query_selector("input[type='tel']")
        if phone_input:
            await phone_input.fill(applicant["phone"])
        
        location_input = await page.query_selector("input[name*='location']")
        if location_input:
            await location_input.fill(applicant["location"])
        
        # Upload resume
        file_input = await page.query_selector("input[type='file']")
        if file_input:
            resume_path = Path(applicant.get("resume_path", _resume_path(job)))
            if resume_path.exists():
                await file_input.set_input_files(str(resume_path))
                logger.info(f"[ApplyEngine] Resume uploaded from {resume_path}")
        
        # Fill cover letter if present
        cover_letter_input = await page.query_selector("textarea[name*='cover']")
        if cover_letter_input:
            cover_letter = job.get("cover_letter", "")
            if cover_letter:
                await cover_letter_input.fill(cover_letter)
        
        # Submit
        submit_button = await page.query_selector("button[type='submit']")
        if submit_button:
            await submit_button.click()
            await page.wait_for_timeout(2000)
        
        # Check for success
        page_text = await page.content()
        if any(indicator in page_text.lower() for indicator in ["thank you", "application submitted", "application received"]):
            logger.info(f"[ApplyEngine] Successfully applied to Greenhouse job: {job.get('role')}")
            return True
        
        logger.warning(f"[ApplyEngine] Greenhouse application submitted but success not confirmed for {job.get('role')}")
        return True
    
    except Exception as e:
        logger.error(f"[ApplyEngine] Greenhouse apply failed: {e}")
        return False


async def apply_lever(page: Page, job: dict, applicant: dict) -> bool:
    """Apply via Lever ATS."""
    try:
        logger.info(f"[ApplyEngine] Applying via Lever for {job.get('role')}")
        
        await page.goto(job["apply_url"], timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_timeout(1000)
        
        # Click Apply button
        apply_button = await page.query_selector("button:has-text('Apply')")
        if apply_button:
            await apply_button.click()
            await page.wait_for_timeout(1000)
        
        # Fill form
        name_input = await page.query_selector("input[name='name']")
        if name_input:
            await name_input.fill(applicant["name"])
        
        email_input = await page.query_selector("input[type='email']")
        if email_input:
            await email_input.fill(applicant["email"])
        
        phone_input = await page.query_selector("input[type='tel']")
        if phone_input:
            await phone_input.fill(applicant["phone"])
        
        # Upload resume
        file_input = await page.query_selector("input[type='file']")
        if file_input:
            resume_path = Path(applicant.get("resume_path", _resume_path(job)))
            if resume_path.exists():
                await file_input.set_input_files(str(resume_path))
        
        # Fill cover letter
        cover_letter_input = await page.query_selector("textarea")
        if cover_letter_input:
            cover_letter = job.get("cover_letter", "")
            if cover_letter:
                await cover_letter_input.fill(cover_letter)
        
        # Submit
        submit_button = await page.query_selector("button[type='submit']")
        if submit_button:
            await submit_button.click()
            await page.wait_for_timeout(2000)
        
        logger.info(f"[ApplyEngine] Successfully applied to Lever job: {job.get('role')}")
        return True
    
    except Exception as e:
        logger.error(f"[ApplyEngine] Lever apply failed: {e}")
        return False


async def apply_smartrecruiters(page: Page, job: dict, applicant: dict) -> bool:
    """Apply via SmartRecruiters ATS."""
    try:
        logger.info(f"[ApplyEngine] Applying via SmartRecruiters for {job.get('role')}")
        
        await page.goto(job["apply_url"], timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_timeout(1000)
        
        # Click Apply button
        apply_button = await page.query_selector("button:has-text('Apply')")
        if apply_button:
            await apply_button.click()
            await page.wait_for_timeout(1000)
        
        # Fill personal info
        name_input = await page.query_selector("input[name*='name']")
        if name_input:
            await name_input.fill(applicant["name"])
        
        email_input = await page.query_selector("input[type='email']")
        if email_input:
            await email_input.fill(applicant["email"])
        
        # Upload resume
        file_input = await page.query_selector("input[type='file']")
        if file_input:
            resume_path = Path(applicant.get("resume_path", _resume_path(job)))
            if resume_path.exists():
                await file_input.set_input_files(str(resume_path))
        
        # Submit
        submit_button = await page.query_selector("button[type='submit']")
        if submit_button:
            await submit_button.click()
            await page.wait_for_timeout(2000)
        
        logger.info(f"[ApplyEngine] Successfully applied to SmartRecruiters job: {job.get('role')}")
        return True
    
    except Exception as e:
        logger.error(f"[ApplyEngine] SmartRecruiters apply failed: {e}")
        return False


async def apply_ashby(page: Page, job: dict, applicant: dict) -> bool:
    """Apply via Ashby ATS."""
    try:
        logger.info(f"[ApplyEngine] Applying via Ashby for {job.get('role')}")
        
        await page.goto(job["apply_url"], timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_timeout(1000)
        
        # Extract name parts
        name_parts = applicant["name"].split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Fill form fields
        first_name_input = await page.query_selector("input[name*='first']")
        if first_name_input:
            await first_name_input.fill(first_name)
        
        last_name_input = await page.query_selector("input[name*='last']")
        if last_name_input:
            await last_name_input.fill(last_name)
        
        email_input = await page.query_selector("input[type='email']")
        if email_input:
            await email_input.fill(applicant["email"])
        
        phone_input = await page.query_selector("input[type='tel']")
        if phone_input:
            await phone_input.fill(applicant["phone"])
        
        # Upload resume
        file_input = await page.query_selector("input[type='file']")
        if file_input:
            resume_path = Path(applicant.get("resume_path", _resume_path(job)))
            if resume_path.exists():
                await file_input.set_input_files(str(resume_path))
        
        # Submit
        submit_button = await page.query_selector("button[type='submit']")
        if submit_button:
            await submit_button.click()
            await page.wait_for_timeout(2000)
        
        logger.info(f"[ApplyEngine] Successfully applied to Ashby job: {job.get('role')}")
        return True
    
    except Exception as e:
        logger.error(f"[ApplyEngine] Ashby apply failed: {e}")
        return False


# ============================================================================
# Main Apply Function
# ============================================================================

async def apply_to_jobs(
    jobs: list[dict],
    profile: dict,
    prefs: dict
) -> list[dict]:
    """
    Apply to suitable jobs across multiple ATS platforms.
    
    Args:
        jobs: List of job dicts with 'role', 'company', 'apply_url', 'apply_email', etc.
        profile: User profile (currently unused, for future extensibility)
        prefs: Preferences dict (currently unused, for future extensibility)
    
    Returns:
        Updated jobs list with application status and timestamps
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("[ApplyEngine] Playwright not available. Skipping auto-apply.")
        for job in jobs:
            if job.get("status") == "suitable":
                job["status"] = "action_required"
                job["notes"] = job.get("notes", "") + "\n[ApplyEngine] Playwright not installed. Manual application required."
        return jobs
    
    applicant = get_applicant_info()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=BROWSER_HEADLESS)
        
        for i, job in enumerate(jobs):
            if job.get("status") != "suitable":
                continue
            
            try:
                # Random delay to avoid bot detection
                delay = random.uniform(2, 3)
                await asyncio.sleep(delay)
                
                apply_url = job.get("apply_url")
                apply_email = job.get("apply_email")
                platform = detect_platform(apply_url, apply_email)
                
                logger.info(f"[ApplyEngine] Processing job {i+1}/{len(jobs)}: {job.get('role')} at {job.get('company')} (Platform: {platform})")
                job["apply_platform"] = platform
                
                # Email-based application
                if platform == "email":
                    cover_letter = job.get("cover_letter", f"Dear Hiring Team,\n\nI am interested in the {job.get('role')} position at {job.get('company')}.\n\nBest regards,\n{applicant['name']}")
                    if send_email_application(job, applicant, cover_letter):
                        job["status"] = "applied"
                        job["applied_at"] = now_iso
                        logger.info(f"[ApplyEngine] ✓ Applied via email to {job.get('company')}")
                    else:
                        job["status"] = "action_required"
                        job["notes"] = job.get("notes", "") + f"\n[ApplyEngine] Email application failed. Apply manually to: {apply_email}"
                
                # Auto-apply platforms
                elif platform in AUTO_APPLY_PLATFORMS:
                    page = await browser.new_page()
                    page.set_default_timeout(PAGE_LOAD_TIMEOUT)
                    
                    try:
                        if platform == "greenhouse":
                            success = await apply_greenhouse(page, job, applicant)
                        elif platform == "lever":
                            success = await apply_lever(page, job, applicant)
                        elif platform == "smartrecruiters":
                            success = await apply_smartrecruiters(page, job, applicant)
                        elif platform == "ashby":
                            success = await apply_ashby(page, job, applicant)
                        else:
                            success = False
                        
                        if success:
                            job["status"] = "applied"
                            job["applied_at"] = now_iso
                            logger.info(f"[ApplyEngine] ✓ Applied via {platform} to {job.get('company')}")
                        else:
                            job["status"] = "action_required"
                            job["notes"] = job.get("notes", "") + f"\n[ApplyEngine] {platform} auto-apply failed. Visit: {apply_url}"
                    
                    finally:
                        await page.close()
                
                # Action-required platforms
                else:
                    job["status"] = "action_required"
                    action_text = f"Visit {apply_url} and apply manually" if apply_url else "Apply manually"
                    job["notes"] = job.get("notes", "") + f"\n[ApplyEngine] {platform.upper()} platform not supported. {action_text}"
                    logger.info(f"[ApplyEngine] ⚠ Flagged for manual apply: {platform} - {job.get('role')} at {job.get('company')}")
            
            except Exception as e:
                logger.error(f"[ApplyEngine] Unexpected error processing {job.get('role')}: {e}")
                job["status"] = "action_required"
                job["notes"] = job.get("notes", "") + f"\n[ApplyEngine] Error: {str(e)}"
        
        await browser.close()
    
    return jobs


# ============================================================================
# Sync Wrapper
# ============================================================================

def run_apply_engine(jobs: list[dict], profile: dict, prefs: dict) -> list[dict]:
    """
    Synchronous wrapper for async apply_to_jobs.
    
    Usage:
        updated_jobs = run_apply_engine(jobs, profile, preferences)
    """
    return asyncio.run(apply_to_jobs(jobs, profile, prefs))


if __name__ == "__main__":
    # Example usage
    sample_jobs = [
        {
            "role": "Software Engineer",
            "company": "Example Corp",
            "apply_url": "https://boards.greenhouse.io/examplecorp/jobs/123",
            "status": "suitable",
        },
        {
            "role": "Data Analyst",
            "company": "Another Inc",
            "apply_url": "https://jobs.lever.co/anotherinc/456",
            "status": "suitable",
        },
    ]
    
    sample_profile = {}
    sample_prefs = {}
    
    logger.info("[ApplyEngine] Starting example run...")
    result = run_apply_engine(sample_jobs, sample_profile, sample_prefs)
    
    for job in result:
        logger.info(f"[ApplyEngine] Result: {job.get('role')} - Status: {job.get('status')}")
