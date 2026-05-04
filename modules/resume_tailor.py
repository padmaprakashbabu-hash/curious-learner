"""
resume_tailor.py — Two-column PDF matching original resume format.
LEFT: Experience | RIGHT: Contact, Education, Skills, Tools, Certifications
"""
import os, json, re, logging
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

def _slug(text): return re.sub(r"[^a-z0-9]+","_",(text or "").lower()).strip("_")[:40]

def _build_prompt(job, profile):
    jd = (job.get("description") or "")[:2500]
    exp_text = ""
    for e in profile.get("experience",[]):
        bullets = "\n    ".join(e.get("highlights",[])[:4])
        exp_text += f"\n  {e['title']} at {e['company']} ({e['duration']}):\n    {bullets}"
    return (
        "You are a professional resume writer. Tailor this resume for the specific job.\n"
        "CRITICAL RULES:\n"
        "- Do NOT invent or fabricate any facts, metrics, jobs, or skills\n"
        "- ONLY rewrite existing bullet points to include JD keywords naturally\n"
        "- Keep ALL company names, job titles, dates, and numbers exactly as-is\n"
        "- Lead each bullet with a strong action verb\n"
        "- Write the summary (2-3 sentences) to mirror the JD language exactly\n"
        "- Rank skills by relevance to this specific JD\n\n"
        f"JOB TITLE: {job.get('title')} at {job.get('company')}\n"
        f"JOB DESCRIPTION:\n{jd}\n\n"
        f"CANDIDATE: {profile.get('name','')}\n"
        f"Current role: {profile.get('experience',[{}])[0].get('title','')} at {profile.get('experience',[{}])[0].get('company','')}\n"
        f"Summary: {profile.get('summary','')}\n"
        f"Skills: {', '.join(profile.get('core_skills',[]))}\n"
        f"Tools: {', '.join(profile.get('tools',[]))}\n"
        f"Experience:{exp_text}\n\n"
        'Return ONLY valid JSON (no markdown):\n'
        '{"tailored_summary":"<2-3 sentences mirroring JD>","skills":["skill1",...],'
        '"experiences":[{"title":"EXACT original title","company":"EXACT original company",'
        '"duration":"EXACT original dates","highlights":["rewritten bullet 1","..."]}],'
        '"keywords_added":["kw1","kw2"]}'
    )

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=20))
def _call_llm(prompt):
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            r = Groq(api_key=groq_key).chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.2, max_tokens=2000,
            )
            return r.choices[0].message.content
        except Exception as e:
            logger.warning(f"[ResumeTailor] Groq 70b: {e}")
            try:
                from groq import Groq
                r = Groq(api_key=groq_key).chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role":"user","content":prompt}],
                    temperature=0.2, max_tokens=1800,
                )
                return r.choices[0].message.content
            except Exception as e2:
                logger.warning(f"[ResumeTailor] Groq 8b: {e2}")
    try:
        from google import genai
        c = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return c.models.generate_content(model="gemini-2.0-flash", contents=prompt).text
    except Exception as e:
        raise RuntimeError(f"All LLMs failed: {e}")

def _parse(raw):
    try:
        clean = raw.strip()
        for f in ("```json","```"):
            if clean.startswith(f): clean = clean[len(f):]
        clean = clean.rstrip("`").strip()
        return json.loads(clean)
    except Exception as e:
        logger.error(f"[ResumeTailor] JSON parse: {e}")
        return {}

def _render_pdf(tailored, profile, job, out_path):
    """Two-column PDF matching original resume format."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        HRFlowable, Table, TableStyle, KeepTogether)
        from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    except ImportError:
        logger.error("[ResumeTailor] reportlab not installed")
        return False

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
          leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)

    BLUE = colors.HexColor("#1A56DB")
    DARK = colors.HexColor("#1a1a2e")
    GREY = colors.HexColor("#555555")
    LGREY= colors.HexColor("#cccccc")
    WHITE= colors.white

    def S(name, **kw):
        base = dict(fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11)
        base.update(kw)
        return ParagraphStyle(name, **base)

    # Styles
    sName   = S("N",  fontSize=18, fontName="Helvetica-Bold", spaceAfter=2)
    sSumm   = S("Su", fontSize=8,  textColor=GREY, leading=11, spaceAfter=6)
    sSecL   = S("SL", fontSize=9,  fontName="Helvetica-Bold", textColor=BLUE, spaceBefore=6, spaceAfter=2)
    sTitle  = S("T",  fontSize=8.5, fontName="Helvetica-Bold", spaceAfter=0)
    sCo     = S("Co", fontSize=8,  textColor=GREY, spaceAfter=2)
    sBul    = S("B",  fontSize=8,  leftIndent=6, spaceAfter=1, leading=11)
    sSecR   = S("SR", fontSize=8,  fontName="Helvetica-Bold", textColor=WHITE, spaceBefore=4, spaceAfter=2)
    sLabelR = S("LR", fontSize=7.5,textColor=colors.HexColor("#cccccc"), spaceBefore=3, spaceAfter=1)
    sItemR  = S("IR", fontSize=8,  textColor=WHITE, leftIndent=4, leading=10, spaceAfter=1)
    sContactR=S("CR", fontSize=7.5,textColor=colors.HexColor("#e0e0e0"), leading=10, spaceAfter=2)

    name    = profile.get("name","")
    phone   = profile.get("phone","")
    email   = profile.get("email","")
    location= profile.get("location","")
    linkedin= profile.get("linkedin","")

    # ── LEFT COLUMN: Name + Summary + Experience ──────────────────────────────
    left = []
    left.append(Paragraph(name, sName))
    left.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=3))
    summ = tailored.get("tailored_summary") or profile.get("summary","")
    left.append(Paragraph(summ, sSumm))
    left.append(Paragraph("EXPERIENCE", sSecL))
    left.append(HRFlowable(width="100%", thickness=0.5, color=LGREY, spaceAfter=3))
    for exp in tailored.get("experiences", profile.get("experience",[])):
        items = [Paragraph(exp.get("title",""), sTitle)]
        items.append(Paragraph(f"{exp.get('company','')}  ({exp.get('duration','')})", sCo))
        for b in exp.get("highlights",[]):
            items.append(Paragraph(f"• {b}", sBul))
        items.append(Spacer(1,4))
        left.append(KeepTogether(items))

    # ── RIGHT COLUMN: Contact + Education + Skills + Tools + Certs ───────────
    right = []
    # Contact
    right.append(Paragraph("CONTACT", sSecR))
    right.append(Paragraph(location, sContactR))
    right.append(Paragraph(email, sContactR))
    right.append(Paragraph(phone, sContactR))
    right.append(Paragraph(linkedin, sContactR))
    right.append(Spacer(1,6))

    # Education
    right.append(Paragraph("EDUCATION", sSecR))
    for edu in profile.get("education",[]):
        right.append(Paragraph(f"{edu.get('degree','')}", sLabelR))
        right.append(Paragraph(f"{edu.get('institution','')}", sItemR))
        right.append(Paragraph(f"({edu.get('year','')}, {edu.get('gpa','')})", sContactR))
        right.append(Spacer(1,4))

    # Core Skills
    skills = tailored.get("skills", profile.get("core_skills",[]))
    right.append(Paragraph("CORE SKILLS", sSecR))
    for sk in skills:
        right.append(Paragraph(f"• {sk}", sItemR))
    right.append(Spacer(1,4))

    # Tools
    right.append(Paragraph("TOOLS", sSecR))
    for t in profile.get("tools",[]):
        right.append(Paragraph(f"• {t}", sItemR))
    right.append(Spacer(1,4))

    # Certifications
    certs = profile.get("certifications",[])
    if certs:
        right.append(Paragraph("CERTIFICATIONS", sSecR))
        for c in certs:
            right.append(Paragraph(f"• {c}", sItemR))

    # ── Assemble two-column table ──────────────────────────────────────────────
    page_w = A4[0] - 24*mm  # usable width
    left_w  = page_w * 0.65
    right_w = page_w * 0.35

    from reportlab.platypus import Frame, PageTemplate
    # Use table for two-column layout
    data = [[left, right]]
    t = Table(data, colWidths=[left_w, right_w])
    t.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (0,0), 0),
        ("RIGHTPADDING", (0,0), (0,0), 8),
        ("LEFTPADDING",  (1,0), (1,0), 8),
        ("RIGHTPADDING", (1,0), (1,0), 0),
        ("BACKGROUND",   (1,0), (1,0), colors.HexColor("#1a1a2e")),
        ("ROUNDEDCORNERS",(1,0),(1,0),[4]),
        ("TOPPADDING",   (1,0), (1,0), 10),
        ("BOTTOMPADDING",(1,0), (1,0), 10),
    ]))
    doc.build([t])
    return True


def tailor_resumes(jobs, profile, prefs):
    out_dir = Path("output/tailored_resumes")
    out_dir.mkdir(parents=True, exist_ok=True)
    suitable = [j for j in jobs if j.get("status") == "suitable"]
    logger.info(f"[ResumeTailor] Tailoring {len(suitable)} (2-col format, quality model)")
    for job in suitable:
        company = job.get("company","co"); title = job.get("title","role")
        try:
            raw      = _call_llm(_build_prompt(job, profile))
            tailored = _parse(raw) or {}
            kws = tailored.get("keywords_added",[])
            if kws: logger.info(f"[ResumeTailor] {company}: +{', '.join(kws[:4])}")
            out = out_dir / f"{_slug(company)}_{_slug(title)}.pdf"
            if _render_pdf(tailored, profile, job, out):
                job["tailored_resume_path"] = str(out)
                logger.info(f"[ResumeTailor] OK  {company} — {title}")
            else:
                job["tailored_resume_path"] = str(Path("config")/"resume.pdf")
        except Exception as e:
            logger.error(f"[ResumeTailor] Failed {company}: {e}")
            job["tailored_resume_path"] = str(Path("config")/"resume.pdf")
    return jobs
