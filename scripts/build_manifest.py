#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from skilllib import activation_path, load_config, load_skill, skill_paths

ROOT = Path(__file__).resolve().parents[1]


def build() -> dict[str, object]:
    config = load_config(ROOT)
    entries = []
    for path in skill_paths(ROOT):
        skill = load_skill(path)
        name = str(skill.metadata.get("name", ""))
        nested_metadata = skill.metadata.get("metadata")
        org_metadata = nested_metadata.get("org") if isinstance(nested_metadata, dict) else {}
        relative_path = path.relative_to(ROOT).as_posix()
        entries.append({
            "name": name,
            "description": str(skill.metadata.get("description", "")),
            "path": relative_path,
            "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "tags": org_metadata.get("tags", []) if isinstance(org_metadata, dict) else [],
            "activation_test": activation_path(ROOT, name).relative_to(ROOT).as_posix(),
            "owners": config.get("owners", []),
        })
    return {
        "schema_version": 1,
        "domain": config["domain"],
        "skills": sorted(entries, key=lambda item: item["name"]),
    }


def rendered() -> str:
    return json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the generated skill manifest")
    parser.add_argument("--check", action="store_true", help="fail if the checked-in manifest is stale")
    args = parser.parse_args()
    config = load_config(ROOT)
    output = ROOT / str(config["manifest_path"])
    expected = rendered()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != expected:
            print(f"ERROR: {output.relative_to(ROOT)} is stale; run python3 scripts/build_manifest.py")
            return 1
        print(f"OK: {output.relative_to(ROOT)} is current")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8")
    print(f"WROTE: {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
