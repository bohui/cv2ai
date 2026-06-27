---
name: cv2ai
description: Build resume-ready career summaries, weekly learning logs, skill inventories, repo/project profiles, and profile metric webpages from Codex chat history and local repositories. Use when the user asks to summarize what techniques, packages, tools, skills, repos, or accomplishments they learned or used with Codex, update a resume/CV, produce a developer profile, or run a weekly Codex-history career/profile report.
---

# CV2AI

## Overview

Use this skill to turn Codex collaboration history into evidence-backed career material: learned techniques, packages used, projects touched, resume bullets, profile metrics, and a static HTML dashboard.

The primary source is local Codex JSONL history under `~/.codex/sessions` and `~/.codex/archived_sessions`, plus package manifests found in repos referenced by those sessions.

## Workflow

1. Collect bounded evidence first:

```bash
python3 /Users/victor/.codex/skills/cv2ai/scripts/cv2ai_collect.py --span last-week
```

Use `--since YYYY-MM-DD --until YYYY-MM-DD` for a specific window, or `--span all` for a broader profile refresh. The script writes a timestamped folder under `~/.cv2ai-reports/` unless `--output-dir` is supplied.

2. Read `references/report-contract.md` before polishing deliverables. It defines the expected artifacts, evidence standard, and resume/profile style.

3. Review the generated `evidence.json`, `metrics.json`, `profile.md`, and `webpage.html`. The collector deterministically generates focus summaries, rough active-time percentages by repo/language/technique, new-vs-continued technique signals, credit/token consumption, and dashboard sections without needing an LLM pass.

4. Improve `profile.md` into a clear human-facing report:
- Start with the date range and repos covered.
- Include credits consumed and token usage from `metrics.json`; if numeric credits are unavailable, say so and use token totals as the consumption proxy.
- Summarize concrete accomplishments and techniques learned.
- Group packages/frameworks by ecosystem.
- Write resume bullets with action, technique, and outcome.
- Call out uncertain items as "possible" or omit them.

5. Use an LLM polish pass only when the user asks for resume prose refinement. For routine weekly reports, the script-generated Markdown and dashboard are the finished artifact.

## Privacy And Evidence Rules

- Do not include secrets, raw tokens, raw environment variables, private keys, or full chat transcripts in final outputs.
- Do not quote long chunks of Codex history. Summarize and cite local evidence paths instead.
- Do not inflate expertise from a single mention. Separate "used", "learned", "explored", and "configured".
- Preserve repo names and package names when they are visible in local manifests or session metadata.
- If history is sparse for the requested range, say so and produce a short report instead of inventing activity.

## Weekly Automation Prompt Pattern

For scheduled runs, use a prompt like:

```text
Use $cv2ai to analyze the previous 7 days of local Codex chat history. Run the collector with --span last-week so it writes to ~/.cv2ai-reports, verify that profile.md and webpage.html were generated, and always include the printed dashboard Markdown link (`[webpage.html](/absolute/path/webpage.html)`) in the final scheduler summary. Do not rewrite the generated dashboard unless the user explicitly asks for a prose polish pass.
```

## Script

- `scripts/cv2ai_collect.py`: scan Codex history, extract bounded evidence, inspect referenced repo manifests, compute metrics, and generate starter `profile.md` and `webpage.html`.
- `scripts/cv2ai_weekly.sh`: deterministic wrapper for weekly cron or LaunchAgent usage.
- `scripts/install_weekly_cron.sh`: optional helper that installs a weekly cron entry for the current skill checkout.
