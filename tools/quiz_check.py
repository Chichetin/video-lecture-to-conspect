#!/usr/bin/env python3
"""Check a self-test (quiz.md) to a lecture or a lab against the rules of .claude/lecture/quiz.md.

A folder with summary.md is a lecture (references «Где в конспекте: раздел N «…»» to its numbered ## sections),
a folder with primer.md is a lab (references «Где в учебнике: вопрос N «…»» to its «## Вопрос N. …» sections).

Usage:
  python tools/quiz_check.py <lecture_dir>                    markup, types, links to summary.md / primer.md sections
  python tools/quiz_check.py <lecture_dir> --calc             run work/quiz_calc.py and compare numeric answers
  python tools/quiz_check.py <lecture_dir> --blind            write work/quiz_blind.md (no answer keys) for the solver
  python tools/quiz_check.py <lecture_dir> --compare <file>   compare solver answers with the keys

Question ids: e/m/h (level) + number, e.g. m3. quiz_blind.md shuffles options (fixed order per question id),
so the solver does not see the author's order. Solver answer file: one line per question,
`e1: 2` (option numbers from quiz_blind.md), `m4: 1, 3`, `m1: 0.92`, `h5: <open answer text>`;
text after ` # ` is a comment, lines starting with `!` are remarks (printed as is).
Prints problems one per line; exits 1 if there are errors (warnings don't fail).
"""
import random
import re
import subprocess
import sys
from pathlib import Path

LEVELS = [("Лёгкий уровень", "e"), ("Средний уровень", "m"), ("Сложный уровень", "h")]
TYPE_NAMES = {"single": "один вариант", "multi": "несколько вариантов", "num": "число", "open": "открытый"}
OPTION = re.compile(r"^- \[( |x|X)\] (.+)$")
NUMBER = re.compile(r"^([-+]?\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)$")
REF = re.compile(r"(\d+)\s*«([^»]+)»")
WHERE = ("**Где в конспекте:**", "**Где в учебнике:**")
FENCE = re.compile(r"^\s*(```+)\s*([\w+-]*)")
CODE_SPAN = re.compile(r"`[^`]*`")


def norm(s):
    return re.sub(r"\s+", " ", s.replace("ё", "е")).strip().rstrip(".").casefold()


def is_lab(lecture):
    return (lecture / "primer.md").exists() and not (lecture / "summary.md").exists()


def summary_sections(lecture):
    """Sections that «Где в …» refers to, [title, ...] in order: numbered ## sections of summary.md,
    or «## Вопрос N. Title» of primer.md (title without «Вопрос N.» and the trailing period)."""
    out = []
    if is_lab(lecture):
        for line in (lecture / "primer.md").read_text(encoding="utf-8").splitlines():
            m = re.match(r"^## Вопрос \d+\.\s*(.+?)\.?\s*$", line)
            if m:
                out.append(m.group(1))
        return out
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
    fence = None  # (строка начала, ```) внутри блока кода
    for i in range(start, len(lines)):
        no, line = i + 1, lines[i]
        m = FENCE.match(line)
        if fence or m:
            # блок кода целиком уходит в текущую часть вопроса как есть: # и - внутри — не разметка
            if fence and m and m.group(1) == fence[1] and not m.group(2):
                fence = None
            elif not fence:
                fence = (no, m.group(1), m.group(2))
                if q is None:
                    problems.append(f"{no}: блок кода вне вопроса")
                elif not m.group(2):
                    problems.append(f"{no}: блок кода без языка (```python, ```sql, ```java…)")
                elif m.group(2) == "mermaid":
                    problems.append(f"{no}: схема Mermaid — в тесте их нет")
                if q is not None and section in ("options", "points", "answer", "where"):
                    problems.append(f"{no}: блок кода после {'вариантов' if section == 'options' else 'ответа'} — "
                                    "код только в тексте вопроса, эталоне и разборе (в вариантах — `код` в строке)")
            if q is not None and section in ("body", "etalon", "explain"):
                q[section].append(line.rstrip())
            if fence and fence[0] != no and no - fence[0] == 21:
                problems.append(f"{fence[0]}: блок кода длиннее 20 строк — оставь то, что нужно для ответа")
            continue
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
        elif s.startswith(WHERE):
            section = "where"
            label = next(w for w in WHERE if s.startswith(w))
            q["where"] = (no, s[len(label):].strip(), label)
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
                q["etalon"].append(line.rstrip())
            elif section == "explain":
                q["explain"].append(line.rstrip())
            elif section == "points":
                problems.append(f"{no}: в «Ключевых пунктах» только список «- …»")
            elif section in ("answer", "options"):
                problems.append(f"{no}: текст после {'ответа' if section == 'answer' else 'вариантов'} без маркера "
                                "(«Разбор:», «Эталон:»…)")
    if fence:
        problems.append(f"{fence[0]}: блок кода не закрыт")
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
    lab = is_lab(lecture)
    where_label = WHERE[1] if lab else WHERE[0]
    src_name, unit = ("primer.md", "вопрос") if lab else ("summary.md", "раздел")
    if not any(re.match(r"^doc-kind:\s*\"?quiz\"?\s*$", m) for m in meta):
        problems.append("YAML: нет doc-kind: quiz")
    for key in ("title", "lab" if lab else "lecture", "course"):
        if not any(m.startswith(f"{key}:") for m in meta):
            problems.append(f"YAML: нет поля {key}")
    if not any(s.strip() for s in intro):
        problems.append("нет вступления перед первым уровнем")

    in_code = None
    for i, line in enumerate(md.splitlines(), 1):
        m = FENCE.match(line)
        if in_code or m:
            if in_code and m and m.group(1) == in_code and not m.group(2):
                in_code = None
            elif not in_code:
                in_code = m.group(1)
            continue
        if line.startswith("> [!"):
            problems.append(f"{i}: плашка {line.split()[1]} — в тесте их нет")
        line = CODE_SPAN.sub("``", line)  # код в строке: <T>, {…} и [^…] в нём — не разметка
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

    titles = [l["title"] for l in levels]
    if titles != [t for t, _ in LEVELS]:
        problems.append(f"уровни {titles} — нужны ровно {[t for t, _ in LEVELS]} в этом порядке")

    sections = summary_sections(lecture)
    if not sections:
        problems.append(f"в {src_name} не найдено разделов, на которые ссылаться")
    content = {n for n, t in enumerate(sections, 1) if lab or "организац" not in t.casefold()}
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
            if q["options"] and re.search(r"\b(перв|втор|трет|четв[её]рт|пят|последн)[а-я]* вариант|вариант[а-я]* \d",
                                          " ".join(q["explain"]), re.I):
                problems.append(f"{where}: разбор называет вариант по номеру — на сайте порядок случайный, "
                                "называй по содержанию")
            if q["type"] in ("single", "multi", "num") and not " ".join(q["explain"]).strip():
                problems.append(f"{where}: нет разбора")
            if not q["where"]:
                problems.append(f"{where}: нет «{where_label.strip('*')[:-1]}»")
            else:
                no, text, label = q["where"]
                if label != where_label:
                    problems.append(f"{no}: {q['id']}: метка {label} — в тесте к {'лабораторной' if lab else 'лекции'} "
                                    f"{where_label}")
                refs = REF.findall(text)
                if not refs:
                    problems.append(f"{no}: {q['id']}: {label} не вида «{unit} N «Название»»")
                for n, title in refs:
                    n = int(n)
                    if not 1 <= n <= len(sections):
                        problems.append(f"{no}: {q['id']}: {unit}а {n} нет в {src_name} (их {len(sections)})")
                    elif norm(title) != norm(sections[n - 1]):
                        problems.append(f"{no}: {q['id']}: {unit} {n} называется «{sections[n - 1]}», а не «{title}»")
                    else:
                        covered.setdefault(prefix, set()).add(n)

        types = [q["type"] for q in qs]
        count = lambda *ts: sum(t in ts for t in types)
        if prefix == "e":
            if count("num", "open"):
                problems.append(f"{level['line']}: на лёгком уровне только вопросы с выбором")
        lo, hi = (round(0.75 * len(content)), round(1.5 * len(content))) if lab else (len(content), 2 * len(content))
        if prefix in ("e", "m") and content and not lo <= len(qs) <= hi:
            warnings.append(f"«{level['title']}»: {len(qs)} вопросов при {len(content)} "
                            f"{'вопросах к защите' if lab else 'содержательных разделах'} (ориентир {lo}–{hi})")
        if prefix == "m":
            if not 1 <= count("open") <= 2:
                warnings.append(f"«{level['title']}»: открытых вопросов {count('open')} (ориентир 1–2)")
            if count("num") > 3:
                warnings.append(f"«{level['title']}»: числовых вопросов {count('num')} (ориентир 2–3)")
        if prefix == "h":
            lo, hi = (10, 12) if lab else (8, 10)
            if not lo <= len(qs) <= hi:
                warnings.append(f"«{level['title']}»: {len(qs)} вопросов (ориентир {lo}–{hi})")
            lo, hi, aim = (0.35, 0.65, "~½") if lab else (0.2, 0.5, "~⅓")
            if qs and not lo <= count("open") / len(qs) <= hi:
                warnings.append(f"«{level['title']}»: открытых {count('open')} из {len(qs)} (ориентир {aim})")
            multi_ref = sum(len(REF.findall(q["where"][1])) >= 2 for q in qs if q["where"])
            if multi_ref < 3:
                warnings.append(f"«{level['title']}»: вопросов на несколько разделов {multi_ref} (нужно ≥ 3)")

    choice = [q for q in questions(levels) if q["options"]]
    first = sum(q["options"][0][0] for q in choice)
    if len(choice) >= 6 and first > 0.5 * len(choice):
        warnings.append(f"верный вариант стоит первым в {first} из {len(choice)} вопросов с выбором — "
                        "расставь верные варианты на разные позиции")
    missing = sorted(content - covered["e"] - covered["m"])
    if missing:
        warnings.append(f"{'вопросы к защите' if lab else 'разделы'} без вопросов на лёгком и среднем уровне: "
                        + ", ".join(map(str, missing)))
    return levels, problems, warnings


def questions(levels):
    return [q for level in levels for q in level["questions"] if "id" in q]


def blind_order(q):
    """Порядок вариантов в quiz_blind.md: индексы вариантов quiz.md, перемешанные с зерном — id вопроса."""
    order = list(range(len(q["options"])))
    random.Random(q["id"]).shuffle(order)
    return order


def run_calc(lecture, levels):
    script = lecture / "work" / "quiz_calc.py"
    if not script.exists():
        has_num = any(q["type"] == "num" for q in questions(levels))
        return [f"нет {script}"] if has_num else []
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
            for k, i in enumerate(blind_order(q), 1):
                out.append(f"{k}. {q['options'][i][1]}")
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
            correct = {k for k, i in enumerate(blind_order(q), 1) if q["options"][i][0]}
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
