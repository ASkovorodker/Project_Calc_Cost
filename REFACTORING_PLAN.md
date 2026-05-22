# План доработок Project_Calc

Документ фиксирует архитектурные решения и порядок работ по переходу
от текущего состояния (Postgres + консольный запуск) к релизной версии
(SQLite + offline exe для Windows 11 без интернета и без прав администратора).

---

## 1. Цель

Превратить проект в готовое приложение для инженера:

- Один `calculator.exe` под Windows 11 Pro
- Запуск двойным кликом
- Работает оффлайн (без интернета на машине пользователя)
- Не требует прав администратора
- Никаких зависимостей кроме самого exe и его рабочей папки

Парсер на машину пользователя **не уезжает** — он остаётся инструментом
разработчика для наполнения БД.

---

## 2. Принятые архитектурные решения

| Вопрос | Решение |
|---|---|
| Формат поставки | PyInstaller `--onedir` exe (не Docker) |
| База данных | SQLite (без миграции с Postgres — пересобираем с нуля) |
| ML-модель | `intfloat/multilingual-e5-base`, упакована в exe, оффлайн-режим |
| FAISS-индекс | Строится на dev-машине, едет в составе релиза |
| База данных у пользователя | Едет готовая (`database.db`), наполненная парсером на dev-машине |
| Парсер у пользователя | Отсутствует — только у разработчика |
| Имя пакета | `project_calc` (вместо `project_parser`) |
| Расположение данных у пользователя | Рядом с exe в подпапке `data/` |
| Шаблон Excel | Снаружи exe — чтобы менять без пересборки |
| ОС сборки | Windows (та же, на которой ведётся разработка) |

---

## 3. Финальная структура у пользователя

```
C:\Users\<user>\Desktop\Project_Calc\
├─ calculator.exe          # PyInstaller --onedir, основной бинарь
├─ _internal\              # папка с зависимостями (PyInstaller)
├─ template.xlsx           # шаблон расчёта, можно править вручную
├─ run.bat                 # опциональная обёртка для двойного клика
└─ data\
   ├─ database.db          # SQLite, read-only при работе
   ├─ index\
   │  ├─ equipment.index           # FAISS
   │  └─ equipment_meta.json
   ├─ input\
   │  └─ input.xlsx                # кладёт инженер
   ├─ output\
   │  └─ result.xlsx               # появляется после запуска
   └─ logs\
      └─ log.txt
```

Сценарий работы пользователя:

1. Положить `input.xlsx` в `data/input/`
2. Дабл-клик `calculator.exe` (или `run.bat`)
3. Через 10–30 сек получить `data/output/result.xlsx`
4. При проблемах смотреть `data/logs/log.txt`

---

## 4. Структура проекта на dev-машине после рефакторинга

```
project_calc/                          # был project_parser
├─ __init__.py
│
├─ common/                             # общее, попадает и в exe, и в парсер
│  ├─ __init__.py
│  ├─ config.py                        # DB_PATH, INDEX_PATH, MODEL_PATH
│  ├─ db/
│  │  ├─ __init__.py
│  │  ├─ connection.py                 # sqlite3 + PRAGMA foreign_keys
│  │  └─ schema/
│  │     └─ init_sqlite.sql            # схема БД
│  ├─ logging_/
│  │  └─ logger.py
│  └─ retrieval/
│     ├─ embedder.py                   # модель и эмбеддинги
│     ├─ search_service.py             # поиск по индексу (для генератора)
│     └─ confidence.py
│
├─ parser/                             # DEV-ONLY, не попадает в exe
│  ├─ __init__.py
│  ├─ __main__.py                      # python -m project_calc.parser
│  ├─ excel/
│  │  └─ reader.py
│  ├─ normalize/
│  │  └─ normalizer.py
│  ├─ validation/
│  │  └─ validator.py
│  ├─ db_writer.py                     # INSERT в БД (был db/writer.py)
│  └─ index_builder.py                 # строит FAISS из SQLite
│
└─ generator/                          # USER-FACING, идёт в exe
   ├─ __init__.py
   ├─ __main__.py                      # python -m project_calc.generator
   ├─ input_reader.py
   ├─ query_service.py
   └─ excel_generator.py

scripts/                               # dev-обёртки
├─ init_db.py                          # создать пустую SQLite
├─ run_parser.py                       # обёртка вокруг parser
├─ build_index.py                      # обёртка вокруг index_builder
└─ build_release.py                    # сборка release-bundle для PyInstaller

tests/
├─ test_common/
├─ test_parser/
└─ test_generator/

template/
└─ template.xlsx

data/                                  # для разработки
├─ raw_projects/                       # 135 xlsx для парсера
├─ input/
├─ output/
├─ database.db                         # генерируется парсером
└─ index/
   ├─ equipment.index
   └─ equipment_meta.json

models/                                # сохранённая модель для упаковки
└─ multilingual-e5-base/

requirements.txt                       # для генератора (попадает в exe)
requirements-dev.txt                   # добавляет парсерные зависимости
.gitignore
README.md
REFACTORING_PLAN.md                    # этот файл
calculator.spec                        # PyInstaller spec (создаётся на этапе Д)
```

### Инвариант, который соблюдаем

`generator/` **никогда не импортирует** из `parser/`. Это позволяет
PyInstaller построить граф зависимостей с entry point
`project_calc.generator` и не утянуть в exe код парсера.

---

## 5. Карта переезда файлов

| Текущее расположение | Новое расположение |
|---|---|
| `project_parser/main.py` | `project_calc/parser/__main__.py` |
| `project_parser/excel/` | `project_calc/parser/excel/` |
| `project_parser/normalize/` | `project_calc/parser/normalize/` |
| `project_parser/validation/` | `project_calc/parser/validation/` |
| `project_parser/db/writer.py` | `project_calc/parser/db_writer.py` |
| `project_parser/retrieval/index_builder.py` | `project_calc/parser/index_builder.py` |
| `project_parser/generator/main.py` | `project_calc/generator/__main__.py` |
| `project_parser/generator/input_reader.py` | `project_calc/generator/input_reader.py` |
| `project_parser/generator/query_service.py` | `project_calc/generator/query_service.py` |
| `project_parser/generator/excel_generator.py` | `project_calc/generator/excel_generator.py` |
| `project_parser/db/connection.py` | `project_calc/common/db/connection.py` |
| `BD Scripts/Create_structure_DB.sql` | `project_calc/common/db/schema/init_sqlite.sql` (адаптировать) |
| `project_parser/config.py` | `project_calc/common/config.py` |
| `project_parser/logging_/` | `project_calc/common/logging_/` |
| `project_parser/retrieval/embedder.py` | `project_calc/common/retrieval/embedder.py` |
| `project_parser/retrieval/search_service.py` | `project_calc/common/retrieval/search_service.py` |
| `project_parser/retrieval/confidence.py` | `project_calc/common/retrieval/confidence.py` |
| `project_parser/retrieval/index_data/` | `data/index/` |
| `project_parser/generator/template/template.xlsx` | `template/template.xlsx` |
| `equipment.index`, `equipment_meta.pkl` (root) | удалить (дубли) |
| `test_*.py` (root) | `tests/` или удалить как пробники |
| `build_index.py` (root) | `scripts/build_index.py` |
| `.env` | удалить из репо, добавить в `.gitignore` |

---

## 6. Этапы работ

### Этап Б — SQLite + рефакторинг + переименование (1.5–2 дня)

Самая крупная работа. Выполняется в одной ветке, целиком, потом мерджится.

**Шаги:**

1. Создать новую структуру каталогов `project_calc/common/`, `project_calc/parser/`, `project_calc/generator/` рядом со старой
2. Создать `project_calc/common/db/schema/init_sqlite.sql` — адаптация текущей схемы:
   - `SERIAL PRIMARY KEY` → `INTEGER PRIMARY KEY AUTOINCREMENT`
   - `DATE DEFAULT CURRENT_DATE` → `TEXT DEFAULT CURRENT_DATE`
   - `NUMERIC`, `TEXT`, `CHECK`, `UNIQUE`, `REFERENCES ... ON DELETE CASCADE` остаются
3. Переписать `connection.py` под `sqlite3`:
   - `PRAGMA foreign_keys = ON` при каждом подключении
   - `row_factory = sqlite3.Row`
   - Поддержка `read_only=True` (URI `file:...?mode=ro`)
   - Создание родительской папки если её нет
4. Создать `project_calc/common/config.py`:
   - `DB_PATH` через `os.getenv` с дефолтом `app_dir() / "data" / "database.db"`
   - `INDEX_PATH`, `INDEX_META_PATH`
   - `MODEL_PATH`
   - `TEMPLATE_PATH`
   - Хелпер `app_dir()` с поддержкой `sys.frozen` для PyInstaller
5. Перенести `embedder.py`, `search_service.py`, `confidence.py` в `common/retrieval/`. Поправить пути в `search_service.py` — читать индекс из `INDEX_PATH`/`INDEX_META_PATH` из конфига
6. Перенести `logging_/` в `common/logging_/`
7. Перенести `db/writer.py` → `parser/db_writer.py`. Обновить SQL:
   - `%s` → `?`
   - Для `equipment`: `INSERT OR IGNORE`, затем `SELECT id` для получения id
   - Для `costs`: условный UPSERT (см. раздел 7.1)
   - Для `components`: вставлять только если `equipment` создана впервые (новый id)
8. Перенести `excel/`, `normalize/`, `validation/` в `parser/`. Импорты подправить
9. Перенести `index_builder.py` → `parser/index_builder.py`. Подправить плейсхолдеры в SQL, прописать запись в `data/index/`
10. Создать `parser/__main__.py` с CLI-аргументами (папка с raw_projects, путь к БД)
11. Перенести `generator/main.py` → `generator/__main__.py`. Убрать `argparse` — пути читаются из конфига
12. Подправить импорты во всех новых файлах: `from project_parser.X` → `from project_calc.X`
13. Удалить старые файлы и папки `project_parser/`
14. Очистить `requirements.txt` от `psycopg2-binary`, `pandas` (если генератор не использует)
15. Создать `requirements-dev.txt` с парсерными зависимостями
16. Создать `.gitignore` с `__pycache__/`, `*.pyc`, `dist/`, `build/`, `.env`, `data/database.db`, `data/index/`, `models/`
17. Удалить `.env` из репо (не из локалки), сменить пароль на dev-машине

**Проверки в конце Этапа Б:**

- [ ] `python scripts/init_db.py` — создаёт пустую `data/database.db` по схеме
- [ ] `python -m project_calc.parser --input data/raw_projects/` — наполняет БД
- [ ] Повторный запуск парсера на тех же файлах не падает (UPSERT-логика работает)
- [ ] `python scripts/build_index.py` — строит FAISS из SQLite
- [ ] `python -m project_calc.generator` — обрабатывает `data/input/input.xlsx`, выдаёт `data/output/result.xlsx`
- [ ] Тесты проходят
- [ ] `psycopg2` в коде нет нигде (`grep -r psycopg2 project_calc/` пусто)

### Этап В — Offline ML-модель (полдня)

1. Один раз сохранить модель локально:
   ```python
   from sentence_transformers import SentenceTransformer
   m = SentenceTransformer("intfloat/multilingual-e5-base")
   m.save("./models/multilingual-e5-base")
   ```
2. Подправить `common/retrieval/embedder.py`:
   ```python
   import os, sys
   from pathlib import Path
   from project_calc.common.config import MODEL_PATH

   class Embedder:
       def __init__(self, model_path: Path = MODEL_PATH):
           self.model = SentenceTransformer(str(model_path))
   ```
3. В `generator/__main__.py` в самом начале, до импорта sentence_transformers:
   ```python
   os.environ["TRANSFORMERS_OFFLINE"] = "1"
   os.environ["HF_HUB_OFFLINE"] = "1"
   ```
4. Проверить запуск без интернета (отключить сеть, запустить генератор)

**Проверки:**

- [ ] Модель сохранена в `models/multilingual-e5-base/`
- [ ] Embedder читает модель локально
- [ ] Генератор работает с отключённым интернетом

### Этап Г — Подготовка release-bundle (1 день)

Скрипт `scripts/build_release.py`, который собирает всё, что нужно для PyInstaller:

1. Удаляет старый `release/` если был
2. Создаёт пустую `data/database.db` через `init_sqlite.sql`
3. Запускает парсер на `data/raw_projects/`
4. Запускает `index_builder` → строит `data/index/equipment.index` + `equipment_meta.json`
5. Проверяет наличие `models/multilingual-e5-base/`
6. Печатает размеры артефактов (для контроля размера exe)

**Проверки:**

- [ ] Скрипт запускается одной командой
- [ ] После прогона в `data/` лежат заполненные `database.db` и `index/`
- [ ] Размер `data/database.db` логирован

### Этап Д — PyInstaller сборка (1–2 дня с отладкой)

1. Создать `calculator.spec`:
   - entry point: `project_calc/generator/__main__.py`
   - `collect_all` для `sentence_transformers`, `transformers`, `tokenizers`, `torch`
   - `datas`:
     - `models/multilingual-e5-base` → `models/multilingual-e5-base`
     - `data/database.db` → `data/database.db`
     - `data/index/` → `data/index/`
     - `template/template.xlsx` → `template.xlsx`
   - режим `--onedir`
2. `pyinstaller calculator.spec --noconfirm`
3. Получить `dist/calculator/calculator.exe`
4. Создать `run.bat` (опционально):
   ```bat
   @echo off
   cd /d "%~dp0"
   calculator.exe
   pause
   ```
5. Запаковать `dist/calculator/` в `release.zip` для распространения

**Подводные камни:**

- faiss на Windows может потребовать `--collect-binaries faiss`
- sentence_transformers тащит динамические импорты — `--collect-all` обязателен
- Антивирус Windows может карантинить unsigned exe — учесть при тестировании

**Проверки:**

- [ ] exe собирается без ошибок
- [ ] Размер `dist/calculator/` — фиксируем в логе (ожидаем 1.5–2.5 GB)
- [ ] exe запускается на dev-машине

### Этап Е — Тестирование на чистой машине (полдня)

Берём чистую Windows 11 Pro без Python, без админских прав, без интернета:

1. Распаковать `release.zip` в `Desktop\Project_Calc\`
2. Положить тестовый `input.xlsx` в `data/input/`
3. Дабл-клик `calculator.exe`
4. Проверить:
   - [ ] Запускается без интернета
   - [ ] Запускается без админских прав
   - [ ] Через 10–30 сек появляется `data/output/result.xlsx`
   - [ ] Excel-формулы пересчитались
   - [ ] При битом `input.xlsx` — понятная ошибка в `log.txt`, без падения
   - [ ] Повторный запуск работает

### Этап Е.1 — Доработки по итогам тестирования на чистой Windows

Все три пункта вылезли при ручной проверке собранного exe на чистой
машине пользователя. Решаются точечными правками в `generator/__main__.py`,
`generator/excel_generator.py` и `common/retrieval/confidence.py`.

#### Е.1.1 (функционал) Сохранять оригинальное название оборудования при retrieval-подмене

**Проблема.** Когда прямой поиск не находит, retrieval подбирает ближайшее
из БД и `get_components_by_id` возвращает `equipment_name` уже из БД.
В `result.xlsx` оказывается имя из БД, и инженер не понимает, какое
именно оборудование из его `input.xlsx` было подменено.

**Решение.** В `generator/__main__.py` после успешного retrieval-матча
формировать составное имя:

```python
combined = f"{input_equipment_name} — {best_match['equipment_name']}"
for comp in components:
    comp["equipment"] = combined
```

Имя из `input.xlsx` идёт первым (это то, что искал инженер), затем
после тире — какое оборудование на самом деле взято из БД.
При прямом поиске составное имя не нужно — они и так совпадают.

#### Е.1.2 (функционал) Колонка "Статус" в result.xlsx

**Проблема.** В `result.xlsx` нет признака, как именно нашлась строка
состава. Инженеру нужно после прогона фильтровать по статусу: что прошло
автоматически, что требует ручной проверки, что не нашлось вообще.

**Решение.**

(а) Пользователь добавит колонку `Статус` в `template.xlsx` —
номер колонки определит сам.

(б) В `generator/excel_generator.py` записывать `status` в эту колонку
(номер колонки прокинуть параметром или константой).

(в) В `generator/__main__.py` присваивать `status` каждому элементу
`full_data` по правилу:

| Источник | Status   |
|---|---|
| Прямое попадание `get_components_for_equipment` | `DIRECT` |
| Retrieval с decision = ACCEPT  | `RETRIEVAL_ACCEPT` |
| Retrieval с decision = REVIEW  | `RETRIEVAL_REVIEW` |
| Retrieval с decision = REJECT, или нет ни в БД, ни в retrieval | `REJECT` |

Это даёт инженеру явный фильтр: `DIRECT` — точно ок, `RETRIEVAL_ACCEPT` —
скорее всего ок, `RETRIEVAL_REVIEW` — обязательная проверка, `REJECT` —
нет в БД, надо добавить.

Альтернативно, если три значения достаточно (без подразделения retrieval'а):
`DIRECT` / `RETRIEVAL` / `REJECT` — обсудить с пользователем.

#### Е.1.3 (отладка) Настройка confidence — REJECT для нерелевантных запросов

**Проблема.** На запросе вроде "Сварочный источник" (нет в БД и тематически
не пересекается с тем, что в БД есть) retrieval всё равно может выдать
ACCEPT или REVIEW, потому что эмбеддинг подбирает хоть какое-то ближайшее
оборудование.

**Текущие пороги** (в `common/retrieval/confidence.py`):
- `top < 0.80` → `REJECT`
- `top >= 0.87` и `gap > 0.05` → `ACCEPT`
- `top >= 0.83` → `REVIEW`
- иначе → `REJECT`

**Контекст.** Calibration confidence — статистическая задача. Чтобы пороги
работали хорошо в проде, распределения "хороших" и "плохих" запросов
должны быть стабильны. У пользователя сейчас в БД ~85 единиц оборудования
(2 проекта). С ростом БД до целевых ~135 проектов распределения сильно
изменятся: confidence нерелевантных запросов снизится естественным
образом (модель найдёт меньше "похожих по словам"), появятся реальные
близкие соседи (например, `Конвейер ленточный 600мм` vs `800мм`),
нужны будут не только новые пороги, но возможно дополнительные эвристики.

Поэтому делим Е.1.3 на три части: быстрый фикс сейчас, подготовка
инструмента калибровки, полная калибровка после набора ~70-100 проектов.

##### Е.1.3.А (сейчас) Быстрый фикс порогов

Минимальная правка, которая снимет самые шумные ACCEPT/REVIEW без
претензий на оптимальность. Цель — сделать "Сварочный источник" → REJECT,
сохранив поведение для нормальных запросов.

В `common/retrieval/confidence.py` поднять все пороги на 0.03-0.05:
- `top < 0.80` → `0.83` (минимум для не-REJECT)
- `top >= 0.83` → `0.86` (минимум для REVIEW)
- `top >= 0.87` → `0.90` (минимум для ACCEPT)
- `gap > 0.05` для ACCEPT — оставляем

Эти пороги не оптимальные, но **переживут пополнение БД** до момента
полной калибровки. Если у пользователя есть несколько проблемных
запросов "из реальной жизни" — после фикса прогнать их вручную через
exe, убедиться что они уходят в REJECT.

**Действия:**
- [ ] Поднять пороги в `ConfidenceEvaluator.evaluate()` (5-минутная правка).
- [ ] Пересобрать exe через `scripts\package_release.bat`.
- [ ] Прогнать на проблемных запросах ("Сварочный источник" и подобные).
- [ ] Зафиксировать новое поведение в истории плана.

##### Е.1.3.Б (сейчас, опционально) Инструмент калибровки

Скрипт `scripts/calibrate_confidence.py`, который автоматизирует сбор
данных для будущей полной калибровки. Делается сейчас, пока контекст
свежий — потом проще пользоваться.

**Вход:** CSV `data/calibration/queries.csv` с колонками:
- `query` — текст запроса (имя оборудования, как в input.xlsx)
- `expected_area` — участок (как в input.xlsx)
- `expected_label` — `positive` (есть в БД, должно найтись) или
  `negative` (нет в БД и нет связи с темой)

**Что делает:**
1. Прогоняет каждый query через `SearchService.search(query, expected_area)`.
2. Сохраняет в `data/calibration/results.csv` колонки:
   - query, expected_label, expected_area
   - top1_similarity, top2_similarity, gap
   - top1_equipment_name, top1_area, top1_area_matches
   - top5_similarities (как список)
   - decision (что вернул ConfidenceEvaluator)
3. Печатает короткую статистику:
   - min/max/mean top1 для positive и negative
   - количество ложных положительных (negative с decision ≠ REJECT)
   - количество ложных отрицательных (positive с decision = REJECT)
   - рекомендуемые пороги по простому квантильному правилу

**Зачем сейчас:** когда наступит момент полноценной калибровки,
пользователь соберёт CSV с запросами (20-40 positive + 15-30 negative)
и одной командой получит готовые числа для новых порогов. Без подготовки
инструмента — собирать вручную утомительно.

##### Е.1.3.В (через 70-100 проектов в БД) Полная калибровка

Когда БД достигнет ~50-70% целевого размера, распределения стабилизируются,
и можно делать настоящую калибровку:

1. **Подготовить датасеты:**
   - 20-40 positive запросов: точные имена из БД, опечатки, сокращения,
     синонимы. Цель — модель должна попадать в ACCEPT/REVIEW.
   - 15-30 negative запросов: тематически нерелевантные (3D-принтер,
     котёл, сварочный источник, ЧПУ-станок, ...). Цель — REJECT.
2. **Прогнать `scripts/calibrate_confidence.py`** на этом датасете.
3. **Проанализировать распределения:**
   - Гистограмма top1 для positive vs negative.
   - Точки квантилей: минимум top1 у positive (нижняя граница "обязательно
     принять"), максимум top1 у negative (верхняя граница "обязательно
     отбросить"), серая зона между ними = REVIEW.
   - Корреляция с gap: бывает, top1 высокий, но top2 тоже — модель
     колеблется, тогда даже при высоком top1 уместно REVIEW.
4. **Принять решение по эвристикам:**
   - Финальные пороги для ACCEPT/REVIEW/REJECT.
   - Жёсткий penalty за несовпадение `area` (сейчас 0.92, возможно
     стоит снизить до 0.7-0.8 или сразу REJECT при полном отсутствии
     участка в БД).
   - Минимальная длина запроса для попадания в ACCEPT (однословные
     запросы тяжело различать — можно их сразу в REVIEW).
   - Confidence-margin (требовать `top1 > threshold AND gap > min_gap`).
5. **Прогнать тот же датасет повторно** с новыми порогами, убедиться
   что false-positive и false-negative ниже целевого уровня.

### Этап Ж — Финальные мелочи

- [ ] **Создать `docs/DEV_GUIDE.md`** — инструкции для разработчика. Минимум четыре сценария:
    - **Запуск парсера** (`python -m project_calc.parser --input <папка|файл>`): что подаётся на вход, какие колонки должны быть в xlsx, опции `--db`, `--dry-run`, что считается "битой" строкой, где смотреть лог.
    - **Запуск генератора** (`python -m project_calc.generator [--input ... --template ... --output ...]`): какие колонки нужны в `input.xlsx` (3 колонки против 7 у парсера — важно не путать), что должно быть в БД и индексе чтобы он работал, как читать `result.xlsx`, статистика retrieval, пометка "НЕ НАЙДЕНО В БД".
    - **Обновление БД на dev-машине**: положить новые xlsx в `data/raw_projects/` → парсер → перестроить индекс через `python -m project_calc.parser.index_builder` → проверить через `python scripts/check_db.py`. Поведение: components не дублируется, costs обновляется только при росте цены.
    - **Обновление БД у пользователя**: dev-сторона готовит свежие `database.db` + `data/index/equipment.index` + `equipment_meta.json` → копируются на машину пользователя поверх старых → пользователь просто запускает `calculator.exe`. Никаких миграций не требуется (генератор открывает БД read-only при каждом запуске).
- [ ] Обновить `README.md` под новую структуру: краткий обзор, ссылка на `docs/DEV_GUIDE.md`.
- [ ] Опционально: `docs/USER_GUIDE.md` — короткая инструкция для инженера, который кладёт `input.xlsx` и кликает `calculator.exe`.
- [ ] Документировать сценарий релиза для будущих обновлений (см. Этап Г + Д).
- [ ] Зафиксировать версии зависимостей в `requirements.txt`.
- [ ] Решить вопрос с code signing (если требуется для антивируса).

---

## 7. Технические заметки

### 7.1. UPSERT-логика парсера

**Equipment (UNIQUE по area, equipment_name):**
```sql
INSERT OR IGNORE INTO equipment (area, equipment_name) VALUES (?, ?);
SELECT id FROM equipment WHERE area = ? AND equipment_name = ?;
```
Возврат `id` через отдельный SELECT — потому что `RETURNING` не сработает,
если `INSERT` был проигнорирован.

**Costs (PK по component_name, unit) — условный UPSERT:**
```sql
INSERT INTO costs (component_name, unit, cost_with_vat, valid_from)
VALUES (?, ?, ?, CURRENT_DATE)
ON CONFLICT(component_name, unit) DO UPDATE SET
    cost_with_vat = excluded.cost_with_vat,
    valid_from    = CURRENT_DATE
WHERE excluded.cost_with_vat > costs.cost_with_vat;
```
Перезапись только если новая цена выше существующей. Иначе — игнор.

**Components (без UNIQUE):**
Состав вставляется **только если equipment создан впервые**. Если оборудование
уже было в БД — компоненты не дублируем, оставляем тот состав, что есть.

### 7.2. Пути к ресурсам в exe и в dev-режиме

В реализации (`project_calc/common/config.py`) три хелпера и список констант
с поддержкой env-override на всех ключевых путях:

```python
def app_dir() -> Path:
    """Папка с exe (release) или корень репо (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path:
    """sys._MEIPASS (release, --add-data ресурсы) или app_dir() (dev)."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else app_dir()


def resource_path(rel: str | Path) -> Path:
    """Ищем ресурс сначала в bundle_dir, потом в app_dir."""
    bundled = bundle_dir() / rel
    return bundled if bundled.exists() else app_dir() / rel


DATA_DIR        = Path(os.getenv("DATA_DIR",        app_dir() / "data"))
DB_PATH         = Path(os.getenv("DB_PATH",         DATA_DIR / "database.db"))
INDEX_DIR       = DATA_DIR / "index"
INDEX_PATH      = Path(os.getenv("INDEX_PATH",      INDEX_DIR / "equipment.index"))
INDEX_META_PATH = Path(os.getenv("INDEX_META_PATH", INDEX_DIR / "equipment_meta.json"))
MODEL_PATH      = Path(os.getenv("MODEL_PATH",      resource_path("models/multilingual-e5-base")))
TEMPLATE_PATH   = Path(os.getenv("TEMPLATE_PATH",   app_dir() / "template" / "template.xlsx"))
INPUT_PATH      = Path(os.getenv("INPUT_PATH",      DATA_DIR / "input"  / "input.xlsx"))
OUTPUT_PATH     = Path(os.getenv("OUTPUT_PATH",     DATA_DIR / "output" / "result.xlsx"))
LOG_PATH        = Path(os.getenv("LOG_PATH",        DATA_DIR / "logs"   / "log.txt"))


def ensure_dirs() -> None:
    """Создать data/input, data/output, data/logs и родителя БД."""
```

`MODEL_PATH` через `resource_path()` поддерживает оба сценария упаковки модели:
внутри PyInstaller-бандла (через `--add-data`, путь резолвится в `_MEIPASS`)
или рядом с exe в `models/`. Решение, какой из них использовать, оставлено
до Шага Д.

### 7.3. SQLite Connection — эскиз

```python
import sqlite3
from project_calc.common.config import DB_PATH


class DatabaseConnectionError(Exception):
    pass


def get_connection(read_only: bool = False) -> sqlite3.Connection:
    if read_only and not DB_PATH.exists():
        raise DatabaseConnectionError(f"БД не найдена: {DB_PATH}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if read_only:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn
```

### 7.4. Запуск всех процессов

| Процесс | Команда | Где |
|---|---|---|
| Создать пустую БД | `python scripts/init_db.py` | dev |
| Наполнить БД из xlsx | `python -m project_calc.parser --input data/raw_projects/` | dev |
| Построить FAISS | `python scripts/build_index.py` | dev |
| Сгенерировать расчёт | `python -m project_calc.generator` | dev и user (через exe) |
| Собрать релиз | `python scripts/build_release.py && pyinstaller calculator.spec` | dev |

---

## 8. Открытые вопросы (на потом)

- Code signing exe для устранения предупреждений Windows Defender
- Стратегия обновлений у пользователя (полная замена exe vs только `database.db`)
- Если БД вырастет за 1 GB — рассмотреть переход на DuckDB или вынос горячей/холодной частей
- Локальная LLM (Этап 9 исходного плана) — отложен до v2

---

## 9. Чек-лист готовности к v1

- [x] Этап Б — SQLite + рефакторинг + переименование
- [x] Этап В — Offline ML-модель
- [x] Этап Г — Build release-bundle скрипт
- [x] Этап Д — PyInstaller сборка (на dev-машине)
- [x] Этап Е — Тестирование на чистой машине
- [ ] Этап Е.1 — Доработки по итогам тестирования (см. ниже)
- [ ] Этап Ж — README, версии, документация
- [ ] Релиз `release.zip` лежит в готовом виде

---

## 10. История версий документа

| Дата | Изменение |
|---|---|
| 2026-05-09 | Первая версия плана |
| 2026-05-10 | Этап Б, Шаг 1 выполнен: создана структура каталогов `project_calc/` (common, parser, generator) с пустыми `__init__.py`. Старая `project_parser/` оставлена нетронутой — работаем параллельно. |
| 2026-05-10 | Этап Б, Шаг 2 выполнен: создан `project_calc/common/db/schema/init_sqlite.sql`. Адаптации: `SERIAL → INTEGER PRIMARY KEY AUTOINCREMENT`, `DATE → TEXT DEFAULT CURRENT_DATE`. Добавлены `IF NOT EXISTS` / `INSERT OR IGNORE` для идемпотентности и индекс `idx_components_equipment_id`. Схема прогнана на тестовой БД: проверены FK, CHECK, UNIQUE, CASCADE, условный UPSERT и повторное применение — все 8 проверок зелёные. |
| 2026-05-10 | Этап Б, Шаг 3 выполнен: создан `project_calc/common/db/connection.py`. `get_connection(db_path=None, read_only=False)`. Путь к БД: явный аргумент → `env DB_PATH` → fallback `cwd/data/database.db`. На каждом подключении — `PRAGMA foreign_keys = ON` и `row_factory = sqlite3.Row`. Read-only через URI `file:{path.as_posix()}?mode=ro` (posix-форма для совместимости Linux/Windows). Модуль не зависит от `config.py` — конфиг подключим на Шаге 4. Прогнаны 7 проверок: rw-открытие с автосозданием папки, PRAGMA, row_factory, FK CASCADE, чтение и запрет записи в read-only, ошибка при отсутствующей БД, env-fallback. |
| 2026-05-10 | Этап Б, Шаг 4 выполнен: создан `project_calc/common/config.py`. Хелперы `app_dir()`, `bundle_dir()`, `resource_path()`, `ensure_dirs()` + константы `DATA_DIR`, `DB_PATH`, `INDEX_PATH`, `INDEX_META_PATH`, `MODEL_PATH`, `TEMPLATE_PATH`, `INPUT_PATH`, `OUTPUT_PATH`, `LOG_PATH`. Все ключевые пути поддерживают env-override. По сравнению с эскизом раздела 7.2 добавлены `bundle_dir`/`resource_path` для гибкости с PyInstaller `--add-data` (модель может лежать как в `_MEIPASS`, так и рядом с exe — решение оставлено до Шага Д). Раздел 7.2 плана обновлён под реализацию. Прогнаны 7 проверок: dev-режим, env-override, эмуляция release через `sys.frozen` и `sys.executable`, `_MEIPASS` через `bundle_dir`, fallback `resource_path` на `app_dir`, `ensure_dirs`, связка `config + connection` через `env DB_PATH`. |
| 2026-05-10 | Этап Б, Шаг 5 выполнен: `embedder.py`, `confidence.py`, `search_service.py` перенесены в `project_calc/common/retrieval/`. `embedder` и `confidence` скопированы без изменений (внутрипроектных зависимостей у них нет). В `search_service.py` жёсткие пути к индексу и метаданным заменены на импорт из `config.INDEX_PATH` / `INDEX_META_PATH`, импорты `Embedder` и `ConfidenceEvaluator` идут из новых модулей, формат меты только JSON. Подмечен мёртвый pickle-формат в `project_parser/retrieval/index_builder.py` (`equipment_meta.pkl`) — это будет приведено к JSON на Шаге 9. Проверки: `py_compile` всех трёх, импорт через заглушки `sentence_transformers`/`faiss` (тяжёлых либ в sandbox нет), 7 юнит-кейсов `ConfidenceEvaluator`, статическая ревизия `search_service.py` (нет старых констант и `project_parser`-импортов, есть `INDEX_PATH`/`INDEX_META_PATH` и `json.load`), env-override через `INDEX_PATH` подхватывается, `_load_index` корректно падает на отсутствующих файлах. Старые файлы в `project_parser/retrieval/` нетронуты — удалим на Шаге 13. |
| 2026-05-10 | Этап Б, Шаг 6 выполнен: `logging_/logger.py` перенесён в `project_calc/common/logging_/`. Жёсткий `LOG_FILE = Path("parser.log")` заменён на импорт `LOG_PATH` из `config.py`. Имя логгера `"project_parser"` → `"project_calc"`. Перед созданием `FileHandler` добавлен `LOG_PATH.parent.mkdir(parents=True, exist_ok=True)` — логгер устойчив, даже если `ensure_dirs()` ещё не вызывался. API `LoggerWrapper` (методы `error`/`critical` с `row_number`/`message`/`payload`) сохранён без изменений. Прогнаны 7 проверок: `py_compile`, статический скан исходника, реальная запись `ERROR`/`CRITICAL` в файл с правильным форматом, `propagate=False`, идемпотентность `get_logger()` (после 3 вызовов один handler), отсутствие дублирования в `stderr`, старый файл нетронут. |
| 2026-05-10 | Этап Б, Шаг 7 выполнен: создан `project_calc/parser/db_writer.py`. **Изменение API относительно `project_parser/db/writer.py`**: per-row `write_row(row)` → блочный `write_equipment(area, equipment_name, items)`. Это нужно для корректной реализации правила 7.1 "не дублировать состав при повторе оборудования" — без блока пришлось бы предполагать упорядоченность строк Excel по equipment, что не гарантия. Сохранение `write_row` несовместимо с этим правилом и не нужно — старый writer остаётся в `project_parser/`, новый main парсера на Шаге 10 будет писаться сразу под блочный API (с группировкой строк перед вызовом). Реализация: psycopg2 → sqlite3, `%s` → `?`, `INSERT OR IGNORE INTO equipment` + `SELECT id` (вместо SELECT-then-INSERT-RETURNING), `executemany` для components, условный UPSERT для costs (`WHERE excluded.cost_with_vat > costs.cost_with_vat`). Транзакция: commit на успехе, rollback на любой ошибке. Возвращает stats `{equipment_new, components_added, costs_upserted}` для агрегации в парсере. Прогнаны 11 проверок на реальной SQLite: новое оборудование, повторное (без дублей состава), UPSERT cost (выше / ниже / равна), rollback при `CHECK qty>0`, пустой `items`, идемпотентность, связка через env `DB_PATH`. |
| 2026-05-10 | Этап Б, Шаг 8 выполнен: `excel/reader.py`, `normalize/normalizer.py`, `validation/validator.py` перенесены в `project_calc/parser/`. Все три модуля без внутрипроектных импортов, перенос байт-в-байт (подтверждено diff'ом). Прогнаны 6 проверок: `py_compile` всех трёх, импорт из новых мест, идентичность с оригиналами, юнит-тесты `Validator` (счастливый путь + 5 ошибочных кейсов: NULL, пусто, не-число, отрицательное, ноль), юнит-тесты `Normalizer` (alias `Шт./шт`, `Метров/м`, `Металлоконструкции/м-к`, `Комп./комп`, схлопывание пробелов), end-to-end на программно созданном Excel: ExcelReader → группировка по `(area, equipment_name)` → Validator → Normalizer → `DBWriter.write_equipment` → 4 строки превращаются в 2 equipment / 4 components / 4 costs в SQLite, юниты и типы в БД канонические. Это полная репетиция работы будущего `parser/__main__.py`. |
| 2026-05-10 | Этап Б, доработка Шага 8: три правки в `project_calc/parser/`. (1) В `excel/reader.py` исправлена опечатка `"Себестоиомость комплектующих, с НДС"` → `"Себестоимость комплектующих, с НДС"` (Excel со своей стороны будет обновлён). (2) В `normalize/normalizer.py` в `TYPE_ALIASES` добавлены варианты для типа `товар`: `товар`/`товары`/`тов.` → `товар` (тип уже был в схеме `component_types`, но не покрывался нормализатором). (3) В `excel/reader.py` исправлен type-warning PyCharm на `headers[cell.value] = idx` — теперь шапка собирается с фильтром `if cell.value is None: continue` и явным приведением к `str(cell.value)`, добавлена аннотация `headers: dict[str, int]`. Старые файлы в `project_parser/` оставлены с прежней опечаткой — их трогать нельзя, чтобы старая ветка продолжала работать. Прогнаны проверки: целостность UTF-8 (после первой попытки записи через `Edit` файлы оказывались обрезаны на половине кириллического байта — пришлось пере-записать через bash heredoc, тогда AST и py_compile прошли), 9 кейсов `normalize_type` для `товар` и старых алиасов, устойчивость headers-loop к `None` и нестроковым заголовкам, end-to-end на 4-строчном Excel с типами `Товары`/`комп.`/`Металлоконструкции`/`услуга` — все нормализовались, прошли FK на `component_types`, в БД 4 канонических типа. `grep` подтвердил, что опечатки `Себестоиомость` в `project_calc/` не осталось. |
| 2026-05-10 | Этап Б, Шаг 9 выполнен: `index_builder.py` перенесён в `project_calc/parser/`. Импорты переехали на `project_calc.common.retrieval.embedder` и `project_calc.common.db.connection`. Пути к артефактам подтянуты из конфига (`INDEX_PATH`, `INDEX_META_PATH`), параметры `index_path`/`meta_path` остались опциональными для override в тестах. Подключение к БД — `read_only=True`. **Главное содержательное изменение**: формат метаданных `pickle` → `json` — это устраняет рассинхрон с `search_service.py` (отмечен на Шаге 5). JSON записывается с `ensure_ascii=False, indent=2`, читается глазами. Добавлены: `mkdir(parents=True, exist_ok=True)` для родительской папки индекса перед записью и защита от пустой `equipment`-таблицы (`RuntimeError` вместо непонятного `np.array([]).shape[1]`). Прогнаны 5 проверок: AST-скан подтвердил отсутствие `pickle` и `project_parser`-импортов в коде (старые срабатывания статического grep были в docstring, где описан переход), end-to-end на тестовой БД с тремя записями оборудования: 3 объекта в индексе, JSON-мета с правильным контентом, `faiss.write_index` вызван с верными аргументами через заглушку, parent-папка создана, защита от пустой БД работает, контракт ключей JSON-меты (`equipment_id`, `equipment_name`, `area`) согласован с `search_service.search()`. |
| 2026-05-11 | Этап Б, Шаг 10 выполнен: создан `project_calc/parser/__main__.py` — entry-point парсера. Запуск через `python -m project_calc.parser`. CLI: `--input` (файл .xlsx или папка), `--db` (override `DB_PATH`), `--dry-run` (без записи). Pipeline: `ExcelReader → Validator → Normalizer → группировка по (area, equipment_name) → DBWriter.write_equipment`. Ошибки обрабатываются на двух уровнях: невалидная строка пишется как `ERROR` в `log.txt` с контекстом (имя файла, номер строки, raw-данные) и пропускается, остальные строки её группы всё равно собираются; ошибка записи блока (`IntegrityError`/FK) пишется как `CRITICAL` и парсер переходит к следующему оборудованию. Схема БД применяется автоматически при первом запуске через `init_sqlite.sql` (`CREATE TABLE IF NOT EXISTS` идемпотентно). Lock-файлы Excel (`~$*.xlsx`) фильтруются при сборе из папки. Return code: 0 если все блоки записаны, 1 если есть `groups_failed`. Прогнаны 8 проверок: один xlsx → 5 строк/2 equipment/5 components/5 costs, папка с 2 файлами и игнор lock-файла, dry-run (БД не создаётся), 4 битые строки логируются с контекстом и валидные продолжают писаться, `--db` перекрывает env, повторный запуск без дублей состава, `SystemExit` на несуществующем пути, `ValueError` от ExcelReader на Excel без нужной шапки. |
| 2026-05-11 | Этап Б, Шаг 11 выполнен: блок генератора перенесён в `project_calc/generator/`. Файлы: `input_reader.py` и `excel_generator.py` скопированы без правок (нет внутрипроектных импортов), `query_service.py` переписан под SQLite (`%s → ?`, импорт `get_connection` из `common.db.connection`, режим `read_only=True`), `__main__.py` создан с CLI с дефолтами из `config` (`INPUT_PATH`/`OUTPUT_PATH`/`TEMPLATE_PATH`). Шаблон `template.xlsx` физически перенесён из `project_parser/generator/template/` в `template/` в корне репозитория. **Содержательное изменение в `query_service.py`**: исправлен баг в `LEFT JOIN costs` — добавлено условие `AND cost.unit = c.unit`. Раньше JOIN был только по `component_name`, что давало дубли строк при наличии одинаковых имён компонентов с разными единицами. **Улучшение в `__main__.py`**: `SearchService` инициализируется лениво через обёртку `_LazySearch` — модель и FAISS-индекс грузятся только при первом промахе прямого поиска. В типичном сценарии "БД покрывает все запросы" ML-стек не трогается совсем, экономится 3-5 секунд старта. `_LazySearch.search()` также обрабатывает `FileNotFoundError` от отсутствующего индекса — генератор не падает, помечает блок как не найденный и продолжает работу. Прогнаны 5 проверок: end-to-end на тестовой БД с прямым поиском (4 строки в result.xlsx, формула `eq_qty × qty_per_eq` правильная, JOIN с costs корректный, модуль search_service в `sys.modules` НЕ загружен), Retrieval-fallback с lazy-инициализацией (модуль грузится при первом промахе, REJECT правильно даёт пометку), graceful handling отсутствующего индекса (rc=0 с пометкой), дефолты `parse_args` из config, `rc=1` на отсутствующем входном файле с записью в лог. |
| 2026-05-11 | Этап Б, Шаг 12 выполнен: верификация импортов `project_calc/`. AST-обход всех 13 рабочих .py файлов (плюс 10 пустых `__init__.py`). Проверки: (1) `py_compile` всех файлов проходит; (2) ни одного импорта `project_parser` в коде project_calc; (3) архитектурные слои выдерживаются — `common/` ни от чего не зависит внутри пакета, `parser/` зависит только от `common/`, `generator/` зависит только от `common/`, нет cross-зависимостей между `parser/` и `generator/`; (4) в коде (вне docstring) нет хвостов `psycopg2`, `pickle`, постгресовых `%s` плейсхолдеров; (5) все 36 внутренних модулей/пакетов разрешаются (нет битых импортов); (6) карта внутренних импортов задокументирована. **Финальный end-to-end на чистой среде**: парсер на трёх xlsx с пересекающимся Конвейером → в БД 2 equipment, 4 components без дублей, цены по max-strategy (Болт 4→6 перезаписалось, Гайка 2 сохранилось т.к. новая 1<2, Монтаж 10000→15000 перезаписалось); index_builder построил FAISS-индекс на 2 объекта с правильной JSON-метой; генератор обработал 3 строки входа — для Конвейера x3 единицы получилось comp_qty=30/30/3, для Стола x2 единицы comp_qty=4 с актуальными ценами, для отсутствующего оборудования lazy-SearchService подгрузился и вернул REJECT с пометкой. Цикл `parser → index_builder → generator` отрабатывает на чистом project_calc/ без зависимостей от старой `project_parser/`. |
| 2026-05-11 | План: дополнен Этап Ж — добавлен пункт `docs/DEV_GUIDE.md` с четырьмя сценариями: запуск парсера, запуск генератора, обновление БД на dev-машине (xlsx → парсер → index_builder → check_db), обновление БД у пользователя (доставка готовых артефактов `database.db` + `data/index/` без миграций). Плюс пометка про опциональный `docs/USER_GUIDE.md`. Сейчас не делается — фиксируется как задача перед v1. |
| 2026-05-20 | **Е.1.3.Б реализован** — создан `scripts/calibrate_confidence.py` (инструмент для будущей полной калибровки порогов). Читает CSV `data/calibration/queries.csv` (колонки `query;expected_area;expected_label` где label = `positive`/`negative`), прогоняет каждый запрос через `SearchService.search()`, сохраняет в `data/calibration/results.csv` 13 колонок с метриками (decision, top1_similarity, top2_similarity, gap, top1_equipment_name, top1_area, top1_area_matches, top5_similarities, is_false_positive, is_false_negative). Печатает статистику: распределение top1 (min/max/mean/median) для positive и negative, число FP/FN, рекомендуемые пороги по простому квантильному правилу (10-й перцентиль positive vs 90-й перцентиль negative). Если распределения разделимы — печатает конкретные числа для `REJECT_BELOW`/`REVIEW_FROM`/`ACCEPT_FROM`; если пересекаются — обозначает "серую зону" для REVIEW. Создан `data/calibration/queries.sample.csv` как образец из 8 запросов (3 positive + 5 negative включая "Сварочный источник"). Offline-env выставляется до импорта sentence_transformers, как в других entry-points. Прогнаны 11 проверок: py_compile/AST, статика, импорт модуля, read_queries на sample, 4 кейса ошибочных CSV, process через заглушку SearchService с верными FP/FN, write_results с проверкой шапки, _percentile, print_stats на синтетических разделимых распределениях (recommendation вывела `REJECT_BELOW≈0.74`, `REVIEW_FROM≈0.81`, `ACCEPT_FROM≈0.88`), --help. Инструмент готов к моменту калибровки (Е.1.3.В) — у пользователя в БД ~70-100 проектов. |
| 2026-05-12 | **Е.1.3.А реализован** — быстрый фикс порогов confidence. В `common/retrieval/confidence.py` пороги вынесены в константы модуля (`REJECT_BELOW=0.83`, `REVIEW_FROM=0.86`, `ACCEPT_FROM=0.90`, `GAP_MIN=0.05`) и подняты на +0.03 от исходных (`0.80/0.83/0.87`). В docstring зафиксирована история v0→v1→v2 и причина изменения. Параметры `threshold`/`margin` в `__init__` оставлены для совместимости. Прогнаны 15 кейсов с матрицей "было / стало": 5 из 15 решений изменились в сторону более строгой оценки (REVIEW→REJECT для `top1 ∈ [0.80, 0.86)`, ACCEPT→REVIEW для `top1 ∈ [0.87, 0.90)`). Главное ядро не тронуто: идеальные матчи (`top1 ≥ 0.90, gap > 0.05`) остаются ACCEPT, слабые (`top1 < 0.83`) — REJECT. Серая зона сжалась — нерелевантные запросы вроде "Сварочный источник" со средним confidence ~0.85 теперь уходят в REJECT. Это промежуточная мера, оптимальные пороги подобьём в Е.1.3.В после набора 70-100 проектов в БД. |
| 2026-05-12 | План: Е.1.3 разбит на три части (А — быстрый фикс порогов сейчас, Б — инструмент `scripts/calibrate_confidence.py` для будущей калибровки, В — полная калибровка после набора ~70-100 проектов в БД). Это согласовано с пользователем после обсуждения: полноценная калибровка имеет смысл только когда распределения confidence стабильны, а сейчас в БД всего 2 проекта из 135. Быстрый фикс — поднять все пороги на 0.03-0.05 (`0.80→0.83`, `0.83→0.86`, `0.87→0.90`), это уберёт самые шумные ACCEPT/REVIEW и переживёт пополнение БД. Инструмент калибровки делается сейчас, чтобы потом был готов на момент сбора датасета. |
| 2026-05-12 | **Е.1.2 реализован** — четыре статуса в `result.xlsx`. (1) `excel_generator.py` переписан: вместо жёстких номеров колонок теперь поиск по именам шапки через `_norm_header` (lower, без пробелов и точек, тот же подход, что в `parser/excel/reader.py`). Маппинг `data_key → canonical_header` в константе `COLUMN_MAP`. Если в шаблоне нет хоть одной нужной колонки — `ExcelGeneratorError` с понятным сообщением. Шаблон теперь можно безопасно тронуть (переставить колонки, чуть переименовать, добавить новые) без правки кода. (2) В `generator/__main__.py` каждому компоненту проставляется `status` по четырём правилам: `DIRECT` (прямой поиск нашёл), `RETRIEVAL_ACCEPT` или `RETRIEVAL_REVIEW` (retrieval вернул соответствующее decision), `REJECT` (не нашли ни прямым, ни через retrieval, либо retrieval вернул REJECT). Статус пишется в колонку B "Статус подбора из БД" в result.xlsx. Прогнаны 6 сценариев: A–D — каждый из четырёх статусов в отдельности; E — микс: одна input.xlsx с четырьмя строками даёт четыре разных статуса в правильном порядке; F — защита: шаблон без колонки "Статус подбора из БД" → `ExcelGeneratorError: В шаблоне нет обязательных колонок: ...`. Инженер теперь может фильтровать result.xlsx по статусу. |
| 2026-05-12 | **Е.1.1 реализован** — в `generator/__main__.py` после успешного retrieval-матча (decision = ACCEPT или REVIEW) `equipment` в каждом компоненте подменяется на составное имя `f"{input_equipment} — {db_equipment_name}"`. Это даёт инженеру в `result.xlsx` видеть и то, что он искал (имя из input), и то, что retrieval подобрал (имя из БД), разделённые длинным тире. Edge-case: если после `.strip()` имена совпали (например, в input было имя с пробелом, который InputReader уже снял) — не дублируем, оставляем оригинал из input. При REJECT и прямом поиске составное имя не формируется (там подмены нет). В консоль добавлен print `составное имя: ...` для отладки. Прогнаны 5 сценариев на заглушках QueryService/SearchService: A) edge-case с совпадением после strip → не дублируем; B) REJECT → имя из input, пометка `НЕ НАЙДЕНО В БД` в компоненте; C) ключевой кейс retrieval ACCEPT с разными именами → `'Конвейер-XYZ — Конвейер'`; D) REVIEW тоже даёт составное имя; E) прямой поиск — имя из input без изменений, retrieval не вызывается. |
| 2026-05-12 | **Этап Е выполнен** — `dist/calculator/calculator.exe` запущен на чистой Windows-машине без Python и без интернета, генератор отработал без сбоев. Тест на реальном железе подтвердил, что bundle самодостаточен. По итогам тестирования открыты три задачи для **Этапа Е.1** (доработки): (1) при retrieval-подмене сохранять оригинальное имя оборудования из input.xlsx в виде `<input> — <db_match>` (чтобы инженер видел подмену); (2) добавить колонку `Статус` в шаблон расчёта с значениями DIRECT / RETRIEVAL_ACCEPT / RETRIEVAL_REVIEW / REJECT для фильтрации в Excel; (3) настройка confidence — нерелевантные запросы вроде "Сварочный источник" сейчас могут попадать в ACCEPT/REVIEW, нужно поднять пороги и/или ужесточить penalty за несовпадение area. Подтверждено, что пустой `log.txt` при чистом прогоне — нормальное поведение (логгер пишет только ERROR/CRITICAL; INFO-логирование retrieval-решений можно добавить отдельной задачей, если потребуется наблюдаемость). |
| 2026-05-12 | **Этап Д реально завершён** — сборка PyInstaller выполнена на Windows 11 Pro + Python 3.14. `dist/calculator/calculator.exe` создан, рядом скопированы `data/`, `template/`, `run.bat`, и служебная `_internal/` с зависимостями + моделью. По ходу: ~30 ERROR-сообщений вида "Hidden import 'torch.distributed._shard.checkpoint.*' not found" — это deprecated-алиасы во внутренностях torch, PyInstaller-хук пытается их собрать; на работу exe не влияет (наш код к ним не обращается). Несколько warnings: `transformers.cli.serving` (внутренний баг transformers с `CompletionCreateParamsStreaming`, нашим генератором не вызывается), `torch.utils.tensorboard` (нет tensorboard, не используется), `scipy.special._cdflib` (sub-модуль scipy, не нужен), `libgomp.so.1` (Linux-библиотека в torch-хуке, на Windows игнорируется). Финальное сообщение `Build complete!` и успешный COLLECT-стейдж означают, что bundle готов к запуску. Следующие шаги: проверить запуск `dist/calculator/run.bat` на dev-машине, замерить размер папки, перенести на чистую Windows-машину для Этапа Е. |
| 2026-05-12 | **Этап Д готов к запуску на Windows** — создан `calculator.spec`, `scripts/run.bat`, `scripts/package_release.bat`. **`calculator.spec`**: entry point `project_calc/generator/__main__.py`, режим `--onedir` (быстрый старт без распаковки), `console=True`, `upx=False`, `collect_all` для `sentence_transformers`, `transformers`, `tokenizers`, `torch`, `huggingface_hub`, `safetensors` (обязательно из-за динамических импортов в ML-стеке). Модель `models/multilingual-e5-base` упакована в bundle через `datas` — `config.MODEL_PATH` через `resource_path()` найдёт её в `_internal/models/` после распаковки. **`run.bat`**: для пользователя — `chcp 65001` для кириллицы, `cd /d %~dp0`, вызов `calculator.exe`, `pause` для удержания консоли. **`scripts/package_release.bat`**: 5 шагов оркестрации — проверка артефактов (database.db, index, model, template, spec), очистка `dist/`/`build/`, `pyinstaller calculator.spec --noconfirm`, копирование `template/` + `data/database.db` + `data/index/` рядом с exe, создание пустых `data/input` `data/output` `data/logs`, копирование `run.bat`. Артефакты template/db/index НЕ в bundle — кладутся рядом с exe, чтобы их можно было обновлять без пересборки. Найдена и исправлена проблема в `.gitignore`: `*.spec` заигнорил бы наш `calculator.spec` — добавлено `!calculator.spec`. Прогнаны статические проверки spec (AST + 10 ключевых элементов), `run.bat` (5 элементов), `package_release.bat` (16 элементов), пути в spec соответствуют реальной структуре. Реальный прогон PyInstaller — у разработчика на Windows: `scripts\package_release.bat`. Ожидаемый размер `dist/calculator/` ≈ 1.5-2 GB. |
| 2026-05-12 | **Этап Г завершён** — подготовка release-bundle. Созданы три скрипта: (1) `scripts/init_db.py` — создаёт пустую SQLite по `init_sqlite.sql`, с защитой от случайной перезаписи (rc=1 если БД уже есть); (2) `scripts/build_index.py` — обёртка над `IndexBuilder` с обработкой `RuntimeError`/`FileNotFoundError`; (3) `scripts/build_release.py` — оркестратор полного workflow: clean → init_db → parser → build_index → проверка артефактов с табличной сводкой размеров. Опции `--raw`, `--skip-parse`, `--skip-index`, `--no-clean` для частичных прогонов. Итоговый отчёт показывает все 5 артефактов (БД, Index, Index meta, Model, Template) с размерами и статусом OK/MISSING, плюс суммарный вес bundle. **Бонусная правка**: `parser/excel/reader.py` теперь толерантен к написанию шапки — нормализация заголовков (lower, без пробелов и точек). Это решило реальный кейс пользователя: один файл с `'ед. изм'`, второй — с `'едизм'`. Прогнаны 6 проверок: оба xlsx читаются, end-to-end build_release с двумя реальными xlsx (1168 строк → 19 area, 85 equipment, 861 components, 239 costs; модель 1.08 GB обнаружена в `models/`), `--no-clean` корректно прерывается на init_db, `--help` отображается, `init_db.py` защищён от перезаписи. |
| 2026-05-11 | **Этап В завершён** — offline ML-модель. (1) Создан `scripts/download_model.py` для разовой загрузки `intfloat/multilingual-e5-base` в `models/multilingual-e5-base/` — запускается на dev-машине при наличии интернета, проверяет что папка пуста, печатает размер после загрузки. (2) Переписан `Embedder` — параметр `model` опционален и по умолчанию = `config.MODEL_PATH` (локальная папка). При передаче `Path` и его отсутствии — `RuntimeError` с подсказкой запустить `download_model.py` (вместо менее понятной ошибки от sentence_transformers). При передаче строкой (HF-ID) — пропускается без `exists`-проверки, удобно для dev. (3) В `generator/__main__.py` и `parser/index_builder.py` ДО любых импортов (включая косвенные через Embedder/SearchService) выставлены `os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")` и `os.environ.setdefault("HF_HUB_OFFLINE", "1")` — это гарантирует, что в release-сборке без интернета `sentence_transformers` и `huggingface_hub` не пойдут в сеть. `setdefault` уважает явное значение разработчика (можно переопределить через env). `parser/__main__.py` env не трогает — он не тянет ML, Embedder используется только в `index_builder` (отдельная команда). Прогнаны 12 проверок: `py_compile`, дефолт MODEL_PATH, RuntimeError при отсутствии, передача HF-ID строкой, выставление env в обоих entry-point, `setdefault` не перетирает, отсутствие env-выставления в `parser/__main__`, AST-проверка порядка (`setdefault` ДО ML-импортов), статика `download_model.py`, `.gitignore` содержит `models/`, корректный резолв `MODEL_PATH`. |
| 2026-05-11 | **Этап Б завершён** — Шаг 13 (финальная очистка). Удалено: `project_parser/` целиком (625 KB, 49 файлов), `BD Scripts/` (4 файла Postgres-схемы), корневые дубли `equipment.index` (404 KB) и `equipment_meta.pkl` (17 KB), пробники `test_model.py`/`test_embedder.py`/`test_search.py`, `build_index.py` (обёртка для старого пакета), `.env` (содержал устаревшие Postgres-credentials `DB_PASSWORD=q`). Создано: `.gitignore` (Python артефакты, .venv, IDE, OS, dist/build/, data/database.db/index/logs/, models/), `.env.example` (документация всех env-override), `requirements-dev.txt` (`-r requirements.txt` + `pyinstaller>=6.0`). Обновлён `requirements.txt`: удалён `psycopg2-binary`, остальное (полный pin-freeze) оставлено как есть — остальные мнимо лишние пакеты могут быть транзитивными зависимостями `sentence-transformers`, агрессивная чистка отложена до Шага Д через PyInstaller `--exclude-module`. Подчищены docstring-комментарии "Отличия от prior project_parser/..." в `query_service.py`, `db_writer.py`, `index_builder.py` — после удаления project_parser эти упоминания только запутывают. **Финальный full pipeline** на полностью очищенной среде прошёл: parser на 2 xlsx → 2 equipment / 3 components / 3 costs; index_builder → 2 объекта в FAISS + JSON-мета; generator → result.xlsx с правильным расчётом количеств (Конвейер×2 → Болт 10, Гайка 10; Шкаф×1 → Корпус 1). Структура корня финальна и готова к Этапу В. |
| 2026-05-22 | **Этап Ж, пункт «сценарий релиза» выполнен** — создан `docs/RELEASE_PLAYBOOK.md`, процедурный playbook для актa выпуска (в отличие от справочного DEV_GUIDE). Семь разделов. (1) Развилка по типу релиза — таблица «что поменялось → A/B/не нужен», главная идея: 80% случаев это релиз A (три файла), пересборка exe только при изменении кода/шаблона/модели/requirements. (2) **Релиз A — обновление данных**: чек-лист (build_release.py → check_db → smoke-тест → доставка) с раскрытыми подпунктами, smoke-тест генератора как отдельный обязательный шаг с конкретными критериями (Status заполнен, доля REJECT не растёт резко, есть хотя бы один DIRECT), когда лог может быть непустым (битые исторические строки — ок, CRITICAL про блоки + `groups_failed > 0` — стоп-сигнал), три файла доставки с путями, готовый шаблон сообщения пользователю. (3) **Релиз B — пересборка exe**: чек-лист с git tag, обязательный тест на чистой машине (с отключённой сетью, без `.venv` — пересмотр Этапа Е), процедура доставки с сохранением пользовательского input.xlsx, шаблон сообщения. (4) **Версионирование и архив**: схема имён `data_YYYY-MM-DD.zip` и `release_YYYY-MM-DD.zip` с суффиксом `-bN`, формат CHANGELOG.md с примером записи, структура `releases/{builds,data,CHANGELOG.md}` на dev-стороне, правило хранения (данные 3 мес, сборки exe — год), привязка к git (тег только для B), особый случай точечной замены шаблона. (5) **Rollback**: дешёвый откат A (подложить предыдущий data_*.zip), дорогой откат B (распаковать предыдущий release_*.zip с переименованием сломанного), список «что мы НЕ делаем» (никаких горячих патчей `database.db`/`equipment.index` руками, никаких правок `_internal/`, парсер у пользователя не появляется). (6) Таблица 6 типичных проблем с указанием куда смотреть (PyInstaller hidden imports / ImportError при запуске / тишина при дабл-клике = антивирус / раздутый bundle = торч не +cpu / REJECT после релиза A = индекс несинхронен / рост REJECT в smoke = парсинг отвалился). (7) Ссылки на DEV_GUIDE/USER_GUIDE/REFACTORING_PLAN. Дополнительно: в `.gitignore` добавлена строка `releases/` со ссылкой на раздел 4.3 — архив релизов хранится локально и в облаке, в git не идёт. CHANGELOG.md физически НЕ создан сейчас (создастся при первом релизе по этому playbook'у — формат и место зафиксированы). |
| 2026-05-22 | **Этап Ж, пункт requirements.txt выполнен** — версии зависимостей зафиксированы и файлы реструктурированы. **Состав и версии не менялись** (`pip install -r requirements.txt` даёт идентичный результат — это намеренно, чтобы не задеть собранный bundle). Что сделано: (1) В `requirements.txt` добавлена шапка с инструкциями (как пересобрать pin-freeze, замечание про обязательный `+cpu`-суффикс у torch — иначе exe раздуется CUDA-сборкой в 3-4 раза). (2) Пакеты разделены на две секции: **прямые зависимости** project_calc (6 шт.: `openpyxl`, `pandas`, `numpy`, `faiss-cpu`, `sentence-transformers`, `torch+cpu`) с inline-комментариями, где какой используется, и **транзитивные** (41 пакет, алфавитный pin-freeze). Прямые определены по AST-обходу импортов `project_calc/` и `scripts/`. (3) `requirements-dev.txt` тоже получил шапку и пояснение, что парсер не требует доп. зависимостей сверх production — поэтому здесь только `pyinstaller>=6.0` для сборки exe. (4) Намеренно НЕ удалены подозрительные на мёртвость пакеты (`python-dotenv` после удаления .env, `typer`/`click` — без явных импортов в коде) — по решению Шага 13 Этапа Б они могут быть транзитивами от `sentence-transformers`/`transformers`/`huggingface_hub`, агрессивная чистка перенесена в PyInstaller через `--exclude-module`. Это документировано в шапке файла. Главный win — теперь видно, на чём проект реально стоит, и при обновлении любой из 6 прямых зависимостей понятно, что именно может поломаться. |
| 2026-05-22 | **Этап Ж, пункт USER_GUIDE выполнен** — создан `docs/USER_GUIDE.md`. Восемь разделов, написан простым языком для инженера-пользователя (не для разработчика), без developer-жаргона. (1) Какие файлы и папки должны быть на компьютере после установки — дерево с подписями простым языком и пометкой про автосоздание недостающих папок. (2) Как подготовить `input.xlsx` — таблица из трёх обязательных колонок с примерами значений, требование точного совпадения заголовков, правила для количества (целое > 0), указание положить в `data\input\` заменив старый файл. (3) Как запустить — `run.bat` дабл-кликом vs прямой `calculator.exe`, что увидит пользователь, типичное время старта (30 сек первый раз, 10-15 сек далее). (4) Как читать `result.xlsx` — таблица четырёх статусов (DIRECT/RETRIEVAL_ACCEPT/RETRIEVAL_REVIEW/REJECT) с понятной колонкой «что делать», объяснение составного имени `<input> — <db>` при retrieval-подмене, пометка `НЕ НАЙДЕНО В БД` при REJECT, совет фильтровать по статусу. (5) Если что-то пошло не так — где лежит `log.txt`, таблица «симптом → причина → действие» из 6 типичных ситуаций (мелькнуло окно, нет колонок, не появился result, много REJECT, повреждён файл, устаревшие цены), что приложить при обращении к разработчику. (6) Обновление базы — какие три файла приходят (database.db + equipment.index + equipment_meta.json), куда копировать поверх старых, что программа открывает БД read-only и поэтому замена безопасна. (7) Чего НЕ делать — не запускать от админа, не править служебные файлы и шаблон руками, не переименовывать input.xlsx, как реагировать на предупреждение Windows Defender про unsigned exe. (8) Куда обращаться при проблемах — к разработчику с приложенными input.xlsx + result.xlsx + log.txt. Все факты сверены с фактическим поведением кода: трёхколоночный input (`generator/input_reader.py` REQUIRED_COLUMNS), четыре статуса (`generator/__main__.py` Е.1.2), составное имя (`generator/__main__.py` Е.1.1), open read-only БД (`query_service.py`), `template\template.xlsx` рядом с exe (не в `_internal/`, см. `scripts/package_release.bat`). |
| 2026-05-22 | **Этап Ж, пункт README выполнен** — `README.md` переписан под новую структуру. Старый README (10 строк, ссылки на несуществующий `project_parser`, `equipment.index`/`equipment_meta.pkl` в корне, bash-команды `rm`/`ls`) удалён. Новый README — короткий обзор для нового человека на проекте: что делает Project Calc (расчёт состава и стоимости комплектующих по историческим проектам через SQLite + FAISS на multilingual-e5-base), два режима использования (релизный `calculator.exe` оффлайн без Python — для инженера; Python-окружение со всеми скриптами — для разработчика), структура репозитория с пояснением каждой папки (project_calc/common·parser·generator, scripts, template, data, models, docs, calculator.spec), архитектурный инвариант «generator ↛ parser», быстрый старт из 6 команд (venv → download_model → положить xlsx → build_release → генератор → package_release.bat), таблица связанных документов. Все подробности (CLI, обновление БД, траблшут) делегированы в `docs/DEV_GUIDE.md` ссылкой — README сознательно держим коротким, чтобы новый человек прочитал его за минуту и пошёл в нужный документ. |
| 2026-05-22 | **Этап Ж, пункт DEV_GUIDE выполнен** — создан `docs/DEV_GUIDE.md`. Восемь разделов: (0) архитектурный контекст и инвариант `generator ↛ parser`, путь через `config.py` + env-override; (1) **запуск парсера** — CLI `--input/--db/--dry-run`, семь канонических колонок шапки с толерантным матчингом (`_norm_header`), правила «битой» строки и поведение логгера (ERROR vs CRITICAL), консольный вывод и rc, UPSERT-семантика для повторных прогонов (equipment INSERT OR IGNORE, components только при новом equipment, costs только при росте цены); (2) **запуск генератора** — CLI, **три обязательные колонки** input.xlsx с точным матчингом (контраст с 7 колонками парсера явно проговорён), требования к БД/индексу/шаблону/модели, pipeline прямой → lazy retrieval, четыре статуса DIRECT/RETRIEVAL_ACCEPT/RETRIEVAL_REVIEW/REJECT, составное имя `<input> — <db>`, открытие БД в read-only, формат `result.xlsx`, статистика retrieval; (3) **обновление БД на dev** — стандартный цикл xlsx → parser → build_index → check_db с пояснением что произойдёт, рецепт «с нуля» через init_db и алтернатива через `scripts/build_release.py`; (4) **обновление БД у пользователя** — миграций нет (БД read-only), что готовится на dev (3 файла), как доставить и куда положить, что НЕ делать на release-машине, отдельные случаи с заменой шаблона и пересборкой exe; (5) полный цикл «с нуля до bundle» одной выжимкой; (6) шпаргалка из 12 команд таблицей; (7) траблшут-таблица «симптом → куда смотреть»; (8) ссылки на REFACTORING_PLAN, README, опциональный USER_GUIDE. Все CLI-опции и заголовки колонок свёрены с фактическим кодом (`project_calc/parser/__main__.py`, `project_calc/generator/__main__.py`, `project_calc/generator/input_reader.py`, `project_calc/parser/excel/reader.py`, `scripts/init_db.py`, `scripts/build_index.py`, `scripts/check_db.py`, `scripts/build_release.py`, `scripts/package_release.bat`). |
