from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from skilllib import parse_frontmatter  # pyright: ignore[reportMissingImports]
from validate_skills import SECRET_PATTERNS  # pyright: ignore[reportMissingImports]


class FrontmatterParserTest(unittest.TestCase):
    def parse(self, frontmatter: str) -> dict[str, object]:
        text = f"---\n{frontmatter}\n---\n# Body\n"
        return parse_frontmatter(text, Path("SKILL.md"))[2]

    def test_parses_tags_only_under_metadata_org(self) -> None:
        metadata = self.parse(
            "name: singlestore-test\n"
            "description: Use when testing a workflow.\n"
            "metadata:\n"
            "  org:\n"
            "    tags: [product, test]\n"
            "  hermes:\n"
            "    tags: [runtime, specific]"
        )

        nested = cast(dict[str, object], metadata["metadata"])
        org = cast(dict[str, object], nested["org"])
        self.assertEqual(org["tags"], ["product", "test"])

    def test_rejects_duplicate_top_level_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate frontmatter key metadata"):
            self.parse(
                "name: singlestore-test\n"
                "metadata:\n"
                "  org:\n"
                "    tags: [product, test]\n"
                "metadata:\n"
                "  hermes:\n"
                "    tags: [runtime, specific]"
            )

    def test_rejects_invalid_indentation(self) -> None:
        with self.assertRaisesRegex(ValueError, "indentation must use 2 spaces"):
            self.parse(
                "name: singlestore-test\n"
                "metadata:\n"
                " org:\n"
                "   tags: [product, test]"
            )


class SecretPatternTest(unittest.TestCase):
    def test_detects_standard_bearer_authorization_header(self) -> None:
        bearer_pattern = dict(SECRET_PATTERNS)["generic bearer token"]
        self.assertIsNotNone(
            bearer_pattern.search("Authorization: Bearer syntheticTokenValue123456")
        )

    def test_does_not_flag_placeholder_bearer_header(self) -> None:
        bearer_pattern = dict(SECRET_PATTERNS)["generic bearer token"]
        self.assertIsNone(bearer_pattern.search("Authorization: Bearer <TOKEN>"))


if __name__ == "__main__":
    unittest.main()
