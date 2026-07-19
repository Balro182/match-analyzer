from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from engine import analyze_match, metric_label
from scraper import create_session, list_matches_for_dates, scrape_matches

ROOT = Path(__file__).parent

st.set_page_config(page_title="Analizator meczów", page_icon="⚽", layout="wide")


@st.cache_data(ttl=900, show_spinner=False)
def load_listing_for_dates(date_values: tuple[date, ...]):
    return list_matches_for_dates(create_session(), date_values)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def date_sequence(start: date, end: date) -> tuple[date, ...]:
    return tuple(start + timedelta(days=offset) for offset in range((end - start).days + 1))


def build_runtime_config(base_config: dict) -> dict:
    runtime = copy.deepcopy(base_config)
    st.subheader("Progi predykcji")
    st.caption("Tutaj ustawiasz wszystkie warunki używane do oceny spotkań. Zmiany obowiązują dla bieżącej analizy.")

    for rule_index, rule in enumerate(runtime.get("recommendations", {}).get("rules", [])):
        with st.expander(rule["label"], expanded=False):
            rule["enabled"] = st.checkbox(
                "Predykcja aktywna",
                value=bool(rule.get("enabled", True)),
                key=f"rule_enabled_{rule_index}",
            )
            for condition_index, condition in enumerate(rule.get("conditions", [])):
                metric_name = metric_label(condition["metric"])
                side = condition.get("side")
                aggregation = condition.get("aggregation")
                if side == "home":
                    method = "gospodarze"
                elif side == "away":
                    method = "goście"
                else:
                    method = {
                        "min": "niższa wartość obu drużyn",
                        "max": "wyższa wartość obu drużyn",
                        "sum": "suma obu drużyn",
                        "mean": "średnia obu drużyn",
                    }.get(aggregation, "średnia obu drużyn")

                label = f"{metric_name} — {method} {condition.get('operator', '>=')}"
                current = float(condition["threshold"])
                step = 0.05 if current < 10 else 1.0
                condition["threshold"] = st.number_input(
                    label,
                    value=current,
                    step=step,
                    key=f"threshold_{rule_index}_{condition_index}",
                )
    return runtime


base_config = load_config()
st.title("⚽ Analizator meczów")
st.caption("Analiza spotkań, filtrowanie według kraju i ligi oraz testowanie reguł na dostępnych datach historycznych.")

today = date.today()
available_min = today - timedelta(days=2)
available_max = today + timedelta(days=2)

with st.sidebar:
    st.header("Zakres analizy")
    selected_range = st.date_input(
        "Zakres dat",
        value=(today, today),
        min_value=available_min,
        max_value=available_max,
        format="DD.MM.YYYY",
        help="Mutating udostępnia w tym widoku dane od przedwczoraj do dwóch dni naprzód.",
    )
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start_date, end_date = selected_range
    else:
        start_date = end_date = selected_range

    max_matches = st.slider("Maksymalna liczba analizowanych spotkań", 1, 100, 20)
    min_score = st.slider(
        "Minimalny wynik rekomendacji",
        0,
        100,
        int(base_config["recommendations"].get("min_score", 60)),
        help="Pokazuje rekomendacje z wynikiem równym lub wyższym od progu. To zgodność z regułami, a nie prawdopodobieństwo procentowe.",
    )
    st.divider()
    runtime_config = build_runtime_config(base_config)

if start_date > end_date:
    st.error("Data początkowa nie może być późniejsza niż data końcowa.")
    st.stop()

selected_dates = date_sequence(start_date, end_date)

try:
    with st.spinner("Pobieranie listy spotkań..."):
        listing, unsupported_dates = load_listing_for_dates(selected_dates)
except Exception as exc:
    st.error(f"Nie udało się pobrać listy spotkań: {exc}")
    st.stop()

if unsupported_dates:
    formatted = ", ".join(value.strftime("%d.%m.%Y") for value in unsupported_dates)
    st.warning(f"Źródło nie udostępnia stron dla dat: {formatted}.")

countries = sorted({match.country for match in listing if match.country})
col1, col2, col3 = st.columns(3)
selected_country = col1.selectbox("Kraj", ["Wszystkie"] + countries)

country_filtered_leagues = sorted(
    {
        match.league
        for match in listing
        if match.league and (selected_country == "Wszystkie" or match.country == selected_country)
    }
)
selected_league = col2.selectbox("Liga", ["Wszystkie"] + country_filtered_leagues)
search = col3.text_input("Wyszukaj drużynę")

filtered = [
    match
    for match in listing
    if (selected_country == "Wszystkie" or match.country == selected_country)
    and (selected_league == "Wszystkie" or match.league == selected_league)
    and (not search or search.casefold() in f"{match.home_team} {match.away_team}".casefold())
]

summary_col1, summary_col2, summary_col3 = st.columns(3)
summary_col1.metric("Dostępne spotkania", len(listing))
summary_col2.metric("Po zastosowaniu filtrów", len(filtered))
summary_col3.metric("Kraje", len(countries))

st.caption(
    f"Wybrany okres: {start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}. "
    f"Do analizy zostanie użyte maksymalnie {min(max_matches, len(filtered))} spotkań."
)

if not countries and listing:
    st.warning("Nie udało się rozpoznać nazw krajów w danych źródłowych. Parser został zaktualizowany, ale układ strony mógł ponownie się zmienić.")

if st.button("Pobierz statystyki i rozpocznij analizę", type="primary", disabled=not filtered):
    progress = st.progress(0, text="Przygotowywanie analizy...")
    selected = filtered[:max_matches]
    details = []
    for index, summary in enumerate(selected, start=1):
        progress.progress(
            index / len(selected),
            text=f"Analizowanie meczu {index} z {len(selected)}: {summary.home_team} – {summary.away_team}",
        )
        details.extend(scrape_matches([summary], delay_seconds=0))
    progress.empty()

    rows = []
    full_results = []
    for match in details:
        match_dict = match.to_dict()
        recommendations = analyze_match(match_dict, runtime_config)
        full_results.append(
            {"match": match_dict, "recommendations": [recommendation.to_dict() for recommendation in recommendations]}
        )
        for recommendation in recommendations:
            if recommendation.score >= min_score:
                rows.append(
                    {
                        "Data": match.match_date or match.listing_date,
                        "Godzina": match.kickoff,
                        "Kraj": match.country,
                        "Liga": match.league,
                        "Mecz": f"{match.home_team} – {match.away_team}",
                        "Rekomendacja": recommendation.label,
                        "Wynik zgodności": recommendation.score,
                        "Wszystkie warunki spełnione": "TAK" if recommendation.passed else "NIE",
                        "Uzasadnienie": " | ".join(recommendation.reasons),
                        "Adres źródłowy": match.url,
                    }
                )

    st.session_state["analysis_results"] = full_results
    st.session_state["analysis_rows"] = rows
    st.session_state["analysis_period"] = (start_date.isoformat(), end_date.isoformat())

if "analysis_rows" in st.session_state:
    rows = st.session_state["analysis_rows"]
    full_results = st.session_state["analysis_results"]
    period = st.session_state.get("analysis_period")

    st.subheader("Ranking rekomendacji")
    if period:
        st.caption(f"Wyniki analizy dla okresu {period[0]}–{period[1]}")

    if rows:
        dataframe = pd.DataFrame(rows).sort_values(
            ["Wynik zgodności", "Data", "Mecz"], ascending=[False, True, True]
        )
        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True,
            column_config={"Adres źródłowy": st.column_config.LinkColumn("Źródło danych")},
        )
        st.download_button(
            "Pobierz wyniki jako plik CSV",
            dataframe.to_csv(index=False).encode("utf-8-sig"),
            "rekomendacje_meczowe.csv",
            "text/csv",
        )
    else:
        st.warning("Żadna rekomendacja nie osiągnęła ustawionego minimalnego wyniku.")

    st.subheader("Szczegóły analizowanych spotkań")
    for item in full_results:
        match = item["match"]
        display_date = match.get("match_date") or match.get("listing_date") or "brak daty"
        with st.expander(
            f"{display_date} | {match['home_team']} – {match['away_team']} "
            f"({match.get('kickoff') or 'brak podanej godziny'})"
        ):
            st.write(f"**Kraj:** {match.get('country') or 'brak danych'}  \n**Liga:** {match.get('league') or 'brak danych'}")
            if match.get("errors"):
                st.error("; ".join(match["errors"]))

            recommendation_rows = [
                {
                    "Rekomendacja": recommendation["label"],
                    "Wynik zgodności": recommendation["score"],
                    "Wszystkie warunki spełnione": "TAK" if recommendation["passed"] else "NIE",
                    "Uzasadnienie": " | ".join(recommendation["reasons"]),
                }
                for recommendation in item["recommendations"]
            ]
            recommendation_frame = pd.DataFrame(recommendation_rows)
            if not recommendation_frame.empty:
                st.dataframe(recommendation_frame, use_container_width=True, hide_index=True)

            stats = match.get("stats", {})
            if stats:
                stats_frame = pd.DataFrame(
                    [
                        {
                            "Statystyka": metric_label(name),
                            "Gospodarze": values["home"],
                            "Goście": values["away"],
                        }
                        for name, values in stats.items()
                    ]
                )
                st.dataframe(stats_frame, use_container_width=True, hide_index=True)

    payload = json.dumps(full_results, ensure_ascii=False, indent=2)
    st.download_button(
        "Pobierz pełne dane jako plik JSON",
        payload.encode("utf-8"),
        "pelna_analiza_meczow.json",
        "application/json",
    )

st.info(
    "Weryfikacja historyczna: wybierz wczoraj lub przedwczoraj, uruchom analizę i porównaj rekomendacje z końcowymi wynikami meczów. "
    "Obecne źródło udostępnia w widoku dziennym ograniczone okno dat; aplikacja nie udaje dostępu do starszych danych, których strona nie publikuje pod stałym adresem."
)

# Wymuszenie spójnego ponownego wdrożenia po aktualizacji parsera dat.
