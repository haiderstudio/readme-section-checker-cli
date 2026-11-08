#!/usr/bin/env python3
"""Check a README has Install, Usage and Examples, fail CI when a section is missing.

Run: python3 src/readme_section_checker.py README.md
     python3 src/readme_section_checker.py docs/
     python3 src/readme_section_checker.py --stdin < README.md

A README that is missing Install or Usage blocks every new user:
they cannot run the project, and they leave. Most READMEs are
missing at least one of the sections a reader needs. This tool
reads a README, looks for the three sections a reader needs —
Install (or Installation), Usage, and Examples (or Getting
Started) — and reports every missing one, with the file and
the section name. It exits 1 when any required section is
missing, so it can fail a CI run. A README with all three
exits 0.

It checks what is INSIDE a README, never whether one exists:
Day 10's repo-hygiene-checker-cli checks a README exists;
this one checks what it contains — a different job. Day 1's
readme-writer-skill WRITES a README; checking an existing
one is the other half.

Section names are matched case-insensitively, and a heading
inside a fenced code block does not count — a code example
that mentions "Install" is not an Install section. Aliases
are accepted: "Installation" counts as Install, "How to
use" counts as Usage, and "Getting Started" (or "Quick
start") counts as Examples. Anything else is not a match:
"Setup" is not Install, and "Contributing" is not Usage.

It never rewrites a file, never touches the network, and
reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

# The three sections a README needs, each with the heading texts
# that count as that section. Matching is case-insensitive and
# ignores trailing punctuation, closing hashes, and anchor suffixes.
REQUIRED_GROUPS = [
    ("Install", {"install", "installation", "installing"}),
    ("Usage", {"usage", "how to use"}),
    ("Examples", {"example", "examples", "getting started",
                  "quick start", "quickstart"}),
]

README_NAMES = {"readme", "readme.md", "readme.markdown",
                "readme.txt", "readme.rst"}

_ATX_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_ANCHOR_RE = re.compile(r"\{#[\w-]+\}\s*$")
_LIST_RE = re.compile(r"^ {0,3}([-*+]|\d+[.)])\s")


def normalize_heading(raw):
    """Turn a heading's text into the form used for matching."""
    text = raw.strip()
    text = _ANCHOR_RE.sub("", text)
    text = re.sub(r"\s+#+\s*$", "", text)
    text = text.strip("*_`")
    text = re.sub(r"[:.!?]+$", "", text.strip())
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def extract_headings(text):
    """Return a list of (line_number, normalized_text) headings.

    ATX headings (# to ######) and setext headings (text underlined
    with === or ---) count. Headings inside fenced code blocks do
    not count, and a YAML front-matter block at the top of the file
    is skipped. A line that is a list item, a blockquote, or a table
    row is never a setext heading.
    """
    lines = text.splitlines()
    headings = []
    in_fence = None
    prev_text = None
    prev_line_no = None

    # YAML front matter: a --- block at the very top of the file,
    # skipped only when a closing --- line actually exists.
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                start = j + 1
                break

    for index in range(start, len(lines)):
        line = lines[index]
        line_no = index + 1

        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0]
            length = len(fence.group(1))
            if in_fence is None:
                in_fence = (marker, length)
            elif marker == in_fence[0] and length >= in_fence[1]:
                in_fence = None
            prev_text = None
            prev_line_no = None
            continue
        if in_fence is not None:
            prev_text = None
            prev_line_no = None
            continue

        atx = _ATX_RE.match(line)
        if atx:
            normalized = normalize_heading(atx.group(1))
            if normalized:
                headings.append((line_no, normalized))
            prev_text = None
            prev_line_no = None
            continue

        if _SETEXT_RE.match(line) and prev_text is not None:
            normalized = normalize_heading(prev_text)
            if normalized:
                headings.append((prev_line_no, normalized))
            prev_text = None
            prev_line_no = None
            continue

        stripped = line.strip()
        if (stripped and not stripped.startswith(">")
                and not _LIST_RE.match(line)
                and not stripped.startswith("|")):
            prev_text = line
            prev_line_no = line_no
        else:
            prev_text = None
            prev_line_no = None

    return headings


def find_groups(text):
    """Return the set of required group names found in the text."""
    found = set()
    for _, normalized in extract_headings(text):
        for name, aliases in REQUIRED_GROUPS:
            if normalized in aliases:
                found.add(name)
    return found


def check_text(text, extra=()):
    """Return the list of missing section names for README text.

    ``extra`` is a list of extra section names the caller also
    requires, matched the same way (case-insensitive, exact
    normalized heading).
    """
    found = find_groups(text)
    missing = [name for name, _ in REQUIRED_GROUPS if name not in found]
    headings = {normalized for _, normalized in extract_headings(text)}
    for name in extra:
        if normalize_heading(name) not in headings:
            missing.append(name)
    return missing


def check_file(path, extra=()):
    """Check one README file. Returns a dict with the result."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"path": str(path), "missing": [], "error": "not valid UTF-8"}
    except OSError as exc:
        return {"path": str(path), "missing": [], "error": str(exc)}
    return {"path": str(path), "missing": check_text(text, extra),
            "error": None}


def is_readme_file(path):
    """True if the file looks like a README (checked by name)."""
    return path.name.lower() in README_NAMES


def collect(paths, recursive=True, exclude=()):
    """Turn paths into a sorted list of README files to check.

    A file given directly is always checked, whatever its name.
    A folder is walked for README files; .git folders are never
    walked and directory links are never followed.
    """
    found = []
    for given in paths:
        path = Path(given)
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            if recursive:
                for root, dirs, files in os.walk(path, followlinks=False):
                    dirs[:] = [d for d in dirs
                               if d != ".git"
                               and not any(fnmatch.fnmatch(d, pat)
                                           for pat in exclude)]
                    for name in files:
                        candidate = Path(root) / name
                        if is_readme_file(candidate) and not any(
                                fnmatch.fnmatch(name, pat)
                                for pat in exclude):
                            found.append(candidate)
            else:
                for name in sorted(os.listdir(path)):
                    candidate = path / name
                    if candidate.is_file() and is_readme_file(candidate) \
                            and not any(fnmatch.fnmatch(name, pat)
                                        for pat in exclude):
                        found.append(candidate)
        else:
            raise FileNotFoundError("no such file or folder: %s" % given)
    return sorted(set(found))


def report(results, as_json=False):
    """Print the results. Returns the number of problems found."""
    problems = 0
    checked = 0
    for result in results:
        checked += 1
        if result["error"] is not None:
            print("ERROR %s: %s" % (result["path"], result["error"]),
                  file=sys.stderr if as_json else sys.stdout)
            problems += 1
        elif result["missing"]:
            for name in result["missing"]:
                print("FAIL %s: missing section: %s"
                      % (result["path"], name),
                      file=sys.stderr if as_json else sys.stdout)
            problems += len(result["missing"])
    if as_json:
        payload = {
            "files": [{"path": r["path"], "missing": r["missing"],
                       "error": r["error"]} for r in results],
            "checked": checked,
            "problems": problems,
        }
        print(json.dumps(payload, indent=2))
    if problems == 0:
        print("OK — %d file(s) checked, all required sections present."
              % checked, file=sys.stderr if as_json else sys.stdout)
    else:
        print("Checked %d file(s), %d problem(s) in %d file(s)."
              % (checked, problems,
                 sum(1 for r in results
                     if r["missing"] or r["error"] is not None)),
              file=sys.stderr if as_json else sys.stdout)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="readme-section-checker",
        description="Check a README has Install, Usage and Examples, "
                    "fail CI when a section is missing.")
    parser.add_argument("paths", nargs="*", default=["README.md"],
                        help="README files or folders to check "
                             "(default: README.md)")
    parser.add_argument("--extra", action="append", default=[],
                        metavar="SECTION",
                        help="also require this section "
                             "(repeatable, matched like the built-ins)")
    parser.add_argument("--stdin", action="store_true",
                        help="read one README from standard input")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON "
                             "(summary goes to standard error)")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        metavar="PATTERN",
                        help="skip files or folders matching this glob "
                             "(repeatable)")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    try:
        if args.stdin:
            text = sys.stdin.read()
            results = [{"path": "<stdin>",
                        "missing": check_text(text, args.extra),
                        "error": None}]
        else:
            files = collect(args.paths,
                            recursive=not args.no_recursive,
                            exclude=args.exclude)
            if not files:
                print("no README files found", file=sys.stderr)
                return 2
            results = [check_file(path, args.extra) for path in files]
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    problems = report(results, as_json=args.json)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
