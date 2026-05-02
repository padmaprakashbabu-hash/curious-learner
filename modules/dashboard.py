"""
Dashboard module for Priyanka's job search agent.
Generates a self-contained HTML dashboard with job listings and statistics.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional


def generate_dashboard(jobs: list[dict], stats: dict, run_history: list[dict]) -> str:
    """
    Generate a beautiful self-contained HTML dashboard.
    
    Args:
        jobs: List of job dictionaries with keys: role, company, source, score, salary, posted_date, status, apply_url, job_url
        stats: Dict with keys: total_fetched, total_filtered, total_suitable, total_applied, total_action_required, total_skipped
        run_history: List of dicts with keys: date, applied, action_required
    
    Returns:
        HTML string for the dashboard
    """
    # Sort jobs by score descending
    sorted_jobs = sorted(jobs, key=lambda x: x.get("score") or 0, reverse=True)
    
    # Generate applications over time chart data
    chart_labels = [run["date"] for run in run_history[-14:]]  # Last 14 days
    chart_applied = [run["applied"] for run in run_history[-14:]]
    chart_action = [run["action_required"] for run in run_history[-14:]]
    
    labels_json = '[' + ', '.join(f'"{label}"' for label in chart_labels) + ']'
    applied_json = '[' + ', '.join(str(val) for val in chart_applied) + ']'
    action_json = '[' + ', '.join(str(val) for val in chart_action) + ']'
    
    # Build jobs table rows
    jobs_html = ""
    for idx, job in enumerate(sorted_jobs, 1):
        status = job.get("status", "found")
        status_color = {
            "applied": "#10b981",
            "suitable": "#3b82f6",
            "action_required": "#f59e0b",
            "skipped": "#9ca3af"
        }.get(status, "#9ca3af")
        
        salary_text = f"${job.get('salary', 'N/A')}" if job.get("salary") else "N/A"
        
        action_html = f'<a href="{job.get("job_url", "#")}" target="_blank" style="color: #3b82f6; text-decoration: none;">View Job</a>'
        
        if status == "action_required" and job.get("apply_url"):
            action_html += f' | <a href="{job.get("apply_url", "#")}" target="_blank" style="color: #ef4444; text-decoration: none; font-weight: bold;">Apply Now</a>'
        
        jobs_html += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: #9ca3af;">{idx}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: #f3f4f6;">{job.get("role", "N/A")}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: #f3f4f6;">{job.get("company", "N/A")}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: #9ca3af;">{job.get("source", "N/A")}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: #10b981; font-weight: bold;">{job.get("score", 0):.1f}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: #9ca3af;">{salary_text}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: #9ca3af;">{job.get("posted_date", "N/A")}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <span style="background-color: {status_color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                    {status.replace("_", " ").title()}
                </span>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px;">
                {action_html}
            </td>
        </tr>
        """
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name}'s Job Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #111827;
            --bg-secondary: #1f2937;
            --bg-tertiary: #374151;
            --text-primary: #f3f4f6;
            --text-secondary: #d1d5db;
            --text-tertiary: #9ca3af;
            --border-color: #4b5563;
            --color-blue: #3b82f6;
            --color-orange: #f59e0b;
            --color-green: #10b981;
            --color-teal: #14b8a6;
            --color-red: #ef4444;
            --color-gray: #9ca3af;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            margin-bottom: 30px;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 20px;
        }}
        
        h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            color: var(--text-primary);
        }}
        
        .last-updated {{
            font-size: 13px;
            color: var(--text-tertiary);
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }}
        
        .stat-card.blue {{ border-left: 4px solid var(--color-blue); }}
        .stat-card.orange {{ border-left: 4px solid var(--color-orange); }}
        .stat-card.green {{ border-left: 4px solid var(--color-green); }}
        .stat-card.teal {{ border-left: 4px solid var(--color-teal); }}
        .stat-card.red {{ border-left: 4px solid var(--color-red); }}
        .stat-card.gray {{ border-left: 4px solid var(--color-gray); }}
        
        .stat-label {{
            font-size: 12px;
            color: var(--text-tertiary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        
        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        .filters {{
            margin-bottom: 20px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        .filter-btn {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s;
        }}
        
        .filter-btn:hover, .filter-btn.active {{
            background-color: var(--color-blue);
            border-color: var(--color-blue);
            color: white;
        }}
        
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin: 30px 0 16px 0;
            color: var(--text-primary);
        }}
        
        .chart-container {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            max-width: 100%;
            height: 300px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        table thead {{
            background-color: var(--bg-tertiary);
            border-bottom: 2px solid var(--border-color);
        }}
        
        table th {{
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-secondary);
            letter-spacing: 0.5px;
        }}
        
        table tbody tr:hover {{
            background-color: var(--bg-tertiary);
        }}
        
        a {{
            color: var(--color-blue);
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            table {{
                font-size: 12px;
            }}
            
            table td, table th {{
                padding: 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 {name}'s Job Dashboard</h1>
            <div class="last-updated">Last updated: {datetime.now().strftime("%B %d, %Y at %I:%M %p IST")}</div>
        </header>
        
        <section class="stats-grid">
            <div class="stat-card blue">
                <div class="stat-label">🔍 Searched</div>
                <div class="stat-value">{stats.get("total_fetched", 0)}</div>
            </div>
            <div class="stat-card orange">
                <div class="stat-label">📋 Filtered</div>
                <div class="stat-value">{stats.get("total_filtered", 0)}</div>
            </div>
            <div class="stat-card green">
                <div class="stat-label">✅ Suitable</div>
                <div class="stat-value">{stats.get("total_suitable", 0)}</div>
            </div>
            <div class="stat-card teal">
                <div class="stat-label">📤 Applied</div>
                <div class="stat-value">{stats.get("total_applied", 0)}</div>
            </div>
            <div class="stat-card red">
                <div class="stat-label">⚡ Action Required</div>
                <div class="stat-value">{stats.get("total_action_required", 0)}</div>
            </div>
            <div class="stat-card gray">
                <div class="stat-label">⏭️ Skipped</div>
                <div class="stat-value">{stats.get("total_skipped", 0)}</div>
            </div>
        </section>
        
        <div class="section-title">📊 Applications Over Time</div>
        <div class="chart-container">
            <canvas id="applicationsChart"></canvas>
        </div>
        
        <div style="margin-bottom: 20px;">
            <div class="filters" id="filterButtons">
                <button class="filter-btn active" onclick="filterTable('all')">All</button>
                <button class="filter-btn" onclick="filterTable('applied')">Applied</button>
                <button class="filter-btn" onclick="filterTable('suitable')">Suitable</button>
                <button class="filter-btn" onclick="filterTable('action_required')">Action Required</button>
            </div>
        </div>
        
        <div class="section-title">💼 Job Listings</div>
        <table id="jobsTable">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Role</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Score</th>
                    <th>Salary</th>
                    <th>Posted</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {jobs_html}
            </tbody>
        </table>
    </div>
    
    <script>
        const ctx = document.getElementById('applicationsChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {labels_json},
                datasets: [
                    {{
                        label: 'Applied',
                        data: {applied_json},
                        backgroundColor: '#14b8a6',
                        borderColor: '#0d9488',
                        borderWidth: 1
                    }},
                    {{
                        label: 'Action Required',
                        data: {action_json},
                        backgroundColor: '#f59e0b',
                        borderColor: '#d97706',
                        borderWidth: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#d1d5db' }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#9ca3af' }},
                        grid: {{ color: '#4b5563' }}
                    }},
                    y: {{
                        beginAtZero: true,
                        ticks: {{ color: '#9ca3af' }},
                        grid: {{ color: '#4b5563' }}
                    }}
                }}
            }}
        }});
        
        function filterTable(status) {{
            const rows = document.querySelectorAll('#jobsTable tbody tr');
            rows.forEach(row => {{
                if (status === 'all') {{
                    row.style.display = '';
                }} else {{
                    const statusCell = row.querySelector('span').textContent.toLowerCase();
                    if (statusCell.includes(status.replace('_', ' '))) {{
                        row.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                    }}
                }}
            }});
            
            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            event.target.classList.add('active');
        }}
    </script>
</body>
</html>"""
    
    return html


def save_dashboard(html: str, path: str = "dashboard/index.html") -> bool:
    """
    Save the dashboard HTML to a file.
    Creates directory if needed.
    
    Args:
        html: HTML string to save
        path: File path (relative or absolute)
    
    Returns:
        True on success, False on failure
    """
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(html)
        return True
    except Exception as e:
        print(f"Error saving dashboard: {e}")
        return False
