# text-extractor

Превращает видеозапись лекции и PDF слайдов в:

- **`transcript.txt`** — дословную расшифровку с таймкодами (Yandex SpeechKit v3);
- **`output/<лекция>_conspect.pdf`** — конспект, по которому можно познакомиться с материалом вместо прослушивания лекции (вёрстка LaTeX);
- **`report.md`** — отчёт: что сделано, какие были проблемы, что проверить вручную;
- **`quiz.md`** — тест для самопроверки по конспекту в трёх уровнях сложности (см. «Тест для самопроверки»).

Вторая команда, `/lab`, готовит учебник по вопросам к защите лабораторной из PDF с условием и, если есть, репозитория с решением (см. «Учебник по вопросам к лабораторной»).

Весь процесс ведёт Claude Code через slash-команду `/lecture` (`.claude/commands/lecture.md`). Главный агент готовит слайды, расшифровку и правку терминов, а заметки, разделы конспекта, схемы и вёрстку PDF поручает субагентам из `.claude/agents/`. Скрипты в `tools/` — вспомогательные, их можно запускать и вручную.

Обработка полуторочасовой лекции тратит примерно ~50 рублей на Yandex API и ~30% 5-часового лимита Claude Code при использовании Opus 5.5 на Medium thinking.
## Структура

```
.claude/commands/lecture.md   # сценарий команды /lecture (главный агент)
.claude/agents/               # субагенты команды /lecture:
  lecture-notes.md            #   заметки по кускам расшифровки
  lecture-section.md          #   разделы конспекта
  lecture-figures.md          #   схемы со слайдов
  lecture-layout.md           #   сборка и проверка PDF
  lecture-quiz.md             #   тест для самопроверки (/quiz)
  lecture-quiz-solver.md      #   решение теста вслепую для проверки ключей (/quiz)
.claude/lecture/conspect.md   # общие правила конспекта: голос, стиль, разметка, структура
.claude/commands/quiz.md      # сценарий команды /quiz (тест к готовому конспекту; /lecture вызывает её шаги сам)
.claude/lecture/quiz.md       # правила теста: уровни, типы вопросов, разметка
.claude/lecture/quiz-sample.md # эталон разметки теста
tools/quiz_check.py           # проверка теста: разметка, ссылки на разделы, пересчёт чисел, сверка с решателем
.claude/commands/lab.md       # сценарий команды /lab (учебник по вопросам к защите лабы)
.claude/agents/lab-section.md #   субагент: один раздел учебника
.claude/lab/primer.md         # правила учебника: устройство раздела, разметка, схемы Mermaid
.claude/lab/sample.md         # эталон разметки учебника
tools/lab_check.py            # проверка учебника: все вопросы по порядку, ссылки, разметка
course.md                     # контекст курса и словарь терминов
tools/asr.py                  # извлечение звука, нарезка, отправка в SpeechKit, склейка результата
tools/latex/build.sh          # сборка PDF: summary.md / primer.md → pandoc → xelatex
tools/latex/conspect.tex      # LaTeX-шаблон конспекта
tools/latex/conspect.lua      # pandoc-фильтр разметки конспекта
env.example                   # шаблон .env
lectures/                     # входные материалы (в .gitignore)
labs/                         # лабораторные: условия и учебники (в .gitignore)
output/                       # готовые PDF (в .gitignore)
```

## Зависимости

- Python 3 с пакетами `requests` и `pymupdf`;
- `ffmpeg` / `ffprobe`;
- `pandoc`;
- XeLaTeX с пакетами `fontspec`, `polyglossia`, `tcolorbox`, `titlesec`, `tikz`, `needspace`, `newunicodechar`;
- шрифты **PT Serif**, **PT Sans** и **DejaVu Sans Mono**;
- [Claude Code](https://claude.com/claude-code) — для команды `/lecture`.

На Arch Linux:

```bash
sudo pacman -S ffmpeg python-requests python-pymupdf pandoc-cli \
  texlive-xetex texlive-latexrecommended texlive-latexextra texlive-pictures \
  texlive-langcyrillic texlive-fontsrecommended ttf-dejavu
```

Проверка:

```bash
kpsewhich fontspec.sty polyglossia.sty tcolorbox.sty titlesec.sty tikz.sty needspace.sty newunicodechar.sty
fc-list | grep -i "PT S"
```

## Настройка Yandex Cloud

1. Создайте сервисный аккаунт с ролью `ai.speechkit-stt.user` и API-ключ для него.
2. Скопируйте шаблон и заполните его:

   ```bash
   cp env.example .env
   ```

   ```
   YC_API_KEY=<API-ключ сервисного аккаунта>
   YC_FOLDER_ID=<ID каталога>
   ```

`.env` в `.gitignore`, не коммитьте его.

## Запуск

1. Положите материалы лекции в отдельную папку внутри `lectures/`:

   ```
   lectures/r1/
   ├── lecture.mp4     # видео: .mp4 / .mkv / .webm / .mov
   └── slides.pdf      # презентация
   ```

2. Запустите Claude Code в корне репозитория и выполните команду:

   ```
   /lecture lectures/r1
   ```

   Для дешёвого отложенного распознавания (результат может идти до суток):

   ```
   /lecture lectures/r1 --deferred
   ```

   Если папку не указать, команда возьмёт единственную необработанную лекцию из `lectures/`.

   Субагенты из `.claude/agents/` подхватываются при запуске Claude Code: после их правки перезапустите сессию.

3. Результат:
   - `lectures/r1/transcript.txt` — расшифровка;
   - `lectures/r1/summary.md` — исходник конспекта;
   - `lectures/r1/report.md` — отчёт;
   - `lectures/r1/quiz.md` — тест для самопроверки;
   - `output/r1_conspect.pdf` — готовый конспект;
   - `lectures/r1/work/` — промежуточные файлы (части аудио, состояние распознавания, заметки, логи LaTeX).

Распознавание платное, поэтому его состояние хранится в `work/parts.json`, а шаги `submit`/`poll` идемпотентны: если процесс прервался, запустите `/lecture` для той же папки ещё раз, и уже отправленные части повторно оплачены не будут. Не удаляйте и не правьте `parts.json` и `*.ndjson` вручную.

## Ручной запуск скриптов

Распознавание (`W` — рабочая папка, например `lectures/r1/work`):

```bash
python tools/asr.py extract lectures/r1/lecture.mp4 W/audio.mp3  # моно MP3, ~22 МБ/час
python tools/asr.py split   W/audio.mp3 W                         # части по ~25 мин по паузам → W/parts.json
python tools/asr.py submit  W --only 0                            # пробная отправка первой части
python tools/asr.py submit  W [--deferred]                        # остальные части
python tools/asr.py poll    W 90                                  # проверка статуса и скачивание готовых частей
python tools/asr.py parse   W W/segments.json                     # склейка частей с учётом сдвигов
```

`poll` повторяйте, пока все части не будут скачаны.

Сборка PDF из готового `summary.md`:

```bash
tools/latex/build.sh lectures/r1   # → output/r1_conspect.pdf, лог: lectures/r1/work/latex/summary.log
```

## Учебник по вопросам к лабораторной

1. Положите PDF с условием (требования и список вопросов к защите) в отдельную папку внутри `labs/`:

   ```
   labs/db-2/
   └── task.pdf
   ```

2. Выполните команду; ссылка на репозиторий с решением и `--pdf` — необязательны:

   ```
   /lab labs/db-2 https://github.com/user/db-lab-2 --pdf
   ```

   С репозиторием в разделах появляются блоки «В твоей работе» с цитатами кода и тем, как защищать принятые решения. Репозиторий клонируется в `labs/db-2/work/repo` только для чтения: код из него не запускается.

3. Результат:
   - `labs/db-2/primer.md` — учебник: по разделу на каждый вопрос (постановка, разбор, примеры кода, схемы Mermaid, подводные камни, дополнительные вопросы). Читается в любом просмотрщике Markdown;
   - `labs/db-2/report.md` — расхождения условия с практикой, допущения, слабые места;
   - с `--pdf`: `output/db-2_questions.pdf`.

Для схем в PDF нужен Mermaid CLI: `npm i -g @mermaid-js/mermaid-cli`. Без него PDF собирается, но схемы в нём остаются кодом.

Ручная проверка и сборка:

```bash
python tools/lab_check.py labs/db-2                        # вопросы по порядку, ссылки, разметка
tools/latex/build.sh labs/db-2 primer.md questions         # → output/db-2_questions.pdf
```

## Тест для самопроверки

`/lecture` в конце составляет тест по конспекту, `/lab` — по учебнику к лабораторной. Для уже обработанной лекции или лабы его можно составить отдельно:

```
/quiz lectures/r2
/quiz labs/web_lab3
```

Тест — `lectures/r2/quiz.md`, три уровня: лёгкий (термины и определения, только выбор ответа), средний (понимание, простые расчёты, 1–2 открытых вопроса), сложный (расчёты в несколько шагов, связь разделов, открытые вопросы). У каждого вопроса — разбор и ссылка на раздел конспекта. Вопросы составляются только по `summary.md`. Числовые ответы пересчитывает скрипт `work/quiz_calc.py`, а весь тест решает вслепую отдельный субагент; расхождения с ключом разбираются и попадают в `report.md`.

Тест к лабораторной составляется по `primer.md` и устроен как репетиция защиты: лёгкий уровень — термины и факты, средний — понимание, «что вернёт этот код», «плохо / хорошо», сложный — открытые вопросы как на защите, вопросы по коду работы из блоков «В твоей работе» и по расхождениям с практикой. Ссылки ведут на вопрос учебника; в вопросах, эталонах и разборах бывают блоки кода.

На сайте конспектов тест — страница «Проверить себя» рядом с конспектом или учебником: вопросы проверяются сразу, открытые оцениваются самостоятельно по эталону, лучший результат по уровням сохраняется. Все тесты собраны на странице «Тесты» (ссылка в шапке сайта).

Ручная проверка:

```bash
python tools/quiz_check.py lectures/r2           # разметка, типы вопросов, ссылки на разделы конспекта
python tools/quiz_check.py lectures/r2 --calc    # + пересчёт числовых ответов work/quiz_calc.py
```

## Словарь курса

`course.md` описывает курс, правильное написание терминов и типичные искажения SpeechKit. По нему исправляются термины в расшифровке, и после каждой лекции он пополняется. Сейчас это «Рекомендательные системы» (VK Education). Для лекций другого курса замените содержимое файла.
