from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from engine import ALGORITHM_VERSION, analyze_match
from manual_parser import METRICS, parse_pasted_stats


ROOT = Path(__file__).parent
SELECTION_PREFIX = "Selekcja końcowa:"

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


def meets_runtime_filters(rec: dict, minimum_score: float, minimum_quality: float) -> bool:
    return (
        float(rec.get("score", 0)) >= minimum_score
        and float(rec.get("data_quality", 0)) >= minimum_quality
    )


def is_raw_candidate(rec: dict, minimum_score: float, minimum_quality: float) -> bool:
    selection_rejected = any(
        str(reason).startswith(SELECTION_PREFIX)
        for reason in rec.get("reasons", [])
    )
    return (
        meets_runtime_filters(rec, minimum_score, minimum_quality)
        and (bool(rec.get("passed")) or selection_rejected)
    )


def result_rows(
    recommendations: list[dict],
    minimum_score: float,
    minimum_quality: float,
) -> list[dict]:
    rows = []
    for rec in recommendations:
        reasons = [str(reason) for reason in rec.get("reasons", [])]
        filter_passed = meets_runtime_filters(rec, minimum_score, minimum_quality)
        selected = bool(rec.get("passed")) and filter_passed
        raw_candidate = is_raw_candidate(rec, minimum_score, minimum_quality)

        if not filter_passed:
            filter_reasons = []
            if float(rec.get("score", 0)) < minimum_score:
                filter_reasons.append(
                    f"score {float(rec.get('score', 0)):.1f} < {minimum_score:g}"
                )
            if float(rec.get("data_quality", 0)) < minimum_quality:
                filter_reasons.append(
                    f"jakość {float(rec.get('data_quality', 0)):.1f}% < {minimum_quality:g}%"
                )
            reasons.append("Filtr ręczny: ODRZUCONE — " + ", ".join(filter_reasons))

        rows.append(
            {
                "Rynek": rec.get("label"),
                "Rule ID": rec.get("rule_id"),
                "Wartość": rec.get("raw_value"),
                "Próg": rec.get("threshold"),
                "Score": rec.get("score"),
                "Jakość %": rec.get("data_quality"),
                "Spełnia aktualne suwaki": "TAK" if filter_passed else "NIE",
                "Spełnił regułę przed selekcją": "TAK" if raw_candidate else "NIE",
                "Wybrany końcowo": "TAK" if selected else "NIE",
                "Uzasadnienie": " | ".join(reasons),
            }
        )
    return rows


base_config = load_config()
base_recommendations = base_config.get("recommendations", {})
default_score = int(base_recommendations.get("min_score", 100))
default_quality = int(base_recommendations.get("min_data_quality", 100))
max_recommendations = int(
    base_recommendations.get("selection", {}).get("max_recommendations", 5)
)

st.title("📋 Ręczny analizator statystyk meczu")
st.info(
    "Wklej cały blok statystyk w takim samym układzie jak z football-stats: "
    "wartość gospodarza, nazwa metryki, wartość gościa. Program używa tego samego "
    "engine.py i config.yaml co główna aplikacja."
)

st.subheader("Filtry końcowej selekcji")
score_col, quality_col = st.columns(2)
minimum_score = score_col.slider(
    "Minimalny score",
    min_value=50,
    max_value=150,
    value=default_score,
    step=1,
    help="Score 100 oznacza osiągnięcie progu rynku. Wyższa wartość zaostrza końcową selekcję.",
)
minimum_quality = quality_col.slider(
    "Minimalna jakość danych %",
    min_value=0,
    max_value=100,
    value=default_quality,
    step=1,
    help="Rynek przejdzie tylko wtedy, gdy jego jakość danych osiągnie co najmniej tę wartość.",
)
config = runtime_config(base_config, minimum_score, minimum_quality)
recommendation_config = config.get("recommendations", {})

st.caption(
    f"Algorytm {ALGORITHM_VERSION} · score ≥ {minimum_score:g} · "
    f"jakość ≥ {minimum_quality:g}% · maksymalnie TOP {max_recommendations}"
)
st.caption(
    "Ustawienia suwaków obowiązują wyłącznie w bieżącej analizie i nie zmieniają pliku config.yaml."
)

name_col_a, name_col_b = st.columns(2)
home_team = name_col_a.text_input(
    "Gospodarz",
    placeholder="np. Raków Częstochowa",
    key="manual_home_team",
)
away_team = name_col_b.text_input(
    "Gość",
    placeholder="np. Valletta FC",
    key="manual_away_team",
)

pasted = st.text_area(
    "Dane meczu",
    height=430,
    placeholder=(
        "Main Stats\n"
        "Gospodarz\nLast 10 games home\nGość\nLast 10 games away\n"
        "2.10    Goals scored per game    0.80\n"
        "1.00    Goals conceded per game    1.10\n"
        "..."
    ),
    key="manual_pasted_stats",
)

analyze_col, clear_col = st.columns([3, 1])
analyze = analyze_col.button(
    "🔎 Analizuj",
    type="primary",
    use_container_width=True,
)
clear_col.button(
    "🧹 Wyczyść",
    use_container_width=True,
    on_click=clear_manual_form,
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
    rows = result_rows(recommendations, minimum_score, minimum_quality)
    selected_rows = [row for row in rows if row["Wybrany końcowo"] == "TAK"]
    raw_rows = [
        row for row in rows if row["Spełnił regułę przed selekcją"] == "TAK"
    ]

    st.divider()
    st.subheader(f"{match['home_team']} – {match['away_team']}")
    st.caption(
        f"Filtry tej analizy: score ≥ {minimum_score}, jakość ≥ {minimum_quality}%"
    )

    if selected_rows:
        st.success(f"Końcowa selekcja: {len(selected_rows)} rynków")
        selected_frame = pd.DataFrame(selected_rows).sort_values(
            by=["Score", "Jakość %", "Wartość"],
            ascending=[False, False, False],
            na_position="last",
        )
        selected_frame.insert(0, "Miejsce", range(1, len(selected_frame) + 1))
        st.dataframe(
            selected_frame[
                [
                    "Miejsce",
                    "Rynek",
                    "Rule ID",
                    "Wartość",
                    "Próg",
                    "Score",
                    "Jakość %",
                    "Uzasadnienie",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("Żaden rynek nie przetrwał pełnej selekcji końcowej.")

    st.subheader("Wszystkie rynki spełniające progi przed selekcją kategorii/TOP")
    if raw_rows:
        raw_frame = pd.DataFrame(raw_rows).sort_values(
            by=["Score", "Jakość %", "Wartość"],
            ascending=[False, False, False],
            na_position="last",
        )
        st.dataframe(raw_frame, use_container_width=True, hide_index=True)
    else:
        st.info(
            "Brak rynków spełniających jednocześnie regułę, score i jakość danych."
        )

    with st.expander("Pełne wyliczenia wszystkich aktywnych reguł"):
        st.caption(
            "Ta tabela celowo pokazuje również rynki odrzucone. Kolumna „Spełnia aktualne suwaki” "
            "jednoznacznie wskazuje, czy rynek osiągnął ustawiony score i jakość."
        )
        all_frame = pd.DataFrame(rows).sort_values(
            by=["Wybrany końcowo", "Spełnia aktualne suwaki", "Score"],
            ascending=[False, False, False],
            na_position="last",
        )
        st.dataframe(all_frame, use_container_width=True, hide_index=True)

    with st.expander("Rozpoznane dane wejściowe"):
        input_rows = [
            {
                "Metryka": metric,
                "Gospodarz": values["home"],
                "Gość": values["away"],
            }
            for metric, values in parsed.stats.items()
        ]
        st.dataframe(
            pd.DataFrame(input_rows), use_container_width=True, hide_index=True
        )

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
