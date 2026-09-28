# text-extractor

Превращает видеозапись лекции и PDF слайдов в:

- **`transcript.txt`** — дословную расшифровку с таймкодами (Yandex SpeechKit v3);
- **`output/<лекция>_conspect.pdf`** — конспект, по которому можно познакомиться с материалом вместо прослушивания лекции (вёрстка LaTeX);
- **`report.md`** — отчёт: что сделано, какие были проблемы, что проверить вручную.

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
.claude/lecture/conspect.md   # общие правила конспекта: голос, стиль, разметка, структура
course.md                     # контекст курса и словарь терминов
tools/asr.py                  # извлечение звука, нарезка, отправка в SpeechKit, склейка результата
tools/latex/build.sh          # сборка PDF: summary.md → pandoc → xelatex
tools/latex/conspect.tex      # LaTeX-шаблон конспекта
tools/latex/conspect.lua      # pandoc-фильтр разметки конспекта
env.example                   # шаблон .env
lectures/                     # входные материалы (в .gitignore)
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

## Словарь курса

`course.md` описывает курс, правильное написание терминов и типичные искажения SpeechKit. По нему исправляются термины в расшифровке, и после каждой лекции он пополняется. Сейчас это «Рекомендательные системы» (VK Education). Для лекций другого курса замените содержимое файла.
