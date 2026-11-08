#!/bin/sh
# Run the checker over each example README and show the result.
# Bad examples fail on purpose, so each run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/good.md examples/missing-usage.md examples/missing-examples.md examples/install-alias.md examples/code-block.md; do
  echo "== $f =="
  python3 src/readme_section_checker.py "$f" || true
  echo
done
echo "== . : the whole repo =="
python3 src/readme_section_checker.py . || true
