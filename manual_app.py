from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from display_logic import (
    decision_label,
    meets_runtime_filters,
    was_candidate_before_selection,
)
from engine import ALGORITHM_VERSION, analyze_match
from exact_score import exact_score_diagnostics
from manual_parser import METRICS, parse_pasted_stats


ROOT = Path(__file__).parent

st.set_page_config(
    page_title="Ręczny analizator meczów",
    page_icon="📋",
    layout="wide",
)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def runtime_config(base: dict, minimum_score: int, minimum_quality: int) -> dict:
    result = copy.deepcopy(base)
    recommendations = result.setdefault("recommendations", {})
    recommendations["min_score"] = int(minimum_score)
    recommendations["min_data_quality"] = int(minimum_quality)
    return result


def clear_manual_form() -> None:
    st.session_state["manual_home_team"] = ""
    st.session_state["manual_away_team"] = ""
    st.session_state["manual_pasted_stats"] = ""


def result_rows(
    recommendations: list[dict],
    score_range: tuple[int, int],
    quality_range: tuple[int, int],
) -> list[dict]:
    rows = []
    score_min, score_max = score_range
    quality_min, quality_max = quality_range

    for rec in recommendations:
        reasons = [str(reason) for reason in rec.get("reasons", [])]
        score = float(rec.get("score", 0))
        quality = float(rec.get("data_quality", 0))
        filter_passed = meets_runtime_filters(rec, score_range, quality_range)
        selected = bool(rec.get("passed")) and filter_passed
        raw_candidate = was_candidate_before_selection(rec, score_range, quality_range)

        if not filter_passed:
            filter_reasons = []
            if score < score_min:
                filter_reasons.append(f"score {score:.1f} < {score_min:g}")
            elif score > score_max:
                filter_reasons.append(f"score {score:.1f} > {score_max:g}")
            if quality < quality_min:
                filter_reasons.append(f"jakość {quality:.1f}% < {quality_min:g}%")
            elif quality > quality_max:
                filter_reasons.append(f"jakość {quality:.1f}% > {quality_max:g}%")
            reasons.append("Filtr ręczny: ODRZUCONE — " + ", ".join(filter_reasons))

        rows.append(
            {
                "Rynek": rec.get("label"),
                "Rule ID": rec.get("rule_id"),
                "Wartość": rec.get("raw_value"),
                "Próg": rec.get("threshold"),
                "Score": rec.get("score"),
                "Jakość %": rec.get("data_quality"),
                "Decyzja": decision_label(rec, score_range, quality_range),
                "Spełnia aktualne zakresy": "TAK" if filter_passed else "NIE",
                "Spełnił regułę przed selekcją": "TAK" if raw_candidate else "NIE",
                "Wybrany końcowo": "TAK" if selected else "NIE",
                "Uzasadnienie": " | ".join(reasons),
            }
        )
    return rows


def exact_score_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).rename(
        columns={
            "score": "Dokładny wynik",
            "model_share": "Udział modelu %",
            "raw_score": "Wskaźnik zgodności",
        }
    )
    if not frame.empty:
        frame["Udział modelu %"] = frame["Udział modelu %"].map(
            lambda value: f"{float(value):.0f}%"
        )
        frame.insert(0, "Miejsce", range(1, len(frame) + 1))
    return frame


def compact_market_frame(rows: list[dict], with_rank: bool = False) -> pd.DataFrame:
    frame = pd.DataFrame(rows).sort_values(
        by=["Score", "Jakość %", "Wartość"],
        ascending=[False, False, False],
        na_position="last",
    )
    if with_rank and not frame.empty:
        frame.insert(0, "Miejsce", range(1, len(frame) + 1))
    columns = ["Rynek", "Wartość", "Próg", "Score", "Jakość %", "Decyzja"]
    if with_rank:
        columns.insert(0, "Miejsce")
    return frame[columns]


base_config = load_config()
base_recommendations = base_config.get("recommendations", {})
default_score = int(base_recommendations.get("min_score", 100))
default_quality = int(base_recommendations.get("min_data_quality", 100))
max_recommendations = int(
    base_recommendations.get("selection", {}).get("max_recommendations", 5)
)

st.title("📋 Ręczny analizator statystyk meczu")
st.info(
    "Wklej cały blok statystyk w takim samym układzie jak z football-stats. "
    "Program używa tego samego engine.py i config.yaml co główna aplikacja."
)

st.subheader("Zakresy końcowej selekcji")
score_col, quality_col = st.columns(2)
score_range = score_col.slider(
    "Zakres score", min_value=0, max_value=150,
    value=(default_score, 150), step=1,
)
quality_range = quality_col.slider(
    "Zakres jakości danych %", min_value=0, max_value=100,
    value=(default_quality, 100), step=1,
)

score_min, score_max = score_range
quality_min, quality_max = quality_range
config = runtime_config(base_config, score_min, quality_min)
recommendation_config = config.get("recommendations", {})

st.caption(
    f"Algorytm {ALGORITHM_VERSION} · score {score_min}–{score_max} · "
    f"jakość {quality_min}–{quality_max}% · maksymalnie TOP {max_recommendations}"
)
st.caption(
    "Ustawienia zakresów obowiązują wyłącznie w bieżącej analizie i nie zmieniają config.yaml."
)

name_col_a, name_col_b = st.columns(2)
home_team = name_col_a.text_input(
    "Gospodarz", placeholder="np. Raków Częstochowa", key="manual_home_team"
)
away_team = name_col_b.text_input(
    "Gość", placeholder="np. Valletta FC", key="manual_away_team"
)

pasted = st.text_area(
    "Dane meczu",
    height=430,
    placeholder=(
        "Main Stats\nGospodarz\nLast 10 games home\nGość\nLast 10 games away\n"
        "2.10    Goals scored per game    0.80\n"
        "1.00    Goals conceded per game    1.10\n..."
    ),
    key="manual_pasted_stats",
)

analyze_col, clear_col = st.columns([3, 1])
analyze = analyze_col.button("🔎 Analizuj", type="primary", use_container_width=True)
clear_col.button(
    "🧹 Wyczyść", use_container_width=True, on_click=clear_manual_form,
    help="Usuwa nazwy drużyn, wklejone statystyki i wynik poprzedniej analizy.",
)

if analyze:
    if not pasted.strip():
        st.error("Wklej dane statystyczne przed uruchomieniem analizy.")
        st.stop()

    parsed = parse_pasted_stats(pasted)
    if not parsed.stats:
        st.error("Nie rozpoznano żadnych wierszy statystycznych.")
        st.stop()

    summary_a, summary_b, summary_c = st.columns(3)
    summary_a.metric("Rozpoznane metryki", len(parsed.stats))
    summary_b.metric("Brakujące metryki", len(parsed.missing_metrics))
    summary_c.metric("Duplikaty", len(parsed.duplicate_metrics))

    if parsed.duplicate_metrics:
        st.warning(
            "Powtórzone metryki — użyto ostatniej wartości: "
            + ", ".join(parsed.duplicate_metrics)
        )

    enabled_metrics = {
        condition.get("metric")
        for rule in recommendation_config.get("rules", [])
        if rule.get("enabled", True)
        for condition in rule.get("conditions", [])
        if condition.get("metric")
    }
    missing_enabled = sorted(
        metric for metric in enabled_metrics if metric not in parsed.stats
    )
    if missing_enabled:
        st.error(
            "Brakuje danych wymaganych przez aktywne reguły: "
            + ", ".join(missing_enabled)
        )
        st.stop()

    match = {
        "home_team": home_team.strip() or "Gospodarz",
        "away_team": away_team.strip() or "Gość",
        "stats": parsed.stats,
        "errors": [],
    }
    recommendations = [rec.to_dict() for rec in analyze_match(match, config)]
    rows = result_rows(recommendations, score_range, quality_range)
    selected_rows = [row for row in rows if row["Wybrany końcowo"] == "TAK"]
    remaining_candidates = [
        row for row in rows
        if row["Spełnił regułę przed selekcją"] == "TAK"
        and row["Wybrany końcowo"] == "NIE"
    ]
    below_threshold_rows = [
        row for row in rows if row["Spełnił regułę przed selekcją"] == "NIE"
    ]
    exact_scores = exact_score_diagnostics(parsed.stats)

    st.divider()
    st.subheader(f"{match['home_team']} – {match['away_team']}")
    st.caption(
        f"Filtry tej analizy: score {score_min}–{score_max}, "
        f"jakość {quality_min}–{quality_max}%"
    )

    st.subheader("Końcowa selekcja")
    if selected_rows:
        st.success(f"Wybrano {len(selected_rows)} rynków do końcowego TOP {max_recommendations}")
        st.dataframe(
            compact_market_frame(selected_rows, with_rank=True),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("Żaden rynek nie przetrwał pełnej selekcji i ustawionych zakresów.")

    st.subheader("Pozostałe rynki, które przeszły progi")
    st.caption(
        "Te rynki spełniły własną regułę oraz filtry score i jakości, ale zostały "
        "odrzucone podczas kontroli spójności, konkurencji kategorii albo limitu TOP."
    )
    if remaining_candidates:
        st.dataframe(
            compact_market_frame(remaining_candidates),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Brak dodatkowych kandydatów odrzuconych dopiero podczas selekcji.")

    st.subheader("Diagnostyka dokładnego wyniku")
    st.caption(
        "Udział modelu to znormalizowany ranking TOP 3, a nie skalibrowane "
        "prawdopodobieństwo bukmacherskie. Te wyniki nie wchodzą do oficjalnego TOP 5."
    )
    ht_col, ft_col = st.columns(2)
    with ht_col:
        st.markdown("#### Dokładny wynik HT — TOP 3")
        st.dataframe(
            exact_score_frame(exact_scores["ht"]),
            use_container_width=True,
            hide_index=True,
        )
    with ft_col:
        st.markdown("#### Dokładny wynik FT — TOP 3")
        st.dataframe(
            exact_score_frame(exact_scores["ft"]),
            use_container_width=True,
            hide_index=True,
        )

    if exact_scores["ht"] and exact_scores["ft"]:
        st.info(
            "Główny scenariusz diagnostyczny: "
            f"HT {exact_scores['ht'][0]['score']} → FT {exact_scores['ft'][0]['score']}"
        )

    with st.expander("Rynki poniżej progów lub poza zakresami"):
        if below_threshold_rows:
            st.dataframe(
                compact_market_frame(below_threshold_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Wszystkie aktywne rynki były kandydatami przed selekcją.")

    with st.expander("Pełne wyliczenia wszystkich aktywnych reguł"):
        all_frame = pd.DataFrame(rows).sort_values(
            by=["Wybrany końcowo", "Spełnia aktualne zakresy", "Score"],
            ascending=[False, False, False], na_position="last",
        )
        st.dataframe(all_frame, use_container_width=True, hide_index=True)

    with st.expander("Rozpoznane dane wejściowe"):
        input_rows = [
            {"Metryka": metric, "Gospodarz": values["home"], "Gość": values["away"]}
            for metric, values in parsed.stats.items()
        ]
        st.dataframe(pd.DataFrame(input_rows), use_container_width=True, hide_index=True)

    if parsed.ignored_lines:
        with st.expander("Pominięte nagłówki i nierozpoznane wiersze"):
            st.code("\n".join(parsed.ignored_lines))

with st.expander("Wymagany format i lista obsługiwanych metryk"):
    st.write(
        "Każdy wiersz metryki musi zawierać dwie liczby: wartość gospodarza przed nazwą "
        "metryki i wartość gościa po nazwie. Procent może być zapisany z symbolem `%` lub bez."
    )
    st.code("60.00%    Win    30.00%\n1.40    Goals scored per game    1.50")
    st.write(f"Obsługiwane metryki: {len(METRICS)}")
    st.code("\n".join(METRICS))
