"""
resume_tailor.py — Tailors resume per job using Groq, renders PDF matching original format.
"""
import os, json, re, logging
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:40]


def _build_prompt(job, profile):
    jd = (job.get("description") or "")[:4000]
    exp_text = ""
    for e in profile.get("experience", []):
        bullets = "\n    ".join(e.get("highlights", []))
        exp_text += f"\n  {e['title']} at {e['company']} ({e['duration']}):\n    {bullets}"
    return (
        "You are a professional resume writer for tech Program Manager roles.\n\n"
        "Tailor this resume for the specific job. Rules:\n"
        "- Do NOT invent facts or jobs — only reframe real content\n"
        "- Weave JD keywords naturally into existing bullets\n"
        "- Lead each bullet with a strong action verb\n"
        "- Tailor summary to mirror JD language (3 sentences max)\n"
        "- Put most JD-relevant skills first\n"
        "- Keep all company names, titles, dates exactly as-is\n\n"
        f"JOB: {job.get('title')} at {job.get('company')}\n"
        f"JD: {jd}\n\n"
        f"CANDIDATE: {profile.get('name','')}\n"
        f"Summary: {profile.get('summary','')}\n"
        f"Skills: {', '.join(profile.get('core_skills',[]))}\n"
        f"Tools: {', '.join(profile.get('tools',[]))}\n"
        f"Experience:{exp_text}\n\n"
        "Return ONLY valid JSON:\n"
        '{"tailored_summary":"<3 sentences>","skills":["s1","s2",...],'
        '"experiences":[{"title":"","company":"","duration":"","highlights":["..."]}],'
        '"keywords_added":["k1","k2"]}'
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=10, max=30))
def _call_llm(prompt):
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=1500,
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning(f"[ResumeTailor] Groq failed: {e}")
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return client.models.generate_content(
        model=os.getenv("GEMINI_MODEL","gemini-2.0-flash"), contents=prompt).text


def _parse(raw):
    try:
        clean = raw.strip()
        for f in ("```json","```"):
            if clean.startswith(f): clean = clean[len(f):]
        clean = clean.rstrip("`").strip()
        return json.loads(clean)
    except Exception as e:
        logger.error(f"[ResumeTailor] JSON parse failed: {e}")
        return {}


def _render_pdf(tailored, profile, job, out_path):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                        Spacer, HRFlowable, Table, TableStyle)
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
    except ImportError:
        logger.error("[ResumeTailor] reportlab not installed")
        return False

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=14*mm, bottomMargin=14*mm)

    BLUE  = colors.HexColor("#1A56DB")
    DARK  = colors.HexColor("#1a1a2e")
    GREY  = colors.HexColor("#555555")
    LGREY = colors.HexColor("#aaaaaa")

    def sty(name, **kw):
        base = dict(fontName="Helvetica", fontSize=9, textColor=DARK,
                    leading=12, spaceAfter=0, spaceBefore=0)
        base.update(kw)
        return ParagraphStyle(name, **base)

    s_name   = sty("N", fontSize=20, fontName="Helvetica-Bold",
                   textColor=DARK, spaceAfter=4)
    s_contact= sty("C", fontSize=8.5, textColor=GREY, spaceAfter=3)
    s_sec    = sty("S", fontSize=9.5, fontName="Helvetica-Bold",
                   textColor=BLUE, spaceBefore=7, spaceAfter=2)
    s_summ   = sty("Su", fontSize=9, leading=13, alignment=TA_JUSTIFY, spaceAfter=4)
    s_title  = sty("T", fontSize=9.5, fontName="Helvetica-Bold", spaceAfter=0)
    s_co     = sty("Co", fontSize=8.5, textColor=GREY, spaceAfter=2)
    s_bul    = sty("B", fontSize=8.5, leading=12, leftIndent=8, spaceAfter=1)
    s_skill  = sty("Sk", fontSize=8.5, leading=12, spaceAfter=2)
    s_edu    = sty("E", fontSize=9, fontName="Helvetica-Bold", spaceAfter=0)
    s_edusub = sty("Es", fontSize=8.5, textColor=GREY, spaceAfter=3)
    s_cert   = sty("Cr", fontSize=8.5, leading=12)

    name   = profile.get("name","")
    phone  = profile.get("phone","")
    email  = profile.get("email","")
    loc    = profile.get("location","")
    li     = profile.get("linkedin","")

    story = []

    # ── Name ──
    story.append(Paragraph(name, s_name))

    # ── Contact line ──
    parts = [x for x in [phone, email, loc, li] if x]
    story.append(Paragraph("  |  ".join(parts), s_contact))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=4))

    # ── Summary ──
    story.append(Paragraph("PROFESSIONAL SUMMARY", s_sec))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LGREY, spaceAfter=3))
    summ = tailored.get("tailored_summary") or profile.get("summary","")
    story.append(Paragraph(summ, s_summ))

    # ── Experience ──
    story.append(Paragraph("EXPERIENCE", s_sec))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LGREY, spaceAfter=3))
    for exp in tailored.get("experiences", profile.get("experience",[])):
        story.append(Paragraph(exp.get("title",""), s_title))
        story.append(Paragraph(
            f"{exp.get('company','')}  •  {exp.get('duration','')}", s_co))
        for b in exp.get("highlights",[]):
            story.append(Paragraph(f"• {b}", s_bul))
        story.append(Spacer(1, 4))

    # ── Skills ──
    story.append(Paragraph("CORE SKILLS", s_sec))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LGREY, spaceAfter=3))
    skills = tailored.get("skills", profile.get("core_skills",[]))
    tools  = profile.get("tools",[])
    story.append(Paragraph(
        f"<b>Skills:</b>  {chr(160)}{'  •  '.join(skills)}", s_skill))
    story.append(Paragraph(
        f"<b>Tools:</b>   {chr(160)}{'  •  '.join(tools)}", s_skill))

    # ── Education ──
    story.append(Paragraph("EDUCATION", s_sec))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LGREY, spaceAfter=3))
    for edu in profile.get("education",[]):
        story.append(Paragraph(
            f"{edu.get('degree','')}  •  {edu.get('institution','')}  •  {edu.get('year','')}", s_edu))
        story.append(Paragraph(f"GPA: {edu.get('gpa','')}", s_edusub))

    # ── Certifications ──
    certs = profile.get("certifications",[])
    if certs:
        story.append(Paragraph("CERTIFICATIONS", s_sec))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LGREY, spaceAfter=3))
        story.append(Paragraph("  •  ".join(certs), s_cert))

    doc.build(story)
    return True


def tailor_resumes(jobs, profile, prefs):
    out_dir = Path("output/tailored_resumes")
    out_dir.mkdir(parents=True, exist_ok=True)
    suitable = [j for j in jobs if j.get("status") == "suitable"]
    logger.info(f"[ResumeTailor] Tailoring {len(suitable)} resumes...")

    for job in suitable:
        company = job.get("company","co")
        title   = job.get("title","role")
        try:
            raw      = _call_llm(_build_prompt(job, profile))
            tailored = _parse(raw) or {}
            kws = tailored.get("keywords_added",[])
            if kws: logger.info(f"[ResumeTailor] {company}: {', '.join(kws[:4])}")
            out = out_dir / f"{_slug(company)}_{_slug(title)}.pdf"
            if _render_pdf(tailored, profile, job, out):
                job["tailored_resume_path"] = str(out)
                logger.info(f"[ResumeTailor] OK  {company} — {title}")
            else:
                job["tailored_resume_path"] = prefs.get("apply_settings",{}).get("resume_path","config/resume.pdf")
        except Exception as e:
            logger.error(f"[ResumeTailor] Failed {company}: {e}")
            job["tailored_resume_path"] = prefs.get("apply_settings",{}).get("resume_path","config/resume.pdf")

    logger.info(f"[ResumeTailor] Done — {len(suitable)}")
    return jobs
