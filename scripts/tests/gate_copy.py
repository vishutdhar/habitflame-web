"""Run the site gate on a throwaway copy of the repository.

The gate checks a fresh render and holds every committed page byte equal to
it, so a gate rule is shown failing by breaking the copy's generator,
template, config or measure.js, rebuilding, and running the copy's gate.
The copy lives in a temporary folder removed after each test.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _ignored_by_git(root: pathlib.Path) -> set[str]:
    """The top level entries git ignores in the real repository (its own
    folder, the Vercel folder, local tools' scratch): none of them is part
    of the site, and a copy without .git would otherwise count them."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return set()
    # Top level folders only: "scripts/__pycache__/" is a cache inside a
    # folder the site needs, not an ignored top level entry.
    return {rel[:-1] for rel in out.decode().split("\0") if rel.endswith("/") and rel.count("/") == 1}


_IGNORED = _ignored_by_git(ROOT) | {".git", ".vercel", "node_modules", "__pycache__"}


def _not_site(folder: str, names: list[str]) -> set[str]:
    """What a copy leaves out: the repository's own folder, dependencies,
    Python caches, and whatever git ignores at the top level (.vercel, a
    local tool's scratch). .well-known and every dot file stay."""
    if pathlib.Path(folder) != ROOT:
        return {n for n in names if n in ("node_modules", "__pycache__")}
    return {n for n in names if n in _IGNORED}


class GateCopy:
    """A mixin for unittest.TestCase: a fresh copy of the repository per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="habitflame-web-gate-")
        self.site = pathlib.Path(self._tmp.name) / "site"
        shutil.copytree(ROOT, self.site, ignore=_not_site)

    def tearDown(self):
        self._tmp.cleanup()

    def set_token(self, pt: str) -> None:
        config = self.site / "scripts" / "pages.json"
        text = config.read_text(encoding="utf-8")
        new, n = re.subn(r'"app_store_campaign": \{"pt": "[0-9]*"\}', f'"app_store_campaign": {{"pt": "{pt}"}}', text)
        self.assertEqual(n, 1, "pages.json has no app_store_campaign entry to set")
        config.write_text(new, encoding="utf-8")

    def run_script(self, name: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.site / "scripts" / name)], capture_output=True, text=True)

    def build_and_gate(self) -> subprocess.CompletedProcess:
        built = self.run_script("build-pages.py")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return self.run_script("verify-pages.py")

    def edit(self, rel: str, old: str, new: str) -> None:
        """Replace the first occurrence of old in one file of the copy."""
        path = self.site / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assert_gate_fails_with(self, *messages: str) -> None:
        """Rebuild the copy, run its gate, and require a failure naming each message."""
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 1, gate.stdout)
        for message in messages:
            self.assertIn(message, gate.stdout)

    def assert_gate_passes(self) -> None:
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 0, gate.stdout)
