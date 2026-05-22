"""
Оценка confidence retrieval-результатов.

Принимает список similarities (top-k косинусных схожестей, отсортированных
по убыванию) и возвращает решение:
  * ACCEPT — модель уверена, можно использовать без проверки
  * REVIEW — нашлось похожее, но нужна проверка инженером
  * REJECT — ничего адекватного, нужно добавить в БД

ТЕКУЩИЕ ПОРОГИ (Е.1.3.А — быстрый фикс, +0.03 от исходных):
  top1 < 0.83                      → REJECT
  top1 >= 0.90  AND  gap > 0.05    → ACCEPT
  top1 >= 0.86                      → REVIEW
  иначе                              → REJECT

ИСТОРИЯ ПОРОГОВ:
  v0 (исходные):  REJECT_BELOW=0.80, REVIEW=0.83, ACCEPT=0.87
  v1 (Е.1.3.А):   REJECT_BELOW=0.83, REVIEW=0.86, ACCEPT=0.90  ← сейчас
  v2 (Е.1.3.В):   будет откалибровано после ~70-100 проектов в БД
                  через scripts/calibrate_confidence.py

Эти числа — НЕ оптимальные, это промежуточная мера. Полная калибровка
требует стабильного распределения confidence по реальной БД, что
наступит только после набора большей части целевых 135 проектов.
"""


# Пороги вынесены в константы — удобно править и видеть состояние.
REJECT_BELOW: float = 0.83  # top1 ниже этого — всегда REJECT
REVIEW_FROM:  float = 0.86  # top1 в [REVIEW_FROM, ACCEPT_FROM) — REVIEW
ACCEPT_FROM:  float = 0.90  # top1 >= ACCEPT_FROM с gap > GAP_MIN — ACCEPT
GAP_MIN:      float = 0.05  # минимальный отрыв top1 от top2 для ACCEPT


class ConfidenceEvaluator:

    def __init__(
        self,
        threshold: float = ACCEPT_FROM,
        margin: float = GAP_MIN,
    ):
        # Параметры threshold/margin сейчас не используются evaluate()
        # напрямую (тот читает константы модуля), но оставлены в API
        # для совместимости с прежними вызовами и для будущей возможности
        # переопределять пороги через конструктор.
        self.threshold = threshold
        self.margin = margin

    def evaluate(self, similarities: list[float]) -> str:

        if not similarities:
            return "REJECT"

        top_score = similarities[0]

        # Жёсткий REJECT для откровенно слабых матчей.
        # Это первая линия защиты от нерелевантных запросов
        # (вроде "Сварочный источник" при БД из совсем другой области).
        if top_score < REJECT_BELOW:
            return "REJECT"

        # gap между лучшим и вторым — мера "уверенности" модели.
        # Большой gap = модель явно выделила фаворита.
        # Маленький gap = несколько кандидатов почти равны, нужна проверка.
        if len(similarities) > 1:
            gap = similarities[0] - similarities[1]
        else:
            gap = 0.0

        # Ключевая логика.
        # ACCEPT — высокий top1 + явный отрыв от ближайших.
        if top_score >= ACCEPT_FROM and gap > GAP_MIN:
            return "ACCEPT"

        # REVIEW — top1 в "серой зоне", или ACCEPT-уровень без отрыва.
        if top_score >= REVIEW_FROM:
            return "REVIEW"

        return "REJECT"
