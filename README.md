# readme-section-checker-cli

Check a README has Install, Usage and Examples, fail CI when a section is missing.

[![CI](https://github.com/haiderstudio/readme-section-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/readme-section-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`readme_section_checker` reads a README and checks it has the
three sections a new user needs — Install (or Installation),
Usage, and Examples (or Getting Started) — and reports every
missing one, with the file and the section name. It exits 1
when any required section is missing, so it can fail a CI run.
A README with all three exits 0.

- Most READMEs are missing Install or Usage, and a new user
  cannot run the project without them. This tool catches that
  before the README ships, instead of after a user gives up.
- Section names are matched case-insensitively: `## install`
  counts, `## INSTALLATION` counts, and a trailing colon or
  full stop does not matter (`## Usage:` counts as Usage).
- Aliases are accepted: "Installation" counts as Install,
  "How to use" counts as Usage, and "Getting Started" (or
  "Quick start") counts as Examples.
- A heading inside a fenced code block does **not** count —
  a code example that mentions "Install" is not an Install
  section. Setext headings (text underlined with `===` or
  `---`) count, and so do headings with anchor suffixes
  (`## Install {#install}`).
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for README
  files (`README.md`, `README.markdown`, `README.txt`,
  `README.rst`, or a plain `README`), recursively by default
  (`--no-recursive` stops at the top level). `.git` folders
  are never walked, and directory links are never followed.
- `--extra SECTION` (repeatable) also requires a section of
  your own, matched the same way — for example
  `--extra Contributing`.
- `--json` prints the result as JSON (the human-readable
  lines go to standard error), and `--stdin` checks one
  README read from standard input.

## Who it is for

Anyone who owns a repo and wants every README to be usable
by a stranger — open-source maintainers, teams that review
each other's docs, and anyone who has ever been asked
"how do I run this?" for a project whose README never says.

## What it does NOT do

- It does not check whether a README *exists* — that is
  Day 10's repo-hygiene-checker-cli. This tool checks what
  is inside a README, never whether one is there.
- It does not check the *quality* of a section — a one-line
  Install section passes, as long as it exists. Writing a
  good section is still the author's job.
- It does not check any other file type, and it never
  rewrites a file. It is report-only, and it never touches
  the network.

## How this differs

- kasyap0420/readme-completeness-checker (0 stars) is a
  Python tool that checks whether a README includes
  practical sections (purpose, features, setup, run
  commands). It has no CI workflow, so it cannot fail a
  build. This tool is a tested command-line gate with a
  CI exit code, folder walking, file-and-section
  reporting, and a fixed, documented rule.
- Day 10's repo-hygiene-checker-cli checks a README
  exists; this one checks what is inside it — a
  different job.
- Day 1's readme-writer-skill writes a README; checking
  an existing one is the other half.

## Install

```sh
git clone https://github.com/haiderstudio/readme-section-checker-cli.git
cd readme-section-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one README:

```sh
python3 src/readme_section_checker.py README.md
```

A complete README passes:

```sh
$ python3 src/readme_section_checker.py examples/good.md
OK — 1 file(s) checked, all required sections present.
```

A README missing Usage fails:

```sh
$ python3 src/readme_section_checker.py examples/missing-usage.md
FAIL examples/missing-usage.md: missing section: Usage
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a whole folder (README files only):

```sh
python3 src/readme_section_checker.py docs/
```

Check one README from standard input:

```sh
$ python3 src/readme_section_checker.py --stdin < examples/missing-examples.md
FAIL <stdin>: missing section: Examples
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/readme_section_checker.py --json examples/missing-usage.md
{
  "files": [
    {
      "path": "examples/missing-usage.md",
      "missing": [
        "Usage"
      ],
      "error": null
    }
  ],
  "checked": 1,
  "problems": 1
}
```

Require an extra section of your own:

```sh
python3 src/readme_section_checker.py --extra Contributing README.md
```

Exit codes: 0 when every README checked has all required
sections, 1 when any section is missing or a file cannot be
read, 2 for a usage error (a missing path, a bad flag, or no
README files found).

## Examples

A README whose section names only appear inside a fenced
code block has none of the three sections:

```sh
$ python3 src/readme_section_checker.py examples/code-block.md
FAIL examples/code-block.md: missing section: Install
FAIL examples/code-block.md: missing section: Usage
FAIL examples/code-block.md: missing section: Examples
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

Aliases count — "Installation" is Install, and "Getting
Started" is Examples:

```sh
$ python3 src/readme_section_checker.py examples/install-alias.md
OK — 1 file(s) checked, all required sections present.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_readme_section_checker.py
```

The tests cover heading parsing (ATX headings at every
level, setext headings, case-insensitive matching,
trailing punctuation and anchor suffixes stripped,
headings inside fenced code blocks ignored, YAML front
matter skipped, list items and blockquotes never counted
as setext headings), aliases ("Installation" counts as
Install, "Getting Started" counts as Examples, "Setup"
does not count as Install), the check itself (every
missing section reported, an empty file, a file with no
headings, a file whose section names only appear inside a
code block), the CLI (exit 0/1/2, folder walking,
`--no-recursive`, `.git` skipped, `--exclude`, a direct
file checked even without a README name, `--extra`,
`--stdin`, `--json` output, `--version`, bad flags,
missing paths, empty folders, a non-UTF-8 file reported,
input files left unchanged), the bundled examples
(sample output compared byte-for-byte against a fresh
run, and the README-quoted outputs checked against it),
and hygiene checks (no placeholder text, no absolute
paths, stdlib imports only, `.env` first in
`.gitignore`, CI file runs the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking README sections is not new — the similar tool
named above (the 0-star readme-completeness-checker) is
listed in "How this differs" — but every line of code
here is original, and the tool builds on nothing but
Python's standard library.
