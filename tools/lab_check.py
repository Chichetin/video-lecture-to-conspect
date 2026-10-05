#!/usr/bin/env python3
"""Check a lab primer (primer.md) against the question list and the markup rules
of .claude/lab/primer.md.

Usage: python tools/lab_check.py <lab_dir>
Reads <lab_dir>/primer.md and <lab_dir>/work/questions.json ([{"n": 1, "text": "..."}]).
Prints problems one per line and exits 1 if there are any.
"""
import json
import re
import sys
from pathlib import Path

ALERTS = {"NOTE", "TIP", "WARNING", "CAUTION"}
MERMAID = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "erDiagram", "stateDiagram-v2")


def norm(s):
    return re.sub(r"\s+", " ", s.replace("ё", "е")).strip().rstrip(".").casefold()


def main():
    lab = Path(sys.argv[1])
    md = (lab / "primer.md").read_text(encoding="utf-8")
    questions = json.loads((lab / "work" / "questions.json").read_text(encoding="utf-8"))
    problems = []

    # code blocks are skipped by the text checks; mermaid blocks are checked separately
    lines = md.splitlines()
    in_code, fence, code_lang, code_start = False, "", "", 0
    text_lines = []  # (line_no, line) outside code blocks
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip("> ").rstrip() if line.startswith(">") else line.strip()
        m = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
        if m and not in_code:
            in_code, fence, code_lang, code_start = True, m.group(1), m.group(2).strip(), i
            if code_lang.startswith("{"):
                problems.append(f"{i}: атрибуты у блока кода ({code_lang}) — пиши только язык")
            continue
        if in_code:
            if stripped.startswith(fence) and stripped.strip("`~") == "":
                in_code = False
            elif code_lang == "mermaid" and i == code_start + 1:
                if not stripped.startswith(MERMAID):
                    problems.append(f"{i}: тип схемы Mermaid не из списка: {stripped[:40]}")
                if stripped.startswith("%%{"):
                    problems.append(f"{i}: %%{{init}}%% в схеме Mermaid")
            continue
        text_lines.append((i, line))
    if in_code:
        problems.append(f"{code_start}: незакрытый блок кода")

    headings = []
    for i, line in text_lines:
        if line.startswith(":::"):
            problems.append(f"{i}: fenced div (:::) — используй GitHub alerts")
        if re.match(r"^#{1,6} .*\{[#.]", line):
            problems.append(f"{i}: атрибуты у заголовка — их ставит фильтр")
        m = re.match(r"^>\s*\[!(\w+)\]", line)
        if m and m.group(1) not in ALERTS:
            problems.append(f"{i}: неизвестный тип плашки [!{m.group(1)}]")
        m = re.match(r"^## (.*)$", line)
        if m:
            headings.append((i, m.group(1)))

    # sections = questions: same count, order and wording
    found = []
    for i, h in headings:
        m = re.match(r"^Вопрос (\d+)\.\s*(.*)$", h)
        if not m:
            problems.append(f"{i}: заголовок второго уровня не вида «Вопрос N. …»: {h[:60]}")
            continue
        found.append((i, int(m.group(1)), m.group(2)))
    nums = [n for _, n, _ in found]
    expected = [q["n"] for q in questions]
    if nums != expected:
        problems.append(f"номера разделов {nums} не совпадают с вопросами {expected}")
    by_n = {q["n"]: q["text"] for q in questions}
    for i, n, text in found:
        if n in by_n and norm(text) != norm(by_n[n]):
            problems.append(f"{i}: формулировка вопроса {n} отличается от questions.json")

    # cross references
    for i, line in text_lines:
        for n in re.findall(r"\]\(#q(\d+)\)", line):
            if int(n) not in by_n:
                problems.append(f"{i}: ссылка на несуществующий вопрос #q{n}")

    for p in problems:
        print(p)
    print(f"разделов: {len(found)} из {len(questions)}; проблем: {len(problems)}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
