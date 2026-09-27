#!/usr/bin/env bash
# Build a lecture summary PDF: summary.md -> work/latex/summary.tex -> output/<lecture>_conspect.pdf
# (xelatex, repeated until labels/TOC are stable, max 4 passes).
# Usage: tools/latex/build.sh <lecture_dir>
set -euo pipefail
L="${1:?lecture dir}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
NAME="$(basename "$(cd "$L" && pwd)")"
PDF="$ROOT/output/${NAME}_conspect.pdf"
OUT="$L/work/latex"
mkdir -p "$OUT"
pandoc "$L/summary.md" -f markdown -t latex -s \
  --template="$HERE/conspect.tex" --lua-filter="$HERE/conspect.lua" \
  --shift-heading-level-by=-1 -o "$OUT/summary.tex"
for pass in 1 2 3 4; do
  # run from the lecture dir: image paths in summary.md are relative to it (work/figures/…)
  if ! (cd "$L" && xelatex -interaction=nonstopmode -halt-on-error -output-directory=work/latex work/latex/summary.tex) >"$OUT/xelatex.log" 2>&1; then
    grep -nA6 '^!' "$OUT/summary.log" | head -40 || tail -40 "$OUT/xelatex.log"
    echo "xelatex failed (pass $pass); full log: $OUT/summary.log" >&2
    exit 1
  fi
  [ "$pass" -ge 2 ] && ! grep -qE 'Rerun to get|Label\(s\) may have changed' "$OUT/summary.log" && break
done
mkdir -p "$ROOT/output"
cp "$OUT/summary.pdf" "$PDF"
grep -E 'Overfull \\hbox \(([2-9][0-9]|[0-9]{3,})' "$OUT/summary.log" | head -5 || true
echo "ok: $PDF"
