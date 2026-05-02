"""app.py — Job Search Agent Web UI"""
import os, json, re, threading, webbrowser, sys
from pathlib import Path
from flask import Flask, jsonify, request, send_file, abort, Response

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
app = Flask(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_db():
    from modules.db import JobDatabase
    return JobDatabase(str(project_root / "data" / "jobs.db"))

def slug(t):
    return re.sub(r"[^a-z0-9]+","_",(t or "").lower()).strip("_")[:40]

# ── API: jobs ─────────────────────────────────────────────────────────────────
@app.route("/api/jobs")
def api_jobs():
    try:
        db   = get_db()
        jobs = db.get_all_jobs()
        show = [j for j in jobs if j.get("status") in
                ("suitable","approved","action_required","applied","skipped_by_user")]
        show.sort(key=lambda j: j.get("score") or 0, reverse=True)
        return jsonify(show)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── API: stats ────────────────────────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    try:
        from dotenv import load_dotenv; load_dotenv()
        db  = get_db()
        raw = db.get_stats()
        by  = raw.get("by_status", {})
        runs = db.get_run_history(days=1) if hasattr(db,"get_run_history") else []
        fetched = runs[0].get("jobs_fetched", raw.get("total",0)) if runs else raw.get("total",0)
        name = os.environ.get("APPLICANT_NAME","Job Hunter")
        return jsonify({
            "applicant_name":        name,
            "total_fetched":         fetched,
            "total_suitable":        by.get("suitable",0)+by.get("approved",0),
            "total_applied":         by.get("applied",0),
            "total_action_required": by.get("action_required",0),
            "total_skipped":         by.get("skipped",0)+by.get("skipped_by_user",0),
        })
    except Exception as e:
        return jsonify({"applicant_name":"Job Hunter","total_fetched":0,
                        "total_suitable":0,"total_applied":0,
                        "total_action_required":0,"total_skipped":0,"error":str(e)})

# ── API: apply ────────────────────────────────────────────────────────────────
@app.route("/api/apply", methods=["POST"])
def api_apply():
    data    = request.get_json()
    job_url = data.get("job_url","")
    if not job_url:
        return jsonify({"error":"job_url required"}),400
    try:
        from dotenv import load_dotenv; load_dotenv()
        from modules.apply_engine import run_apply_engine
        db   = get_db()
        jobs = [j for j in db.get_all_jobs() if j.get("job_url")==job_url]
        if not jobs: return jsonify({"error":"not found"}),404
        job = jobs[0]
        # Don't re-apply to already applied jobs
        if job.get("status") == "applied":
            return jsonify({"status": "applied",
                            "apply_platform": job.get("apply_platform",""),
                            "applied_at": job.get("applied_at",""),
                            "message": "already applied"})
        job["status"] = "approved"
        profile = json.loads((project_root/"config"/"profile.json").read_text())
        prefs   = json.loads((project_root/"config"/"preferences.json").read_text())
        # Tailor resume on-demand
        if not job.get("tailored_resume_path"):
            try:
                from modules.resume_tailor import tailor_resumes
                job["status"]="suitable"
                [job]=tailor_resumes([job],profile,prefs)
                job["status"]="approved"
                if job.get("tailored_resume_path"):
                    db.update_job(job_url,tailored_resume_path=job["tailored_resume_path"])
            except Exception as te:
                app.logger.warning(f"Tailor failed: {te}")
        result = run_apply_engine([job],profile,prefs)[0]
        db.update_job(job_url, status=result.get("status","action_required"),
                      apply_platform=result.get("apply_platform",""),
                      applied_at=result.get("applied_at",""))
        return jsonify({"status":result.get("status"),
                        "apply_platform":result.get("apply_platform"),
                        "apply_url":result.get("apply_url"),
                        "applied_at":result.get("applied_at")})
    except Exception as e:
        return jsonify({"error":str(e)}),500

# ── API: save cover letter ────────────────────────────────────────────────────
@app.route("/api/save_cover_letter", methods=["POST"])
def api_save_cl():
    data = request.get_json()
    job_url = data.get("job_url",""); cl = data.get("cover_letter","")
    if not job_url: return jsonify({"error":"job_url required"}),400
    try:
        db = get_db()
        db.update_job(job_url, cover_letter=cl)
        jobs = [j for j in db.get_all_jobs() if j.get("job_url")==job_url]
        if jobs:
            j = jobs[0]
            fp = project_root/"output"/"cover_letters"/f"{slug(j.get('company',''))}_{slug(j.get('title',''))}.txt"
            fp.parent.mkdir(parents=True,exist_ok=True)
            fp.write_text(cl,encoding="utf-8")
        return jsonify({"ok":True})
    except Exception as e:
        return jsonify({"error":str(e)}),500

# ── API: cover letter file ────────────────────────────────────────────────────
@app.route("/api/cover_letter/<path:filename>")
def api_cl_file(filename):
    p = project_root/"output"/"cover_letters"/filename
    if p.exists(): return p.read_text(encoding="utf-8"),200,{"Content-Type":"text/plain"}
    abort(404)

# ── API: resume PDF ───────────────────────────────────────────────────────────
@app.route("/output/tailored_resumes/<path:filename>")
def api_resume(filename):
    p = project_root/"output"/"tailored_resumes"/filename
    if p.exists(): return send_file(str(p),mimetype="application/pdf")
    abort(404)

# ── API: export CSV ───────────────────────────────────────────────────────────
@app.route("/api/export")
def api_export():
    import csv, io
    jobs = get_db().get_all_jobs()
    out  = io.StringIO()
    fields = ["title","company","location","score","salary_text","source",
              "status","date_posted","applied_at","job_url","score_reason"]
    w = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    w.writeheader(); w.writerows(jobs)
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment;filename=jobs.csv"})

# ── HTML UI ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_file(str(project_root / "ui.html"))

def _open():
    import time, subprocess, sys
    time.sleep(1.2)
    url = "http://localhost:8080"
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url])   # macOS — most reliable
        else:
            import webbrowser; webbrowser.open(url)
    except Exception:
        import webbrowser; webbrowser.open(url)

def run_server(port=8080, open_browser_auto=True):
    if open_browser_auto:
        threading.Thread(target=_open, daemon=True).start()
    print(f"\n  Web UI -> http://localhost:{port}  (Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_server()
