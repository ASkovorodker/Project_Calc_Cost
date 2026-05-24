# ARCHITECTURE — Project Calc

Архитектурная блок-схема проекта в нескольких разрезах. Каждая диаграмма
отвечает на свой вопрос: «как устроен код», «куда движутся данные»,
«как собирается релиз», «что происходит при запуске генератора».

Диаграммы сделаны в Mermaid — GitHub рендерит их прямо в браузере.
Для правки достаточно открыть этот файл в любом текстовом редакторе.

---

## 1. Код-слои и инвариант `generator ↛ parser`

```mermaid
flowchart TB
    subgraph PC["project_calc/"]
        direction TB

        subgraph COMMON["common/ — общая инфраструктура (попадает и в exe, и в dev)"]
            direction LR
            CFG["config.py<br/>(пути, env-override)"]
            CONN["db/connection.py<br/>(SQLite, FK, read-only)"]
            LOG["logging_/logger.py"]
            SCHEMA["db/schema/<br/>init_sqlite.sql"]
            EMB["retrieval/embedder.py<br/>(multilingual-e5-base)"]
            SRCH["retrieval/search_service.py<br/>(FAISS поиск)"]
            CONF["retrieval/confidence.py<br/>(ACCEPT/REVIEW/REJECT)"]
        end

        subgraph PARSER["parser/ — DEV-ONLY (не идёт в exe)"]
            direction LR
            EXCEL["excel/reader.py"]
            VAL["validation/validator.py"]
            NORM["normalize/normalizer.py"]
            DBW["db_writer.py<br/>(UPSERT-логика)"]
            IB["index_builder.py"]
            PMAIN["__main__.py<br/>(CLI парсера)"]
        end

        subgraph GEN["generator/ — USER-FACING (упаковано в calculator.exe)"]
            direction LR
            IR["input_reader.py"]
            QS["query_service.py"]
            EG["excel_generator.py"]
            GMAIN["__main__.py<br/>(CLI генератора)"]
        end

        PARSER -->|импорт| COMMON
        GEN    -->|импорт| COMMON
    end

    NOTE["⚠ ИНВАРИАНТ: generator/ никогда не импортирует из parser/.<br/>Это позволяет PyInstaller собрать минимальный bundle без кода парсера."]

    GEN -.не зависит.-x PARSER

    classDef common  fill:#e3f2fd,stroke:#1976d2,color:#0d47a1
    classDef parser  fill:#fff3e0,stroke:#f57c00,color:#e65100
    classDef gen     fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    classDef note    fill:#fff9c4,stroke:#f9a825,color:#5d4037

    class CFG,CONN,LOG,SCHEMA,EMB,SRCH,CONF common
    class EXCEL,VAL,NORM,DBW,IB,PMAIN parser
    class IR,QS,EG,GMAIN gen
    class NOTE note
```

Три слоя. `common/` не зависит ни от чего внутри пакета. `parser/`
и `generator/` оба зависят от `common/`, но **не друг от друга** —
это и есть архитектурный инвариант, который позволяет PyInstaller
собрать exe без кода парсера.

---

## 2. Поток данных end-to-end

```mermaid
flowchart LR
    subgraph DEV["🛠 DEV-машина (разработчик)"]
        direction TB
        RAW["data/raw_projects/<br/>*.xlsx<br/>(исторические проекты)"]
        PARS["python -m<br/>project_calc.parser"]
        DB[("data/database.db<br/>SQLite")]
        IDXBUILD["python<br/>scripts/build_index.py"]
        IDX["data/index/<br/>equipment.index<br/>equipment_meta.json"]

        RAW -->|"ExcelReader →<br/>Validator →<br/>Normalizer →<br/>DBWriter"| PARS
        PARS -->|UPSERT| DB
        DB -->|read| IDXBUILD
        IDXBUILD -->|FAISS-эмбеддинги| IDX
    end

    subgraph DELIVERY["📦 Доставка"]
        direction TB
        BUNDLE["dist/calculator/<br/>(release_*.zip)"]
        DATAPACK["3 файла:<br/>database.db<br/>equipment.index<br/>equipment_meta.json<br/>(data_*.zip)"]
    end

    subgraph USER["🖥 USER-машина (через calculator.exe)"]
        direction TB
        INPUT["data/input/<br/>input.xlsx<br/>(задание инженера)"]
        GEN["calculator.exe<br/>= project_calc.generator"]
        OUTPUT["data/output/<br/>result.xlsx<br/>(готовый расчёт)"]

        INPUT -->|"InputReader →<br/>QueryService →<br/>(SearchService) →<br/>ExcelGenerator"| GEN
        GEN -->|"4 статуса:<br/>DIRECT / ACCEPT /<br/>REVIEW / REJECT"| OUTPUT
    end

    MODEL["models/<br/>multilingual-e5-base<br/>(~1.1 GB)"]
    TMPL["template/<br/>template.xlsx"]

    MODEL -.embedder.-> IDXBUILD
    MODEL -.embedder.-> GEN
    TMPL  -.shape.-> GEN

    DEV -->|первый раз<br/>или релиз B| BUNDLE
    DEV -->|регулярно<br/>релиз A| DATAPACK
    BUNDLE --> USER
    DATAPACK -->|поверх старых| USER

    classDef devbox  fill:#fff3e0,stroke:#f57c00
    classDef userbox fill:#e8f5e9,stroke:#388e3c
    classDef artifact fill:#e3f2fd,stroke:#1976d2
    classDef shared  fill:#f3e5f5,stroke:#7b1fa2

    class RAW,PARS,IDXBUILD devbox
    class INPUT,GEN,OUTPUT userbox
    class DB,IDX,BUNDLE,DATAPACK artifact
    class MODEL,TMPL shared
```

Стрелки пунктиром — это «ресурс, который используется», сплошные —
«данные текут вот сюда». БД и индекс готовятся на dev-машине и
доезжают до пользователя готовыми артефактами. Модель и шаблон
у пользователя статичны (приехали в bundle при установке).

---

## 3. Релизный pipeline

```mermaid
flowchart LR
    subgraph PREP["1. Подготовка артефактов"]
        direction TB
        INITDB[init_db.py]
        PARSER[python -m project_calc.parser]
        BIDX[build_index.py]
        BREL["build_release.py<br/>(оркестратор)"]

        BREL --> INITDB
        BREL --> PARSER
        BREL --> BIDX
    end

    subgraph PKG["2. Упаковка в exe"]
        direction TB
        SPEC[calculator.spec]
        PYINST["pyinstaller<br/>calculator.spec"]
        COPY["copy: template/,<br/>data/database.db,<br/>data/index/,<br/>run.bat"]
        PKGBAT["package_release.bat<br/>(оркестратор)"]

        PKGBAT --> SPEC
        SPEC --> PYINST
        PYINST --> COPY
    end

    subgraph DELIVER["3. Доставка"]
        direction TB
        DIST["dist/calculator/<br/>~1.5–2 GB"]
        ZIPA["data_YYYY-MM-DD.zip<br/>(релиз A — только данные)"]
        ZIPB["release_YYYY-MM-DD.zip<br/>(релиз B — весь bundle)"]
        USR["Project_Calc/<br/>на машине пользователя"]

        DIST --> ZIPB
        ZIPB --> USR
        ZIPA --> USR
    end

    PREP -->|при релизе B| PKG
    PKG --> DELIVER
    PREP -->|при релизе A<br/>(берём только 3 файла)| ZIPA

    SUPP["📋 Вспомогательные:<br/>download_model.py — раз на dev<br/>check_db.py — проверка содержимого<br/>calibrate_confidence.py — настройка порогов"]

    classDef step fill:#e3f2fd,stroke:#1976d2
    classDef orch fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    classDef out  fill:#e8f5e9,stroke:#388e3c

    class INITDB,PARSER,BIDX,SPEC,PYINST,COPY step
    class BREL,PKGBAT orch
    class DIST,ZIPA,ZIPB,USR out
```

Два сценария релиза:
- **Релиз A** (часто) — данные обновились, exe не пересобираем. Берём
  три файла из `data/` после `build_release.py`, кладём в архив.
- **Релиз B** (редко) — меняли код или шаблон, пересобираем всё. Полный
  цикл `build_release.py → package_release.bat → release_*.zip`.

Подробности — [`RELEASE_PLAYBOOK.md`](RELEASE_PLAYBOOK.md).

---

## 4. Runtime-логика генератора (что происходит для каждой строки input)

```mermaid
flowchart TD
    START(["строка input.xlsx<br/>(участок, оборудование, кол-во)"]) --> DIRECT["QueryService.<br/>get_components_for_equipment<br/>(прямой поиск по area+name)"]
    DIRECT --> Q1{Нашли в БД?}

    Q1 -->|Да| SD["status = DIRECT<br/>имя = из input"]

    Q1 -->|Нет| LAZY["⚙ Lazy-init SearchService<br/>(модель + FAISS грузятся<br/>только на первом промахе)"]
    LAZY --> SEARCH["SearchService.search<br/>(FAISS top-K + confidence)"]
    SEARCH --> Q2{decision?}

    Q2 -->|ACCEPT<br/>top1 ≥ 0.90<br/>gap > 0.05| SA["status = RETRIEVAL_ACCEPT<br/>имя = 'input — db_match'<br/>(составное)"]
    Q2 -->|REVIEW<br/>0.86 ≤ top1 < 0.90| SR["status = RETRIEVAL_REVIEW<br/>имя = 'input — db_match'<br/>(составное)"]
    Q2 -->|REJECT<br/>top1 < 0.86| SX["status = REJECT<br/>component = 'НЕ НАЙДЕНО В БД'"]

    Q2 -.индекс отсутствует.-> SX

    SD --> WRITE[["ExcelGenerator.generate<br/>→ result.xlsx"]]
    SA --> WRITE
    SR --> WRITE
    SX --> WRITE

    classDef hit  fill:#c8e6c9,stroke:#388e3c
    classDef warn fill:#fff9c4,stroke:#f9a825
    classDef bad  fill:#ffcdd2,stroke:#c62828
    classDef proc fill:#e3f2fd,stroke:#1976d2

    class SD hit
    class SA hit
    class SR warn
    class SX bad
    class DIRECT,LAZY,SEARCH,WRITE proc
```

Главные особенности:

- **Lazy-init** `SearchService` экономит 3–5 секунд старта, если БД покрывает всё прямым поиском.
- **Составное имя** при retrieval-подмене (Е.1.1) — инженер видит и свой запрос, и то, что подобралось из БД.
- **Четыре статуса** в `result.xlsx` (Е.1.2) — инженер фильтрует и работает только с теми строками, что требуют внимания.
- **Защита от отсутствующего индекса** — при `FileNotFoundError` от индекса генератор не падает, помечает строку как REJECT и идёт дальше.

Пороги confidence — в `common/retrieval/confidence.py`. Текущие значения
зафиксированы в Этапе Е.1.3.А (быстрый фикс, до полной калибровки на
~70-100 проектах в БД).

---

## 5. Структура файлов на машине пользователя

```mermaid
flowchart TB
    subgraph DESKTOP["C:\\Users\\&lt;user&gt;\\Desktop\\Project_Calc\\"]
        direction TB
        EXE["calculator.exe<br/>(основной бинарь)"]
        RUN["run.bat<br/>(удобный запуск)"]
        INT["_internal/<br/>(зависимости PyInstaller,<br/>~1.5 GB)"]

        subgraph TPL["template/"]
            TMPL["template.xlsx<br/>(правится без пересборки)"]
        end

        subgraph DATA["data/"]
            DB2[("database.db<br/>read-only")]
            subgraph IDXFOLDER["index/"]
                IDX2["equipment.index<br/>equipment_meta.json"]
            end
            subgraph INPUT2["input/"]
                IN["input.xlsx<br/>(кладёт инженер)"]
            end
            subgraph OUT2["output/"]
                OUTRES["result.xlsx<br/>(появляется<br/>после запуска)"]
            end
            subgraph LOGS["logs/"]
                LOGF["log.txt<br/>(ERROR/CRITICAL)"]
            end
        end
    end

    classDef bin   fill:#e3f2fd,stroke:#1976d2
    classDef data  fill:#e8f5e9,stroke:#388e3c
    classDef user  fill:#fff9c4,stroke:#f9a825
    classDef tech  fill:#f5f5f5,stroke:#9e9e9e

    class EXE,RUN,TMPL bin
    class DB2,IDX2 data
    class IN,OUTRES user
    class INT,LOGF tech
```

Зелёное — артефакты из релиза (приходят с dev-машины). Жёлтое —
пользовательское (создаётся при работе). Голубое — программа и
её конфигурация. Серое — служебное, не трогать.

---

## 6. Карта зависимостей внутри `project_calc/`

```mermaid
flowchart LR
    GMAIN["generator/<br/>__main__.py"] --> IR["generator/<br/>input_reader.py"]
    GMAIN --> QS["generator/<br/>query_service.py"]
    GMAIN --> EG["generator/<br/>excel_generator.py"]
    GMAIN -.lazy.-> SRCH

    QS --> CONN["common/db/<br/>connection.py"]
    GMAIN --> CFG["common/<br/>config.py"]
    GMAIN --> LOGGER["common/logging_/<br/>logger.py"]

    SRCH["common/retrieval/<br/>search_service.py"] --> EMB["common/retrieval/<br/>embedder.py"]
    SRCH --> CONF["common/retrieval/<br/>confidence.py"]
    SRCH --> CFG
    EMB --> CFG

    PMAIN["parser/<br/>__main__.py"] --> EXCEL["parser/excel/<br/>reader.py"]
    PMAIN --> VAL["parser/validation/<br/>validator.py"]
    PMAIN --> NORM["parser/normalize/<br/>normalizer.py"]
    PMAIN --> DBW["parser/<br/>db_writer.py"]
    PMAIN --> CONN
    PMAIN --> CFG
    PMAIN --> LOGGER

    IB["parser/<br/>index_builder.py"] --> EMB
    IB --> CONN
    IB --> CFG

    CONN --> CFG
    LOGGER --> CFG

    classDef gen    fill:#e8f5e9,stroke:#388e3c
    classDef parser fill:#fff3e0,stroke:#f57c00
    classDef common fill:#e3f2fd,stroke:#1976d2

    class GMAIN,IR,QS,EG gen
    class PMAIN,EXCEL,VAL,NORM,DBW,IB parser
    class CONN,CFG,LOGGER,SRCH,EMB,CONF common
```

Видна та же история: всё опирается на `common/`, между `generator/`
и `parser/` стрелок нет.

---

## Легенда

| Цвет | Смысл |
|---|---|
| 🟢 Зелёный | `generator/` — то, что попадает в exe и работает у пользователя |
| 🟠 Оранжевый | `parser/` — dev-only, не уезжает к пользователю |
| 🔵 Голубой | `common/` — общая инфраструктура / артефакты / шаги pipeline |
| 🟡 Жёлтый | Заметки, оркестраторы, пользовательские артефакты |
| 🔴 Красный | Проблемные ветки (REJECT, отсутствие данных) |
| 🟣 Фиолетовый | Внешние ресурсы (модель, шаблон) |

---

## Связанные документы

- [`../README.md`](../README.md) — обзор проекта одной страницей.
- [`DEV_GUIDE.md`](DEV_GUIDE.md) — как запускать инструменты, опции CLI.
- [`USER_GUIDE.md`](USER_GUIDE.md) — инструкция для инженера-пользователя.
- [`RELEASE_PLAYBOOK.md`](RELEASE_PLAYBOOK.md) — процедура выпуска обновлений.
- [`../REFACTORING_PLAN.md`](../REFACTORING_PLAN.md) — архитектурные решения, история этапов, технические заметки.
