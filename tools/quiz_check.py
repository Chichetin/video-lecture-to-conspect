#!/usr/bin/env python3
"""Check a lecture self-test (quiz.md) against the rules of .claude/lecture/quiz.md.

Usage:
  python tools/quiz_check.py <lecture_dir>                    markup, types, links to summary.md sections
  python tools/quiz_check.py <lecture_dir> --calc             run work/quiz_calc.py and compare numeric answers
  python tools/quiz_check.py <lecture_dir> --blind            write work/quiz_blind.md (no answer keys) for the solver
  python tools/quiz_check.py <lecture_dir> --compare <file>   compare solver answers with the keys

Question ids: e/m/h (level) + number, e.g. m3. Solver answer file: one line per question,
`e1: 2` (option numbers from quiz_blind.md), `m4: 1, 3`, `m1: 0.92`, `h5: <open answer text>`;
text after ` # ` is a comment, lines starting with `!` are remarks (printed as is).
Prints problems one per line; exits 1 if there are errors (warnings don't fail).
"""
import re
import subprocess
import sys
from pathlib import Path

LEVELS = [("Лёгкий уровень", "e"), ("Средний уровень", "m"), ("Сложный уровень", "h")]
TYPE_NAMES = {"single": "один вариант", "multi": "несколько вариантов", "num": "число", "open": "открытый"}
OPTION = re.compile(r"^- \[( |x|X)\] (.+)$")
NUMBER = re.compile(r"^([-+]?\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)$")
REF = re.compile(r"(\d+)\s*«([^»]+)»")
MARKERS = ("**Ответ:**", "**Эталон:**", "**Ключевые пункты:**", "**Разбор:**", "**Где в конспекте:**")


def norm(s):
    return re.sub(r"\s+", " ", s.replace("ё", "е")).strip().rstrip(".").casefold()


def summary_sections(lecture):
    """Numbered ## sections of summary.md: [title, ...] in order."""
    out = []
    for line in (lecture / "summary.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (.+?)\s*(\{[^}]*\})?\s*$", line)
        if m and "unnumbered" not in (m.group(2) or ""):
            out.append(m.group(1))
    return out


def parse(md):
    """quiz.md → (meta lines, intro lines, levels, problems). Level: {title, prefix, line, questions}.
    Question: {id, n, line, body, options [(correct, text)], answer, tol, etalon, points, explain, where, type}."""
    lines = md.splitlines()
    problems = []
    meta, start = [], 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                meta, start = lines[1:j], j + 1
                break
    if not meta:
        problems.append("1: нет YAML-шапки")

    levels, intro, q, section = [], [], None, None
    for i in range(start, len(lines)):
        no, line = i + 1, lines[i]
        if re.match(r"^#{1,6} ", line) and i > start and lines[i - 1].strip():
            problems.append(f"{no}: нет пустой строки перед заголовком — pandoc склеит его с абзацем")
        if line.startswith("## "):
            levels.append({"title": line[3:].strip(), "line": no, "questions": []})
            q = None
            continue
        if line.startswith("### "):
            if not levels:
                problems.append(f"{no}: вопрос до заголовка уровня")
                continue
            m = re.match(r"^### Вопрос (\d+)\s*$", line)
            if not m:
                problems.append(f"{no}: заголовок вопроса не вида «### Вопрос N»: {line[:60]}")
            q = {"n": int(m.group(1)) if m else 0, "line": no, "body": [], "options": [], "plain_items": [],
                 "answer": None, "tol": None, "etalon": [], "points": [], "explain": [], "where": None}
            levels[-1]["questions"].append(q)
            section = "body"
            continue
        if line.startswith("#"):
            if re.match(r"^#{1,6} ", line):
                problems.append(f"{no}: заголовок {line.split()[0]} — в тесте только ## и ###")
            continue
        if q is None:
            if levels:
                if line.strip():
                    problems.append(f"{no}: текст между заголовком уровня и первым вопросом")
            else:
                intro.append(line)
            continue
        s = line.strip()
        if section == "body" and not s:
            q["body"].append("")
            continue
        if s.startswith("**Ответ:**"):
            section = "answer"
            raw = s[len("**Ответ:**"):].strip()
            m = NUMBER.match(raw)
            if m:
                q["answer"], q["tol"] = float(m.group(1)), float(m.group(2))
            else:
                q["answer"] = raw
                problems.append(f"{no}: ответ не вида «0.92 ± 0.01» (точка, допуск обязателен): {raw[:40]}")
        elif s.startswith("**Эталон:**"):
            section = "etalon"
            q["etalon"].append(s[len("**Эталон:**"):].strip())
        elif s.startswith("**Ключевые пункты:**"):
            section = "points"
            if s != "**Ключевые пункты:**":
                problems.append(f"{no}: после «Ключевые пункты:» — список с новой строки")
        elif s.startswith("**Разбор:**"):
            section = "explain"
            q["explain"].append(s[len("**Разбор:**"):].strip())
        elif s.startswith("**Где в конспекте:**"):
            section = "where"
            q["where"] = (no, s[len("**Где в конспекте:**"):].strip())
        elif m := OPTION.match(s):
            q["options"].append((m.group(1) != " ", m.group(2).strip()))
            if section not in ("body", "options"):
                problems.append(f"{no}: варианты ответа должны идти сразу после текста вопроса")
            section = "options"
        elif section == "points" and s.startswith("- "):
            q["points"].append(s[2:].strip())
        elif s:
            if s.startswith("- ") and section in ("body", "options"):
                q["plain_items"].append(no)
            if section == "where":
                problems.append(f"{no}: текст после «Где в конспекте» — это должен быть последний абзац вопроса")
            elif section == "body":
                q["body"].append(line.rstrip())
            elif section == "etalon":
                q["etalon"].append(s)
            elif section == "explain":
                q["explain"].append(s)
            elif section == "points":
                problems.append(f"{no}: в «Ключевых пунктах» только список «- …»")
            elif section in ("answer", "options"):
                problems.append(f"{no}: текст после {'ответа' if section == 'answer' else 'вариантов'} без маркера "
                                "(«Разбор:», «Эталон:»…)")
    return meta, intro, levels, problems


def classify(q):
    kinds = []
    if q["options"]:
        kinds.append("multi" if sum(c for c, _ in q["options"]) >= 2 else "single")
    if q["answer"] is not None:
        kinds.append("num")
    if q["etalon"] or q["points"]:
        kinds.append("open")
    return kinds


def check(lecture, md):
    meta, intro, levels, problems = parse(md)
    warnings = []
    if not any(re.match(r"^doc-kind:\s*\"?quiz\"?\s*$", m) for m in meta):
        problems.append("YAML: нет doc-kind: quiz")
    for key in ("title", "lecture", "course"):
        if not any(m.startswith(f"{key}:") for m in meta):
            problems.append(f"YAML: нет поля {key}")
    if not any(s.strip() for s in intro):
        problems.append("нет вступления перед первым уровнем")

    for i, line in enumerate(md.splitlines(), 1):
        if line.startswith(":::"):
            problems.append(f"{i}: fenced div (:::) — в тесте не используется")
        if re.search(r"\{[#.][^}]*\}", line) and not line.lstrip().startswith("$"):
            problems.append(f"{i}: атрибуты {{…}}")
        if "![" in line:
            problems.append(f"{i}: картинка — в тесте их нет")
        if re.search(r"</?[a-zA-Z][a-zA-Z0-9]*(\s[^>]*)?>", line):
            problems.append(f"{i}: HTML-тег")
        if re.search(r"\[\^[^\]]+\]", line):
            problems.append(f"{i}: сноска — в тесте их нет")
        if "```" in line:
            problems.append(f"{i}: блок кода — в тесте их нет")

    titles = [l["title"] for l in levels]
    if titles != [t for t, _ in LEVELS]:
        problems.append(f"уровни {titles} — нужны ровно {[t for t, _ in LEVELS]} в этом порядке")

    sections = summary_sections(lecture)
    content = {n for n, t in enumerate(sections, 1) if "организац" not in t.casefold()}
    covered = {"e": set(), "m": set(), "h": set()}
    seen_bodies = {}
    for level in levels:
        prefix = dict(LEVELS).get(level["title"], "?")
        qs = level["questions"]
        level["prefix"] = prefix
        if [q["n"] for q in qs] != list(range(1, len(qs) + 1)):
            problems.append(f"{level['line']}: «{level['title']}»: номера вопросов {[q['n'] for q in qs]} — нужно 1…{len(qs)} подряд")
        for q in qs:
            q["id"] = f"{prefix}{q['n']}"
            where = f"{q['line']}: {q['id']}"
            kinds = classify(q)
            q["type"] = kinds[0] if len(kinds) == 1 else None
            if len(kinds) != 1:
                problems.append(f"{where}: в вопросе должен быть ровно один маркер типа (варианты / Ответ / Эталон), "
                                f"найдено: {kinds or 'ни одного'}")
            q["body"] = "\n".join(q["body"]).strip("\n").splitlines()
            if not q["body"]:
                problems.append(f"{where}: нет текста вопроса")
            else:
                key = norm(" ".join(q["body"]))
                if key in seen_bodies:
                    warnings.append(f"{where}: тот же текст, что у {seen_bodies[key]}")
                seen_bodies[key] = q["id"]
            for no in q["plain_items"]:
                problems.append(f"{no}: {q['id']}: обычный список в вопросе — варианты пишутся как «- [ ]» / «- [x]»")
            if q["options"]:
                n_opt, n_ok = len(q["options"]), sum(c for c, _ in q["options"])
                if not 3 <= n_opt <= 5:
                    problems.append(f"{where}: вариантов {n_opt} — нужно 3–5")
                if n_ok == 0:
                    problems.append(f"{where}: нет верного варианта [x]")
                if n_ok == n_opt:
                    problems.append(f"{where}: все варианты верные")
                texts = [norm(t) for _, t in q["options"]]
                if len(set(texts)) != len(texts):
                    problems.append(f"{where}: повторяющиеся варианты")
                for _, t in q["options"]:
                    if re.search(r"все (перечисленн|вышеперечисл)|ничего из перечисл|оба варианта", t, re.I):
                        problems.append(f"{where}: вариант «{t[:40]}» не работает при перемешивании")
            if q["type"] == "open":
                if not " ".join(q["etalon"]).strip():
                    problems.append(f"{where}: пустой эталон")
                if not 2 <= len(q["points"]) <= 5:
                    problems.append(f"{where}: ключевых пунктов {len(q['points'])} — нужно 2–5")
            if q["type"] in ("single", "multi", "num") and not " ".join(q["explain"]).strip():
                problems.append(f"{where}: нет разбора")
            if not q["where"]:
                problems.append(f"{where}: нет «Где в конспекте»")
            else:
                no, text = q["where"]
                refs = REF.findall(text)
                if not refs:
                    problems.append(f"{no}: {q['id']}: «Где в конспекте» не вида «раздел N «Название»»")
                for n, title in refs:
                    n = int(n)
                    if not 1 <= n <= len(sections):
                        problems.append(f"{no}: {q['id']}: раздела {n} нет в summary.md (их {len(sections)})")
                    elif norm(title) != norm(sections[n - 1]):
                        problems.append(f"{no}: {q['id']}: раздел {n} называется «{sections[n - 1]}», а не «{title}»")
                    else:
                        covered.setdefault(prefix, set()).add(n)

        types = [q["type"] for q in qs]
        count = lambda *ts: sum(t in ts for t in types)
        if prefix == "e":
            if count("num", "open"):
                problems.append(f"{level['line']}: на лёгком уровне только вопросы с выбором")
        if prefix in ("e", "m") and content and not len(content) <= len(qs) <= 2 * len(content):
            warnings.append(f"«{level['title']}»: {len(qs)} вопросов при {len(content)} содержательных разделах "
                            f"(ориентир {len(content)}–{2 * len(content)})")
        if prefix == "m":
            if not 1 <= count("open") <= 2:
                warnings.append(f"«{level['title']}»: открытых вопросов {count('open')} (ориентир 1–2)")
            if count("num") > 3:
                warnings.append(f"«{level['title']}»: числовых вопросов {count('num')} (ориентир 2–3)")
        if prefix == "h":
            if not 8 <= len(qs) <= 10:
                warnings.append(f"«{level['title']}»: {len(qs)} вопросов (ориентир 8–10)")
            if qs and not 0.2 <= count("open") / len(qs) <= 0.5:
                warnings.append(f"«{level['title']}»: открытых {count('open')} из {len(qs)} (ориентир ~⅓)")
            multi_ref = sum(len(REF.findall(q["where"][1])) >= 2 for q in qs if q["where"])
            if multi_ref < 3:
                warnings.append(f"«{level['title']}»: вопросов на несколько разделов {multi_ref} (нужно ≥ 3)")

    missing = sorted(content - covered["e"] - covered["m"])
    if missing:
        warnings.append("разделы без вопросов на лёгком и среднем уровне: " + ", ".join(map(str, missing)))
    return levels, problems, warnings


def questions(levels):
    return [q for level in levels for q in level["questions"] if "id" in q]


def run_calc(lecture, levels):
    script = lecture / "work" / "quiz_calc.py"
    if not script.exists():
        return [f"нет {script}"]
    res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    if res.returncode:
        return [f"quiz_calc.py упал: {res.stderr.strip()[-400:]}"]
    got = {}
    for line in res.stdout.splitlines():
        m = re.match(r"^\s*([emh]\d+)\s+([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*$", line)
        if m:
            got[m.group(1)] = float(m.group(2))
    problems = []
    by_id = {q["id"]: q for q in questions(levels)}
    for q in by_id.values():
        if q["type"] == "num" and isinstance(q["answer"], float):
            if q["id"] not in got:
                problems.append(f"{q['id']}: нет строки в выводе quiz_calc.py")
            elif abs(got[q["id"]] - q["answer"]) > q["tol"]:
                problems.append(f"{q['id']}: в тесте {q['answer']} ± {q['tol']}, скрипт даёт {got[q['id']]:.6g}")
    for qid, v in got.items():
        if qid not in by_id:
            problems.append(f"{qid}: в тесте нет такого вопроса (скрипт печатает {v:.6g})")
        elif by_id[qid]["type"] != "num":
            print(f"{qid}: {v:.6g} — вопрос с выбором, сверь с верным вариантом вручную")
    print(f"quiz_calc.py: значений {len(got)}")
    return problems


def write_blind(lecture, levels):
    out = ["# Тест без ответов", "",
           "Ответы — в отдельный файл, по строке на вопрос: `e1: 2`, `m4: 1, 3`, `m1: 0.92`, `h5: текст ответа`.", ""]
    for level in levels:
        out += [f"## {level['title']}", ""]
        for q in level["questions"]:
            if "id" not in q:
                continue
            out += [f"### {q['id']} — {TYPE_NAMES.get(q['type'], '?')}", ""]
            out += q["body"] + [""]
            for k, (_, text) in enumerate(q["options"], 1):
                out.append(f"{k}. {text}")
            if q["options"]:
                out.append("")
    path = lecture / "work" / "quiz_blind.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"записан {path}")


def compare(levels, answers_path):
    by_id = {q["id"]: q for q in questions(levels)}
    got, problems = {}, []
    for line in Path(answers_path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("!"):
            print(s)
            continue
        m = re.match(r"^([emh]\d+)\s*:\s*(.*?)(?:\s+#\s+(.*))?$", s)
        if m:
            got[m.group(1)] = (m.group(2).strip(), m.group(3) or "")
    agree = 0
    for qid, q in by_id.items():
        if qid not in got:
            problems.append(f"{qid}: решатель не ответил")
            continue
        value, note = got[qid]
        note = f" — {note}" if note else ""
        if q["type"] in ("single", "multi"):
            chosen = {int(x) for x in re.findall(r"\d+", value)}
            correct = {k for k, (c, _) in enumerate(q["options"], 1) if c}
            if chosen == correct:
                agree += 1
            else:
                problems.append(f"{qid}: ключ {sorted(correct)}, решатель {sorted(chosen)}{note}")
        elif q["type"] == "num":
            m = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
            v = float(m.group(0).replace(",", ".")) if m else None
            if v is not None and isinstance(q["answer"], float) and abs(v - q["answer"]) <= q["tol"]:
                agree += 1
            else:
                problems.append(f"{qid}: ключ {q['answer']} ± {q['tol']}, решатель {value}{note}")
        elif q["type"] == "open":
            print(f"{qid} (открытый): решатель: {value}{note}")
            print("    ключевые пункты: " + "; ".join(q["points"]))
    print(f"совпало с ключом: {agree} из {sum(q['type'] != 'open' for q in by_id.values())} вопросов с автопроверкой")
    return problems


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lecture = Path(sys.argv[1])
    md = (lecture / "quiz.md").read_text(encoding="utf-8")
    levels, problems, warnings = check(lecture, md)
    mode = sys.argv[2] if len(sys.argv) > 2 else None
    if mode == "--calc":
        problems += run_calc(lecture, levels)
    elif mode == "--blind":
        write_blind(lecture, levels)
    elif mode == "--compare":
        problems += compare(levels, sys.argv[3])
    elif mode:
        sys.exit(f"неизвестный режим {mode}")

    for p in problems:
        print(p)
    for w in warnings:
        print(f"предупреждение: {w}")
    stats = []
    for level in levels:
        types = [q.get("type") for q in level["questions"]]
        parts = [f"{TYPE_NAMES[t]} {types.count(t)}" for t in TYPE_NAMES if types.count(t)]
        stats.append(f"{level['title']}: {len(types)} ({', '.join(parts)})")
    print("; ".join(stats))
    print(f"проблем: {len(problems)}, предупреждений: {len(warnings)}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
