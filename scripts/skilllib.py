#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.+)\Z", re.DOTALL)
SUPPORT_REF_RE = re.compile(r"(?<![A-Za-z0-9_.-])((?:references|templates|scripts|assets)/[A-Za-z0-9_./-]+)")


@dataclass(frozen=True)
class Skill:
    directory: Path
    path: Path
    frontmatter_text: str
    body: str
    metadata: dict[str, object]


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    inner = value[1:-1].strip()
    return [] if not inner else [_scalar(item) for item in inner.split(",")]


def _value(value: str) -> object:
    return _inline_list(value) if value.strip().startswith("[") else _scalar(value)


def _mapping(frontmatter: str, path: Path) -> dict[str, object]:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-2, root)]
    for number, line in enumerate(frontmatter.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            raise ValueError(f"{path}:{number}: tabs are not allowed in frontmatter")
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2:
            raise ValueError(f"{path}:{number}: frontmatter indentation must use 2 spaces")
        match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)", line)
        if not match:
            raise ValueError(f"{path}:{number}: unsupported frontmatter syntax")
        while stack[-1][0] >= indent:
            stack.pop()
        parent_indent, parent = stack[-1]
        if indent != parent_indent + 2:
            raise ValueError(f"{path}:{number}: invalid frontmatter nesting")
        key, raw_value = match.groups()
        if key in parent:
            raise ValueError(f"{path}:{number}: duplicate frontmatter key {key}")
        if raw_value:
            parent[key] = _value(raw_value)
        else:
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def parse_frontmatter(text: str, path: Path) -> tuple[str, str, dict[str, object]]:
    if text.startswith("\ufeff") or text.startswith("\n"):
        raise ValueError(f"{path}: frontmatter must start at byte 0")
    match = FRONTMATTER_RE.match(text.replace("\r\n", "\n"))
    if not match:
        raise ValueError(f"{path}: expected --- frontmatter, closing ---, and non-empty body")
    frontmatter, body = match.groups()
    return frontmatter, body, _mapping(frontmatter, path)


def load_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, metadata = parse_frontmatter(text, path)
    return Skill(path.parent, path, frontmatter, body, metadata)


def load_config(root: Path) -> dict[str, object]:
    return json.loads((root / "skill-repo.json").read_text(encoding="utf-8"))


def skill_paths(root: Path) -> list[Path]:
    skills_root = root / "skills"
    return sorted(path / "SKILL.md" for path in skills_root.iterdir() if path.is_dir())


def activation_path(root: Path, name: str) -> Path:
    return root / "tests" / "activation" / f"{name}.json"


def support_references(skill: Skill) -> list[str]:
    return sorted(set(SUPPORT_REF_RE.findall(skill.body)))
