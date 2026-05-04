"""app.py — Job Search Agent Web UI"""
import os, json, re, sys, threading, webbrowser
from urllib.parse import unquote
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
    data    = request.get_json() or {}
    job_url = data.get("job_url","")
    if not job_url:
        return jsonify({"error":"job_url required"}), 400
    try:
        from dotenv import load_dotenv; load_dotenv()
        from modules.apply_engine import run_apply_engine
        db      = get_db()
        all_j   = db.get_all_jobs()
        matches = [j for j in all_j if j.get("job_url") == job_url]
        if not matches:
            return jsonify({"error":"Job not found in DB"}), 404

        job = matches[0]

        # Already applied — return success without re-applying
        if job.get("status") == "applied":
            return jsonify({"status":"applied",
                            "apply_platform": job.get("apply_platform",""),
                            "applied_at":     job.get("applied_at",""),
                            "message":"already applied"})

        job["status"] = "approved"
        profile = json.loads((project_root / "config" / "profile.json").read_text())
        prefs   = json.loads((project_root / "config" / "preferences.json").read_text())

        # Tailor resume on-demand (only if not already tailored)
        if not job.get("tailored_resume_path"):
            try:
                from modules.resume_tailor import tailor_resumes
                job["status"] = "suitable"
                result = tailor_resumes([job], profile, prefs)
                job = result[0] if result else job
                job["status"] = "approved"
                if job.get("tailored_resume_path"):
                    db.update_job(job_url, tailored_resume_path=job.get("tailored_resume_path",""))
            except Exception as te:
                app.logger.warning(f"Resume tailor failed: {te} — using base resume")
                job["tailored_resume_path"] = "config/resume.pdf"

        # Apply
        results = run_apply_engine([job], profile, prefs)
        result  = results[0] if results else job

        db.update_job(job_url,
                      status         = result.get("status","action_required"),
                      apply_platform = result.get("apply_platform",""),
                      applied_at     = result.get("applied_at",""))

        return jsonify({
            "status":         result.get("status"),
            "apply_platform": result.get("apply_platform",""),
            "apply_url":      result.get("apply_url",""),
            "applied_at":     result.get("applied_at",""),
        })
    except Exception as e:
        app.logger.error(f"[Apply] Error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

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

@app.route("/api/generate_cl", methods=["POST"])
def api_generate_cl():
    """Generate cover letter on-demand for a single job."""
    data    = request.get_json()
    job_url = data.get("job_url","")
    if not job_url: return jsonify({"error":"job_url required"}),400
    try:
        from dotenv import load_dotenv; load_dotenv()
        db      = get_db()
        jobs    = [j for j in db.get_all_jobs() if j.get("job_url")==job_url]
        if not jobs: return jsonify({"error":"not found"}),404
        job     = jobs[0]
        profile = json.loads((project_root/"config"/"profile.json").read_text())
        prefs   = json.loads((project_root/"config"/"preferences.json").read_text())
        from modules.cover_letter import generate_cover_letters
        job["status"] = "suitable"
        result = generate_cover_letters([job], profile, prefs)
        job = result[0] if result else job
        cl = job.get("cover_letter","")
        if cl and cl.strip():
            db.update_job(job_url, cover_letter=cl)
            return jsonify({"cover_letter": cl})
        return jsonify({"error": "Cover letter generation failed. Check Groq token quota or try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}),500


# ── Job detail page ──────────────────────────────────────────────────────────
@app.route("/job/<path:eu>")
def job_detail_page(eu):
    p = project_root / "templates" / "job_detail.html"
    if p.exists(): return send_file(str(p))
    return "Job detail page not found. Run setup.", 404


@app.route("/api/job/<path:eu>")
def api_job_detail(eu):
    job_url = unquote(eu)
    db = get_db()
    jobs = [j for j in db.get_all_jobs() if j.get("job_url") == job_url]
    if not jobs: return jsonify({"error":"not found"}), 404
    return jsonify(jobs[0])


@app.route("/api/regenerate_cl", methods=["POST"])
def api_regenerate_cl():
    data     = request.get_json() or {}
    job_url  = data.get("job_url","")
    feedback = data.get("feedback","").strip()
    if not job_url: return jsonify({"error":"job_url required"}), 400
    try:
        from dotenv import load_dotenv; load_dotenv()
        db      = get_db()
        all_j   = db.get_all_jobs()
        matches = [j for j in all_j if j.get("job_url")==job_url]
        if not matches: return jsonify({"error":"Job not found"}), 404
        job     = matches[0]
        profile = json.loads((project_root/"config"/"profile.json").read_text())
        prefs   = json.loads((project_root/"config"/"preferences.json").read_text())

        # Build enhanced prompt with feedback
        from modules.cover_letter import _build_prompt, _call_llm, _slug
        import re as _re
        max_w = prefs.get("apply_settings",{}).get("cover_letter_max_words",320)
        job["status"] = "suitable"
        base_prompt = _build_prompt(job, profile, max_w)
        if feedback:
            base_prompt += "\nUSER FEEDBACK:\n" + feedback + "Please regenerate the cover letter taking this feedback into account."

        letter = _call_llm(base_prompt)
        if letter and letter.strip():
            db.update_job(job_url, cover_letter=letter)
            import re as _re
            def _s(t): return _re.sub(r"[^a-z0-9]+","_",(t or "").lower()).strip("_")[:40]
            fp = project_root/"output"/"cover_letters"/(
                _s(job.get("company",""))+"_"+_s(job.get("title",""))+".txt")
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(letter, encoding="utf-8")
            return jsonify({"cover_letter": letter})
        return jsonify({"error": "Generation failed — check Groq quota"}), 500
    except Exception as e:
        app.logger.error(f"[RegenerateCL] {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate_resume", methods=["POST"])
def api_generate_resume():
    data    = request.get_json() or {}
    job_url = data.get("job_url", "")
    if not job_url:
        return jsonify({"error": "job_url required"}), 400
    try:
        from dotenv import load_dotenv; load_dotenv()
        db      = get_db()
        matches = [j for j in db.get_all_jobs() if j.get("job_url") == job_url]
        if not matches:
            return jsonify({"error": "Job not found"}), 404
        job     = matches[0]
        profile = json.loads((project_root / "config" / "profile.json").read_text())
        prefs   = json.loads((project_root / "config" / "preferences.json").read_text())
        job["status"] = "suitable"
        from modules.resume_tailor import tailor_resumes
        result = tailor_resumes([job], profile, prefs)
        job = result[0] if result else job
        rp = job.get("tailored_resume_path", "")
        if rp:
            db.update_job(job_url, tailored_resume_path=rp)
            fn = Path(rp).name
            return jsonify({"pdf_url": f"/output/tailored_resumes/{fn}"})
        return jsonify({"error": "Resume generation failed"}), 500
    except Exception as e:
        app.logger.error(f"[GenerateResume] {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/regenerate_resume", methods=["POST"])
def api_regenerate_resume():
    data     = request.get_json() or {}
    job_url  = data.get("job_url", "")
    feedback = data.get("feedback", "").strip()
    if not job_url:
        return jsonify({"error": "job_url required"}), 400
    try:
        from dotenv import load_dotenv; load_dotenv()
        db      = get_db()
        matches = [j for j in db.get_all_jobs() if j.get("job_url") == job_url]
        if not matches:
            return jsonify({"error": "Job not found"}), 404
        job     = matches[0]
        profile = json.loads((project_root / "config" / "profile.json").read_text())
        prefs   = json.loads((project_root / "config" / "preferences.json").read_text())
        job["tailored_resume_path"] = None
        job["status"] = "suitable"
        from modules.resume_tailor import _build_prompt, _call_llm, _parse, _render_pdf, _slug
        import time as _time
        prompt = _build_prompt(job, profile)
        if feedback:
            prompt += ("\n\nUSER FEEDBACK:\n" + feedback +
                       "\nPlease incorporate this feedback when tailoring the resume.")
        raw      = _call_llm(prompt)
        tailored = _parse(raw) or {}
        ts       = int(_time.time()) % 100000
        out      = (project_root / "output" / "tailored_resumes" /
                    f"{_slug(job.get('company',''))}_{_slug(job.get('title',''))}_{ts}.pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        if _render_pdf(tailored, profile, job, out):
            db.update_job(job_url, tailored_resume_path=str(out))
            return jsonify({"pdf_url": f"/output/tailored_resumes/{out.name}"})
        return jsonify({"error": "PDF render failed"}), 500
    except Exception as e:
        app.logger.error(f"[RegenerateResume] {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/cl/<path:eu>")
def download_cl_pdf(eu):
    """Convert cover letter text to a downloadable PDF."""
    from urllib.parse import unquote as _uq
    job_url = _uq(eu)
    db  = get_db()
    jobs = [j for j in db.get_all_jobs() if j.get("job_url") == job_url]
    if not jobs:
        return jsonify({"error": "not found"}), 404
    job = jobs[0]
    cl  = (job.get("cover_letter") or "").strip()
    if not cl:
        return jsonify({"error": "No cover letter generated yet"}), 404
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_JUSTIFY
        from datetime import date
        from dotenv import load_dotenv; load_dotenv()
        import os, io
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
              leftMargin=25*mm, rightMargin=25*mm,
              topMargin=25*mm,  bottomMargin=25*mm)
        DARK = colors.HexColor("#1a1a2e")
        GREY = colors.HexColor("#555555")
        def S(name, **kw):
            base = dict(fontName="Helvetica", fontSize=11, textColor=DARK, leading=16)
            base.update(kw)
            return ParagraphStyle(name, **base)
        name  = os.environ.get("APPLICANT_NAME",  "")
        email = os.environ.get("APPLICANT_EMAIL", "")
        phone = os.environ.get("APPLICANT_PHONE", "")
        story = []
        story.append(Paragraph(name, S("H", fontSize=13, fontName="Helvetica-Bold")))
        story.append(Paragraph(f"{email}  |  {phone}",
                               S("Sub", fontSize=10, textColor=GREY, spaceAfter=16)))
        story.append(Paragraph(date.today().strftime("%B %d, %Y"),
                               S("D", fontSize=10, textColor=GREY, spaceAfter=8)))
        story.append(Paragraph(
            f"Re: Application for {job.get('title','')} at {job.get('company','')}",
            S("Re", fontSize=11, fontName="Helvetica-Bold", spaceAfter=16)))
        for para in cl.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(para,
                             S("B", fontSize=11, leading=16,
                               alignment=TA_JUSTIFY, spaceAfter=8)))
        story.append(Spacer(1, 16))
        story.append(Paragraph("Sincerely,", S("Sign")))
        story.append(Paragraph(name, S("Name", fontName="Helvetica-Bold")))
        doc.build(story)
        buf.seek(0)
        from flask import Response
        co = job.get("company","co").replace(" ", "_")
        return Response(buf.read(), mimetype="application/pdf",
                        headers={"Content-Disposition":
                                 f"attachment;filename=CoverLetter_{co}.pdf"})
    except Exception as e:
        app.logger.error(f"[DownloadCL] {e}")
        return jsonify({"error": str(e)}), 500



@app.route("/api/resume_suggestions", methods=["POST"])
def api_resume_suggestions():
    """Analyse JD vs profile and return keywords + sentences to add to resume."""
    data    = request.get_json() or {}
    job_url = data.get("job_url", "")
    if not job_url:
        return jsonify({"error": "job_url required"}), 400
    try:
        from dotenv import load_dotenv; load_dotenv()
        db      = get_db()
        matches = [j for j in db.get_all_jobs() if j.get("job_url") == job_url]
        if not matches:
            return jsonify({"error": "Job not found"}), 404
        job     = matches[0]
        profile = json.loads((project_root / "config" / "profile.json").read_text())

        jd    = (job.get("description") or "")[:2500]
        title = job.get("title", "")
        co    = job.get("company", "")

        prompt = (
            "You are an expert ATS resume coach. Analyse this job description "
            "and the candidate profile, then provide specific, actionable suggestions "
            "to improve the resume for this specific role.\n\n"
            f"JOB: {title} at {co}\n"
            f"JD:\n{jd}\n\n"
            f"CANDIDATE: {profile.get('name','')}\n"
            f"Current role: {profile.get('experience',[{}])[0].get('title','')} "
            f"at {profile.get('experience',[{}])[0].get('company','')}\n"
            f"Skills: {', '.join(profile.get('core_skills',[]))}\n"
            f"Summary: {profile.get('summary','')}\n\n"
            "Provide suggestions in this EXACT JSON format:\n"
            '{"keywords_to_add": ["keyword1", "keyword2", ...],'
            '"summary_suggestion": "Rewrite the summary as: <exact text>",'
            '"bullet_suggestions": ['
            '  {"role": "Supply Chain Solution Consultant, Tech Mahindra",'
            '   "add_bullet": "• Exact new bullet point to add"},'
            '  {"role": "Senior Business Analyst, Optym",'
            '   "add_bullet": "• Exact new bullet point to add"}'
            '],'
            '"skills_to_highlight": ["skill1", "skill2"],'
            '"avoid_phrases": ["generic phrase to remove"]}'
        )

        groq_key = __import__("os").getenv("GROQ_API_KEY")
        result_text = ""
        if groq_key:
            try:
                from groq import Groq
                r = Groq(api_key=groq_key).chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3, max_tokens=1200,
                )
                result_text = r.choices[0].message.content
            except Exception as e:
                app.logger.warning(f"[ResumeSuggestions] Groq: {e}")

        if not result_text:
            try:
                from google import genai
                c = genai.Client(api_key=__import__("os").getenv("GEMINI_API_KEY"))
                result_text = c.models.generate_content(
                    model="gemini-2.0-flash", contents=prompt).text
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        import re as _re
        clean = result_text.strip()
        for fence in ("```json", "```"):
            if clean.startswith(fence): clean = clean[len(fence):]
        clean = clean.rstrip("`").strip()
        import json as _json
        suggestions = _json.loads(clean)
        return jsonify(suggestions)
    except Exception as e:
        app.logger.error(f"[ResumeSuggestions] {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return send_file(str(project_root / "ui.html"))


def _open():
    import time
    time.sleep(1.2)
    import subprocess, sys
    url = "http://localhost:8080"
    if sys.platform == "darwin":
        subprocess.Popen(["open", url])
    else:
        import webbrowser; webbrowser.open(url)


def run_server(port=8080, open_browser_auto=True):
    import threading
    if open_browser_auto:
        threading.Thread(target=_open, daemon=True).start()
    print(f"\n  Web UI -> http://localhost:{port}  (Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_server()
