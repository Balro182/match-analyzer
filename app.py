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
from settlement import settle_recommendations
from storage import delete_match, init_db, list_matches, save_match, settle_match

ROOT = Path(__file__).parent
st.set_page_config(page_title="Analizator meczów", page_icon="⚽", layout="wide")
init_db()


@st.cache_data(ttl=900, show_spinner=False)
def load_listing_for_dates(date_values: tuple[date, ...]):
    return list_matches_for_dates(create_session(), date_values)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dates_between(start: date, end: date) -> tuple[date, ...]:
    return tuple(start + timedelta(days=i) for i in range((end - start).days + 1))


def runtime_config(base: dict) -> dict:
    result = copy.deepcopy(base)
    with st.sidebar:
        st.subheader("Progi predykcji")
        st.caption("Każdy próg dotyczy bieżącej analizy i zostaje zapisany razem z meczem.")
        for r_i, rule in enumerate(result["recommendations"]["rules"]):
            with st.expander(rule["label"]):
                rule["enabled"] = st.checkbox("Predykcja aktywna", bool(rule.get("enabled", True)), key=f"en_{r_i}")
                for c_i, condition in enumerate(rule.get("conditions", [])):
                    side = condition.get("side")
                    method = "gospodarze" if side == "home" else "goście" if side == "away" else {
                        "min": "niższa wartość", "max": "wyższa wartość", "sum": "suma", "mean": "średnia"
                    }.get(condition.get("aggregation"), "średnia")
                    current = float(condition["threshold"])
                    condition["threshold"] = st.number_input(
                        f"{metric_label(condition['metric'])} — {method} {condition.get('operator', '>=')}",
                        value=current, step=0.05 if current < 10 else 1.0, key=f"th_{r_i}_{c_i}"
                    )
    return result


def prediction_table(item: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Predykcja": r["label"],
            "Wynik zgodności": r["score"],
            "Aktywna rekomendacja": "TAK" if r["passed"] else "NIE",
            "Uzasadnienie": " | ".join(r.get("reasons", [])),
        }
        for r in item["recommendations"]
    ])


base_config = load_config()
st.title("⚽ Analizator meczów")
st.caption("Predykcje przedmeczowe, zapis do weryfikacji, rozliczanie wyników i kalibracja progów.")

analysis_tab, pending_tab, history_tab, calibration_tab = st.tabs([
    "Analiza meczów", "Mecze do rozliczenia", "Historia", "Kalibracja progów"
])

with analysis_tab:
    today = date.today()
    with st.sidebar:
        st.header("Zakres analizy")
        selected_range = st.date_input(
            "Zakres dat", value=(today, today), min_value=today - timedelta(days=2),
            max_value=today + timedelta(days=2), format="DD.MM.YYYY"
        )
        start_date, end_date = selected_range if isinstance(selected_range, tuple) and len(selected_range) == 2 else (selected_range, selected_range)
        max_matches = st.slider("Maksymalna liczba spotkań", 1, 100, 20)
        min_score = st.slider("Minimalny wynik rekomendacji", 0, 100, int(base_config["recommendations"].get("min_score", 60)))
        current_config = runtime_config(base_config)

    try:
        listing, unsupported = load_listing_for_dates(dates_between(start_date, end_date))
    except Exception as exc:
        st.error(f"Nie udało się pobrać listy spotkań: {exc}")
        listing, unsupported = [], []

    countries = sorted({m.country for m in listing if m.country})
    c1, c2, c3 = st.columns(3)
    country = c1.selectbox("Kraj", ["Wszystkie"] + countries)
    leagues = sorted({m.league for m in listing if m.league and (country == "Wszystkie" or m.country == country)})
    league = c2.selectbox("Liga", ["Wszystkie"] + leagues)
    search = c3.text_input("Wyszukaj drużynę")
    filtered = [m for m in listing if (country == "Wszystkie" or m.country == country) and (league == "Wszystkie" or m.league == league) and (not search or search.casefold() in f"{m.home_team} {m.away_team}".casefold())]

    if st.button("Pobierz statystyki i rozpocznij analizę", type="primary", disabled=not filtered):
        selected = filtered[:max_matches]
        progress = st.progress(0, text="Rozpoczynanie analizy...")
        details = []
        for idx, summary in enumerate(selected, 1):
            progress.progress(idx / len(selected), text=f"Analiza {idx}/{len(selected)}: {summary.home_team} – {summary.away_team}")
            details.extend(scrape_matches([summary], delay_seconds=0))
        progress.empty()
        results = []
        for match in details:
            recs = analyze_match(match.to_dict(), current_config)
            results.append({
                "match": match.to_dict(),
                "recommendations": [r.to_dict() for r in recs],
                "thresholds": current_config["recommendations"]["rules"],
                "minimum_score": min_score,
            })
        st.session_state["analysis_results"] = results

    for index, item in enumerate(st.session_state.get("analysis_results", [])):
        match = item["match"]
        with st.expander(f"{match.get('match_date') or match.get('listing_date')} | {match['home_team']} – {match['away_team']}"):
            st.write(f"**Kraj:** {match.get('country') or 'brak danych'}  \n**Liga:** {match.get('league') or 'brak danych'}")
            table = prediction_table(item)
            shown = table[table["Wynik zgodności"] >= item.get("minimum_score", 0)]
            st.dataframe(shown, use_container_width=True, hide_index=True)
            if st.button("Zapisz ten mecz do weryfikacji", key=f"save_{index}"):
                ok, message = save_match(item)
                (st.success if ok else st.warning)(message)

with pending_tab:
    pending = list_matches("oczekuje")
    st.subheader("Mecze oczekujące na wynik")
    if not pending:
        st.info("Brak zapisanych meczów oczekujących na rozliczenie.")
    for row in pending:
        with st.expander(f"{row['match_date']} | {row['home_team']} – {row['away_team']}"):
            snapshot = json.loads(row["snapshot_json"])
            st.dataframe(prediction_table(snapshot), use_container_width=True, hide_index=True)
            col1, col2 = st.columns(2)
            home_ft = col1.number_input(f"Gole: {row['home_team']}", min_value=0, max_value=30, step=1, key=f"hft_{row['id']}")
            away_ft = col2.number_input(f"Gole: {row['away_team']}", min_value=0, max_value=30, step=1, key=f"aft_{row['id']}")
            include_ht = st.checkbox("Podaj także wynik do przerwy", key=f"iht_{row['id']}")
            home_ht = away_ht = None
            if include_ht:
                h1, h2 = st.columns(2)
                home_ht = h1.number_input(f"Do przerwy: {row['home_team']}", min_value=0, max_value=20, step=1, key=f"hht_{row['id']}")
                away_ht = h2.number_input(f"Do przerwy: {row['away_team']}", min_value=0, max_value=20, step=1, key=f"aht_{row['id']}")
            b1, b2 = st.columns(2)
            if b1.button("Rozlicz predykcje", type="primary", key=f"settle_{row['id']}"):
                settlement = settle_recommendations(snapshot["recommendations"], int(home_ft), int(away_ft), None if home_ht is None else int(home_ht), None if away_ht is None else int(away_ht))
                settle_match(row["id"], int(home_ft), int(away_ft), None if home_ht is None else int(home_ht), None if away_ht is None else int(away_ht), settlement)
                st.success("Mecz został rozliczony.")
                st.rerun()
            if b2.button("Usuń zapis", key=f"delete_{row['id']}"):
                delete_match(row["id"])
                st.rerun()

with history_tab:
    settled = list_matches("rozliczony")
    st.subheader("Historia rozliczonych meczów")
    all_rows = []
    for row in settled:
        settlement = json.loads(row["settlement_json"] or "[]")
        with st.expander(f"{row['match_date']} | {row['home_team']} {row['home_ft']}:{row['away_ft']} {row['away_team']}"):
            frame = pd.DataFrame(settlement)
            if not frame.empty:
                frame = frame.rename(columns={"label": "Predykcja", "score": "Wynik zgodności", "predicted": "Przewidywana", "actual": "Rzeczywista", "result": "Ocena"})
                st.dataframe(frame[["Predykcja", "Wynik zgodności", "Przewidywana", "Rzeczywista", "Ocena"]], use_container_width=True, hide_index=True)
            for item in settlement:
                all_rows.append({"Mecz": f"{row['home_team']} – {row['away_team']}", "Predykcja": item["label"], "Wynik zgodności": item["score"], "Ocena": item["result"]})
    if all_rows:
        st.download_button("Pobierz historię CSV", pd.DataFrame(all_rows).to_csv(index=False).encode("utf-8-sig"), "historia_predykcji.csv", "text/csv")

with calibration_tab:
    settled = list_matches("rozliczony")
    records = []
    for row in settled:
        for item in json.loads(row["settlement_json"] or "[]"):
            if item["result"] in {"trafiona", "nietrafiona"}:
                records.append(item)
    if not records:
        st.info("Kalibracja pojawi się po rozliczeniu pierwszych meczów.")
    else:
        frame = pd.DataFrame(records)
        frame["trafiona"] = frame["result"].eq("trafiona")
        summary = frame.groupby("label").agg(Typy=("trafiona", "size"), Trafione=("trafiona", "sum"), Średni_wynik=("score", "mean")).reset_index()
        summary["Skuteczność %"] = (summary["Trafione"] / summary["Typy"] * 100).round(1)
        summary = summary.rename(columns={"label": "Predykcja", "Średni_wynik": "Średni wynik zgodności"})
        st.dataframe(summary.sort_values(["Skuteczność %", "Typy"], ascending=[False, False]), use_container_width=True, hide_index=True)
        chosen = st.selectbox("Predykcja do analizy progów", sorted(frame["label"].unique()))
        subset = frame[frame["label"] == chosen]
        threshold_rows = []
        for threshold in range(0, 101, 5):
            sample = subset[subset["score"] >= threshold]
            if len(sample):
                threshold_rows.append({"Minimalny wynik": threshold, "Liczba typów": len(sample), "Trafione": int(sample["trafiona"].sum()), "Skuteczność %": round(sample["trafiona"].mean() * 100, 1)})
        st.dataframe(pd.DataFrame(threshold_rows), use_container_width=True, hide_index=True)
        st.caption("Wnioski są wiarygodniejsze przy większej liczbie rozliczonych typów. Nie należy optymalizować progu na kilku spotkaniach.")

st.warning("Dane są przechowywane w lokalnej bazie SQLite aplikacji. Na Streamlit Community Cloud mogą zostać utracone podczas przebudowy lub przeniesienia aplikacji. Do pełnej trwałości potrzebna będzie zewnętrzna baza, np. Supabase lub PostgreSQL.")
