# Contributing to Job Search Agent

Thank you for your interest in contributing! 🎉

## How to Contribute

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/add-new-source`
3. Make your changes
4. Test thoroughly: `python main.py --find`
5. Submit a PR with a clear description

## Priority Areas

- 🔍 **New job sources** — Dice, Hired, SimplyHired, LinkedIn Jobs API
- 🤖 **Better auto-apply** — Workday, iCIMS, Taleo support  
- 🪟 **Windows .exe launcher** — equivalent of Job Agent.app for Windows
- 📱 **Notifications** — Slack, Telegram, WhatsApp integration
- 🌍 **Internationalisation** — support for more countries/currencies

## Code Style

- Python 3.10+ compatible
- Use `pathlib.Path` (not `os.path`) for file operations
- All secrets via `os.getenv()` — never hardcode credentials
- Each module must be self-contained with clear docstrings
- Handle errors gracefully — a single failure should never crash the pipeline

## Running Tests

```bash
# Syntax check all files
python3 -c "import ast, pathlib; [ast.parse(f.read_text()) for f in pathlib.Path('modules').glob('*.py')]"

# Test UI
python main.py --ui
```
