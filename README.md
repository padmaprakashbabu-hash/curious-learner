# 🚀 Job Search Agent

> **The most complete open-source job search automation agent.**
> Finds, scores, tailors, and applies to jobs across 9 sources — with your approval.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **9 Job Sources** | LinkedIn, Indeed, Google Jobs, Naukri, Monster, Remotive, Adzuna, Greenhouse (50+ companies), Lever (30+ companies), Wellfound |
| **AI Scoring** | Gemini AI scores each job 0–100 against your profile |
| **Tailored Resume** | AI generates a custom PDF resume per job |
| **Custom Cover Letters** | AI writes a targeted cover letter per job |
| **Web UI** | Beautiful browser-based review interface with dark mode |
| **Smart Apply** | Auto-applies on Greenhouse/Lever; flags others for manual action |
| **Email Digest** | Daily summary email with applied + action-required jobs |
| **Persistent DB** | SQLite — remembers every job, every run |
| **Cross-Platform** | Mac + Windows |

---

## 🖥 Demo

```
python main.py --find
```
→ Fetches ~450 jobs → Filters to ~20 PM roles → Scores with AI → Opens browser

![Dashboard Preview](docs/screenshots/dashboard.png)

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10+
- Free [Gemini API key](https://aistudio.google.com) (1,500 req/day)
- Gmail App Password (for email digest)

### Mac / Linux
```bash
git clone https://github.com/YOUR_USERNAME/job-search-agent
cd job-search-agent
python setup.py          # interactive wizard — 5 mins
./run.sh                 # start the agent
```

### Windows
```cmd
git clone https://github.com/YOUR_USERNAME/job-search-agent
cd job-search-agent
python setup.py
run.bat
```

---

## 🧙 Setup Wizard

Running `python setup.py` will ask you for:

1. Your name, email, phone, LinkedIn
2. Target job role (e.g. "Senior Program Manager")
3. Resume PDF path
4. Salary floor
5. Gemini API key → [get free key](https://aistudio.google.com)
6. Gmail App Password → [how to create](https://myaccount.google.com/apppasswords)
7. Adzuna API key (optional, better India coverage) → [free registration](https://developer.adzuna.com)

---

## 📋 How It Works

```
python main.py --find
       │
       ├─ [1/4] Fetch — 9 sources, ~450 raw jobs (10s)
       ├─ [2/4] Filter — date, title relevance, dedup → ~20 PM roles
       ├─ [3/4] Score — Gemini AI 0-100 per job (~5 mins)
       ├─ [4/4] Prepare — tailored resume PDF + cover letter per job
       │
       └─ Browser opens at http://localhost:5000
                    │
          Review each job card
          📑 View tailored resume
          ✏️  Edit cover letter
          ✅ Click Apply → agent submits
          ⚡ Manual apply link for unsupported platforms
```

---

## 🔍 Job Sources

| Source | Type | Coverage |
|--------|------|----------|
| Indeed | Job board | Global |
| Google Jobs | Aggregator | Career pages of 1000s of companies |
| LinkedIn | Network | Global (optional, can be slow) |
| Remotive | Remote-only | Global tech companies |
| Adzuna | API | India + Global |
| Naukri | Scraper | India #1 |
| Monster | Scraper | India + Global |
| Greenhouse | Career pages API | 50+ tech companies |
| Lever | Career pages API | 30+ tech companies |
| Wellfound | Startup jobs | Global startups |

---

## ⚙️ Configuration

All config lives in:
- `.env` — API keys and personal details (never committed)
- `config/profile.json` — your skills, experience, target roles
- `config/preferences.json` — salary floor, job boards, apply settings

Copy the examples to get started:
```bash
cp .env.example .env
cp config/profile.example.json config/profile.json
cp config/preferences.example.json config/preferences.json
```

---

## 🤖 Auto-Apply Support

| Platform | Auto-Apply | Notes |
|----------|-----------|-------|
| Greenhouse | ✅ Yes | Most reliable |
| Lever | ✅ Yes | Very reliable |
| SmartRecruiters | ✅ Yes | |
| Ashby | ✅ Yes | |
| Workday | ⚡ Manual | Complex forms |
| LinkedIn Easy Apply | ⚡ Manual | ToS concerns |
| Email | ✅ Yes | Sends with resume attached |
| Other | ⚡ Manual | Direct link provided |

---

## 🆓 Running Costs

**Everything is free:**
- Gemini API: Free tier, 1,500 req/day (enough for ~50 runs/month with title filter)
- All job board sources: Free (no paid API keys needed)
- Only optional paid: Adzuna free tier works fine

---

## 📁 Project Structure

```
job-search-agent/
├── main.py              # Entry point
├── app.py               # Flask web UI server
├── setup.py             # First-time setup wizard
├── launcher.sh          # Mac/Linux smart launcher
├── run.sh               # Mac/Linux one-click runner
├── run.bat              # Windows one-click runner
├── requirements.txt
├── .env.example         # Config template
├── config/
│   ├── profile.json         # Your profile (gitignored)
│   └── preferences.json     # Search settings (gitignored)
├── modules/
│   ├── job_fetcher.py       # 9-source job fetcher
│   ├── date_filter.py       # Filter + title relevance
│   ├── scorer.py            # Gemini AI scorer
│   ├── cover_letter.py      # Cover letter generator
│   ├── resume_tailor.py     # PDF resume tailoring
│   ├── apply_engine.py      # Playwright auto-apply
│   ├── dashboard.py         # HTML dashboard
│   ├── email_digest.py      # Gmail digest
│   └── db.py                # SQLite wrapper
└── output/                  # Generated files (gitignored)
    ├── cover_letters/
    └── tailored_resumes/
```

---

## 🛡 Privacy

- Your `.env`, `config/profile.json`, `config/resume.pdf` are **gitignored** — never uploaded
- All data stays on your machine
- No cloud server, no third-party data sharing

---

## 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Ideas for contributions:
- Add more job sources (Dice, Hired, SimplyHired)
- Improve Workday auto-apply
- Add Slack/Telegram notifications
- Build a Windows .exe launcher

---

## 📄 License

MIT — free for personal and commercial use.
