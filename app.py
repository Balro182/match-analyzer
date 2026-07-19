from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from engine import analyze_match, metric_label
from scraper import create_session, list_matches, scrape_matches

ROOT = Path(__file__).parent

st.set_page_config(page_title="Analizator meczów", page_icon="⚽", layout="wide")


@st.cache_data(ttl=900, show_spinner=False)
def load_listing(url: str):
    return list_matches(create_session(), url)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


config = load_config()
st.title("⚽ Analizator meczów")
st.caption("Analiza spotkań na podstawie statystyk Mutating oraz konfigurowalnych reguł rekomendacyjnych.")

with st.sidebar:
    st.header("Źródło danych i ustawienia")
    listing_url = st.text_input("Adres strony z listą spotkań", config["source"]["listing_url"])
    max_matches = st.slider("Maksymalna liczba analizowanych spotkań", 1, 50, 10)
    min_score = st.slider(
        "Minimalny wynik rekomendacji",
        0,
        100,
        int(config["recommendations"].get("min_score", 60)),
        help="Pokazuje tylko rekomendacje z wynikiem równym lub wyższym od ustawionego progu. Wynik oznacza zgodność z regułami, a nie procentowe prawdopodobieństwo zdarzenia.",
    )
    st.info("Reguły analizy są zapisane w konfiguracji aplikacji.")

try:
    listing = load_listing(listing_url)
except Exception as exc:
    st.error(f"Nie udało się pobrać listy spotkań: {exc}")
    st.stop()

countries = sorted({m.country for m in listing if m.country})
leagues = sorted({m.league for m in listing if m.league})
col1, col2, col3 = st.columns(3)
selected_country = col1.selectbox("Kraj", ["Wszystkie"] + countries)
selected_league = col2.selectbox("Liga", ["Wszystkie"] + leagues)
search = col3.text_input("Wyszukaj drużynę")

filtered = [
    m
    for m in listing
    if (selected_country == "Wszystkie" or m.country == selected_country)
    and (selected_league == "Wszystkie" or m.league == selected_league)
    and (not search or search.casefold() in f"{m.home_team} {m.away_team}".casefold())
]

st.write(
    f"Znaleziono **{len(filtered)}** spotkań. "
    f"Do analizy zostanie użyte maksymalnie **{min(max_matches, len(filtered))}**."
)

if st.button("Pobierz statystyki i rozpocznij analizę", type="primary", disabled=not filtered):
    progress = st.progress(0, text="Przygotowywanie analizy...")
    selected = filtered[:max_matches]
    details = []
    for idx, summary in enumerate(selected, start=1):
        progress.progress(
            idx / len(selected),
            text=f"Analizowanie meczu {idx} z {len(selected)}: {summary.home_team} – {summary.away_team}",
        )
        details.extend(scrape_matches([summary], delay_seconds=0))
    progress.empty()

    rows = []
    full_results = []
    for match in details:
        match_dict = match.to_dict()
        recs = analyze_match(match_dict, config)
        full_results.append({"match": match_dict, "recommendations": [r.to_dict() for r in recs]})
        for rec in recs:
            if rec.score >= min_score:
                rows.append(
                    {
                        "Data": match.match_date,
                        "Godzina": match.kickoff,
                        "Kraj": match.country,
                        "Liga": match.league,
                        "Mecz": f"{match.home_team} – {match.away_team}",
                        "Rekomendacja": rec.label,
                        "Wynik zgodności": rec.score,
                        "Wszystkie warunki spełnione": "TAK" if rec.passed else "NIE",
                        "Uzasadnienie": " | ".join(rec.reasons),
                        "Adres źródłowy": match.url,
                    }
                )

    st.session_state["analysis_results"] = full_results
    st.session_state["analysis_rows"] = rows

if "analysis_rows" in st.session_state:
    rows = st.session_state["analysis_rows"]
    full_results = st.session_state["analysis_results"]
    st.subheader("Ranking rekomendacji")
    if rows:
        df = pd.DataFrame(rows).sort_values(["Wynik zgodności", "Mecz"], ascending=[False, True])
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={"Adres źródłowy": st.column_config.LinkColumn("Źródło danych")},
        )
        st.download_button(
            "Pobierz wyniki jako plik CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            "rekomendacje_meczowe.csv",
            "text/csv",
        )
    else:
        st.warning("Żadna rekomendacja nie osiągnęła ustawionego minimalnego wyniku.")

    st.subheader("Szczegóły analizowanych spotkań")
    for item in full_results:
        match = item["match"]
        with st.expander(
            f"{match['home_team']} – {match['away_team']} "
            f"({match.get('kickoff') or 'brak podanej godziny'})"
        ):
            if match.get("errors"):
                st.error("; ".join(match["errors"]))

            recommendations = []
            for recommendation in item["recommendations"]:
                recommendations.append(
                    {
                        "Rekomendacja": recommendation["label"],
                        "Wynik zgodności": recommendation["score"],
                        "Wszystkie warunki spełnione": "TAK" if recommendation["passed"] else "NIE",
                        "Uzasadnienie": " | ".join(recommendation["reasons"]),
                    }
                )
            rec_df = pd.DataFrame(recommendations)
            if not rec_df.empty:
                st.dataframe(rec_df, use_container_width=True, hide_index=True)

            stats = match.get("stats", {})
            if stats:
                stat_df = pd.DataFrame(
                    [
                        {
                            "Statystyka": metric_label(name),
                            "Gospodarze": values["home"],
                            "Goście": values["away"],
                        }
                        for name, values in stats.items()
                    ]
                )
                st.dataframe(stat_df, use_container_width=True, hide_index=True)

    payload = json.dumps(full_results, ensure_ascii=False, indent=2)
    st.download_button(
        "Pobierz pełne dane jako plik JSON",
        payload.encode("utf-8"),
        "pelna_analiza_meczow.json",
        "application/json",
    )
