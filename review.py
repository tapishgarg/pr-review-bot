#!/usr/bin/env python3
"""
PR Review Bot - CLI Tool (Python)
Usage:
    python review.py changes.diff
    git diff main...feature | python review.py
    python review.py --security --markdown -o report.md pr.diff
"""

import sys
import os
import json
import argparse
import http.client
import urllib.parse
from textwrap import indent

# ─── Config ──────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000
API_HOST = "api.anthropic.com"
API_PATH = "/v1/messages"

# ─── ANSI Colors ─────────────────────────────────────────────────────────────

class C:
    RESET   = "\x1b[0m"
    BOLD    = "\x1b[1m"
    DIM     = "\x1b[2m"
    RED     = "\x1b[31m"
    GREEN   = "\x1b[32m"
    YELLOW  = "\x1b[33m"
    BLUE    = "\x1b[34m"
    MAGENTA = "\x1b[35m"
    CYAN    = "\x1b[36m"

def _c(code, text): return f"{code}{text}{C.RESET}"
def bold(t):    return _c(C.BOLD, t)
def dim(t):     return _c(C.DIM, t)
def red(t):     return _c(C.RED, t)
def green(t):   return _c(C.GREEN, t)
def yellow(t):  return _c(C.YELLOW, t)
def blue(t):    return _c(C.BLUE, t)
def magenta(t): return _c(C.MAGENTA, t)
def cyan(t):    return _c(C.CYAN, t)

NO_COLOR = not sys.stdout.isatty()
if NO_COLOR:
    bold = dim = red = green = yellow = blue = magenta = cyan = lambda t: t

# ─── Argument Parser ──────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        prog="review.py",
        description="AI-powered PR code review using Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python review.py changes.diff
  git diff main...feature | python review.py
  python review.py --security --markdown -o report.md pr.diff
  python review.py --json pr.diff | python -m json.tool
        """
    )
    parser.add_argument("file", nargs="?", help="Path to .diff file")
    parser.add_argument("--bugs",      action="store_true", help="Focus on bugs only")
    parser.add_argument("--security",  action="store_true", help="Focus on security issues")
    parser.add_argument("--style",     action="store_true", help="Focus on style issues")
    parser.add_argument("--json",      action="store_true", help="Output raw JSON")
    parser.add_argument("--markdown", "--md", action="store_true", help="Output Markdown report")
    parser.add_argument("-o", "--output", metavar="FILE", help="Save output to file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all sections even if empty")
    return parser.parse_args()

# ─── Read Input ───────────────────────────────────────────────────────────────

def read_input(args):
    if args.file:
        if not os.path.exists(args.file):
            print(red(f"Error: File not found: {args.file}"), file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print(red("Error: No diff input. Provide a file or pipe from git diff."), file=sys.stderr)
    sys.exit(1)

# ─── Claude API Call ──────────────────────────────────────────────────────────

def call_claude(diff: str, focus: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print(red("Error: ANTHROPIC_API_KEY environment variable is not set."), file=sys.stderr)
        print(dim("Get your key at: https://console.anthropic.com"), file=sys.stderr)
        sys.exit(1)

    focus_note = f"\nFocus primarily on: {focus} issues." if focus != "full" else ""

    system_prompt = (
        "You are an expert code reviewer. Analyze the provided git diff and return ONLY a valid JSON object:\n"
        "{\n"
        '  "summary": "2-3 sentence overall assessment",\n'
        '  "score": 75,\n'
        '  "bugs": [{"line": "filename:linenum", "description": "issue", "fix": "suggested fix", "severity": "high|medium|low"}],\n'
        '  "security": [{"line": "filename:linenum", "description": "concern", "fix": "how to fix", "severity": "high|medium|low"}],\n'
        '  "style": [{"line": "filename:linenum", "description": "style issue", "fix": "improvement", "severity": "low"}],\n'
        '  "suggestions": [{"line": "filename:linenum", "description": "idea", "fix": "approach", "severity": "low"}]\n'
        "}\n"
        "score is 0-100 (higher = better). severity: high=must fix, medium=should fix, low=optional.\n"
        "Return ONLY valid JSON, no markdown fences, no explanation." + focus_note
    )

    payload = json.dumps({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": f"Review this PR diff:\n\n{diff}"}],
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": api_key,
        "Content-Length": str(len(payload)),
    }

    conn = http.client.HTTPSConnection(API_HOST)
    conn.request("POST", API_PATH, body=payload, headers=headers)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()

    data = json.loads(body)
    if resp.status != 200:
        msg = data.get("error", {}).get("message", f"HTTP {resp.status}")
        print(red(f"API Error: {msg}"), file=sys.stderr)
        sys.exit(2)

    raw_text = "".join(b.get("text", "") for b in data.get("content", []))
    clean = raw_text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)

# ─── Spinner ──────────────────────────────────────────────────────────────────

import threading
import time

class Spinner:
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    def __init__(self, msg="Analyzing with Claude..."):
        self.msg = msg
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)
    def _spin(self):
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r  {cyan(self.frames[i % len(self.frames)])}  {dim(self.msg)}")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1
    def start(self):
        if sys.stdout.isatty(): self._thread.start()
    def stop(self):
        self._stop.set()
        if sys.stdout.isatty():
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()

# ─── Output Formatters ────────────────────────────────────────────────────────

SEV_ICON  = {"high": "●", "medium": "◐", "low": "○"}
SEV_COLOR = {"high": red,  "medium": yellow, "low": dim}

def sev_fmt(sev):
    fn = SEV_COLOR.get(sev, dim)
    ic = SEV_ICON.get(sev, "○")
    return fn(ic)

def render_pretty(result: dict, verbose: bool) -> str:
    lines = [""]
    lines.append(bold("┌─ PR Review Bot Results ─────────────────────────────────────────"))
    lines.append("")

    score = result.get("score", 0)
    filled = round(score / 5)
    empty  = 20 - filled
    score_color = green if score >= 80 else yellow if score >= 60 else red
    bar = score_color("█" * filled) + dim("░" * empty)
    lines.append(f"  {bold('Quality Score')}  {bar}  {score_color(bold(str(score) + '/100'))}")
    lines.append("")
    lines.append(f"  {bold('Summary')}")
    lines.append(f"  {dim(result.get('summary', 'No summary.'))}")
    lines.append("")

    sections = [
        ("bugs",        "🐛", "BUGS",        red),
        ("security",    "🔒", "SECURITY",    magenta),
        ("style",       "🎨", "STYLE",       blue),
        ("suggestions", "💡", "SUGGESTIONS", cyan),
    ]

    for key, icon, label, color_fn in sections:
        items = result.get(key, [])
        if not verbose and not items:
            continue
        lines.append(f"  {icon}  {color_fn(bold(label))}  {dim(f'({len(items)})')}")
        lines.append(f"  {'─' * 60}")
        if not items:
            lines.append(f"  {green('✓')}  {dim('No issues found')}")
        else:
            for i, item in enumerate(items):
                sev = item.get("severity", "low")
                lines.append(f"  {sev_fmt(sev)}  {item.get('description', '')}")
                if item.get("line"):
                    lines.append(f"     {dim('at')} {cyan(item['line'])}")
                if item.get("fix"):
                    fix_lines = item["fix"].split("\n")
                    lines.append(f"     {dim('→')} {fix_lines[0]}")
                    for fl in fix_lines[1:]:
                        lines.append(f"       {fl}")
                if i < len(items) - 1:
                    lines.append("")
        lines.append("")

    total = sum(len(result.get(k, [])) for k in ["bugs","security","style"])
    lines.append(f"  {dim('Total issues: ' + str(total) + '  |  Model: ' + MODEL)}")
    lines.append(bold("└────────────────────────────────────────────────────────────────"))
    lines.append("")
    return "\n".join(lines)


def render_markdown(result: dict) -> str:
    lines = ["# PR Review Bot Report\n"]
    lines.append(f"**Quality Score:** {result.get('score', 0)}/100\n")
    lines.append(f"## Summary\n{result.get('summary', '')}\n")

    sections = [
        ("bugs",        "🐛 Bugs"),
        ("security",    "🔒 Security"),
        ("style",       "🎨 Style"),
        ("suggestions", "💡 Suggestions"),
    ]
    for key, label in sections:
        items = result.get(key, [])
        lines.append(f"## {label}\n")
        if not items:
            lines.append("_No issues found._\n")
        else:
            for item in items:
                lines.append(f"### {item.get('description', '')}")
                if item.get("line"):      lines.append(f"**Location:** `{item['line']}`")
                if item.get("severity"):  lines.append(f"**Severity:** {item['severity']}")
                if item.get("fix"):       lines.append(f"\n**Fix:**\n```\n{item['fix']}\n```")
                lines.append("")

    lines.append(f"---\n_Generated by PR Review Bot using {MODEL}_")
    return "\n".join(lines)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    diff = read_input(args)
    if not diff.strip():
        print(red("Error: Diff input is empty."), file=sys.stderr)
        sys.exit(1)

    # Determine focus
    if args.bugs:      focus = "bugs"
    elif args.security: focus = "security"
    elif args.style:    focus = "style"
    else:               focus = "full"

    spinner = Spinner()
    spinner.start()

    try:
        result = call_claude(diff, focus)
    finally:
        spinner.stop()

    # Format output
    if args.json:
        output = json.dumps(result, indent=2)
    elif args.markdown:
        output = render_markdown(result)
    else:
        output = render_pretty(result, args.verbose)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(green(f"✓ Report saved to: {args.output}"))
    else:
        print(output)

    # Exit 1 if high-severity bugs/security found
    high = any(
        i.get("severity") == "high"
        for k in ("bugs", "security")
        for i in result.get(k, [])
    )
    sys.exit(1 if high else 0)


if __name__ == "__main__":
    main()
