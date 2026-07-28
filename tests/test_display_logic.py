from display_logic import decision_label, selection_reason, was_candidate_before_selection


SCORE_RANGE = (100, 150)
QUALITY_RANGE = (100, 100)


def rec(*, passed=False, score=120, quality=100, reasons=None):
    return {
        "passed": passed,
        "score": score,
        "data_quality": quality,
        "reasons": reasons or [],
    }


def test_selected_market_without_tier_keeps_legacy_label():
    item = rec(passed=True)
    assert decision_label(item, SCORE_RANGE, QUALITY_RANGE) == "Wybrany do TOP 5"


def test_main_pick_gets_main_label():
    item = rec(passed=True, reasons=["Poziom selekcji: główny typ; selection score 123.4"])
    assert decision_label(item, SCORE_RANGE, QUALITY_RANGE) == "Główny typ"


def test_additional_signal_gets_additional_label():
    item = rec(passed=True, reasons=["Poziom selekcji: dodatkowy sygnał; selection score 101.2"])
    assert decision_label(item, SCORE_RANGE, QUALITY_RANGE) == "Dodatkowy sygnał"


def test_category_rejection_is_readable_and_remains_candidate():
    item = rec(reasons=["Obliczenie", "Selekcja końcowa: słabszy, skorelowany rynek w kategorii full_time_goals"])
    assert selection_reason(item) == "słabszy, skorelowany rynek w kategorii full_time_goals"
    assert was_candidate_before_selection(item, SCORE_RANGE, QUALITY_RANGE) is True
    assert decision_label(item, SCORE_RANGE, QUALITY_RANGE) == "Przegrał kategorię"


def test_final_list_rejection_is_readable():
    item = rec(reasons=["Selekcja końcowa: poza końcową listą"])
    assert decision_label(item, SCORE_RANGE, QUALITY_RANGE) == "Poza końcową listą"


def test_ambiguous_half_outcome_is_readable():
    item = rec(reasons=["Selekcja końcowa: brak jednoznacznego lidera 1X2 HT; najlepsze bazy są równe (40%)"])
    assert decision_label(item, SCORE_RANGE, QUALITY_RANGE) == "Niejednoznaczny wynik HT"


def test_failed_rule_and_filter_are_separate_states():
    failed_rule = rec(score=90)
    assert decision_label(failed_rule, SCORE_RANGE, QUALITY_RANGE) == "Poza zakresem score"

    failed_rule_inside_filters = rec(score=110)
    assert decision_label(failed_rule_inside_filters, SCORE_RANGE, QUALITY_RANGE) == "Nie przeszedł progu reguły"
