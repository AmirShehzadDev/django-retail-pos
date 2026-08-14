import os
import re
from pathlib import Path
from urllib.parse import unquote

from django.test import SimpleTestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "data:")
EXCLUDED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "releases",
    "var",
}


class DocumentationLayoutTests(SimpleTestCase):
    def test_project_documents_are_not_stored_in_repository_root(self):
        forbidden_patterns = (
            "FEATURE_SPEC_M*.md",
            "TECHNICAL_DESIGN_M*.md",
            "DEVELOPMENT_TASKS_M*.md",
            "M*_COMPLETION.md",
        )

        misplaced = sorted(
            path.name
            for pattern in forbidden_patterns
            for path in REPOSITORY_ROOT.glob(pattern)
        )

        self.assertEqual(misplaced, [])
        self.assertTrue((REPOSITORY_ROOT / "docs/product/mvp-requirements.md").is_file())
        self.assertTrue((REPOSITORY_ROOT / "docs/product/roadmap.md").is_file())
        self.assertTrue((REPOSITORY_ROOT / "docs/architecture/technical-design.md").is_file())

    def test_local_markdown_links_resolve(self):
        broken_links = []

        documents = []
        for directory, subdirectories, filenames in os.walk(REPOSITORY_ROOT):
            subdirectories[:] = [
                name for name in subdirectories if name not in EXCLUDED_DIRECTORIES
            ]
            documents.extend(
                Path(directory) / filename for filename in filenames if filename.endswith(".md")
            )

        for document in documents:
            content = document.read_text(encoding="utf-8")
            for match in MARKDOWN_LINK.finditer(content):
                target = match.group(1).strip()
                if not target or target.startswith("#") or target.startswith(EXTERNAL_PREFIXES):
                    continue

                path_text = target.split("#", maxsplit=1)[0]
                if path_text.startswith("<") and path_text.endswith(">"):
                    path_text = path_text[1:-1]
                path_text = unquote(path_text)

                resolved = (document.parent / path_text).resolve()
                if not resolved.exists():
                    line = content.count("\n", 0, match.start()) + 1
                    relative_document = document.relative_to(REPOSITORY_ROOT)
                    broken_links.append(f"{relative_document}:{line} -> {target}")

        self.assertEqual(
            broken_links,
            [],
            "Broken documentation links:\n" + "\n".join(broken_links),
        )
