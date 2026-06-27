# CV2AI Report Contract

## Generated Files

The collector creates:

- `evidence.json`: bounded source evidence from Codex sessions, commands, repo paths, package manifests, and snippets.
- `metrics.json`: aggregate counts for repos, packages, techniques, skills, commands, and files.
- `profile.md`: deterministic Markdown report for resume/profile use.
- `webpage.html`: static local dashboard with rough active-time percentages by repo, language, and technique, plus focus summary, new/continued technique signals, credits consumed, and token usage.

Reports are written under `~/.cv2ai-reports/` by default. Each run should create a timestamped folder and keep all run artifacts together.

## Evidence Standard

Use extracted data as follows:

- Strong evidence: repo manifests, explicit user requests, file paths, commands, generated artifacts, test/lint/build outputs.
- Medium evidence: repeated assistant summaries, repeated technique/package mentions across sessions.
- Weak evidence: one-off mentions, planned work, errors, or exploratory discussion.

Resume bullets should rely on strong or medium evidence. Weak evidence may appear in a "learning signals" section only when useful.

## Profile Structure

Use this order for polished Markdown:

1. Date range and coverage summary.
2. Career snapshot in 3-5 lines.
3. Top accomplishments by repo/project.
4. Techniques learned or practiced.
5. Packages/frameworks/tools grouped by ecosystem.
6. Resume-ready bullets.
7. Rough active-time allocation by repo, language, and technique.
8. New technique signals and continued technique signals.
9. Consumption metrics: credits consumed when available, otherwise token totals as the consumption proxy.
10. Web/profile metrics.
11. Evidence notes and caveats.

## Static Dashboard

The collector should generate `webpage.html` as a finished static dashboard without an LLM polish pass:

- Lead with last-week focus: most touched repo, strongest language, leading technique, and rough active hours.
- Show percentages with visual bars, not plain tables.
- Label active time as rough because it is estimated from Codex session timestamp gaps.
- Separate "new technique signals" from "kept using" by comparing the selected window with earlier Codex history.
- Keep every claim derivable from `metrics.json` or `evidence.json`.

## Consumption Metrics

Codex history may include `token_count` events. Use `metrics.json.usage` for consumption reporting:

- Show `credits_display` as "Credits consumed" in the webpage.
- If `credits_available` is false, keep `n/a` for credits and state that numeric credits were not exposed in the history.
- Always show token totals so the report still captures consumption.
- Do not infer currency cost or paid credits from tokens unless the user provides an explicit conversion rule.

## Resume Bullet Style

Prefer:

- Built/implemented/debugged/refactored/validated/deployed ...
- Name the technique or package only when it is evidence-backed.
- Include outcomes when visible: passing tests, shipped feature, reduced risk, improved UX, automation, report, dashboard, or integration.

Avoid:

- "Expert in" unless long-running repeated evidence supports it.
- Listing every package as a skill.
- Exposing private repo details beyond what the user asks to publish.
