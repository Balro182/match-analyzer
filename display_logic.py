from __future__ import annotations

from typing import Any


SELECTION_PREFIX = "Selekcja końcowa:"
MAIN_LEVEL_PREFIX = "Poziom selekcji: główny typ"
ADDITIONAL_LEVEL_PREFIX = "Poziom selekcji: dodatkowy sygnał"


def meets_runtime_filters(
    rec: dict[str, Any],
    score_range: tuple[int, int],
    quality_range: tuple[int, int],
) -> bool:
    score = float(rec.get("score", 0))
    quality = float(rec.get("data_quality", 0))
    return (
        score_range[0] <= score <= score_range[1]
        and quality_range[0] <= quality <= quality_range[1]
    )


def selection_reason(rec: dict[str, Any]) -> str | None:
    for reason in reversed(rec.get("reasons", [])):
        text = str(reason)
        if text.startswith(SELECTION_PREFIX):
            return text.removeprefix(SELECTION_PREFIX).strip()
    return None


def selection_level(rec: dict[str, Any]) -> str | None:
    for reason in reversed(rec.get("reasons", [])):
        normalized = str(reason).casefold()
        if MAIN_LEVEL_PREFIX.casefold() in normalized:
            return "main"
        if ADDITIONAL_LEVEL_PREFIX.casefold() in normalized:
            return "additional"
    return None


def was_candidate_before_selection(
    rec: dict[str, Any],
    score_range: tuple[int, int],
    quality_range: tuple[int, int],
) -> bool:
    return meets_runtime_filters(rec, score_range, quality_range) and (
        bool(rec.get("passed")) or selection_reason(rec) is not None
    )


def decision_label(
    rec: dict[str, Any],
    score_range: tuple[int, int],
    quality_range: tuple[int, int],
) -> str:
    in_filters = meets_runtime_filters(rec, score_range, quality_range)
    reason = selection_reason(rec)
    level = selection_level(rec)

    if bool(rec.get("passed")) and in_filters:
        if level == "main":
            return "Główny typ"
        if level == "additional":
            return "Dodatkowy sygnał"
        return "Wybrany do TOP 5"

    if not in_filters:
        score = float(rec.get("score", 0))
        quality = float(rec.get("data_quality", 0))
        if score < score_range[0] or score > score_range[1]:
            return "Poza zakresem score"
        if quality < quality_range[0] or quality > quality_range[1]:
            return "Poza zakresem jakości"
        return "Poza zakresami analizy"

    if reason is None:
        quality = float(rec.get("data_quality", 0))
        if quality < quality_range[0]:
            return "Niewystarczająca jakość danych"
        return "Nie przeszedł progu reguły"

    normalized = reason.casefold()
    if "poza końcowym top" in normalized or "poza końcową listą" in normalized:
        return "Poza końcową listą"
    if "kategorii" in normalized:
        return "Przegrał kategorię"
    if "ht/ft bez potwierdzenia" in normalized:
        return "Brak potwierdzenia HT/FT"
    if "brak jednoznacznego lidera" in normalized:
        return "Niejednoznaczny wynik HT"
    if "przewaga bazy 1x2 ht" in normalized:
        return "Za mała przewaga HT"
    if "nie jest najwyższą surową bazą 1x2 ht" in normalized:
        return "Słabsza baza HT"
    if "wzajemnie wykluczający" in normalized:
        return "Słabszy sygnał 1X2"
    if "sprzeczny z silniejszym" in normalized:
        return "Sprzeczny z silniejszym rynkiem"
    return "Odrzucony w selekcji"
