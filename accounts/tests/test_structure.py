"""
Structural guards for the views packages.

``accounts/views.py`` and ``proposals/views.py`` were each split into a package
of themed modules, with ``__init__.py`` re-exporting every public name so
``urls.py`` keeps working. These tests make sure that contract holds — if
someone adds a view to a submodule and forgets the re-export, or reintroduces a
duplicate definition, the suite fails rather than a URL 500-ing in production.
"""

import ast
import pathlib
from collections import Counter

from django.test import SimpleTestCase
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

VIEW_PACKAGES = [
    REPO_ROOT / "accounts" / "views",
    REPO_ROOT / "proposals" / "views",
]


def _submodules(package_dir):
    return sorted(
        p for p in package_dir.glob("*.py") if p.name != "__init__.py"
    )


def _top_level_defs(path):
    tree = ast.parse(path.read_text())
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]


class URLResolutionTests(SimpleTestCase):
    """Every routed URL must point at a real, importable callable."""

    def _all_patterns(self):
        found = []

        def walk(resolver):
            for pattern in resolver.url_patterns:
                if isinstance(pattern, URLResolver):
                    walk(pattern)
                elif isinstance(pattern, URLPattern):
                    found.append(pattern)

        walk(get_resolver())
        return found

    def test_every_url_pattern_has_a_callback(self):
        patterns = self._all_patterns()
        self.assertGreater(len(patterns), 200, "URLconf looks unexpectedly small")

        for pattern in patterns:
            with self.subTest(url=pattern.name or str(pattern.pattern)):
                self.assertIsNotNone(pattern.callback)
                self.assertTrue(callable(pattern.callback))


class ViewPackageTests(SimpleTestCase):
    def test_no_duplicate_definitions_within_a_package(self):
        """A shadowed duplicate silently disables the earlier definition.

        ``proposal_moa_draft`` was defined twice in the old
        ``proposals/views.py``; the first 35-line version was dead code that
        nothing could reach.
        """
        for package in VIEW_PACKAGES:
            names = []
            for module in _submodules(package):
                names.extend(_top_level_defs(module))

            duplicates = sorted(n for n, count in Counter(names).items() if count > 1)
            with self.subTest(package=package.name):
                self.assertEqual(duplicates, [], f"duplicate definitions: {duplicates}")

    def test_every_public_view_is_re_exported(self):
        """``urls.py`` refers to ``views.<name>``, so the package must expose it."""
        import accounts.views
        import proposals.views

        packages = [
            (REPO_ROOT / "accounts" / "views", accounts.views),
            (REPO_ROOT / "proposals" / "views", proposals.views),
        ]

        for package_dir, module in packages:
            for submodule in _submodules(package_dir):
                for name in _top_level_defs(submodule):
                    if name.startswith("_"):
                        continue
                    with self.subTest(package=package_dir.name, name=name):
                        self.assertTrue(
                            hasattr(module, name),
                            f"{name} is defined in {submodule.name} but not re-exported",
                        )

    def test_submodules_stay_a_reasonable_size(self):
        """Guard against the packages silently growing back into monoliths."""
        limit = 1400
        for package in VIEW_PACKAGES:
            for module in _submodules(package):
                line_count = len(module.read_text().split("\n"))
                with self.subTest(module=f"{package.name}/{module.name}"):
                    self.assertLess(
                        line_count,
                        limit,
                        f"{module.name} has {line_count} lines; consider splitting it",
                    )


class RepositoryHygieneTests(SimpleTestCase):
    """Generated and uploaded artefacts must stay out of version control."""

    def _tracked(self, pattern):
        import subprocess

        result = subprocess.run(
            ["git", "ls-files", pattern],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.skipTest("git is unavailable in this environment")
        return [line for line in result.stdout.split("\n") if line.strip()]

    def test_no_uploaded_media_is_tracked(self):
        """Uploads belong in Supabase Storage, not the repository.

        47 files (~120 MB) were untracked deliberately; this stops them
        creeping back in via `git add -A`.
        """
        tracked = self._tracked("media/")
        self.assertEqual(
            tracked, [], f"{len(tracked)} media files are tracked again: {tracked[:5]}"
        )

    def test_no_sqlite_database_is_tracked(self):
        tracked = self._tracked("*.sqlite3")
        self.assertEqual(tracked, [], f"database committed: {tracked}")

    def test_document_templates_are_still_tracked(self):
        """These are source assets, not uploads — they must stay in the repo."""
        tracked = self._tracked("proposals/template_files/")
        self.assertGreater(
            len(tracked), 5, "the DOCX/XLSX templates appear to have been removed"
        )
