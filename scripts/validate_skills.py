#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from skilllib import NAME_RE, activation_path, load_config, load_skill, skill_paths, support_references

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_HEADINGS = [
    "## Overview",
    "## When to Use",
    "## Do Not Use",
    "## Prerequisites",
    "## Procedure",
    "## Failure and Rollback",
    "## Common Pitfalls",
    "## Verification Checklist",
    "## References",
]
ALLOWED_SKILL_ENTRIES = {"SKILL.md", "references", "templates", "scripts", "assets"}
SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub-style token", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "generic bearer token",
        re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{16,}(?![A-Za-z0-9._~+/=-])"),
    ),
]


def error(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_config(errors: list[str]) -> dict[str, object]:
    try:
        config = load_config(ROOT)
    except Exception as exc:
        error(errors, f"skill-repo.json: {exc}")
        return {}
    for key in ("schema_version", "domain", "name_prefix", "owners", "manifest_path"):
        if key not in config:
            error(errors, f"skill-repo.json: missing {key}")
    prefix = str(config.get("name_prefix", ""))
    if prefix and (not prefix.endswith("-") or not NAME_RE.fullmatch(prefix[:-1])):
        error(errors, "skill-repo.json: name_prefix must be lowercase kebab-case ending in '-'")
    return config


def validate_activation(errors: list[str], name: str) -> None:
    path = activation_path(ROOT, name)
    if not path.exists():
        error(errors, f"{path.relative_to(ROOT)}: missing activation fixture")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        error(errors, f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return
    if data.get("skill") != name:
        error(errors, f"{path.relative_to(ROOT)}: skill must equal {name}")
    for key in ("positive", "negative"):
        prompts = data.get(key)
        if not isinstance(prompts, list) or len(prompts) < 2 or not all(isinstance(x, str) and x.strip() for x in prompts):
            error(errors, f"{path.relative_to(ROOT)}: {key} must contain at least 2 non-empty prompts")
    positive = set(data.get("positive", [])) if isinstance(data.get("positive"), list) else set()
    negative = set(data.get("negative", [])) if isinstance(data.get("negative"), list) else set()
    if positive & negative:
        error(errors, f"{path.relative_to(ROOT)}: positive and negative prompts must not overlap")


def validate_authoring_template(errors: list[str]) -> None:
    path = ROOT / "templates" / "SKILL.md"
    try:
        skill = load_skill(path)
    except Exception as exc:
        error(errors, str(exc))
        return
    name = str(skill.metadata.get("name", ""))
    description = str(skill.metadata.get("description", ""))
    if not NAME_RE.fullmatch(name) or len(name) > 64:
        error(errors, f"{path.relative_to(ROOT)}: template name must be lowercase kebab-case and <= 64 chars")
    if not description.startswith("Use when "):
        error(errors, f"{path.relative_to(ROOT)}: template description must start with 'Use when '")
    nested_metadata = skill.metadata.get("metadata")
    org_metadata = nested_metadata.get("org") if isinstance(nested_metadata, dict) else None
    if not isinstance(org_metadata, dict):
        error(errors, f"{path.relative_to(ROOT)}: template must declare metadata.org")
    if "HERMES_SKILL_DIR" in skill.body:
        error(errors, f"{path.relative_to(ROOT)}: template must not use runtime-specific skill paths")
    for heading in REQUIRED_HEADINGS:
        if heading not in skill.body:
            error(errors, f"{path.relative_to(ROOT)}: missing heading {heading}")


def validate_skill(errors: list[str], path: Path, config: dict[str, object], names: set[str]) -> None:
    relative = path.relative_to(ROOT)
    try:
        skill = load_skill(path)
    except Exception as exc:
        error(errors, str(exc))
        return
    metadata = skill.metadata
    name = str(metadata.get("name", ""))
    description = str(metadata.get("description", ""))
    if not NAME_RE.fullmatch(name) or len(name) > 64:
        error(errors, f"{relative}: name must be lowercase kebab-case and <= 64 chars")
    if name != skill.directory.name:
        error(errors, f"{relative}: name must match directory {skill.directory.name}")
    prefix = str(config.get("name_prefix", ""))
    if prefix and not name.startswith(prefix):
        error(errors, f"{relative}: name must start with configured prefix {prefix}")
    if name in names:
        error(errors, f"{relative}: duplicate skill name {name}")
    names.add(name)
    if not description.startswith("Use when "):
        error(errors, f"{relative}: description must start with 'Use when '")
    if not description or len(description) > 1024:
        error(errors, f"{relative}: description must be 1..1024 chars")
    period = description.find(".")
    if period < 0 or period + 1 > 57:
        error(errors, f"{relative}: first trigger sentence must end within 57 chars")
    for key in ("version", "author", "license"):
        if not metadata.get(key):
            error(errors, f"{relative}: missing frontmatter field {key}")
    nested_metadata = metadata.get("metadata")
    org_metadata = nested_metadata.get("org") if isinstance(nested_metadata, dict) else None
    tags = org_metadata.get("tags") if isinstance(org_metadata, dict) else None
    if not isinstance(tags, list) or len(tags) < 2:
        error(errors, f"{relative}: metadata.org.tags must contain at least 2 inline tags")
    if not isinstance(org_metadata, dict):
        error(errors, f"{relative}: frontmatter must declare metadata.org")
    if len(path.read_text(encoding="utf-8")) > 100_000:
        error(errors, f"{relative}: SKILL.md exceeds 100,000 chars")
    positions = []
    for heading in REQUIRED_HEADINGS:
        pos = skill.body.find(heading)
        if pos < 0:
            error(errors, f"{relative}: missing heading {heading}")
        positions.append(pos)
    if all(pos >= 0 for pos in positions) and positions != sorted(positions):
        error(errors, f"{relative}: required headings are out of order")
    unexpected = sorted(item.name for item in skill.directory.iterdir() if item.name not in ALLOWED_SKILL_ENTRIES)
    if unexpected:
        error(errors, f"{skill.directory.relative_to(ROOT)}: unsupported entries {unexpected}")
    for ref in support_references(skill):
        skill_local = skill.directory / ref
        repository_shared = ROOT / ref
        if not skill_local.exists() and not repository_shared.exists():
            error(errors, f"{relative}: linked support file does not exist: {ref}")
    validate_activation(errors, name)
    for package_file in skill.directory.rglob("*"):
        if not package_file.is_file():
            continue
        text = package_file.read_text(encoding="utf-8", errors="replace")
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                package_relative = package_file.relative_to(ROOT)
                error(errors, f"{package_relative}: possible {label} detected")


def main() -> int:
    errors: list[str] = []
    config = validate_config(errors)
    validate_authoring_template(errors)
    paths = skill_paths(ROOT)
    if not paths:
        error(errors, "skills/: no direct child SKILL.md found")
    names: set[str] = set()
    for path in paths:
        validate_skill(errors, path, config, names)
    fixture_dir = ROOT / "tests" / "activation"
    known_fixtures = {activation_path(ROOT, name).resolve() for name in names}
    for fixture in fixture_dir.glob("*.json"):
        if fixture.resolve() not in known_fixtures:
            error(errors, f"{fixture.relative_to(ROOT)}: orphan activation fixture")
    if errors:
        for item in errors:
            print(f"ERROR: {item}")
        print(f"FAILED: {len(errors)} validation error(s)")
        return 1
    print(f"OK: validated {len(paths)} skill(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
