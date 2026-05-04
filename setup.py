#!/usr/bin/env python3
"""
Job Search Agent — Setup Wizard
Run: python setup.py
"""
import os, sys, json, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).parent
G='\033[92m'; Y='\033[93m'; C='\033[96m'; R='\033[91m'; B='\033[1m'; X='\033[0m'

def banner():
    print(f"""
{C}{B}
╔══════════════════════════════════════════╗
║      🚀  Job Search Agent Setup          ║
║      Find & apply to jobs automatically  ║
╚══════════════════════════════════════════╝
{X}""")

def ask(prompt, default="", required=True, secret=False):
    if default:
        full_prompt = f"  {C}{prompt}{X} [{Y}{default}{X}]: "
    else:
        full_prompt = f"  {C}{prompt}{X}: "
    while True:
        try:
            val = input(full_prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Y}Setup cancelled.{X}")
            sys.exit(0)
        if not val and default:
            return default
        if not val and required:
            print(f"  {R}Required — please enter a value.{X}")
            continue
        return val

def check_existing():
    env = ROOT / ".env"
    profile = ROOT / "config" / "profile.json"
    if env.exists() and profile.exists():
        try:
            p = json.loads(profile.read_text())
            if p.get("name") and p.get("name") != "Your Full Name":
                print(f"\n{G}✓ Existing setup detected for: {B}{p['name']}{X}")
                choice = input(f"  Reconfigure? (y/N): ").strip().lower()
                if choice != 'y':
                    print(f"\n{G}Setup already complete. Run:{X}")
                    print(f"  python main.py --find\n")
                    sys.exit(0)
        except Exception:
            pass

def load_env():
    env_path = ROOT / ".env"
    values = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values

def save_env(values):
    env_path = ROOT / ".env"
    lines = ["# Job Search Agent — Configuration\n"]
    for k, v in values.items():
        lines.append(f"{k}={v}\n")
    env_path.write_text("".join(lines))

def test_groq(key):
    try:
        from groq import Groq
        Groq(api_key=key).chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"user","content":"Say OK"}],
            max_tokens=5)
        return True
    except Exception:
        return False

def test_gemini(key):
    try:
        from google import genai
        c = genai.Client(api_key=key)
        c.models.generate_content(model="gemini-2.0-flash", contents="Say OK")
        return True
    except Exception:
        return False

def main():
    banner()
    check_existing()
    existing = load_env()
    values = dict(existing)
    profile = {}

    print(f"{B}Step 1 — Your Profile{X}")
    print(f"  {Y}This stays on your machine and is never uploaded to GitHub.{X}\n")

    name = ask("Your full name", existing.get("APPLICANT_NAME",""))
    email= ask("Your email address", existing.get("APPLICANT_EMAIL",""))
    phone= ask("Your phone number (optional)", existing.get("APPLICANT_PHONE",""), required=False)
    linkedin = ask("Your LinkedIn URL (optional)", existing.get("APPLICANT_LINKEDIN",""), required=False)

    print(f"\n{B}Step 2 — Job Search Preferences{X}")
    role  = ask("Primary target role (e.g. Senior Program Manager)", "Senior Program Manager")
    salary= ask("Minimum salary (INR lakhs, e.g. 40)", existing.get("MIN_SALARY_LAKHS","40"))
    resume_src = ask("Path to your resume PDF (drag & drop or type path)", "", required=False)

    print(f"\n{B}Step 3 — AI API Keys (free){X}")
    print(f"  {Y}Groq: console.groq.com  |  Gemini: aistudio.google.com{X}\n")
    groq_key = ask("Groq API key (gsk_...)", existing.get("GROQ_API_KEY",""))
    print(f"  Testing Groq key...", end="", flush=True)
    if test_groq(groq_key):
        print(f" {G}✓ Valid{X}")
    else:
        print(f" {R}✗ Invalid or quota exceeded (continuing anyway){X}")

    gemini_key = ask("Gemini API key (AIza..., optional fallback)", existing.get("GEMINI_API_KEY",""), required=False)

    print(f"\n{B}Step 4 — Email Digest (optional){X}")
    print(f"  {Y}Gmail App Password: myaccount.google.com → Security → App Passwords{X}\n")
    gmail_pass = ask("Gmail App Password (16 chars, optional)", existing.get("GMAIL_APP_PASSWORD",""), required=False)

    print(f"\n{B}Step 5 — Optional: Adzuna API (better India coverage){X}")
    print(f"  {Y}Free at: developer.adzuna.com{X}\n")
    adz_id  = ask("Adzuna App ID (optional)", existing.get("ADZUNA_APP_ID",""), required=False)
    adz_key = ask("Adzuna App Key (optional)", existing.get("ADZUNA_APP_KEY",""), required=False)

    # Save .env
    values.update({
        "APPLICANT_NAME":    name,
        "APPLICANT_EMAIL":   email,
        "APPLICANT_PHONE":   phone,
        "APPLICANT_LINKEDIN": linkedin,
        "GROQ_API_KEY":      groq_key,
        "GEMINI_API_KEY":    gemini_key,
        "GMAIL_SENDER":      email,
        "DIGEST_RECIPIENT":  email,
        "GMAIL_APP_PASSWORD": gmail_pass,
        "ADZUNA_APP_ID":     adz_id,
        "ADZUNA_APP_KEY":    adz_key,
        "GEMINI_MODEL":      "gemini-2.0-flash",
        "MIN_SUITABILITY_SCORE": "65",
        "MAX_JOB_AGE_DAYS":  "10",
        "DAILY_RUN_TIME":    "08:00",
    })
    save_env(values)

    # Copy resume
    if resume_src:
        src_path = Path(resume_src.strip().strip("'\""))
        if src_path.exists():
            dst = ROOT / "config" / "resume.pdf"
            shutil.copy(src_path, dst)
            print(f"\n  {G}✓ Resume copied to config/resume.pdf{X}")
        else:
            print(f"\n  {Y}⚠ Resume file not found at {resume_src} — skipping{X}")

    # Build profile.json from existing if possible, else create from inputs
    profile_path = ROOT / "config" / "profile.json"
    example_path = ROOT / "config" / "profile.example.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text())
        except Exception:
            profile = {}
    elif example_path.exists():
        profile = json.loads(example_path.read_text())

    # Update with user inputs
    profile["name"]    = name
    profile["email"]   = email
    profile["phone"]   = phone
    profile["linkedin"] = linkedin
    profile["target_roles"] = [role] + [r for r in profile.get("target_roles",[]) if r != role]
    profile["keywords_for_search"] = [
        f"{role} remote",
        f"Senior Program Manager remote",
        f"Principal Program Manager remote",
        f"Technical Program Manager remote India",
    ]
    profile_path.write_text(json.dumps(profile, indent=2))

    # Update preferences.json salary
    prefs_path = ROOT / "config" / "preferences.json"
    example_prefs = ROOT / "config" / "preferences.example.json"
    if not prefs_path.exists() and example_prefs.exists():
        prefs = json.loads(example_prefs.read_text())
        prefs_path.write_text(json.dumps(prefs, indent=2))
    if prefs_path.exists():
        prefs = json.loads(prefs_path.read_text())
        try:
            prefs["job_preferences"]["min_salary_inr_lakhs"] = int(salary)
        except Exception:
            pass
        prefs_path.write_text(json.dumps(prefs, indent=2))

    print(f"""
{G}{B}╔════════════════════════════════════╗
║   ✅  Setup Complete!               ║
╚════════════════════════════════════╝{X}

  Configured for: {B}{name}{X}
  Target role:    {B}{role}{X}

  {B}Next steps:{X}
  1. Run the agent:
     {C}python main.py --find{X}

  2. Or double-click {B}Job Agent.app{X} on Desktop
  
  3. Browser opens at http://localhost:8080
     → Review jobs → Click Details → Generate CL → Apply
""")

if __name__ == "__main__":
    main()
