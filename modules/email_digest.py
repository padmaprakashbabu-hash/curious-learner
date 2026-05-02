"""
Email digest module for Priyanka's job search agent.
Sends daily HTML email digest via Gmail SMTP.
"""

import smtplib
import logging
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


def send_daily_digest(
    jobs: list[dict],
    stats: dict,
    run_date: str
) -> bool:
    """
    Send a daily HTML email digest via Gmail SMTP.
    
    Args:
        jobs: List of job dictionaries with status, role, company, source, score, apply_url, job_url
        stats: Dict with keys: total_fetched, total_filtered, total_suitable, total_applied, total_action_required
        run_date: Date string (e.g., "2026-05-01")
    
    Returns:
        True on success, False on failure
    """
    try:
        logger = logging.getLogger(__name__)
        
        # Get config from environment
        sender = os.getenv("GMAIL_SENDER", os.getenv("GMAIL_SENDER", ""))
        app_password = os.getenv("GMAIL_APP_PASSWORD")
        recipient = os.getenv("DIGEST_RECIPIENT", os.getenv("GMAIL_SENDER", ""))
        dashboard_path = os.getenv("DASHBOARD_PATH", "dashboard/index.html")
        
        if not app_password:
            logger.error("GMAIL_APP_PASSWORD not set in environment")
            return False
        
        # Separate jobs by status
        applied_jobs = [j for j in jobs if j.get("status") == "applied"]
        action_required_jobs = [j for j in jobs if j.get("status") == "action_required"]
        
        # Build email subject
        subject = f"Job Hunt Digest — {run_date} | {len(applied_jobs)} Applied | {len(action_required_jobs)} Need Your Attention"
        
        # Build applied jobs table
        applied_html = ""
        for job in applied_jobs:
            applied_html += f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 10px; color: #f3f4f6;">{job.get("role", "N/A")}</td>
                <td style="padding: 10px; color: #f3f4f6;">{job.get("company", "N/A")}</td>
                <td style="padding: 10px; color: #9ca3af;">{job.get("source", "N/A")}</td>
                <td style="padding: 10px; color: #10b981; font-weight: bold;">{job.get("score", 0):.1f}</td>
            </tr>
            """
        
        if not applied_html:
            applied_html = '<tr><td colspan="4" style="padding: 10px; color: #9ca3af; text-align: center;">No jobs applied today</td></tr>'
        
        # Build action required table
        action_html = ""
        for job in action_required_jobs:
            apply_url = job.get("apply_url", "#")
            action_html += f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 10px; color: #f3f4f6;">{job.get("role", "N/A")}</td>
                <td style="padding: 10px; color: #f3f4f6;">{job.get("company", "N/A")}</td>
                <td style="padding: 10px;"><a href="{apply_url}" style="color: #3b82f6; text-decoration: none; font-weight: bold;">Apply Here</a></td>
                <td style="padding: 10px; color: #10b981; font-weight: bold;">{job.get("score", 0):.1f}</td>
            </tr>
            """
        
        if not action_html:
            action_html = '<tr><td colspan="4" style="padding: 10px; color: #9ca3af; text-align: center;">No action required today</td></tr>'
        
        # Build HTML body
        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Hunt Digest</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #111827;
            color: #f3f4f6;
            line-height: 1.6;
            margin: 0;
            padding: 0;
        }}
        
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #1f2937;
            border: 1px solid #374151;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .header {{
            background-color: #374151;
            padding: 20px;
            border-bottom: 2px solid #4b5563;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 700;
            color: #f3f4f6;
        }}
        
        .header p {{
            margin: 8px 0 0 0;
            color: #9ca3af;
            font-size: 13px;
        }}
        
        .content {{
            padding: 20px;
        }}
        
        .stats-row {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 12px;
            margin-bottom: 24px;
        }}
        
        .stat {{
            background-color: #111827;
            border: 1px solid #4b5563;
            border-radius: 6px;
            padding: 12px;
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 24px;
            font-weight: 700;
            color: #10b981;
        }}
        
        .stat-label {{
            font-size: 11px;
            color: #9ca3af;
            text-transform: uppercase;
            margin-top: 4px;
            letter-spacing: 0.5px;
        }}
        
        .section {{
            margin-bottom: 24px;
        }}
        
        .section-title {{
            font-size: 16px;
            font-weight: 600;
            color: #f3f4f6;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #111827;
            border: 1px solid #4b5563;
            border-radius: 6px;
            overflow: hidden;
        }}
        
        table th {{
            background-color: #374151;
            padding: 10px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            color: #d1d5db;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .footer {{
            padding: 20px;
            background-color: #111827;
            border-top: 1px solid #374151;
            font-size: 12px;
            color: #9ca3af;
            text-align: center;
        }}
        
        .footer a {{
            color: #3b82f6;
            text-decoration: none;
        }}
        
        .footer a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Job Hunt Digest</h1>
            <p>Date: {run_date}</p>
        </div>
        
        <div class="content">
            <div class="stats-row">
                <div class="stat">
                    <div class="stat-value">{stats.get("total_fetched", 0)}</div>
                    <div class="stat-label">Searched</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{stats.get("total_suitable", 0)}</div>
                    <div class="stat-label">Suitable</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{stats.get("total_applied", 0)}</div>
                    <div class="stat-label">Applied</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{stats.get("total_action_required", 0)}</div>
                    <div class="stat-label">Action Required</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">✅ Applied Today</div>
                <table>
                    <thead>
                        <tr>
                            <th>Role</th>
                            <th>Company</th>
                            <th>Source</th>
                            <th>Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {applied_html}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <div class="section-title">⚡ Your Action Required</div>
                <table>
                    <thead>
                        <tr>
                            <th>Role</th>
                            <th>Company</th>
                            <th>Apply</th>
                            <th>Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {action_html}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>📊 <a href="file://{dashboard_path}">Open Full Dashboard</a></p>
            <p style="margin-top: 12px; font-size: 11px;">This is an automated message from your Job Hunt Agent.</p>
        </div>
    </div>
</body>
</html>"""
        
        # Send email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        
        msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.sendmail(sender, recipient, msg.as_string())
        
        logger.info(f"Email digest sent to {recipient}")
        return True
        
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending digest: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending digest: {e}")
        return False
