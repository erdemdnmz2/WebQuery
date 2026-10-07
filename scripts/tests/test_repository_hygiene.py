"""Regression checks for SPEC-0033 AC-02/03/05; no application runtime needed."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


CHECKER_PATH = Path(__file__).resolve().parents[1] / "check_repository.py"
SPEC = importlib.util.spec_from_file_location("repository_checker", CHECKER_PATH)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class RepositoryHygieneTests(unittest.TestCase):
    def test_examples_have_blank_secrets_and_cover_runtime(self):
        errors, count = checker.validate()
        self.assertEqual([], errors)
        self.assertGreater(count, 30)

    def test_example_parser_rejects_duplicates(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            checker.example_values("SECRET_KEY=\nSECRET_KEY=\n")

    def test_example_parser_rejects_non_assignment(self):
        with self.assertRaises(ValueError):
            checker.example_values("SECRET_KEY\n")

    def test_environment_extraction_includes_dynamic_guard_and_throttle(self):
        source = '''
_REQUIRED = ("SECRET_KEY", "APP_DATABASE_URL")
a = os.getenv("COOKIE_SECURE", "false")
b = os.environ.get("REDIS_URL")
c = os.environ["QUERY_ENCRYPTION_KEY"]
d = _positive_int("LOGIN_MAX_FAILURES", "5")
'''
        self.assertEqual(
            {"SECRET_KEY", "APP_DATABASE_URL", "COOKIE_SECURE", "REDIS_URL",
             "QUERY_ENCRYPTION_KEY", "LOGIN_MAX_FAILURES"},
            checker.environment_names(source),
        )

    def test_git_ignores_secrets_but_not_examples_and_sources(self):
        self.assertEqual(set(checker.IGNORED_PATHS), checker.git_ignored(checker.IGNORED_PATHS))
        self.assertEqual(set(), checker.git_ignored(checker.TRACKABLE_PATHS))

    def test_document_checker_reports_missing_local_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "README.md"
            # Temporary fixture data only, never project/secret files.
            with patch.object(Path, "read_text", return_value="[bad](missing.md)\n[web](https://example.com)\n`````\n[example](not-real.md)\n`````\n"):
                with patch.object(checker, "ROOT", root):
                    errors = checker.missing_local_links(document)
            self.assertEqual(["README.md: missing missing.md"], errors)

    def test_compose_shortcuts_do_not_print_resolved_secrets(self):
        makefile = (checker.ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("docker compose -f docker-compose.yml config --quiet", makefile)
        self.assertIn("$(DEV) config --quiet", makefile)


if __name__ == "__main__":
    unittest.main()
