"""
app.py — Local web server for Job Review & apply UI
Serves at http://localhost:5000
"""
import os, json, re, threading, webbrowser
from pathlib import Path
from flask import Flask, jsonify, request, send_file, abort

project_root = Path(__file__).parent
app = Flask(__name__)

def load_db_jobs(status_filter=None):
    try:
        import sys; sys.path.insert(0, str(project_root))
        from modules.db import JobDatabase
        db = JobDatabase(str(project_root / "data" / "jobs.db"))
        jobs = db.get_jobs(status=status_filter) if status_filter else db.get_all_jobs()
        return jobs
    except Exception as e:
        return []

def slug(t):
    return re.sub(r"[^a-z0-9]+", "_", (t or "").lower()).strip("_")[:40]

@app.route("/api/jobs")
def api_jobs():
    jobs = load_db_jobs()
    reviewable = [j for j in jobs if j.get("status") in ("suitable","approved","action_required","applied","skipped_by_user")]
    reviewable.sort(key=lambda j: j.get("score") or 0, reverse=True)
    return jsonify(reviewable)

@app.route("/api/stats")
def api_stats():
    try:
        import sys; sys.path.insert(0, str(project_root))
        from modules.db import JobDatabase
        from dotenv import load_dotenv
        load_dotenv()
        
        db = JobDatabase(str(project_root / "data" / "jobs.db"))
        stats = db.get_stats()
        applicant_name = os.environ.get("APPLICANT_NAME", "Job Hunter")
        stats["applicant_name"] = applicant_name
        return jsonify(stats)
    except:
        return jsonify({"applicant_name": "Job Hunter"})

@app.route("/api/apply", methods=["POST"])
def api_apply():
    data = request.get_json()
    job_url = data.get("job_url")
    if not job_url:
        return jsonify({"error": "job_url required"}), 400
    try:
        import sys; sys.path.insert(0, str(project_root))
        from modules.db import JobDatabase
        from modules.apply_engine import run_apply_engine
        from dotenv import load_dotenv
        load_dotenv()

        db = JobDatabase(str(project_root / "data" / "jobs.db"))
        jobs = [j for j in db.get_all_jobs() if j.get("job_url") == job_url]
        if not jobs:
            return jsonify({"error": "Job not found"}), 404

        job = jobs[0]
        job["status"] = "approved"

        profile = json.loads((project_root / "config" / "profile.json").read_text())
        prefs = json.loads((project_root / "config" / "preferences.json").read_text())

        results = run_apply_engine([job], profile, prefs)
        result = results[0] if results else job

        db.update_job(job_url,
                      status=result.get("status", "action_required"),
                      apply_platform=result.get("apply_platform", ""),
                      applied_at=result.get("applied_at", ""))

        return jsonify({
            "status": result.get("status"),
            "apply_platform": result.get("apply_platform"),
            "applied_at": result.get("applied_at"),
            "apply_url": result.get("apply_url"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cover_letter/<path:filename>")
def serve_cover_letter(filename):
    path = project_root / "output" / "cover_letters" / filename
    if path.exists():
        return path.read_text(encoding="utf-8"), 200, {"Content-Type": "text/plain"}
    abort(404)

@app.route("/api/save_cover_letter", methods=["POST"])
def api_save_cover_letter():
    data = request.get_json()
    job_url = data.get("job_url")
    cover_letter = data.get("cover_letter", "")
    
    if not job_url:
        return jsonify({"error": "job_url required"}), 400
    
    try:
        import sys; sys.path.insert(0, str(project_root))
        from modules.db import JobDatabase
        
        db = JobDatabase(str(project_root / "data" / "jobs.db"))
        jobs = [j for j in db.get_all_jobs() if j.get("job_url") == job_url]
        if not jobs:
            return jsonify({"error": "Job not found"}), 404
        
        job = jobs[0]
        clFile = f"{slug(job.get('company', ''))}__{slug(job.get('title', ''))}.txt"
        cl_path = project_root / "output" / "cover_letters" / clFile
        cl_path.parent.mkdir(parents=True, exist_ok=True)
        cl_path.write_text(cover_letter, encoding="utf-8")
        
        try:
            db.update_job(job_url, cover_letter=cover_letter)
        except:
            pass
        
        return jsonify({"status": "saved", "filename": clFile})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/output/tailored_resumes/<path:filename>")
def serve_resume(filename):
    path = project_root / "output" / "tailored_resumes" / filename
    if path.exists():
        return send_file(str(path), mimetype="application/pdf")
    abort(404)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}'s Job Agent</title>
<style>
:root{--bg:#f5f7fa;--card:#fff;--card-alt:#f8fafc;--border:#e8ecf0;--text:#1a1a2e;--text-muted:#6b7280;--accent:#3b82f6;--accent-hover:#2563eb;--green:#10b981;--orange:#f59e0b;--red:#ef4444;--radius:12px;--shadow:0 2px 12px rgba(0,0,0,.07);--shadow-md:0 6px 24px rgba(0,0,0,.11)}
body.dark-mode{--bg:#0f1117;--card:#1a1d23;--card-alt:#242b33;--border:#2d3139;--text:#e8eaf0;--text-muted:#8b93a0;--shadow:0 2px 12px rgba(0,0,0,.3);--shadow-md:0 6px 24px rgba(0,0,0,.4)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:all .3s}
.header{background:var(--card);border-bottom:1px solid var(--border);padding:18px 32px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:var(--shadow)}
.header-left{display:flex;align-items:center;gap:20px;flex:1}
.header h1{font-size:20px;font-weight:700;color:var(--text);white-space:nowrap}
.header h1 span{color:var(--accent)}
.header-name{font-size:13px;color:var(--text-muted);font-weight:500}
.header-controls{display:flex;align-items:center;gap:16px}
.stats-row{display:flex;gap:20px}
.stat{text-align:center;padding:0 12px;border-right:1px solid var(--border)}
.stat:last-child{border-right:none}
.stat .num{font-size:22px;font-weight:800;line-height:1}
.stat .lbl{font-size:11px;color:var(--text-muted);margin-top:4px;text-transform:uppercase}
.stat.blue .num{color:var(--accent)}.stat.green .num{color:var(--green)}.stat.orange .num{color:var(--orange)}.stat.red .num{color:var(--red)}
.theme-toggle{background:0;border:none;font-size:18px;cursor:pointer;padding:4px 8px;border-radius:6px;transition:background .2s;color:var(--text)}
.theme-toggle:hover{background:var(--card-alt)}
.filter-bar{padding:20px 32px;background:var(--bg);border-bottom:1px solid var(--border);display:flex;gap:16px;flex-wrap:wrap;align-items:center}
.filter-section{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.filter-label{font-size:12px;color:var(--text-muted);font-weight:600;text-transform:uppercase}
.filter-btn{padding:7px 18px;border-radius:20px;border:1.5px solid var(--border);background:var(--card);font-size:13px;font-weight:500;cursor:pointer;transition:all .15s;color:var(--text-muted)}
.filter-btn:hover{border-color:var(--accent);color:var(--accent)}
.filter-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.search-box{padding:8px 14px;border:1.5px solid var(--border);border-radius:20px;background:var(--card);font-size:13px;color:var(--text);min-width:200px}
.search-box:focus{outline:none;border-color:var(--accent)}
.sort-dropdown{padding:8px 14px;border:1.5px solid var(--border);border-radius:8px;background:var(--card);font-size:13px;color:var(--text);cursor:pointer}
.sort-dropdown:focus{outline:none;border-color:var(--accent)}
.quick-apply-btn{padding:8px 16px;border:none;border-radius:8px;background:var(--green);color:#fff;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;display:none}
.quick-apply-btn:hover{background:#059669;transform:scale(1.03)}
.quick-apply-btn.show{display:inline-block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:20px;padding:20px 32px 40px}
.card{background:var(--card);border-radius:var(--radius);border:1px solid var(--border);box-shadow:var(--shadow);overflow:hidden;transition:all .2s;display:flex;flex-direction:column}
.card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px)}
.card-top-bar{height:5px}
.score-high{background:linear-gradient(90deg,#10b981,#34d399)}.score-mid{background:linear-gradient(90deg,#f59e0b,#fbbf24)}.score-low{background:linear-gradient(90deg,#6b7280,#9ca3af)}
.card-body{padding:18px 20px;flex:1}
.card-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;gap:10px}
.card-title{font-size:15px;font-weight:700;color:var(--text);line-height:1.3;flex:1}
.score-badge{font-size:12px;font-weight:700;padding:4px 10px;border-radius:20px;white-space:nowrap;flex-shrink:0}
.score-badge.high{background:#d1fae5;color:#065f46}.score-badge.mid{background:#fef3c7;color:#92400e}.score-badge.low{background:#f3f4f6;color:#374151}
body.dark-mode .score-badge.high{background:rgba(16,185,129,.15);color:#86efac}body.dark-mode .score-badge.mid{background:rgba(245,158,11,.15);color:#fcd34d}body.dark-mode .score-badge.low{background:rgba(107,114,128,.15);color:#d1d5db}
.card-company{font-size:13px;font-weight:600;color:var(--accent);margin-bottom:4px}
.card-meta{font-size:12px;color:var(--text-muted);margin-bottom:10px;display:flex;gap:12px;flex-wrap:wrap}
.source-badge{display:inline-flex;align-items:center;gap:3px;padding:2px 8px;background:var(--card-alt);border-radius:6px;font-size:11px;font-weight:600}
.card-reason{font-size:12px;color:var(--text-muted);line-height:1.5;background:var(--card-alt);border-radius:8px;padding:8px 10px;border-left:3px solid var(--accent);margin-bottom:12px}
.cl-toggle{background:0;border:none;color:var(--accent);font-size:12px;cursor:pointer;padding:0;font-weight:500;display:flex;align-items:center;gap:4px;margin-bottom:6px}
.cl-toggle:hover{text-decoration:underline}
.cl-body{display:none;font-size:12px;line-height:1.65;color:var(--text-muted);background:var(--card-alt);border-radius:8px;padding:12px 14px;border:1px solid var(--border);margin-bottom:12px;max-height:260px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}
.cl-body.open{display:block}
.cl-textarea{width:100%;min-height:200px;max-height:340px;padding:12px 14px;border:1px solid var(--border);border-radius:8px;background:var(--card-alt);color:var(--text);font-size:12px;line-height:1.65;font-family:"Menlo",monospace}
.cl-textarea:focus{outline:none;border-color:var(--accent)}
.cl-editor{display:none;margin-bottom:12px}.cl-editor.open{display:block}
.cl-buttons{display:flex;gap:8px;margin-bottom:12px}
.cl-save-btn{padding:8px 16px;background:var(--green);color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer}
.cl-save-btn:hover:not(:disabled){background:#059669}.cl-save-btn:disabled{background:var(--text-muted);cursor:not-allowed;opacity:.6}
.cl-cancel-btn{padding:8px 16px;background:0;color:var(--text-muted);border:1px solid var(--border);border-radius:8px;font-size:12px;font-weight:600;cursor:pointer}
.cl-cancel-btn:hover{border-color:var(--text-muted)}
.card-footer{padding:14px 20px;border-top:1px solid var(--border);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .15s;text-decoration:none;display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.btn-secondary{background:var(--card-alt);color:var(--text);border:1px solid var(--border)}.btn-secondary:hover{background:var(--border)}
.btn-copy{background:var(--card-alt);color:var(--accent);border:1px solid var(--border)}.btn-copy:hover{background:var(--accent);color:#fff}
.btn-apply{background:var(--accent);color:#fff;margin-left:auto;min-width:90px;justify-content:center}
.btn-apply:hover:not(:disabled){background:var(--accent-hover);transform:scale(1.03)}.btn-apply:disabled{cursor:default;opacity:.8}
.btn-apply.applying{background:#93c5fd}.btn-apply.applied{background:var(--green)}.btn-apply.action{background:var(--orange)}.btn-apply.skipped{background:#9ca3af}
.status-chip{font-size:11px;font-weight:600;padding:3px 9px;border-radius:12px;white-space:nowrap}
.chip-applied{background:#d1fae5;color:#065f46}.chip-action{background:#fef3c7;color:#92400e}.chip-skipped{background:#f3f4f6;color:#6b7280}.chip-pending{background:#eff6ff;color:#1d4ed8}
body.dark-mode .chip-applied{background:rgba(16,185,129,.15);color:#86efac}body.dark-mode .chip-action{background:rgba(245,158,11,.15);color:#fcd34d}body.dark-mode .chip-skipped{background:rgba(107,114,128,.15);color:#d1d5db}body.dark-mode .chip-pending{background:rgba(59,130,246,.15);color:#93c5fd}
.empty{text-align:center;padding:80px 20px;color:var(--text-muted)}.empty svg{width:64px;height:64px;margin-bottom:16px;opacity:.3}.empty h3{font-size:18px;margin-bottom:8px;color:var(--text)}
.loading{display:none;position:fixed;inset:0;background:rgba(255,255,255,.8);z-index:999;flex-direction:column;align-items:center;justify-content:center}
body.dark-mode .loading{background:rgba(15,17,23,.9)}.loading.show{display:flex}
.spinner{width:44px;height:44px;border:4px solid #e5e7eb;border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite}
body.dark-mode .spinner{border-color:#2d3139}
.loading p{margin-top:14px;font-weight:600;color:var(--text);font-size:15px}
@keyframes spin{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:28px;right:28px;background:var(--text);color:#fff;padding:12px 20px;border-radius:10px;font-size:14px;font-weight:500;opacity:0;transform:translateY(12px);transition:all .3s;z-index:200}
.toast.show{opacity:1;transform:translateY(0)}.toast.success{background:var(--green)}.toast.warn{background:var(--orange)}.toast.error{background:var(--red)}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:1000;align-items:center;justify-content:center}.modal.show{display:flex}
.modal-content{background:var(--card);border-radius:var(--radius);padding:28px;max-width:400px;width:90%;box-shadow:0 12px 40px rgba(0,0,0,.2)}
.modal-title{font-size:18px;font-weight:700;color:var(--text);margin-bottom:12px}
.modal-text{font-size:14px;color:var(--text-muted);margin-bottom:24px;line-height:1.6}
.modal-count{font-size:16px;font-weight:700;color:var(--accent)}
.modal-buttons{display:flex;gap:12px;justify-content:flex-end}
.modal-btn{padding:10px 20px;border-radius:8px;border:none;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s}
.modal-btn-cancel{background:var(--card-alt);color:var(--text)}.modal-btn-cancel:hover{background:var(--border)}
.modal-btn-confirm{background:var(--green);color:#fff}.modal-btn-confirm:hover{background:#059669}
@media(max-width:900px){.header{flex-direction:column;gap:12px}.header-left{flex-direction:column;width:100%}.grid{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
@media(max-width:600px){.header{padding:14px 16px}.filter-bar{padding:14px 16px;gap:8px}.grid{padding:12px 16px 32px;grid-template-columns:1fr}.search-box{min-width:140px}.stat{padding:0;border:none}.btn{padding:6px 12px;font-size:12px}}
</style>
</head>
<body>
<div class="loading" id="loading"><div class="spinner"></div><p id="loading-msg">Please wait...</p></div>
<div id="confirmModal" class="modal"><div class="modal-content"><div class="modal-title">🚀 Apply to all suitable jobs?</div><div class="modal-text">You are about to apply to <span class="modal-count" id="modalCount">0</span> jobs.</div><div class="modal-buttons"><button class="modal-btn modal-btn-cancel" onclick="closeModal()">Cancel</button><button class="modal-btn modal-btn-confirm" onclick="confirmApplyAll()">Apply All</button></div></div></div>
<div class="toast" id="toast"></div>
<div class="header"><div class="header-left"><h1>👩‍💼 <span>{name}'s</span> Job Agent</h1><div class="header-name" id="applicant-name">Job Hunter</div></div><div class="header-controls"><div class="stats-row"><div class="stat blue"><div class="num" id="s-fetched">–</div><div class="lbl">Searched</div></div><div class="stat green"><div class="num" id="s-suitable">–</div><div class="lbl">Suitable</div></div><div class="stat blue"><div class="num" id="s-applied">–</div><div class="lbl">Applied</div></div><div class="stat orange"><div class="num" id="s-action">–</div><div class="lbl">Action</div></div><div class="stat red"><div class="num" id="s-skipped">–</div><div class="lbl">Skipped</div></div></div><button class="theme-toggle" onclick="toggleTheme()">🌙</button></div></div>
<div class="filter-bar"><div class="filter-section"><span class="filter-label">Status:</span><button class="filter-btn active" data-filter="all">All Jobs</button><button class="filter-btn" data-filter="suitable,approved">Pending Review</button><button class="filter-btn" data-filter="applied">✅ Applied</button><button class="filter-btn" data-filter="action_required">⚡ Needs Action</button><button class="filter-btn" data-filter="skipped_by_user">Skipped</button></div><div class="filter-section"><span class="filter-label">Sort:</span><select class="sort-dropdown" id="sortDropdown" onchange="applySortAndFilter()"><option value="score">Score (high to low)</option><option value="company">Company (A-Z)</option><option value="date">Date Posted</option><option value="salary">Salary</option></select></div><input type="text" class="search-box" id="searchBox" placeholder="🔍 Search company or role..." onkeyup="applySortAndFilter()"><button class="quick-apply-btn" id="quickApplyBtn" onclick="showApplyAllModal()">🚀 Apply All Pending</button></div>
<div class="grid" id="job-grid"></div>
<script>
let allJobs=[],activeFilter='all',currentSort='score',searchTerm='';
function initTheme(){const saved=localStorage.getItem('darkMode');if(saved==='true'){document.body.classList.add('dark-mode');document.querySelector('.theme-toggle').textContent='☀️'}}
function toggleTheme(){const isDark=document.body.classList.toggle('dark-mode');document.querySelector('.theme-toggle').textContent=isDark?'☀️':'🌙';localStorage.setItem('darkMode',isDark)}
async function loadData(){const [jobs,stats]=await Promise.all([fetch('/api/jobs').then(r=>r.json()),fetch('/api/stats').then(r=>r.json())]);allJobs=jobs;renderStats(stats);applySortAndFilter()}
function renderStats(s){document.getElementById('s-fetched').textContent=s.total_fetched??'–';document.getElementById('s-suitable').textContent=s.total_suitable??'–';document.getElementById('s-applied').textContent=s.total_applied??'–';document.getElementById('s-action').textContent=s.total_action_required??'–';document.getElementById('s-skipped').textContent=s.total_skipped??'–';document.getElementById('applicant-name').textContent=s.applicant_name||'Job Hunter'}
function filterJobs(jobs){if(activeFilter==='all')return jobs;const statuses=activeFilter.split(',');return jobs.filter(j=>statuses.includes(j.status))}
function searchJobs(jobs,term){if(!term)return jobs;term=term.toLowerCase();return jobs.filter(j=>(j.company||'').toLowerCase().includes(term)||(j.title||'').toLowerCase().includes(term))}
function sortJobs(jobs,field){const copy=[...jobs];switch(field){case'company':copy.sort((a,b)=>(a.company||'').localeCompare(b.company||''));break;case'date':copy.sort((a,b)=>new Date(b.date_posted||0)-new Date(a.date_posted||0));break;case'salary':copy.sort((a,b)=>{const sa=parseSalary(a.salary_text||'0');const sb=parseSalary(b.salary_text||'0');return sb-sa});break;default:copy.sort((a,b)=>(b.score||0)-(a.score||0))}return copy}
function parseSalary(text){const match=text.match(/\d+/);return match?parseInt(match[0]):0}
function applySortAndFilter(){currentSort=document.getElementById('sortDropdown').value;searchTerm=document.getElementById('searchBox').value;let filtered=filterJobs(allJobs);filtered=searchJobs(filtered,searchTerm);filtered=sortJobs(filtered,currentSort);renderGrid(filtered);updateQuickApplyBtn()}
function scoreClass(s){return s>=80?'high':s>=65?'mid':'low'}
function barClass(s){return s>=80?'score-high':s>=65?'score-mid':'score-low'}
function daysAgo(iso){if(!iso)return'';try{const diff=Math.floor((Date.now()-new Date(iso))/86400000);return diff===0?'Today':diff===1?'1d ago':`${diff}d ago`}catch{return''}}
function sourceIcon(source){const map={linkedin:'💼',indeed:'🔵',naukri:'🇮🇳',greenhouse:'🏢',workday:'📋',lever:'⚙️'};return map[(source||'').toLowerCase()]||'🔗'}
function clFilename(job){const s=t=>t.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'').slice(0,40);return `${s(job.company||'')}_${s(job.title||'')}.txt`}
function cvFilename(job){if(job.tailored_resume_path)return job.tailored_resume_path.split('/').pop();const s=t=>t.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'').slice(0,40);return `${s(job.company||'')}_${s(job.title||'')}.pdf`}
function statusChip(status){const map={applied:['chip-applied','✅ Applied'],action_required:['chip-action','⚡ Action'],skipped_by_user:['chip-skipped','Skipped'],approved:['chip-pending','Ready'],suitable:['chip-pending','Pending']};const [cls,label]=map[status]||['chip-pending',status];return `<span class="status-chip ${cls}">${label}</span>`}
function buildCard(job){const score=job.score||0;const sc=scoreClass(score);const isApplied=job.status==='applied';const isAction=job.status==='action_required';const isSkipped=job.status==='skipped_by_user';const clFile=clFilename(job);const cvFile=cvFilename(job);const hasCV=!!job.tailored_resume_path;let applyBtn='';if(isApplied){applyBtn=`<button class="btn btn-apply applied" disabled>✅ Applied</button>`}else if(isAction){const platform=job.apply_platform||'Apply';applyBtn=`<a class="btn btn-apply action" href="${job.apply_url||'#'}" target="_blank">⚡ ${platform}</a>`}else if(isSkipped){applyBtn=`<button class="btn btn-apply skipped" disabled>Skipped</button>`}else{applyBtn=`<button class="btn btn-apply" onclick="applyJob('${encodeURIComponent(job.job_url)}',this)">Apply 🚀</button>`}
let copyClBtn='';if(isAction){copyClBtn=`<button class="btn btn-copy" onclick="copyCoverLetter('${encodeURIComponent(job.job_url)}')">📋 Copy CL</button>`}
return `<div class="card" id="card-${encodeURIComponent(job.job_url)}" data-status="${job.status}"><div class="card-top-bar ${barClass(score)}"></div><div class="card-body"><div class="card-header"><div class="card-title">${job.title||'Unknown'}</div><span class="score-badge ${sc}">${score}/100</span></div><div class="card-company">${job.company||''}</div><div class="card-meta"><span>📍 ${job.location||'Remote'}</span>${job.salary_text?`<span>💰 ${job.salary_text}</span>`:''}<span>🗓 ${daysAgo(job.date_posted)}</span><span class="source-badge">${sourceIcon(job.source)} ${job.source||'Job'}</span></div>${job.score_reason?`<div class="card-reason">💡 ${job.score_reason}</div>`:''}<button class="cl-toggle" onclick="toggleCL(this)"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>View Cover Letter</button><div class="cl-body" id="cl-${encodeURIComponent(job.job_url)}">Loading...</div><div class="cl-editor" id="cle-${encodeURIComponent(job.job_url)}"><textarea class="cl-textarea" id="clt-${encodeURIComponent(job.job_url)}"></textarea><div class="cl-buttons"><button class="cl-save-btn" onclick="saveCoverLetter('${encodeURIComponent(job.job_url)}')">💾 Save</button><button class="cl-cancel-btn" onclick="cancelEditCL('${encodeURIComponent(job.job_url)}')">Cancel</button></div></div></div><div class="card-footer">${hasCV?`<a class="btn btn-secondary" href="/output/tailored_resumes/${cvFile}" target="_blank">📑 Resume</a>`:''} ${copyClBtn} ${statusChip(job.status)} ${applyBtn}</div></div>`}
function renderGrid(jobs){const grid=document.getElementById('job-grid');if(!jobs.length){grid.innerHTML=`<div class="empty" style="grid-column:1/-1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><h3>No jobs found</h3><p>Try adjusting filters or search</p></div>`;return}grid.innerHTML=jobs.map(buildCard).join('')}
async function toggleCL(btn){const card=btn.closest('.card');const cardId=card.id.replace('card-','');const body=document.getElementById(`cl-${cardId}`);const editor=document.getElementById(`cle-${cardId}`);if(body.classList.contains('open')&&!editor.classList.contains('open')){body.classList.remove('open');btn.querySelector('svg').style.transform='';return}if(editor.classList.contains('open')){editor.classList.remove('open');body.classList.add('open');btn.querySelector('svg').style.transform='rotate(180deg)';return}body.classList.add('open');btn.querySelector('svg').style.transform='rotate(180deg)';if(body.dataset.loaded)return;const job=allJobs.find(j=>encodeURIComponent(j.job_url)===cardId);const clFile=clFilename(job||{});try{const res=await fetch(`/api/cover_letter/${clFile}`);if(res.ok){body.textContent=await res.text();document.getElementById(`clt-${cardId}`).value=body.textContent;body.dataset.loaded='1'}else{body.textContent='Cover letter not generated.'}}catch{body.textContent='Could not load.'}}
function cancelEditCL(cardId){document.getElementById(`cle-${cardId}`).classList.remove('open');document.getElementById(`cl-${cardId}`).classList.add('open')}
async function saveCoverLetter(cardId){const textarea=document.getElementById(`clt-${cardId}`);const text=textarea.value;const btn=document.querySelector(`#cle-${cardId} .cl-save-btn`);btn.disabled=true;btn.textContent='⏳ Saving...';try{const res=await fetch('/api/save_cover_letter',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_url:decodeURIComponent(cardId),cover_letter:text})});const data=await res.json();if(res.ok){document.getElementById(`cl-${cardId}`).textContent=text;toast('Saved! ✓','success');cancelEditCL(cardId)}else{toast(`Error: ${data.error}`,'error')}}catch{toast('Network error','error')}finally{btn.disabled=false;btn.textContent='💾 Save'}}
async function copyCoverLetter(cardId){const body=document.getElementById(`cl-${cardId}`);let text=body.textContent;if(!body.dataset.loaded){const job=allJobs.find(j=>encodeURIComponent(j.job_url)===cardId);const clFile=clFilename(job||{});try{const res=await fetch(`/api/cover_letter/${clFile}`);if(res.ok)text=await res.text()}catch{}}try{await navigator.clipboard.writeText(text);toast('Copied! 📋','success')}catch{toast('Failed to copy','error')}}
function updateQuickApplyBtn(){document.getElementById('quickApplyBtn').classList.toggle('show',activeFilter==='suitable,approved')}
function showApplyAllModal(){const filtered=filterJobs(allJobs);const pending=filtered.filter(j=>['suitable','approved'].includes(j.status));document.getElementById('modalCount').textContent=pending.length;document.getElementById('confirmModal').classList.add('show')}
function closeModal(){document.getElementById('confirmModal').classList.remove('show')}
let applyAllInProgress=false;
async function confirmApplyAll(){if(applyAllInProgress)return;applyAllInProgress=true;closeModal();const filtered=filterJobs(allJobs);const pending=filtered.filter(j=>['suitable','approved'].includes(j.status));for(let i=0;i<pending.length;i++){showLoading(`Applying ${i+1}/${pending.length}...`);await applyJobAsync(pending[i].job_url);await new Promise(r=>setTimeout(r,500))}hideLoading();toast(`Applied to ${pending.length} jobs! 🎉`,'success');applyAllInProgress=false;setTimeout(loadData,1000)}
async function applyJob(encodedUrl,btn){const job_url=decodeURIComponent(encodedUrl);btn.disabled=true;btn.textContent='⏳ Applying...';btn.classList.add('applying');showLoading('Submitting...');try{const res=await fetch('/api/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_url})});const data=await res.json();hideLoading();const card=document.getElementById(`card-${encodedUrl}`);const chip=card.querySelector('.status-chip');if(data.status==='applied'){btn.textContent='✅ Applied';btn.classList.remove('applying');btn.classList.add('applied');chip.className='status-chip chip-applied';chip.textContent='✅ Applied';card.dataset.status='applied';card.querySelector('.card-top-bar').className='card-top-bar score-high';toast('Submitted! 🎉','success')}else if(data.status==='action_required'){btn.outerHTML=`<a class="btn btn-apply action" href="${data.apply_url||'#'}" target="_blank">⚡ ${data.apply_platform||'Apply'}</a>`;chip.className='status-chip chip-action';chip.textContent='⚡ Action';card.dataset.status='action_required';toast('Auto-apply not supported','warn')}else if(data.error){btn.textContent='❌ Error';btn.classList.add('error');btn.disabled=false;toast(`Error: ${data.error}`,'error')}fetch('/api/stats').then(r=>r.json()).then(renderStats)}catch(e){hideLoading();btn.textContent='Retry';btn.disabled=false;toast('Network error','error')}}
async function applyJobAsync(job_url){return new Promise((resolve)=>{fetch('/api/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_url})}).then(r=>r.json()).then(data=>{const card=document.getElementById(`card-${encodeURIComponent(job_url)}`);if(card&&data.status==='applied'){const chip=card.querySelector('.status-chip');chip.className='status-chip chip-applied';chip.textContent='✅ Applied';const btn=card.querySelector('.btn-apply');if(btn){btn.textContent='✅ Applied';btn.className='btn btn-apply applied';btn.disabled=true}}}).catch(()=>{}).finally(resolve)})}
document.querySelectorAll('.filter-btn').forEach(btn=>{btn.addEventListener('click',()=>{document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');activeFilter=btn.dataset.filter;applySortAndFilter()})});
function showLoading(msg){document.getElementById('loading-msg').textContent=msg||'Please wait...';document.getElementById('loading').classList.add('show')}
function hideLoading(){document.getElementById('loading').classList.remove('show')}
let toastTimer;
function toast(msg,type=''){const el=document.getElementById('toast');el.textContent=msg;el.className=`toast show ${type}`;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),4000)}
document.getElementById('confirmModal').addEventListener('click',(e)=>{if(e.target.id==='confirmModal')closeModal()});
initTheme();
loadData();
setInterval(loadData,30000);
</script>
</body>
</html>
"""


@app.route("/api/export")
def api_export():
    """Export all jobs as CSV."""
    import csv, io
    from flask import Response
    jobs = load_db_jobs()
    output = io.StringIO()
    fieldnames = ["title","company","location","score","salary_text","source",
                  "status","date_posted","applied_at","job_url","apply_url","score_reason"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(jobs)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs_export.csv"}
    )


@app.route("/api/followups")
def api_followups():
    """Jobs applied >7 days ago with no response — follow-up candidates."""
    from datetime import datetime, timezone, timedelta
    jobs   = load_db_jobs("applied")
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = []
    for j in jobs:
        if j.get("applied_at"):
            try:
                applied = datetime.fromisoformat(j["applied_at"].replace("Z","+00:00"))
                if applied < cutoff:
                    result.append(j)
            except Exception:
                pass
    return jsonify(result)


@app.route("/")
def index():
    return HTML

def open_browser():
    import time; time.sleep(1.2)
    webbrowser.open("http://localhost:5000")

def run_server(port=5000, open_browser_auto=True):
    if open_browser_auto:
        t = threading.Thread(target=open_browser, daemon=True)
        t.start()
    print(f"\n  ✅  Web UI ready → http://localhost:{port}")
    print(f"  Press Ctrl+C to stop the server\n")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_server()
