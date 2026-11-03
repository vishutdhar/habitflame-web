"""The nested HTML rule reads only what would be deployed.

A file git ignores never reaches Vercel, which deploys from git, so an HTML
file inside an ignored local folder (a tool's scratch) must not fail the
gate. In a repository copy without .git nothing is ignored, so there a file
inside a dot folder is skipped and a nested html elsewhere still fails.

  python3 -m unittest discover -s scripts/tests
"""
import subprocess
import unittest

from gate_copy import GateCopy


class DeployableScan(GateCopy, unittest.TestCase):
    def test_a_nested_html_in_a_dot_folder_does_not_fail_the_gate(self):
        scratch = self.site / ".scratch" / "references"
        scratch.mkdir(parents=True)
        (scratch / "template.html").write_text("<p>scratch</p>\n", encoding="utf-8")
        gate = self.run_script("verify-pages.py")
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertNotIn("below the root would be served", gate.stdout)

    def test_a_nested_html_outside_a_dot_folder_still_fails(self):
        nested = self.site / "extra"
        nested.mkdir()
        (nested / "page.html").write_text("<p>nested</p>\n", encoding="utf-8")
        gate = self.run_script("verify-pages.py")
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn("extra/page.html: an HTML file below the root would be served", gate.stdout)

    def test_a_git_ignored_html_does_not_fail_the_gate(self):
        subprocess.run(["git", "init", "-q", str(self.site)], check=True)
        (self.site / ".gitignore").write_text("/tool-scratch/\n", encoding="utf-8")
        scratch = self.site / "tool-scratch"
        scratch.mkdir()
        (scratch / "page.html").write_text("<p>ignored</p>\n", encoding="utf-8")
        gate = self.run_script("verify-pages.py")
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)


class CopyBelowAnotherRepository(GateCopy, unittest.TestCase):
    def test_a_copy_inside_an_ignored_folder_of_a_parent_repository_still_scans(self):
        parent = self.site.parent
        subprocess.run(["git", "init", "-q", str(parent)], check=True)
        (parent / ".gitignore").write_text("/site/\n", encoding="utf-8")
        nested = self.site / "extra"
        nested.mkdir()
        (nested / "page.html").write_text("<p>nested</p>\n", encoding="utf-8")
        gate = self.run_script("verify-pages.py")
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn("extra/page.html: an HTML file below the root would be served", gate.stdout)
