from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from engine import analyze_match
from scraper import create_session, list_matches, scrape_matches

ROOT = Path(__file__).parent

st.set_page_config(page_title="Match Analyzer", page_icon="⚽", layout="wide")


@st.cache_data(ttl=900, show_spinner=False)
def load_listing(url: str):
    return list_matches(create_session(), url)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


config = load_config()
st.title("⚽ Match Analyzer")
st.caption("Analiza spotkań na podstawie statystyk Mutating oraz konfigurowalnych reguł rekomendacyjnych.")

with st.sidebar:
    st.header("Źródło i filtry")
    listing_url = st.text_input("URL listy spotkań", config["source"]["listing_url"])
    max_matches = st.slider("Maksymalna liczba analizowanych spotkań", 1, 50, 10)
    min_score = st.slider("Minimalny wynik rekomendacji", 0, 100, int(config["recommendations"].get("min_score", 60)))
    st.info("Reguły można edytować w pliku config.yaml bez zmiany kodu aplikacji.")

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
search = col3.text_input("Szukaj drużyny")

filtered = [
    m for m in listing
    if (selected_country == "Wszystkie" or m.country == selected_country)
    and (selected_league == "Wszystkie" or m.league == selected_league)
    and (not search or search.casefold() in f"{m.home_team} {m.away_team}".casefold())
]

st.write(f"Znaleziono **{len(filtered)}** spotkań. Do analizy zostanie użyte maksymalnie **{min(max_matches, len(filtered))}**.")

if st.button("Pobierz statystyki i analizuj", type="primary", disabled=not filtered):
    progress = st.progress(0)
    selected = filtered[:max_matches]
    details = []
    for idx, summary in enumerate(selected, start=1):
        details.extend(scrape_matches([summary], delay_seconds=0))
        progress.progress(idx / len(selected))

    rows = []
    full_results = []
    for match in details:
        match_dict = match.to_dict()
        recs = analyze_match(match_dict, config)
        full_results.append({"match": match_dict, "recommendations": [r.to_dict() for r in recs]})
        for rec in recs:
            if rec.score >= min_score:
                rows.append({
                    "Data": match.match_date,
                    "Godzina": match.kickoff,
                    "Kraj": match.country,
                    "Liga": match.league,
                    "Mecz": f"{match.home_team} – {match.away_team}",
                    "Rekomendacja": rec.label,
                    "Wynik": rec.score,
                    "Spełniona w 100%": "TAK" if rec.passed else "NIE",
                    "Uzasadnienie": " | ".join(rec.reasons),
                    "URL": match.url,
                })

    st.session_state["analysis_results"] = full_results
    st.session_state["analysis_rows"] = rows

if "analysis_rows" in st.session_state:
    rows = st.session_state["analysis_rows"]
    full_results = st.session_state["analysis_results"]
    st.subheader("Ranking rekomendacji")
    if rows:
        df = pd.DataFrame(rows).sort_values(["Wynik", "Mecz"], ascending=[False, True])
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn("Źródło")})
        st.download_button("Pobierz CSV", df.to_csv(index=False).encode("utf-8-sig"), "recommendations.csv", "text/csv")
    else:
        st.warning("Żadna rekomendacja nie przekroczyła ustawionego progu.")

    st.subheader("Szczegóły spotkań")
    for item in full_results:
        match = item["match"]
        with st.expander(f"{match['home_team']} – {match['away_team']} ({match.get('kickoff') or 'brak godziny'})"):
            if match.get("errors"):
                st.error("; ".join(match["errors"]))
            rec_df = pd.DataFrame(item["recommendations"])
            if not rec_df.empty:
                st.dataframe(rec_df[["label", "score", "passed", "reasons"]], use_container_width=True, hide_index=True)
            stats = match.get("stats", {})
            if stats:
                stat_df = pd.DataFrame([{"Metryka": k, "Gospodarze": v["home"], "Goście": v["away"]} for k, v in stats.items()])
                st.dataframe(stat_df, use_container_width=True, hide_index=True)

    payload = json.dumps(full_results, ensure_ascii=False, indent=2)
    st.download_button("Pobierz pełny JSON", payload.encode("utf-8"), "match_analysis.json", "application/json")
