#!/usr/bin/env python3
"""Tests for readme-section-checker-cli. Standard library unittest only.

Run from the repo root: python3 tests/test_readme_section_checker.py
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import readme_section_checker as rsc  # noqa: E402

ALLOWED_STDLIB = {
    "argparse",
    "ast",
    "contextlib",
    "fnmatch",
    "json",
    "os",
    "re",
    "subprocess",
    "sys",
    "tempfile",
    "unittest",
    "pathlib",
}

BANNED_WORDS = ["TODO", "FIXME", "XXX", "coming soon", "lorem"]


def run_cli(*args, cwd=None, input_text=None):
    """Run the CLI as a subprocess. Returns (exit_code, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "src" / "readme_section_checker.py"),
         *args],
        cwd=str(cwd or REPO_ROOT),
        input=input_text,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestNormalize(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(rsc.normalize_heading("INSTALL"), "install")

    def test_trailing_colon_and_stop(self):
        self.assertEqual(rsc.normalize_heading("Usage:"), "usage")
        self.assertEqual(rsc.normalize_heading("Examples."), "examples")

    def test_trailing_hashes(self):
        self.assertEqual(rsc.normalize_heading("Install ##"), "install")

    def test_anchor_suffix(self):
        self.assertEqual(rsc.normalize_heading("Install {#install}"),
                         "install")

    def test_emphasis_and_code(self):
        self.assertEqual(rsc.normalize_heading("**Install**"), "install")
        self.assertEqual(rsc.normalize_heading("`Usage`"), "usage")

    def test_whitespace_collapsed(self):
        self.assertEqual(rsc.normalize_heading("Getting   Started"),
                         "getting started")

    def test_empty(self):
        self.assertEqual(rsc.normalize_heading(""), "")


class TestExtractHeadings(unittest.TestCase):
    def test_atx_levels(self):
        text = "# Install\n## Usage\n### Examples\n"
        found = rsc.extract_headings(text)
        self.assertEqual([h[1] for h in found],
                         ["install", "usage", "examples"])
        self.assertEqual([h[0] for h in found], [1, 2, 3])

    def test_atx_needs_space_after_hash(self):
        text = "#Install\n##Usage\n"
        self.assertEqual(rsc.extract_headings(text), [])

    def test_atx_up_to_three_leading_spaces(self):
        text = "   ## Install\n    ## Usage\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["install"])

    def test_setext_h1_and_h2(self):
        text = "Install\n=======\n\nUsage\n-----\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["install", "usage"])

    def test_setext_after_list_item_is_not_heading(self):
        text = "- first item\n---\n"
        self.assertEqual(rsc.extract_headings(text), [])

    def test_setext_after_blockquote_is_not_heading(self):
        text = "> a quote\n---\n"
        self.assertEqual(rsc.extract_headings(text), [])

    def test_horizontal_rule_after_blank_line_is_not_heading(self):
        text = "Some text.\n\n---\n\nMore text.\n"
        self.assertEqual(rsc.extract_headings(text), [])

    def test_fenced_code_block_ignored(self):
        text = "```\n## Install\n## Usage\n```\n## Examples\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["examples"])

    def test_tilde_fence_ignored(self):
        text = "~~~md\n## Install\n~~~\n## Usage\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["usage"])

    def test_fence_with_info_string(self):
        text = "```markdown\n## Install\n```\n## Usage\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["usage"])

    def test_longer_closing_fence(self):
        text = "````\n## Install\n`````\n## Usage\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["usage"])

    def test_shorter_closing_fence_does_not_close(self):
        text = "````\n## Install\n```\n## Usage\n````\n## Examples\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["examples"])

    def test_front_matter_skipped(self):
        text = "---\ntitle: My Project\n## Install\n---\n\n## Usage\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["usage"])

    def test_lone_opening_rule_is_not_front_matter(self):
        text = "---\n\n## Install\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["install"])

    def test_empty_heading_skipped(self):
        text = "##\n## Install\n"
        found = [h[1] for h in rsc.extract_headings(text)]
        self.assertEqual(found, ["install"])


class TestFindGroups(unittest.TestCase):
    def test_installation_alias(self):
        self.assertEqual(rsc.find_groups("## Installation\n"), {"Install"})

    def test_installing_alias(self):
        self.assertEqual(rsc.find_groups("## Installing\n"), {"Install"})

    def test_how_to_use_alias(self):
        self.assertEqual(rsc.find_groups("## How to use\n"), {"Usage"})

    def test_getting_started_alias(self):
        self.assertEqual(
            rsc.find_groups("## Getting Started\n"), {"Examples"})

    def test_quick_start_alias(self):
        self.assertEqual(rsc.find_groups("## Quick Start\n"), {"Examples"})

    def test_singular_example_alias(self):
        self.assertEqual(rsc.find_groups("## Example\n"), {"Examples"})

    def test_setup_is_not_install(self):
        self.assertEqual(rsc.find_groups("## Setup\n"), set())

    def test_contributing_is_not_usage(self):
        self.assertEqual(rsc.find_groups("## Contributing\n"), set())

    def test_all_three_found(self):
        text = "# T\n## Install\n## Usage\n## Examples\n"
        self.assertEqual(rsc.find_groups(text),
                         {"Install", "Usage", "Examples"})


class TestCheckText(unittest.TestCase):
    def test_all_present(self):
        text = "# T\n## Install\n## Usage\n## Examples\n"
        self.assertEqual(rsc.check_text(text), [])

    def test_missing_usage(self):
        text = "# T\n## Install\n## Examples\n"
        self.assertEqual(rsc.check_text(text), ["Usage"])

    def test_missing_examples(self):
        text = "# T\n## Install\n## Usage\n"
        self.assertEqual(rsc.check_text(text), ["Examples"])

    def test_missing_all(self):
        text = "# T\n## What it does\n"
        self.assertEqual(rsc.check_text(text),
                         ["Install", "Usage", "Examples"])

    def test_empty_file(self):
        self.assertEqual(rsc.check_text(""),
                         ["Install", "Usage", "Examples"])

    def test_no_headings(self):
        self.assertEqual(rsc.check_text("Just some plain text.\n"),
                         ["Install", "Usage", "Examples"])

    def test_sections_only_in_code_block(self):
        text = "```\n## Install\n## Usage\n## Examples\n```\n"
        self.assertEqual(rsc.check_text(text),
                         ["Install", "Usage", "Examples"])

    def test_extra_section_required(self):
        text = "# T\n## Install\n## Usage\n## Examples\n"
        self.assertEqual(rsc.check_text(text, extra=["Contributing"]),
                         ["Contributing"])

    def test_extra_section_present(self):
        text = "# T\n## Install\n## Usage\n## Examples\n## Contributing\n"
        self.assertEqual(rsc.check_text(text, extra=["Contributing"]), [])

    def test_extra_section_case_insensitive(self):
        text = "# T\n## Install\n## Usage\n## Examples\n## CONTRIBUTING\n"
        self.assertEqual(rsc.check_text(text, extra=["contributing"]), [])


class TestCheckFile(unittest.TestCase):
    def test_good_file(self):
        result = rsc.check_file(REPO_ROOT / "examples" / "good.md")
        self.assertEqual(result["missing"], [])
        self.assertIsNone(result["error"])

    def test_missing_usage_file(self):
        result = rsc.check_file(REPO_ROOT / "examples" / "missing-usage.md")
        self.assertEqual(result["missing"], ["Usage"])

    def test_own_readme_passes(self):
        result = rsc.check_file(REPO_ROOT / "README.md")
        self.assertEqual(result["missing"], [])
        self.assertIsNone(result["error"])

    def test_non_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "README.md"
            path.write_bytes(b"# T\n## Install\n\xff\xfe bad bytes\n")
            result = rsc.check_file(path)
            self.assertEqual(result["error"], "not valid UTF-8")


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, rel, content="# T\n## Install\n## Usage\n## Examples\n"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_direct_file_any_name(self):
        path = self._write("notes.md")
        self.assertEqual(rsc.collect([str(path)]), [path])

    def test_folder_finds_readme_only(self):
        self._write("README.md")
        self._write("CHANGELOG.md")
        self._write("docs/README.md")
        self._write("docs/guide.md")
        found = rsc.collect([str(self.root)])
        self.assertEqual(found, [self.root / "README.md",
                                 self.root / "docs" / "README.md"])

    def test_readme_name_variants(self):
        self._write("README.markdown")
        self._write("README.txt")
        self._write("README")
        found = rsc.collect([str(self.root)])
        self.assertEqual(len(found), 3)

    def test_git_folder_skipped(self):
        self._write("README.md")
        self._write(".git/README.md")
        found = rsc.collect([str(self.root)])
        self.assertEqual(found, [self.root / "README.md"])

    def test_no_recursive(self):
        self._write("README.md")
        self._write("docs/README.md")
        found = rsc.collect([str(self.root)], recursive=False)
        self.assertEqual(found, [self.root / "README.md"])

    def test_exclude(self):
        self._write("README.md")
        self._write("draft/README.md")
        found = rsc.collect([str(self.root)], exclude=["draft*"])
        self.assertEqual(found, [self.root / "README.md"])

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            rsc.collect([str(self.root / "nope.md")])

    def test_symlinked_dir_not_followed(self):
        self._write("README.md")
        real = self.root / "real"
        real.mkdir()
        (real / "README.md").write_text(
            "# T\n## Install\n## Usage\n## Examples\n", encoding="utf-8")
        (self.root / "link").symlink_to(real, target_is_directory=True)
        found = rsc.collect([str(self.root)])
        # The real directory is walked; the symlinked one is not.
        self.assertEqual(found, [self.root / "README.md",
                                 self.root / "real" / "README.md"])
        self.assertNotIn(self.root / "link" / "README.md", found)


class TestCLI(unittest.TestCase):
    def test_good_file_exit_0(self):
        code, out, _ = run_cli("examples/good.md")
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_missing_section_exit_1(self):
        code, out, _ = run_cli("examples/missing-usage.md")
        self.assertEqual(code, 1)
        self.assertIn("FAIL examples/missing-usage.md: missing section: Usage",
                      out)
        self.assertIn("Checked 1 file(s), 1 problem(s) in 1 file(s).", out)

    def test_code_block_file_exit_1_three_problems(self):
        code, out, _ = run_cli("examples/code-block.md")
        self.assertEqual(code, 1)
        self.assertIn("missing section: Install", out)
        self.assertIn("missing section: Usage", out)
        self.assertIn("missing section: Examples", out)
        self.assertIn("Checked 1 file(s), 3 problem(s) in 1 file(s).", out)

    def test_alias_file_exit_0(self):
        code, out, _ = run_cli("examples/install-alias.md")
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_default_path_is_readme(self):
        code, out, _ = run_cli()
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "# T\n## Install\n## Usage\n## Examples\n", encoding="utf-8")
            (root / "notes.md").write_text("# notes\n", encoding="utf-8")
            code, out, _ = run_cli(str(root))
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli("no-such-file.md")
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli("--nope")
        self.assertEqual(code, 2)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(tmp)
            self.assertEqual(code, 2)
            self.assertIn("no README files found", err)

    def test_stdin(self):
        text = "# T\n## Install\n## Usage\n"
        code, out, _ = run_cli("--stdin", input_text=text)
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>: missing section: Examples", out)

    def test_stdin_clean(self):
        text = "# T\n## Install\n## Usage\n## Examples\n"
        code, out, _ = run_cli("--stdin", input_text=text)
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_json_output(self):
        code, out, err = run_cli("--json", "examples/missing-usage.md")
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["checked"], 1)
        self.assertEqual(payload["problems"], 1)
        self.assertEqual(payload["files"][0]["missing"], ["Usage"])
        self.assertIn("FAIL examples/missing-usage.md", err)
        self.assertIn("Checked 1 file(s)", err)

    def test_json_clean(self):
        code, out, err = run_cli("--json", "examples/good.md")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["problems"], 0)
        self.assertIn("OK — 1 file(s) checked", err)

    def test_version(self):
        code, out, _ = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn("readme-section-checker 1.0.0", out)

    def test_extra_flag(self):
        code, _, _ = run_cli("--extra", "Contributing", "examples/good.md")
        self.assertEqual(code, 0)
        code, out, _ = run_cli("--extra", "Changelog",
                               "examples/missing-examples.md")
        self.assertEqual(code, 1)
        self.assertIn("missing section: Examples", out)
        self.assertIn("missing section: Changelog", out)

    def test_non_utf8_file_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "README.md"
            path.write_bytes(b"# T\n\xff\n")
            code, out, _ = run_cli(str(path))
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_input_files_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "README.md"
            content = "# T\n## Install\n## Usage\n"
            path.write_text(content, encoding="utf-8")
            run_cli(str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_exclude_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "# T\n## Install\n## Usage\n## Examples\n", encoding="utf-8")
            draft = root / "draft"
            draft.mkdir()
            (draft / "README.md").write_text("# T\n", encoding="utf-8")
            code, out, _ = run_cli("--exclude", "draft*", str(root))
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)


class TestExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        proc = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=str(REPO_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        saved = (REPO_ROOT / "examples" / "sample-output.md").read_text(
            encoding="utf-8")
        self.assertEqual(proc.stdout, saved)

    def test_readme_quoted_outputs(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        sample = (REPO_ROOT / "examples" / "sample-output.md").read_text(
            encoding="utf-8")
        for line in [
            "OK — 1 file(s) checked, all required sections present.",
            "FAIL examples/missing-usage.md: missing section: Usage",
            "Checked 1 file(s), 1 problem(s) in 1 file(s).",
            "FAIL examples/code-block.md: missing section: Install",
            "FAIL examples/code-block.md: missing section: Usage",
            "FAIL examples/code-block.md: missing section: Examples",
            "Checked 1 file(s), 3 problem(s) in 1 file(s).",
        ]:
            self.assertIn(line, readme, "README must quote: %s" % line)
            self.assertIn(line, sample, "sample output must hold: %s" % line)
        # Quoted in the README only: the --stdin run is not part of
        # run-example.sh, so it is not in sample-output.md.
        self.assertIn("FAIL <stdin>: missing section: Examples", readme)

    def test_run_example_script_exits_zero(self):
        proc = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=str(REPO_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        """All repo files, excluding .git, __pycache__, and tests/."""
        found = []
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")]
            rel_root = Path(root).relative_to(REPO_ROOT)
            if rel_root.parts and rel_root.parts[0] == "tests":
                continue
            for name in files:
                found.append(Path(root) / name)
        return found

    def test_no_placeholder_text(self):
        for path in self._repo_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for word in BANNED_WORDS:
                self.assertNotIn(word.lower(), text.lower(),
                                 "%s contains banned word %r"
                                 % (path, word))

    def test_no_absolute_paths(self):
        for path in self._repo_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/home/", text, str(path))
            self.assertNotIn("/Users/", text, str(path))
            self.assertNotIn("C:\\", text, str(path))

    def test_stdlib_imports_only(self):
        for path in [REPO_ROOT / "src" / "readme_section_checker.py",
                     REPO_ROOT / "tests" / "test_readme_section_checker.py"]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported.add(node.module.split(".")[0])
            # The test file imports the tool itself; that is local
            # code, not a third-party dependency.
            allowed = set(ALLOWED_STDLIB)
            if path.name.startswith("test_"):
                allowed.add("readme_section_checker")
            bad = imported - allowed
            self.assertEqual(bad, set(), "%s imports non-stdlib: %s"
                             % (path, bad))

    def test_no_yaml_import_anywhere(self):
        for path in self._repo_files():
            if path.suffix == ".py":
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("import yaml", text, str(path))
                self.assertNotIn("from yaml", text, str(path))

    def test_gitignore_env_first(self):
        lines = (REPO_ROOT / ".gitignore").read_text(
            encoding="utf-8").splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_test_file(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8")
        self.assertIn("python3 tests/test_readme_section_checker.py", ci)
        self.assertIn("actions/checkout@v4", ci)
        self.assertIn("actions/setup-python@v5", ci)
        self.assertIn('python-version: "3.12"', ci)

    def test_hygiene_scan_excludes_git_and_pycache(self):
        """The Day 21 lesson: a scan must skip .git and __pycache__."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hook = root / ".git" / "hooks"
            hook.mkdir(parents=True)
            (hook / "sample").write_text("# TODO: sample hook\n",
                                         encoding="utf-8")
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "mod.pyc").write_bytes(b"TODO")
            (root / "README.md").write_text("# Clean\n", encoding="utf-8")
            hits = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames
                               if d not in (".git", "__pycache__")]
                for name in filenames:
                    text = (Path(dirpath) / name).read_text(
                        encoding="utf-8", errors="ignore")
                    if "TODO" in text:
                        hits.append(name)
            self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
