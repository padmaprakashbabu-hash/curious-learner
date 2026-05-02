"""
resume_tailor.py — Tailors Priyanka's resume per job using Gemini,
then renders a clean ATS-friendly PDF with reportlab.
"""
import os, json, re, logging
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


# ── Gemini prompt ─────────────────────────────────────────────────────────────
def _build_tailor_prompt(job: dict, profile: dict) -> str:
    jd = (job.get("description") or "")[:4000]

    exp_text = ""
    for e in profile.get("experience", []):
        bullets = "\n    ".join(e.get("highlights", []))
        exp_text += f"\n  {e['title']} at {e['company']} ({e['duration']}):\n    {bullets}"

    skills  = ", ".join(profile.get("core_skills", []))
    tools   = ", ".join(profile.get("tools", []))
    certs   = ", ".join(profile.get("certifications", []))

    return (
        "You are a professional resume writer specialising in tech industry Program Manager roles.\n\n"
        "Tailor the candidate's resume for this specific job. Your goal: make the hiring manager feel "
        "this candidate was built for this exact role.\n\n"
        "RULES:\n"
        "- Do NOT invent facts, metrics, or jobs — only reframe and reorder real content\n"
        "- Weave keywords from the JD naturally into existing bullet points\n"
        "- Lead each bullet with a strong action verb\n"
        "- Quantify wherever the original already has numbers\n"
        "- Tailor the summary (3 sentences max) to directly mirror the JD's language\n"
        "- Put the most JD-relevant skills first in the skills list\n"
        "- Keep all company names, titles, and dates exactly as-is\n\n"
        f"JOB TITLE: {job.get('title')}\n"
        f"COMPANY: {job.get('company')}\n"
        f"JOB DESCRIPTION:\n{jd}\n\n"
        "CANDIDATE PROFILE:\n"
        f"Name: {profile.get('name')}\n"
        f"Summary: {profile.get('summary')}\n"
        f"Skills: {skills}\n"
        f"Tools: {tools}\n"
        f"Certifications: {certs}\n"
        f"Experience:{exp_text}\n\n"
        "Return ONLY valid JSON with this exact structure (no markdown fences):\n"
        "{\n"
        '  "tailored_summary": "<3 sentences, JD-aligned>",\n'
        '  "skills": ["skill1", "skill2", ...],\n'
        '  "experiences": [\n'
        '    {\n'
        '      "title": "<exact original title>",\n'
        '      "company": "<exact original company>",\n'
        '      "duration": "<exact original duration>",\n'
        '      "highlights": ["<rewritten bullet 1>", "<rewritten bullet 2>", ...]\n'
        '    }\n'
        '  ],\n'
        '  "keywords_added": ["kw1", "kw2"]\n'
        "}"
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _call_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        contents=prompt
    )
    return response.text.strip()


def _parse_tailored(raw: str) -> dict:
    try:
        clean = raw
        for fence in ("```json", "```"):
            clean = clean.removeprefix(fence)
        clean = clean.removesuffix("```").strip()
        return json.loads(clean)
    except Exception as e:
        logger.error(f"[ResumeTailor] JSON parse failed: {e}")
        return {}


# ── PDF renderer ──────────────────────────────────────────────────────────────
def _render_pdf(tailored: dict, profile: dict, job: dict, out_path: Path) -> bool:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        HRFlowable, ListFlowable, ListItem)
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    except ImportError:
        logger.error("[ResumeTailor] reportlab not installed. Run: pip install reportlab")
        return False

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm,  bottomMargin=16*mm,
    )

    ACCENT  = colors.HexColor("#1A56DB")
    DARK    = colors.HexColor("#1a1a2e")
    GREY    = colors.HexColor("#555555")
    LGREY   = colors.HexColor("#888888")

    styles  = getSampleStyleSheet()

    s_name  = ParagraphStyle("Name",  fontSize=20, textColor=DARK,
                              fontName="Helvetica-Bold", spaceAfter=1)
    s_meta  = ParagraphStyle("Meta",  fontSize=9,  textColor=GREY,
                              fontName="Helvetica",     spaceAfter=4)
    s_summ  = ParagraphStyle("Summ",  fontSize=9.5, textColor=DARK,
                              fontName="Helvetica",     spaceAfter=6,
                              leading=14, alignment=TA_JUSTIFY)
    s_sec   = ParagraphStyle("Sec",   fontSize=10, textColor=ACCENT,
                              fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3)
    s_role  = ParagraphStyle("Role",  fontSize=9.5, textColor=DARK,
                              fontName="Helvetica-Bold", spaceAfter=1)
    s_co    = ParagraphStyle("Co",    fontSize=9,  textColor=GREY,
                              fontName="Helvetica",     spaceAfter=2)
    s_bul   = ParagraphStyle("Bul",   fontSize=9,  textColor=DARK,
                              fontName="Helvetica",     leading=13,
                              leftIndent=10, spaceAfter=1)
    s_skill = ParagraphStyle("Skill", fontSize=9,  textColor=DARK,
                              fontName="Helvetica",     leading=13)
    s_cert  = ParagraphStyle("Cert",  fontSize=9,  textColor=DARK,
                              fontName="Helvetica",     leading=13)
    s_edu   = ParagraphStyle("Edu",   fontSize=9.5, textColor=DARK,
                              fontName="Helvetica-Bold")
    s_edusub= ParagraphStyle("EduSub",fontSize=9,  textColor=GREY,
                              fontName="Helvetica",     spaceAfter=3)

    story = []
    name  = profile.get("name", "")
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    loc   = profile.get("location", "")
    li    = profile.get("linkedin", "")

    story.append(Paragraph(name, s_name))
    meta_parts = [x for x in [phone, email, loc, li] if x]
    story.append(Paragraph("  |  ".join(meta_parts), s_meta))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceAfter=4))

    # Summary
    story.append(Paragraph("PROFESSIONAL SUMMARY", s_sec))
    story.append(Paragraph(tailored.get("tailored_summary", profile.get("summary", "")), s_summ))
    story.append(HRFlowable(width="100%", thickness=0.4, color=LGREY, spaceAfter=2))

    # Experience
    story.append(Paragraph("EXPERIENCE", s_sec))
    for exp in tailored.get("experiences", profile.get("experience", [])):
        story.append(Paragraph(exp.get("title", ""), s_role))
        story.append(Paragraph(
            f"{exp.get('company', '')}   •   {exp.get('duration', '')}", s_co))
        for bullet in exp.get("highlights", []):
            story.append(Paragraph(f"• {bullet}", s_bul))
        story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=0.4, color=LGREY, spaceAfter=2))

    # Skills
    story.append(Paragraph("CORE SKILLS", s_sec))
    skills = tailored.get("skills", profile.get("core_skills", []))
    tools  = profile.get("tools", [])
    story.append(Paragraph(
        "<b>Skills:</b>  " + "  •  ".join(skills), s_skill))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>Tools:</b>   " + "  •  ".join(tools), s_skill))
    story.append(HRFlowable(width="100%", thickness=0.4, color=LGREY, spaceAfter=2))

    # Education
    story.append(Paragraph("EDUCATION", s_sec))
    for edu in profile.get("education", []):
        story.append(Paragraph(
            f"{edu.get('degree','')}   •   {edu.get('institution','')}   •   {edu.get('year','')}", s_edu))
        story.append(Paragraph(f"GPA: {edu.get('gpa','')}", s_edusub))

    # Certifications
    certs = profile.get("certifications", [])
    if certs:
        story.append(HRFlowable(width="100%", thickness=0.4, color=LGREY, spaceAfter=2))
        story.append(Paragraph("CERTIFICATIONS", s_sec))
        story.append(Paragraph("  •  ".join(certs), s_cert))

    doc.build(story)
    return True


# ── Main entry ────────────────────────────────────────────────────────────────
def tailor_resumes(jobs: list, profile: dict, prefs: dict) -> list:
    """
    For each suitable job: tailor resume content with Gemini, render PDF.
    Stores tailored_resume_path in each job dict.
    """
    out_dir = Path("output/tailored_resumes")
    out_dir.mkdir(parents=True, exist_ok=True)

    suitable = [j for j in jobs if j.get("status") == "suitable"]
    logger.info(f"[ResumeTailor] Tailoring {len(suitable)} resumes...")

    for job in suitable:
        company = job.get("company", "co")
        title   = job.get("title",   "role")
        try:
            prompt   = _build_tailor_prompt(job, profile)
            raw      = _call_gemini(prompt)
            tailored = _parse_tailored(raw)

            if not tailored:
                logger.warning(f"[ResumeTailor] Empty parse for {company} — using base profile")
                tailored = {}

            kws = tailored.get("keywords_added", [])
            logger.info(f"[ResumeTailor] {company} — keywords added: {', '.join(kws[:5])}")

            filename = f"{_slug(company)}_{_slug(title)}.pdf"
            out_path = out_dir / filename

            ok = _render_pdf(tailored, profile, job, out_path)
            if ok:
                job["tailored_resume_path"] = str(out_path)
                logger.info(f"[ResumeTailor] OK  {company} — {title} → {out_path}")
            else:
                job["tailored_resume_path"] = prefs.get("apply_settings", {}).get(
                    "resume_path", "config/resume.pdf")
                logger.warning(f"[ResumeTailor] PDF render failed, using base resume")

        except Exception as e:
            logger.error(f"[ResumeTailor] Failed for {company}: {e}")
            job["tailored_resume_path"] = prefs.get("apply_settings", {}).get(
                "resume_path", "config/resume.pdf")

    logger.info(f"[ResumeTailor] Done — {len(suitable)} resumes tailored")
    return jobs
