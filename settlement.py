from __future__ import annotations

import re
from typing import Any


def _norm(value: str) -> str:
    return " ".join((value or "").lower().replace("–", "-").split())


def _actual(label: str, home: int, away: int, home_ht: int | None, away_ht: int | None) -> bool | None:
    text = _norm(label)
    total = home + away
    btts = home > 0 and away > 0

    if "średnia" in text or "gole zdobywane" in text or "gole tracone" in text:
        return None
    if "czyste konto gospodarzy" in text or "gospodarze bez straty" in text:
        return away == 0
    if "czyste konto gości" in text or "goście bez straty" in text:
        return home == 0
    if "gospodarze strzelą co najmniej dwa" in text:
        return home >= 2
    if "goście strzelą co najmniej dwa" in text:
        return away >= 2
    if "gospodarze strzelą" in text:
        return home >= 1
    if "goście strzelą" in text:
        return away >= 1

    if "suma goli 0-1" in text:
        return total <= 1
    if "suma goli 2-3" in text:
        return 2 <= total <= 3
    if "suma goli 4+" in text:
        return total >= 4
    match = re.search(r"suma goli\s+([0-4])(?:\D|$)", text)
    if match:
        return total == int(match.group(1))

    if "powyżej 1,5 gola" in text and "pierwszej połowie" not in text and "do przerwy" not in text:
        base = total > 1
        if "obie drużyny" in text:
            return btts and base
        if "wygrana gospodarzy" in text or "gospodarze" in text and "wygryw" in text:
            return home > away and base
        if "wygrana gości" in text or "goście" in text and "wygryw" in text:
            return away > home and base
        if "porażka gospodarzy" in text:
            return home < away and base
        if "porażka gości" in text:
            return away < home and base
        return base
    if "powyżej 2,5 gola" in text and "pierwszej połowie" not in text and "do przerwy" not in text:
        return (btts and total > 2) if "obie drużyny" in text else total > 2
    if "powyżej 3,5 gola" in text:
        return total > 3
    if "poniżej 1,5 gola" in text:
        return total < 2
    if "poniżej 2,5 gola" in text:
        return total < 3
    if "poniżej 3,5 gola" in text:
        return total < 4

    if "obie drużyny strzelą" in text:
        if "nie" in text:
            return not btts
        if "pierwszej połowie" in text or "do przerwy" in text:
            return None if home_ht is None or away_ht is None else home_ht > 0 and away_ht > 0
        if "drugiej połowie" in text:
            return None if home_ht is None or away_ht is None else (home-home_ht > 0 and away-away_ht > 0)
        if "wygrana gospodarzy" in text:
            return home > away and btts
        if "wygrana gości" in text:
            return away > home and btts
        if "remis" in text:
            return home == away and btts
        return btts

    if "do przerwy" in text or "pierwszą połowę" in text or "pierwszej połowie" in text:
        if home_ht is None or away_ht is None:
            return None
        ht_total = home_ht + away_ht
        if "powyżej 0,5" in text:
            return ht_total > 0
        if "powyżej 1,5" in text:
            return ht_total > 1
        if "powyżej 2,5" in text:
            return ht_total > 2
        if "remis" in text and "na koniec" not in text:
            return home_ht == away_ht
        if "gospodarze" in text and ("prowadzą" in text or "wygrywa" in text):
            return home_ht > away_ht
        if "goście" in text and ("prowadzą" in text or "wygrywa" in text):
            return away_ht > home_ht

    # HT/FT: kolejność wyniku dotyczy analizowanej strony. Dla etykiet ogólnych
    # rozliczamy wariant gospodarzy; wariant gości jest odwrócony przez nazwę etykiety.
    if "przerwy" in text and "na koniec" in text:
        if home_ht is None or away_ht is None:
            return None
        ht = "win" if home_ht > away_ht else "lose" if home_ht < away_ht else "draw"
        ft = "win" if home > away else "lose" if home < away else "draw"
        mapping = {
            "wygrana do przerwy i wygrana na koniec": ("win", "win"),
            "wygrana do przerwy i remis na koniec": ("win", "draw"),
            "wygrana do przerwy i porażka na koniec": ("win", "lose"),
            "remis do przerwy i wygrana na koniec": ("draw", "win"),
            "remis do przerwy i remis na koniec": ("draw", "draw"),
            "remis do przerwy i porażka na koniec": ("draw", "lose"),
            "porażka do przerwy i wygrana na koniec": ("lose", "win"),
            "porażka do przerwy i remis na koniec": ("lose", "draw"),
            "porażka do przerwy i porażka na koniec": ("lose", "lose"),
        }
        for phrase, expected in mapping.items():
            if phrase in text:
                return (ht, ft) == expected

    if "wygrana gospodarzy" in text:
        return home > away
    if "wygrana gości" in text:
        return away > home
    if text == "remis" or text.startswith("remis —"):
        return home == away
    return None


def settle_recommendations(recommendations: list[dict[str, Any]], home: int, away: int, home_ht: int | None = None, away_ht: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for recommendation in recommendations:
        predicted = bool(recommendation.get("passed"))
        actual = _actual(recommendation.get("label", ""), home, away, home_ht, away_ht)
        if actual is None:
            result = "brak danych"
        else:
            result = "trafiona" if predicted == actual else "nietrafiona"
        rows.append({
            "rule_id": recommendation.get("rule_id"),
            "label": recommendation.get("label"),
            "score": recommendation.get("score"),
            "predicted": predicted,
            "actual": actual,
            "result": result,
        })
    return rows
