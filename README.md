# Project Calc

Инструмент для расчёта состава и стоимости комплектующих промышленного
оборудования по историческим проектам. Инженер кладёт `input.xlsx`
с участком линии, наименованием оборудования и количеством — получает
`result.xlsx` со списком комплектующих, ценами и пометками о качестве
подбора.

Под капотом — SQLite-БД, наполненная парсером из исторических расчётов,
и FAISS-индекс на эмбеддингах `intfloat/multilingual-e5-base` для
fallback-поиска по похожим названиям.

---

## Два режима использования

### У пользователя — `calculator.exe`

Релизный bundle (PyInstaller `--onedir`) с предзаполненной БД и индексом.
Работает оффлайн, без Python, без прав администратора. Пользователь
кладёт `input.xlsx` в `data/input/`, двойным кликом запускает exe,
через 10–30 секунд получает `data/output/result.xlsx`.

Подробности — в опциональном `docs/USER_GUIDE.md`.

### У разработчика — Python-окружение

Полный набор: парсер (наполнение БД из исторических xlsx), генератор
(то же, что в exe — для отладки), индексер, скрипты сборки релиза.

Подробности — в [`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md).

---

## Структура репозитория

```
project_calc/
├─ common/           общая инфраструктура (config, БД, логгер, retrieval)
├─ parser/           DEV-ONLY: наполнение SQLite из xlsx
└─ generator/        USER-FACING: расчёт по input.xlsx → result.xlsx (в exe)

scripts/             init_db, build_index, check_db, build_release,
                     download_model, package_release.bat, run.bat,
                     calibrate_confidence
template/            template.xlsx — шаблон result.xlsx (правится без пересборки)
data/                рабочие данные (database.db, index/, raw_projects/,
                     input/, output/, logs/) — игнорируется git
models/              сохранённая ML-модель — игнорируется git
docs/                DEV_GUIDE.md (+ опциональный USER_GUIDE.md)
calculator.spec      PyInstaller-конфиг
```

**Архитектурный инвариант:** `generator/` никогда не импортирует из
`parser/`. Это позволяет PyInstaller собрать минимальный bundle с
entry point `project_calc.generator`, не утянув в exe код парсера.

---

## Быстрый старт (разработчик)

```
# 1. Окружение
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. ML-модель (один раз, нужен интернет)
python scripts/download_model.py

# 3. Положить исторические xlsx в data/raw_projects/

# 4. Собрать БД + FAISS-индекс одной командой
python scripts/build_release.py

# 5. Прогнать генератор для проверки
python -m project_calc.generator

# 6. (опционально) Собрать exe для пользователя
scripts\package_release.bat
```

Подробное описание каждого шага, опции CLI, формат входных файлов,
поведение на ошибках, обновление БД у пользователя — в
[`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md).

---

## Связанные документы

| Файл | Кому | О чём |
|---|---|---|
| [`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md) | разработчик | как запускать парсер/генератор, как обновлять БД на dev и у пользователя |
| `docs/USER_GUIDE.md` (опционально) | инженер | как пользоваться `calculator.exe` |
| [`REFACTORING_PLAN.md`](REFACTORING_PLAN.md) | разработчик | архитектурные решения, история этапов, SQL/PyInstaller-заметки |
