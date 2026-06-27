#!/usr/bin/env python3
"""Collect Codex-history evidence for CV/profile generation."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    tomllib = None


TOKEN_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|authorization)\s*[:=]\s*['\"]?[^'\"\s,}]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
]

TECH_PATTERNS = {
    "React": r"\bReact\b",
    "Next.js": r"\bNext(?:\.js|JS)?\b",
    "TypeScript": r"\bTypeScript\b|\btsx?\b",
    "JavaScript": r"\bJavaScript\b|\bjsx?\b",
    "Python": r"\bPython\b|\bpytest\b|\bpyproject\b",
    "Playwright": r"\bPlaywright\b",
    "Tailwind CSS": r"\bTailwind\b",
    "Node.js": r"\bNode(?:\.js)?\b|\bnpm\b|\bpnpm\b|\byarn\b",
    "OpenAI API": r"\bOpenAI\b|\bResponses API\b|\bChatGPT\b",
    "Codex": r"\bCodex\b",
    "MCP": r"\bMCP\b|\bmcp_servers\b",
    "GitHub": r"\bGitHub\b|\bgh\b|\bpull request\b|\bPR\b",
    "GitHub Actions": r"\bGitHub Actions\b|\bworkflow\b",
    "Docker": r"\bDocker\b|\bdocker compose\b|\bcontainer\b",
    "Supabase": r"\bSupabase\b",
    "PostgreSQL": r"\bPostgreSQL\b|\bPostgres\b",
    "SQLite": r"\bSQLite\b",
    "Prisma": r"\bPrisma\b",
    "Drizzle": r"\bDrizzle\b",
    "FastAPI": r"\bFastAPI\b",
    "Django": r"\bDjango\b",
    "Flask": r"\bFlask\b",
    "Vite": r"\bVite\b",
    "ESLint": r"\bESLint\b",
    "Vitest": r"\bVitest\b",
    "Jest": r"\bJest\b",
    "Testing Library": r"\bTesting Library\b",
    "Security Review": r"\bsecurity\b|\baudit\b|\bsecrets?\b",
    "Automation": r"\bcron\b|\bautomation\b|\bscheduled\b|\bweekly\b",
    "Data Analysis": r"\bdata analysis\b|\bdashboard\b|\breport\b|\bmetrics?\b",
    "Frontend UX": r"\bfrontend\b|\bUI\b|\bUX\b|\bresponsive\b|\baccessibility\b",
    "API Design": r"\bAPI\b|\bREST\b|\bGraphQL\b|\bendpoint\b",
}

SKILL_PATTERN = re.compile(r"\$([a-z0-9][a-z0-9-]{1,80})")
FILE_PATTERN = re.compile(r"(?<![A-Za-z0-9_/-])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,8}")

LANGUAGE_EXTENSIONS = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".py": "Python",
    ".ipynb": "Python",
    ".sql": "SQL",
    ".css": "CSS",
    ".scss": "CSS",
    ".html": "HTML",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
}

LANGUAGE_TECHNIQUES = {"TypeScript", "JavaScript", "Python"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Codex history for CV/profile generation.")
    parser.add_argument("--span", choices=["last-week", "all"], default="last-week")
    parser.add_argument("--since", help="Inclusive start date/time, e.g. 2026-06-20 or 2026-06-20T00:00:00")
    parser.add_argument("--until", help="Exclusive end date/time, e.g. 2026-06-27 or 2026-06-27T00:00:00")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    parser.add_argument("--output-dir", default=str(Path.home() / ".cv2ai-reports"))
    parser.add_argument("--max-snippet-chars", type=int, default=360)
    return parser.parse_args()


def local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def parse_datetime(value: str, end_of_day: bool = False) -> dt.datetime:
    if "T" not in value and len(value) == 10:
        parsed = dt.datetime.fromisoformat(value)
        if end_of_day:
            parsed += dt.timedelta(days=1)
    else:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_now().tzinfo)
    return parsed.astimezone()


def resolve_window(args: argparse.Namespace) -> tuple[dt.datetime | None, dt.datetime | None, str]:
    if args.since or args.until:
        since = parse_datetime(args.since, end_of_day=False) if args.since else None
        until = parse_datetime(args.until, end_of_day=True) if args.until else None
        label = f"{since.date() if since else 'begin'}_to_{until.date() if until else 'now'}"
        return since, until, label
    if args.span == "all":
        return None, None, "all-history"
    until = local_now()
    since = until - dt.timedelta(days=7)
    return since, until, f"{since.date()}_to_{until.date()}"


def parse_json_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone()


def redact(text: str) -> str:
    redacted = text
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    redacted = re.sub(r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=\n\r]+", "[IMAGE_DATA]", redacted)
    return redacted


def clean_snippet(text: str, max_chars: int) -> str:
    text = redact(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "..."
    return text


def is_context_noise(text: str) -> bool:
    markers = (
        "# AGENTS.md instructions",
        "<environment_context>",
        "<INSTRUCTIONS>",
        "You are Codex, a coding agent",
        "Desired oververbosity",
        "Knowledge cutoff:",
    )
    return any(marker in text for marker in markers)


def is_low_value_request(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"continue", "go on", "keep going", "resume", "ok", "yes"} or len(lowered) < 12


def iter_session_files(codex_home: Path) -> list[Path]:
    roots = [codex_home / "sessions", codex_home / "archived_sessions"]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(root.rglob("*.jsonl"))
    return sorted(files)


def extract_text(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        if "data:image/" not in value:
            texts.append(value)
    elif isinstance(value, list):
        for item in value:
            texts.extend(extract_text(item))
    elif isinstance(value, dict):
        item_type = value.get("type")
        if item_type in {"input_image", "image_url"}:
            return texts
        for key in ("text", "content", "message"):
            if key in value:
                texts.extend(extract_text(value[key]))
    return texts


def extract_commands(value: Any) -> list[str]:
    commands: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"cmd", "command"} and isinstance(item, str):
                commands.append(clean_snippet(item, 220))
            else:
                commands.extend(extract_commands(item))
    elif isinstance(value, list):
        for item in value:
            commands.extend(extract_commands(item))
    return commands


def empty_usage() -> dict[str, Any]:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "token_count_events": 0,
        "reported_credits_consumed": 0.0,
        "reported_credit_events": 0,
    }


def numeric_credit(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("consumed", "used", "usage", "credits_consumed", "total"):
            if key in value:
                found = numeric_credit(value[key])
                if found is not None:
                    return found
    return None


def add_token_usage(session_usage: dict[str, Any], payload: dict[str, Any]) -> None:
    if payload.get("type") != "token_count":
        return
    info = payload.get("info") or {}
    usage = info.get("last_token_usage") or info.get("total_token_usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            session_usage[key] += value
    session_usage["token_count_events"] += 1

    rate_limits = payload.get("rate_limits") or {}
    credit_value = numeric_credit(payload.get("credits"))
    if credit_value is None and isinstance(rate_limits, dict):
        credit_value = numeric_credit(rate_limits.get("credits"))
    if credit_value is not None:
        session_usage["reported_credits_consumed"] += credit_value
        session_usage["reported_credit_events"] += 1


def in_window(timestamp: dt.datetime | None, since: dt.datetime | None, until: dt.datetime | None) -> bool:
    if timestamp is None:
        return since is None and until is None
    if since and timestamp < since:
        return False
    if until and timestamp >= until:
        return False
    return True


def estimate_active_minutes(timestamps: list[dt.datetime]) -> float:
    if not timestamps:
        return 0.0
    ordered = sorted(set(timestamps))
    if len(ordered) == 1:
        return 5.0
    minutes = 0.0
    for earlier, later in zip(ordered, ordered[1:]):
        gap = (later - earlier).total_seconds() / 60
        if gap <= 0:
            continue
        minutes += min(gap, 30)
    return max(5.0, round(minutes, 1))


def detect_languages(files: list[str], techniques: list[str], manifests: dict[str, list[str]] | None = None) -> list[str]:
    languages: set[str] = set()
    for file_name in files:
        suffix = Path(file_name).suffix.lower()
        if suffix in LANGUAGE_EXTENSIONS:
            languages.add(LANGUAGE_EXTENSIONS[suffix])
    for technique in techniques:
        if technique in LANGUAGE_TECHNIQUES:
            languages.add(technique)

    manifests = manifests or {}
    if any(name in manifests for name in ("pyproject.toml", "requirements.txt")) or any(name.startswith("requirements") for name in manifests):
        languages.add("Python")
    if "package.json" in manifests:
        package_names = set(manifests["package.json"])
        if "typescript" in package_names or any(file_name.endswith((".ts", ".tsx")) for file_name in files):
            languages.add("TypeScript")
        else:
            languages.add("JavaScript")
    if "go.mod" in manifests:
        languages.add("Go")
    if "Cargo.toml" in manifests:
        languages.add("Rust")
    return sorted(languages)


def share_rows(counter: collections.Counter[str], total: float | None = None, limit: int = 16) -> list[dict[str, Any]]:
    if total is None:
        total = sum(counter.values())
    rows = []
    for name, value in counter.most_common(limit):
        percent = round((value / total * 100), 1) if total else 0.0
        rows.append({"name": name, "value": round(value, 1), "percent": percent})
    return rows


def load_session(path: Path, since: dt.datetime | None, until: dt.datetime | None, max_chars: int) -> dict[str, Any] | None:
    session: dict[str, Any] = {
        "path": str(path),
        "session_id": None,
        "started_at": None,
        "last_at": None,
        "cwd": None,
        "workspace_roots": [],
        "user_requests": [],
        "assistant_notes": [],
        "commands": [],
        "files": [],
        "languages": [],
        "skills": [],
        "techniques": [],
        "usage": empty_usage(),
        "active_minutes": 0.0,
        "event_count": 0,
    }
    all_text: list[str] = []
    window_timestamps: list[dt.datetime] = []
    session_has_window_event = False

    try:
        handle = path.open("r", encoding="utf-8")
    except OSError:
        return None

    with handle:
        for raw in handle:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            timestamp = parse_json_time(event.get("timestamp"))
            if timestamp:
                session["started_at"] = min(filter(None, [session["started_at"], timestamp.isoformat()]), default=timestamp.isoformat())
                session["last_at"] = timestamp.isoformat()
            payload = event.get("payload", {})

            # Preserve repo/session metadata even when the event itself falls outside
            # the requested reporting window.
            if event.get("type") == "session_meta":
                meta = payload
                session["session_id"] = meta.get("id") or session["session_id"]
                session["cwd"] = meta.get("cwd") or session["cwd"]
            if event.get("type") == "turn_context":
                session["cwd"] = payload.get("cwd") or session["cwd"]
                roots = payload.get("workspace_roots")
                if isinstance(roots, list):
                    session["workspace_roots"].extend(str(root) for root in roots)

            if not in_window(timestamp, since, until):
                continue
            session_has_window_event = True
            session["event_count"] += 1
            if timestamp:
                window_timestamps.append(timestamp)
            add_token_usage(session["usage"], payload)

            commands = extract_commands(payload)
            session["commands"].extend(commands[:10])

            role = payload.get("role")
            if isinstance(payload, dict) and isinstance(payload.get("type"), str) and payload.get("type") == "message":
                role = payload.get("role", role)
            texts = extract_text(payload)
            if not texts:
                continue
            combined = clean_snippet(" ".join(texts), max_chars)
            if is_context_noise(combined):
                continue
            all_text.append(combined)
            if role == "user" or event.get("type") == "event_msg":
                if combined and not is_low_value_request(combined) and len(session["user_requests"]) < 12:
                    session["user_requests"].append(combined)
            elif role == "assistant" or event.get("type") == "response_item":
                if combined and len(session["assistant_notes"]) < 8:
                    session["assistant_notes"].append(combined)

    if not session_has_window_event:
        return None

    text_blob = "\n".join(all_text + session["commands"])
    session["skills"] = sorted(set(SKILL_PATTERN.findall(text_blob)))
    session["files"] = sorted(set(FILE_PATTERN.findall(text_blob)))[:40]
    techniques = []
    for name, pattern in TECH_PATTERNS.items():
        if re.search(pattern, text_blob, re.I):
            techniques.append(name)
    session["techniques"] = sorted(set(techniques))
    session["languages"] = detect_languages(session["files"], session["techniques"])
    session["active_minutes"] = estimate_active_minutes(window_timestamps)
    if window_timestamps:
        session["window_first_at"] = min(window_timestamps).isoformat()
        session["window_last_at"] = max(window_timestamps).isoformat()
    session["workspace_roots"] = sorted(set(session["workspace_roots"]))
    session["commands"] = sorted(set(session["commands"]))[:30]
    return session


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_pyproject(path: Path) -> list[str]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8")) if tomllib else {}
    except Exception:
        return []
    names: list[str] = []
    project = data.get("project", {})
    for dep in project.get("dependencies", []) or []:
        if isinstance(dep, str):
            names.append(re.split(r"[<>=!~;\[]", dep, 1)[0].strip())
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for deps in optional.values():
            for dep in deps or []:
                if isinstance(dep, str):
                    names.append(re.split(r"[<>=!~;\[]", dep, 1)[0].strip())
    tool = data.get("tool", {})
    poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
    for group in ("dependencies", "dev-dependencies"):
        deps = poetry.get(group, {})
        if isinstance(deps, dict):
            names.extend(deps.keys())
    return sorted(set(filter(None, names)))


def parse_repo_manifests(repo: Path) -> dict[str, list[str]]:
    manifests: dict[str, list[str]] = {}
    if not repo.exists() or not repo.is_dir():
        return manifests

    package_json = repo / "package.json"
    if package_json.exists():
        data = read_json(package_json)
        packages: list[str] = []
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            deps = data.get(key, {})
            if isinstance(deps, dict):
                packages.extend(deps.keys())
        manifests["package.json"] = sorted(set(packages))

    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        manifests["pyproject.toml"] = parse_pyproject(pyproject)

    for req in sorted(repo.glob("requirements*.txt"))[:4]:
        packages = []
        try:
            for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    packages.append(re.split(r"[<>=!~;\[]", line, 1)[0].strip())
        except OSError:
            continue
        manifests[req.name] = sorted(set(filter(None, packages)))

    go_mod = repo / "go.mod"
    if go_mod.exists():
        packages = []
        try:
            for line in go_mod.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("require "):
                    packages.append(line.split()[1])
        except OSError:
            pass
        manifests["go.mod"] = sorted(set(packages))

    cargo = repo / "Cargo.toml"
    if cargo.exists():
        packages = []
        in_deps = False
        try:
            for line in cargo.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped.startswith("["):
                    in_deps = stripped in {"[dependencies]", "[dev-dependencies]"}
                    continue
                if in_deps and "=" in stripped and not stripped.startswith("#"):
                    packages.append(stripped.split("=", 1)[0].strip())
        except OSError:
            pass
        manifests["Cargo.toml"] = sorted(set(packages))

    return {key: value for key, value in manifests.items() if value}


def repo_name(path_text: str | None) -> str:
    if not path_text:
        return "unknown"
    return Path(path_text).name or path_text


def focus_sentence(
    top_repo: str | None,
    top_language: str | None,
    top_technique: str | None,
    total_active_minutes: float,
    new_techniques: list[str],
    continued_techniques: list[str],
) -> str:
    hours = round(total_active_minutes / 60, 1)
    pieces = []
    if top_repo:
        pieces.append(f"Most visible work centered on {top_repo}")
    if top_language:
        pieces.append(f"with {top_language} as the strongest language signal")
    if top_technique:
        pieces.append(f"and {top_technique} as the leading technique")
    sentence = ", ".join(pieces) if pieces else "No clear focus emerged from the selected history window"
    if hours:
        sentence += f" across roughly {hours} active Codex hours"
    if new_techniques:
        sentence += f". New signals: {', '.join(new_techniques[:5])}"
    if continued_techniques:
        sentence += f". Continued signals: {', '.join(continued_techniques[:5])}"
    return sentence + "."


def aggregate(
    sessions: list[dict[str, Any]],
    baseline_sessions: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, list[str]]]]:
    repo_paths = sorted(set(filter(None, [session.get("cwd") for session in sessions])))
    repo_manifests = {path: parse_repo_manifests(Path(path)) for path in repo_paths}
    package_counter: collections.Counter[str] = collections.Counter()
    for manifests in repo_manifests.values():
        for packages in manifests.values():
            package_counter.update(packages)

    technique_counter: collections.Counter[str] = collections.Counter()
    technique_time_counter: collections.Counter[str] = collections.Counter()
    language_time_counter: collections.Counter[str] = collections.Counter()
    skill_counter: collections.Counter[str] = collections.Counter()
    command_counter: collections.Counter[str] = collections.Counter()
    file_counter: collections.Counter[str] = collections.Counter()
    repo_counter: collections.Counter[str] = collections.Counter()
    repo_time_counter: collections.Counter[str] = collections.Counter()
    usage = empty_usage()
    total_active_minutes = 0.0
    for session in sessions:
        repo = repo_name(session.get("cwd"))
        manifests = repo_manifests.get(session.get("cwd") or "", {})
        session["languages"] = detect_languages(session.get("files", []), session.get("techniques", []), manifests)
        minutes = float(session.get("active_minutes") or 0.0)
        total_active_minutes += minutes
        repo_counter[repo] += 1
        repo_time_counter[repo] += minutes
        technique_counter.update(session.get("techniques", []))
        techniques = session.get("techniques", [])
        if techniques and minutes:
            share = minutes / len(techniques)
            for technique in techniques:
                technique_time_counter[technique] += share
        languages = session.get("languages", [])
        if languages and minutes:
            share = minutes / len(languages)
            for language in languages:
                language_time_counter[language] += share
        skill_counter.update(session.get("skills", []))
        command_counter.update(session.get("commands", []))
        file_counter.update(session.get("files", []))
        for key, value in session.get("usage", {}).items():
            if key in usage and isinstance(value, (int, float)):
                usage[key] += value

    usage["credits_available"] = usage["reported_credit_events"] > 0
    usage["credits_display"] = (
        f"{usage['reported_credits_consumed']:.2f}".rstrip("0").rstrip(".")
        if usage["credits_available"]
        else "n/a"
    )
    usage["credits_note"] = (
        "Numeric credit usage was present in Codex token_count events."
        if usage["credits_available"]
        else "Codex history did not expose numeric credits for this window; token totals are shown as the consumption proxy."
    )

    baseline_sessions = baseline_sessions or []
    baseline_techniques = sorted({tech for session in baseline_sessions for tech in session.get("techniques", [])})
    current_techniques = {name for name, _ in technique_counter.items()}
    baseline_technique_set = set(baseline_techniques)
    new_techniques = sorted(current_techniques - baseline_technique_set)
    continued_techniques = sorted(current_techniques & baseline_technique_set)
    top_repo = repo_time_counter.most_common(1)[0][0] if repo_time_counter else None
    top_language = language_time_counter.most_common(1)[0][0] if language_time_counter else None
    top_technique = technique_time_counter.most_common(1)[0][0] if technique_time_counter else None
    summary = {
        "top_repo": top_repo,
        "top_language": top_language,
        "top_technique": top_technique,
        "active_minutes": round(total_active_minutes, 1),
        "active_hours": round(total_active_minutes / 60, 1),
        "focus_sentence": focus_sentence(top_repo, top_language, top_technique, total_active_minutes, new_techniques, continued_techniques),
        "new_techniques": new_techniques,
        "continued_techniques": continued_techniques,
        "baseline_technique_count": len(baseline_technique_set),
    }

    metrics = {
        "session_count": len(sessions),
        "repo_count": len(repo_paths),
        "summary": summary,
        "usage": usage,
        "repos": repo_counter.most_common(),
        "repo_time": share_rows(repo_time_counter, total_active_minutes),
        "language_time": share_rows(language_time_counter, sum(language_time_counter.values())),
        "technique_time": share_rows(technique_time_counter, sum(technique_time_counter.values())),
        "techniques": technique_counter.most_common(),
        "new_techniques": [(name, technique_counter[name]) for name in new_techniques],
        "continued_techniques": [(name, technique_counter[name]) for name in continued_techniques],
        "skills": skill_counter.most_common(),
        "packages": package_counter.most_common(120),
        "commands": command_counter.most_common(80),
        "files": file_counter.most_common(120),
    }
    return metrics, repo_manifests


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def markdown_share_rows(rows: list[dict[str, Any]], suffix: str = "min") -> list[str]:
    if not rows:
        return ["- No signal in this window."]
    lines = []
    for row in rows[:10]:
        value = row["value"]
        formatted = f"{value:.1f}".rstrip("0").rstrip(".")
        lines.append(f"- {row['name']}: {row['percent']}% ({formatted} {suffix})")
    return lines


def markdown_report(out_dir: Path, since: dt.datetime | None, until: dt.datetime | None, metrics: dict[str, Any], sessions: list[dict[str, Any]]) -> str:
    summary = metrics["summary"]
    lines = [
        "# CV2AI Profile Report",
        "",
        f"Generated: {local_now().isoformat(timespec='seconds')}",
        f"Window: {since.isoformat(timespec='seconds') if since else 'begin'} to {until.isoformat(timespec='seconds') if until else 'now'}",
        f"Evidence folder: `{out_dir}`",
        "",
        "## Focus Summary",
        "",
        summary["focus_sentence"],
        "",
        f"- Rough active Codex time: {summary['active_hours']} hours",
        f"- Most touched repo: {summary['top_repo'] or 'n/a'}",
        f"- Strongest language signal: {summary['top_language'] or 'n/a'}",
        f"- Leading technique signal: {summary['top_technique'] or 'n/a'}",
        "",
        "## Coverage",
        "",
        f"- Sessions reviewed: {metrics['session_count']}",
        f"- Repos touched: {metrics['repo_count']}",
    ]
    for name, count in metrics["repos"][:12]:
        lines.append(f"- {name}: {count} session(s)")

    usage = metrics["usage"]
    lines.extend(["", "## Consumption", ""])
    lines.append(f"- Credits consumed: {usage['credits_display']}")
    lines.append(f"- Total tokens: {usage['total_tokens']:,}")
    lines.append(f"- Input tokens: {usage['input_tokens']:,}")
    lines.append(f"- Output tokens: {usage['output_tokens']:,}")
    lines.append(f"- Reasoning output tokens: {usage['reasoning_output_tokens']:,}")
    lines.append(f"- Note: {usage['credits_note']}")

    lines.extend(["", "## Rough Time Allocation By Repo", ""])
    lines.extend(markdown_share_rows(metrics["repo_time"]))

    lines.extend(["", "## Rough Time Allocation By Language", ""])
    lines.extend(markdown_share_rows(metrics["language_time"]))

    lines.extend(["", "## Rough Time Allocation By Technique", ""])
    lines.extend(markdown_share_rows(metrics["technique_time"]))

    lines.extend(["", "## New Technique Signals", ""])
    if metrics["new_techniques"]:
        for name, count in metrics["new_techniques"][:12]:
            lines.append(f"- {name}: {count} current-session signal(s)")
    else:
        lines.append("- No technique signals appear new relative to earlier Codex history.")

    lines.extend(["", "## Continued Technique Signals", ""])
    if metrics["continued_techniques"]:
        for name, count in metrics["continued_techniques"][:12]:
            lines.append(f"- {name}: {count} current-session signal(s)")
    else:
        lines.append("- No continued technique signals found.")

    lines.extend(["", "## Technique Signals", ""])
    for name, count in metrics["techniques"][:30]:
        lines.append(f"- {name}: {count}")
    if not metrics["techniques"]:
        lines.append("- No strong technique signals found in this window.")

    lines.extend(["", "## Package And Tool Signals", ""])
    for name, count in metrics["packages"][:40]:
        lines.append(f"- {name}: {count}")
    if not metrics["packages"]:
        lines.append("- No package manifests found for referenced repos.")

    lines.extend(["", "## Candidate Resume Bullets", ""])
    for repo, _ in metrics["repos"][:8]:
        related = [s for s in sessions if repo_name(s.get("cwd")) == repo]
        techniques = sorted({tech for session in related for tech in session.get("techniques", [])})
        requests = [req for session in related for req in session.get("user_requests", [])]
        technique_text = ", ".join(techniques[:6]) if techniques else "repo-specific tools"
        request_text = requests[0] if requests else "Codex-assisted engineering work"
        lines.append(f"- Advanced `{repo}` by working on {clean_snippet(request_text, 180)}; evidence indicates use of {technique_text}.")

    lines.extend(["", "## Evidence Notes", ""])
    lines.append("- `evidence.json` contains bounded snippets and local source paths for review.")
    lines.append("- Treat one-off mentions as learning signals unless repeated or backed by repo manifests.")
    return "\n".join(lines) + "\n"


def html_report(since: dt.datetime | None, until: dt.datetime | None, metrics: dict[str, Any]) -> str:
    def bars(rows: list[dict[str, Any]], limit: int = 10) -> str:
        if not rows:
            return '<div class="empty">No signal in this window</div>'
        parts = []
        for row in rows[:limit]:
            name = html.escape(str(row["name"]))
            percent = float(row["percent"])
            value = f"{float(row['value']):.1f}".rstrip("0").rstrip(".")
            parts.append(
                f'<div class="bar-row">'
                f'<div class="bar-label"><span>{name}</span><strong>{percent}%</strong></div>'
                f'<div class="track"><span style="width:{min(percent, 100)}%"></span></div>'
                f'<small>{value} rough active minutes</small>'
                f'</div>'
            )
        return "\n".join(parts)

    def count_bars(values: list[tuple[str, int]], limit: int = 10) -> str:
        if not values:
            return '<div class="empty">No signal in this window</div>'
        max_value = max(count for _, count in values[:limit]) or 1
        parts = []
        for name, count in values[:limit]:
            percent = round(count / max_value * 100, 1)
            parts.append(
                f'<div class="bar-row">'
                f'<div class="bar-label"><span>{html.escape(str(name))}</span><strong>{count}</strong></div>'
                f'<div class="track"><span style="width:{min(percent, 100)}%"></span></div>'
                f'<small>{count} manifest signal(s)</small>'
                f'</div>'
            )
        return "\n".join(parts)

    def pills(values: list[str], empty: str) -> str:
        if not values:
            return f'<div class="empty">{html.escape(empty)}</div>'
        return '<div class="pills">' + "".join(f"<span>{html.escape(value)}</span>" for value in values[:14]) + "</div>"

    title = "CV2AI Profile Metrics"
    window = f"{since.date() if since else 'begin'} to {until.date() if until else 'now'}"
    usage = metrics["usage"]
    summary = metrics["summary"]
    credit_note = html.escape(usage["credits_note"])
    focus = html.escape(summary["focus_sentence"])
    new_techniques = summary["new_techniques"]
    continued_techniques = summary["continued_techniques"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17211b; --muted:#5b6860; --line:#d8ded8; --bg:#f6f7f2; --panel:#ffffff; --accent:#0f766e; --accent2:#8b5cf6; --accent3:#b45309; --soft:#eef5f2; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 36px 0 48px; }}
    header {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: end; border-bottom: 1px solid var(--line); padding-bottom: 24px; }}
    h1 {{ margin: 0; font-size: clamp(2.2rem, 7vw, 5rem); line-height: .94; letter-spacing: 0; max-width: 780px; }}
    h2 {{ margin: 0 0 16px; font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
    h3 {{ margin: 0 0 8px; font-size: 1.1rem; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    .window {{ justify-self: end; color: var(--muted); text-align: right; white-space: nowrap; }}
    .summary {{ display: grid; grid-template-columns: 1.3fr .7fr; gap: 16px; margin: 24px 0; }}
    .focus-card, section, .metric {{ background: var(--panel); border: 1px solid var(--line); }}
    .focus-card {{ padding: 24px; }}
    .focus-card p {{ font-size: 1.12rem; color: var(--ink); }}
    .stack {{ display: grid; gap: 1px; background: var(--line); border: 1px solid var(--line); }}
    .mini {{ background: var(--panel); padding: 16px; }}
    .mini span, .metric span {{ display:block; color: var(--muted); font-size: .82rem; }}
    .mini strong {{ display:block; margin-top: 4px; font-size: 1.35rem; overflow-wrap: anywhere; }}
    .metrics {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px; background: var(--line); margin: 24px 0; border: 1px solid var(--line); }}
    .metric {{ border: 0; padding: 18px; min-width: 0; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 1.75rem; color: var(--accent); overflow-wrap: anywhere; }}
    .metric small {{ display: block; margin-top: 8px; color: var(--muted); line-height: 1.35; }}
    .dashboard {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    section {{ padding: 20px; min-width: 0; }}
    .wide {{ grid-column: 1 / -1; }}
    .bar-row {{ display: grid; gap: 6px; padding: 12px 0; border-bottom: 1px solid var(--line); }}
    .bar-row:first-of-type {{ padding-top: 0; }}
    .bar-row:last-child {{ border-bottom: 0; padding-bottom: 0; }}
    .bar-label {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; }}
    .bar-label span {{ overflow-wrap: anywhere; }}
    .bar-label strong {{ color: var(--ink); }}
    .track {{ height: 10px; background: #e8ece8; border-radius: 999px; overflow: hidden; }}
    .track span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: inherit; }}
    .bar-row small {{ color: var(--muted); }}
    .pills {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .pills span {{ border: 1px solid var(--line); background: var(--soft); padding: 7px 10px; border-radius: 999px; font-size: .9rem; }}
    .empty {{ color: var(--muted); padding: 10px 0; }}
    ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }}
    li {{ display: flex; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }}
    li span {{ overflow-wrap: anywhere; }}
    @media (max-width: 860px) {{ header, .summary, .dashboard, .metrics {{ grid-template-columns: 1fr; }} .window {{ justify-self: start; text-align: left; }} main {{ width: min(100% - 20px, 1180px); padding-top: 24px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{title}</h1>
      <p class="window">{html.escape(window)}</p>
    </header>
    <div class="summary">
      <div class="focus-card">
        <h2>Last Week Focus</h2>
        <p>{focus}</p>
      </div>
      <div class="stack">
        <div class="mini"><span>Most Touched Repo</span><strong>{html.escape(str(summary["top_repo"] or "n/a"))}</strong></div>
        <div class="mini"><span>Strongest Language</span><strong>{html.escape(str(summary["top_language"] or "n/a"))}</strong></div>
        <div class="mini"><span>Leading Technique</span><strong>{html.escape(str(summary["top_technique"] or "n/a"))}</strong></div>
      </div>
    </div>
    <div class="metrics">
      <div class="metric"><span>Sessions</span><strong>{metrics["session_count"]}</strong></div>
      <div class="metric"><span>Repos</span><strong>{metrics["repo_count"]}</strong></div>
      <div class="metric"><span>Rough Active Hours</span><strong>{summary["active_hours"]}</strong></div>
      <div class="metric"><span>Packages</span><strong>{len(metrics["packages"])}</strong></div>
      <div class="metric"><span>Credits Consumed</span><strong>{html.escape(str(usage["credits_display"]))}</strong><small>{credit_note}</small></div>
    </div>
    <div class="dashboard">
      <section><h2>Repo Time Split</h2>{bars(metrics["repo_time"])}</section>
      <section><h2>Language Time Split</h2>{bars(metrics["language_time"])}</section>
      <section class="wide"><h2>Technique Time Split</h2>{bars(metrics["technique_time"], 14)}</section>
      <section><h2>New Technique Signals</h2>{pills(new_techniques, "No technique signals appear new relative to earlier Codex history.")}</section>
      <section><h2>Kept Using</h2>{pills(continued_techniques, "No continued technique signals found.")}</section>
      <section><h2>Token Usage</h2><ul>
        <li><span>Total tokens</span><strong>{usage["total_tokens"]:,}</strong></li>
        <li><span>Input tokens</span><strong>{usage["input_tokens"]:,}</strong></li>
        <li><span>Cached input tokens</span><strong>{usage["cached_input_tokens"]:,}</strong></li>
        <li><span>Output tokens</span><strong>{usage["output_tokens"]:,}</strong></li>
        <li><span>Reasoning output tokens</span><strong>{usage["reasoning_output_tokens"]:,}</strong></li>
        <li><span>Token count events</span><strong>{usage["token_count_events"]:,}</strong></li>
      </ul></section>
      <section><h2>Package Signals</h2>{count_bars(metrics["packages"], 12)}</section>
    </div>
  </main>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    since, until, label = resolve_window(args)
    codex_home = Path(args.codex_home).expanduser()
    base_output = Path(args.output_dir).expanduser()
    out_dir = base_output / f"cv2ai-{label}-{local_now().strftime('%Y%m%d-%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    session_files = iter_session_files(codex_home)
    sessions = []
    for path in session_files:
        session = load_session(path, since, until, args.max_snippet_chars)
        if session:
            sessions.append(session)

    baseline_sessions = []
    if since:
        for path in session_files:
            session = load_session(path, None, since, args.max_snippet_chars)
            if session:
                baseline_sessions.append(session)

    metrics, repo_manifests = aggregate(sessions, baseline_sessions)
    evidence = {
        "generated_at": local_now().isoformat(timespec="seconds"),
        "codex_home": str(codex_home),
        "window": {
            "since": since.isoformat(timespec="seconds") if since else None,
            "until": until.isoformat(timespec="seconds") if until else None,
        },
        "sessions": sessions,
        "baseline_session_count": len(baseline_sessions),
        "repo_manifests": repo_manifests,
    }

    write_json(out_dir / "evidence.json", evidence)
    write_json(out_dir / "metrics.json", metrics)
    profile_path = out_dir / "profile.md"
    dashboard_path = out_dir / "webpage.html"
    profile_path.write_text(markdown_report(out_dir, since, until, metrics, sessions), encoding="utf-8")
    dashboard_path.write_text(html_report(since, until, metrics), encoding="utf-8")

    print(f"CV2AI report written to: {out_dir}")
    print(f"Dashboard: {dashboard_path}")
    print(f"Profile: {profile_path}")
    print(f"Dashboard link: [webpage.html]({dashboard_path})")
    print(f"Focus summary: {metrics['summary']['focus_sentence']}")
    print(f"Sessions: {metrics['session_count']} | Repos: {metrics['repo_count']} | Packages: {len(metrics['packages'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
