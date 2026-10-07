"""Check public-repository hygiene without reading real configuration/secrets.

AC-02/03/05 of SPEC-0033. Standard library only; safe to run before dependencies.
Docker checks validate required exclusion rules, not every Docker matcher case.
Markdown checks validate local file targets, not external URLs or heading anchors.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SECRET_EXAMPLES = {
    "SECRET_KEY", "QUERY_ENCRYPTION_KEY", "QUERY_ENCRYPTION_KEYS",
    "APP_DATABASE_URL", "DB_PASSWORD", "CENTRAL_DB_USER", "CENTRAL_DB_PASSWORD",
    "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_URL",
}
IGNORED_PATHS = (
    ".env", ".env.stage", ".env.production", "web_api/.env", "frontend/.env.local",
    "web_api/.env.production", "web_api/.venv/file", "web_api/__pycache__/file.pyc",
    "frontend/node_modules/file", "frontend/dist/file", "web_api/test.db",
    "backups/database.bak", "database.dump", "secrets/token", "private.key",
    ".aws/credentials", "frontend/coverage/file", "web_api/.pytest_cache/file",
)
TRACKABLE_PATHS = (
    ".env.example", "frontend/.env.example", "frontend/package-lock.json",
    "web_api/migrations/versions/b2c3d4e5f6a7_database_lifecycle.py",
    "web_api/tests/unit/test_encrypted_text.py", "licenses/WebQuery-legacy-MIT.txt",
    ".agents/skills/change-review/SKILL.md",
)


def example_values(source: str) -> dict[str, str]:
    values = {}
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError("Invalid example variable name/assignment")
        if name in values:
            raise ValueError(f"Duplicate example key: {name}")
        values[name] = value.strip()
    return values


def environment_names(source: str) -> set[str]:
    """Extract literal env keys, including the guard and throttle helper."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            function = ast.unparse(node.func)
            if function in {"os.getenv", "os.environ.get", "_positive_int"} and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    names.add(node.args[0].value)
        if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                names.add(node.slice.value)
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_REQUIRED" for target in node.targets
        ):
            if isinstance(node.value, (ast.Tuple, ast.List)):
                names.update(item.value for item in node.value.elts if isinstance(item, ast.Constant))
    return names


def missing_local_links(document: Path) -> list[str]:
    source = re.sub(r"```.*?```", "", document.read_text(encoding="utf-8"), flags=re.S)
    errors = []
    for match in re.finditer(r"\[[^\]]+\]\(([^\s)]+)\)", source):
        target = match.group(1).strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = ROOT / unquote(parsed.path).lstrip("/") if parsed.path.startswith("/") else document.parent / unquote(parsed.path)
        if not path.exists():
            errors.append(f"{document.relative_to(ROOT)}: missing {target}")
    return errors


def git_ignored(paths: tuple[str, ...]) -> set[str]:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=ROOT, input="\n".join(paths) + "\n", capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("git check-ignore failed")
    return set(result.stdout.splitlines())


def validate() -> tuple[list[str], int]:
    errors = []
    values = example_values((ROOT / ".env.example").read_text(encoding="utf-8"))
    names = set()
    for path in (ROOT / "web_api").rglob("*.py"):
        if any(part in {"tests", ".venv", "venv", "__pycache__"} for part in path.relative_to(ROOT / "web_api").parts):
            continue
        names.update(environment_names(path.read_text(encoding="utf-8")))
    errors.extend(f"Missing backend example variable: {name}" for name in sorted(names - values.keys()))
    errors.extend(f"Secret example must be blank: {name}" for name in sorted(SECRET_EXAMPLES) if values.get(name) != "")
    frontend = example_values((ROOT / "frontend/.env.example").read_text(encoding="utf-8"))
    if "VITE_API_TARGET" not in frontend:
        errors.append("Missing frontend proxy example")
    ignored = git_ignored(IGNORED_PATHS)
    errors.extend(f"Not ignored by Git: {path}" for path in IGNORED_PATHS if path not in ignored)
    errors.extend(f"Required file ignored by Git: {path}" for path in sorted(git_ignored(TRACKABLE_PATHS)))
    for directory in (ROOT, ROOT / "web_api", ROOT / "frontend"):
        rules = set((directory / ".dockerignore").read_text(encoding="utf-8").splitlines())
        required = {".env", ".env.*", "**/.env", "**/.env.*", "**/*.key", "**/*.bak"}
        errors.extend(f"{directory.relative_to(ROOT)}/.dockerignore missing {rule}" for rule in sorted(required - rules))
        if any(rule.startswith("!") for rule in rules):
            errors.append(f"Review Docker re-inclusion rules: {directory.relative_to(ROOT)}")
    documents = [ROOT / name for name in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "AGENTS.md", "frontend/README.md", "frontend/DESIGN.md")]
    documents.extend((ROOT / "docs").rglob("*.md"))
    for document in documents:
        errors.extend(missing_local_links(document))
    return errors, len(names)


def main() -> None:
    errors, count = validate()
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        raise SystemExit(1)
    print(f"PASS: {count} backend env keys covered; secret examples blank; Git exclusions, Docker rules and local document targets verified.")


if __name__ == "__main__":
    main()
