# 🔍 PR Review Bot (Python)

AI-powered code review using Claude. Analyzes git PR diffs and returns structured feedback on bugs, security, style, and suggestions. **Zero external dependencies** — pure Python stdlib.

## Features

- 🐛 **Bug Detection** — logic errors, null refs, unhandled exceptions
- 🔒 **Security Analysis** — SQL injection, hardcoded secrets, auth flaws
- 🎨 **Style Review** — naming, duplication, complexity
- 💡 **Suggestions** — performance, best practices
- 📊 **Quality Score** — 0–100 overall rating
- 🖥️ **Two interfaces** — CLI tool + Web app

---

## Quick Start

### CLI

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Review a diff file
python review.py changes.diff

# Pipe from git
git diff main...my-feature | python review.py

# Save markdown report
python review.py --markdown -o report.md pr.diff

# JSON output
python review.py --json pr.diff
```

### Web App

```bash
python server.py        # opens http://localhost:3000
python server.py 8080   # custom port
```

Enter your API key in the input field, paste a diff, click **Analyze PR**.

---

## CLI Options

| Flag | Description |
|------|-------------|
| `--bugs` | Focus on bugs only |
| `--security` | Security-focused review |
| `--style` | Style issues only |
| `--json` | Raw JSON output |
| `--markdown` / `--md` | Markdown report |
| `-o FILE` | Save to file |
| `-v` / `--verbose` | Show all sections even if empty |
| `-h` / `--help` | Help |

**Environment:**
```
ANTHROPIC_API_KEY=sk-ant-...   # required
```

---

## JSON Schema

```json
{
  "summary": "Overall assessment",
  "score": 78,
  "bugs": [
    {
      "line": "src/auth.py:14",
      "description": "SQL injection via f-string",
      "fix": "Use parameterized queries: db.execute('... WHERE id=?', (id,))",
      "severity": "high"
    }
  ],
  "security": [...],
  "style":    [...],
  "suggestions": [...]
}
```

**Severity:** `high` = must fix · `medium` = should fix · `low` = optional  
**Exit codes:** `0` = clean · `1` = high-severity found · `2` = error

---

## CI/CD (GitHub Actions)

Add `.github/workflows/review.yml` (included) and set `ANTHROPIC_API_KEY` as a repository secret. The bot will post a review comment on every PR automatically.

---

## Project Structure

```
pr-review-bot-py/
├── review.py                      # CLI tool (pure stdlib, no deps)
├── server.py                      # Dev web server (pure stdlib)
├── index.html                     # Web app UI (single file)
├── requirements.txt               # No required deps; optional extras listed
├── .github/workflows/review.yml   # CI workflow
└── README.md
```