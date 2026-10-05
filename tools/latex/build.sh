#!/usr/bin/env bash
# Build a PDF from a Markdown file of a lecture/lab folder:
#   <dir>/<md> -> work/latex/<md name>.tex -> output/<dir name>_<suffix>.pdf
# (xelatex, repeated until labels/TOC are stable, max 4 passes).
# Usage: tools/latex/build.sh <dir> [<md> <suffix>]
#   lecture (default): tools/latex/build.sh lectures/r1                    -> output/r1_conspect.pdf
#   lab primer:        tools/latex/build.sh labs/db-2 primer.md questions  -> output/db-2_questions.pdf
set -euo pipefail
L="${1:?lecture or lab dir}"
MD="${2:-summary.md}"
SUFFIX="${3:-conspect}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
ABS="$(cd "$L" && pwd)"
NAME="$(basename "$ABS")"
JOB="$(basename "$MD" .md)"
PDF="$ROOT/output/${NAME}_${SUFFIX}.pdf"
OUT="$L/work/latex"
mkdir -p "$OUT"
# Mermaid schemes are rendered by the filter (mmdc) into work/mermaid, absolute paths for xelatex
export MERMAID_DIR="$ABS/work/mermaid"
pandoc "$L/$MD" -f markdown -t latex -s \
  --template="$HERE/conspect.tex" --lua-filter="$HERE/conspect.lua" \
  --shift-heading-level-by=-1 -o "$OUT/$JOB.tex"
for pass in 1 2 3 4; do
  # run from the lecture dir: image paths in summary.md are relative to it (work/figures/…)
  if ! (cd "$L" && xelatex -interaction=nonstopmode -halt-on-error -output-directory=work/latex "work/latex/$JOB.tex") >"$OUT/xelatex.log" 2>&1; then
    grep -nA6 '^!' "$OUT/$JOB.log" | head -40 || tail -40 "$OUT/xelatex.log"
    echo "xelatex failed (pass $pass); full log: $OUT/$JOB.log" >&2
    exit 1
  fi
  [ "$pass" -ge 2 ] && ! grep -qE 'Rerun to get|Label\(s\) may have changed' "$OUT/$JOB.log" && break
done
mkdir -p "$ROOT/output"
cp "$OUT/$JOB.pdf" "$PDF"
grep -E 'Overfull \\hbox \(([2-9][0-9]|[0-9]{3,})' "$OUT/$JOB.log" | head -5 || true
echo "ok: $PDF"
