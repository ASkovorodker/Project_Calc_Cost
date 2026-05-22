"""
Инструмент калибровки порогов retrieval (Е.1.3.Б).

Прогоняет список запросов через SearchService, собирает confidence-метрики
и пишет результат в CSV для последующего анализа. Печатает короткую
статистику (распределение top1 для positive/negative, ложные срабатывания,
рекомендуемые квантильные пороги).

Запуск:
    python scripts/calibrate_confidence.py

По умолчанию читает data/calibration/queries.csv и пишет
data/calibration/results.csv. Через --input/--output можно указать другие.

Формат входа (CSV, UTF-8, разделитель ';'):
    query;expected_area;expected_label
    Конвейер;Линия 1;positive
    Сварочный источник;Цех 5;negative

Колонки:
    query           — текст запроса, как из input.xlsx
    expected_area   — участок (передаётся в search.expected_area)
    expected_label  — 'positive' (есть в БД, должно найтись)
                      или 'negative' (нет в БД и не должно)

Формат выхода (CSV ';'-разделитель):
    query, expected_label, expected_area, decision,
    top1_similarity, top2_similarity, gap,
    top1_equipment_name, top1_area, top1_area_matches,
    top5_similarities (через '|'),
    is_false_positive, is_false_negative

КОГДА ИСПОЛЬЗОВАТЬ
    Когда в БД набирается ~50-70% целевого размера (Е.1.3.В).
    Сейчас (2 проекта из 135) распределения нестабильны — калибровка
    под маленькую БД устареет с её ростом.

КАК ИСПОЛЬЗОВАТЬ
    1. Подготовить CSV с 20-40 positive и 15-30 negative запросами
       (см. data/calibration/queries.sample.csv как образец).
    2. Запустить:  python scripts/calibrate_confidence.py
    3. Открыть data/calibration/results.csv в Excel или анализировать
       программно. Колонки is_false_positive / is_false_negative —
       главные для оценки ошибок.
    4. По распределениям и рекомендациям в консольной сводке
       подобрать новые REJECT_BELOW / REVIEW_FROM / ACCEPT_FROM
       и обновить project_calc/common/retrieval/confidence.py.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Offline-env ДО импорта sentence_transformers через SearchService.
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")


def parse_args() -> argparse.Namespace:
    default_input = ROOT / "data" / "calibration" / "queries.csv"
    default_output = ROOT / "data" / "calibration" / "results.csv"
    p = argparse.ArgumentParser(
        prog="python scripts/calibrate_confidence.py",
        description="Прогон датасета запросов через retrieval для калибровки порогов",
    )
    p.add_argument("--input",  default=str(default_input),
                   help=f"CSV с запросами (по умолчанию: {default_input})")
    p.add_argument("--output", default=str(default_output),
                   help=f"CSV с результатами (по умолчанию: {default_output})")
    p.add_argument("--top-k",  type=int, default=5,
                   help="top_k для SearchService (по умолчанию 5)")
    return p.parse_args()


def read_queries(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"Не найден файл с запросами: {path}\n"
            f"Создайте CSV с колонками query;expected_area;expected_label\n"
            f"Образец: data/calibration/queries.sample.csv"
        )

    queries: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        fields = set(reader.fieldnames or [])
        required = {"query", "expected_area", "expected_label"}
        missing = required - fields
        if missing:
            raise SystemExit(
                f"В CSV {path} нет обязательных колонок: {sorted(missing)}\n"
                f"Ожидается: query;expected_area;expected_label"
            )
        for i, row in enumerate(reader, start=2):
            label = (row.get("expected_label") or "").strip().lower()
            if label not in ("positive", "negative"):
                raise SystemExit(
                    f"Строка {i}: expected_label должна быть 'positive' "
                    f"или 'negative', получено {row.get('expected_label')!r}"
                )
            q = (row.get("query") or "").strip()
            if not q:
                raise SystemExit(f"Строка {i}: пустой query")
            queries.append({
                "query":          q,
                "expected_area":  (row.get("expected_area") or "").strip(),
                "expected_label": label,
            })

    if not queries:
        raise SystemExit(f"CSV {path} не содержит ни одной строки")
    return queries


def process(queries: list[dict], top_k: int) -> list[dict]:
    # Импорт здесь — чтобы сообщение об ошибке CSV выдалось раньше,
    # чем загрузится модель (~3-5 сек).
    from project_calc.common.retrieval.search_service import SearchService

    print(f"Инициализация SearchService...")
    ss = SearchService(top_k=top_k)
    print(f"Прогоняем {len(queries)} запросов...\n")

    results: list[dict] = []
    for i, q in enumerate(queries, 1):
        print(f"  [{i:3d}/{len(queries)}] {q['expected_label']:8s}  {q['query']}")
        sr = ss.search(query=q["query"], expected_area=q["expected_area"])
        top = sr.get("results") or []
        top1 = top[0] if top else None
        top2 = top[1] if len(top) > 1 else None

        top1_sim = float(top1["similarity"]) if top1 else 0.0
        top2_sim = float(top2["similarity"]) if top2 else 0.0
        gap = top1_sim - top2_sim

        decision = sr["decision"]
        is_fp = (q["expected_label"] == "negative" and decision != "REJECT")
        is_fn = (q["expected_label"] == "positive" and decision == "REJECT")

        results.append({
            "query":                q["query"],
            "expected_label":       q["expected_label"],
            "expected_area":        q["expected_area"],
            "decision":             decision,
            "top1_similarity":      f"{top1_sim:.4f}",
            "top2_similarity":      f"{top2_sim:.4f}",
            "gap":                  f"{gap:.4f}",
            "top1_equipment_name":  top1["equipment_name"] if top1 else "",
            "top1_area":            top1["area"] if top1 else "",
            "top1_area_matches":    "yes" if (top1 and top1["area"] == q["expected_area"]) else "no",
            "top5_similarities":    "|".join(f"{r['similarity']:.4f}" for r in top[:5]),
            "is_false_positive":    "yes" if is_fp else "no",
            "is_false_negative":    "yes" if is_fn else "no",
        })
    return results


def write_results(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "query", "expected_label", "expected_area", "decision",
        "top1_similarity", "top2_similarity", "gap",
        "top1_equipment_name", "top1_area", "top1_area_matches",
        "top5_similarities", "is_false_positive", "is_false_negative",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter=";")
        writer.writeheader()
        for row in results:
            writer.writerow(row)


def _percentile(sorted_values: list[float], q: float) -> float:
    """Простой квантиль по интерполяции — без numpy."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def print_stats(results: list[dict]) -> None:
    pos = [r for r in results if r["expected_label"] == "positive"]
    neg = [r for r in results if r["expected_label"] == "negative"]
    pos_top1 = [float(r["top1_similarity"]) for r in pos]
    neg_top1 = [float(r["top1_similarity"]) for r in neg]

    fp = sum(1 for r in results if r["is_false_positive"] == "yes")
    fn = sum(1 for r in results if r["is_false_negative"] == "yes")

    def stats(name: str, values: list[float]) -> None:
        if not values:
            print(f"  {name}: (пусто)")
            return
        print(
            f"  {name}: n={len(values)}, "
            f"min={min(values):.3f}, "
            f"max={max(values):.3f}, "
            f"mean={statistics.mean(values):.3f}, "
            f"median={statistics.median(values):.3f}"
        )

    print("\n" + "=" * 60)
    print("СТАТИСТИКА")
    print("=" * 60)
    print(f"\nВсего запросов: {len(results)}  "
          f"(positive: {len(pos)}, negative: {len(neg)})")
    print("\nРаспределение top1_similarity:")
    stats("positive", pos_top1)
    stats("negative", neg_top1)
    print(f"\nFalse positive (negative → не REJECT): {fp}")
    print(f"False negative (positive → REJECT):    {fn}")

    if pos_top1 and neg_top1:
        pos_sorted = sorted(pos_top1)
        neg_sorted = sorted(neg_top1)
        # 10-й перцентиль positive — ниже него уйдёт 10% positive
        p10_pos = _percentile(pos_sorted, 0.10)
        # 90-й перцентиль negative — выше него 10% negative
        p90_neg = _percentile(neg_sorted, 0.90)

        print(f"\nКвантили для пересмотра порогов:")
        print(f"  10-й перцентиль positive top1 = {p10_pos:.3f}  "
              f"(нижняя граница 'обычно правильных')")
        print(f"  90-й перцентиль negative top1 = {p90_neg:.3f}  "
              f"(верхняя граница 'обычно ошибочных')")

        if p10_pos > p90_neg:
            sep = p10_pos - p90_neg
            print(f"\n  Разделение чёткое: positive выше negative на {sep:.3f}")
            mid = (p10_pos + p90_neg) / 2
            print(f"  Рекомендация:")
            print(f"    REJECT_BELOW ~ {p90_neg + 0.01:.2f}")
            print(f"    REVIEW_FROM  ~ {mid:.2f}")
            print(f"    ACCEPT_FROM  ~ {p10_pos:.2f}")
        else:
            overlap = p90_neg - p10_pos
            print(f"\n  Распределения пересекаются на {overlap:.3f}")
            print(f"  Это 'серая зона' для REVIEW: [{p10_pos:.2f}, {p90_neg:.2f}]")
            print(f"  Рекомендация:")
            print(f"    REJECT_BELOW ~ {p10_pos:.2f}")
            print(f"    ACCEPT_FROM  ~ {p90_neg:.2f}")
            print(f"    REVIEW: между этими порогами")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    queries = read_queries(input_path)
    print(f"Прочитано из {input_path}: {len(queries)} запросов")

    results = process(queries, top_k=args.top_k)
    write_results(output_path, results)
    print(f"\nРезультаты записаны: {output_path}")

    print_stats(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
