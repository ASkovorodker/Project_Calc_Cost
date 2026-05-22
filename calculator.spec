# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для сборки calculator.exe (Этап Д).

Запуск:
    pyinstaller calculator.spec --noconfirm

Результат:
    dist/calculator/calculator.exe   ← exe
    dist/calculator/_internal/       ← зависимости + модель (внутри bundle)

Артефакты, которые НЕ идут в bundle (БД, индекс, шаблон), копируются
рядом с calculator.exe скриптом scripts/package_release.bat — так,
чтобы пользователь мог их обновлять без пересборки.

Что внутри:
  * entry point: project_calc/generator/__main__.py
  * --onedir режим (быстрый старт, без распаковки во временную папку)
  * console=True (пользователь видит вывод и ошибки)
  * upx=False (быстрый старт важнее размера)
  * collect_all для тяжёлых ML-либ (нужно из-за динамических импортов)
  * models/multilingual-e5-base — в bundle через datas (резолвится через
    config.bundle_dir() → sys._MEIPASS)
"""
from PyInstaller.utils.hooks import collect_all

# =========================================================
# Сбор сторонних либ
# =========================================================
# collect_all возвращает (datas, binaries, hiddenimports) — собирает
# Python-модули, бинарники и hidden-импорты для каждого пакета.
# Это обязательно для ML-стека: sentence_transformers тащит модули
# динамически, и без collect_all PyInstaller их пропустит.

datas = []
binaries = []
hiddenimports = []

for pkg in (
    "sentence_transformers",
    "transformers",
    "tokenizers",
    "torch",
    "huggingface_hub",
    "safetensors",
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# =========================================================
# Свои ресурсы в bundle
# =========================================================
# Модель (~1.1 GB) — read-only, упаковываем внутрь bundle.
# config.MODEL_PATH через resource_path() сначала ищет в sys._MEIPASS
# (куда PyInstaller распаковывает datas), потом рядом с exe — то есть
# модель будет найдена в _internal/models/multilingual-e5-base/.

datas += [
    ("models/multilingual-e5-base", "models/multilingual-e5-base"),
]

# Шаблон Excel, стартовая БД и индекс НЕ кладём в bundle:
# они должны лежать рядом с exe, чтобы их можно было обновлять
# без пересборки. См. scripts/package_release.bat.

block_cipher = None


# =========================================================
# Анализ и сборка
# =========================================================

a = Analysis(
    ["project_calc/generator/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="calculator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="calculator",
)
