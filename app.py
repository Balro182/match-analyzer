from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from engine import ALGORITHM_VERSION, analyze_match, metric_label
from scraper import create_session, list_matches_for_dates, scrape_matches
from settlement import settle_recommendations, validate_scoreline
from storage import delete_match, init_db, list_matches, reprocess_match, save_match, settle_match

ROOT = Path(__file__).parent
st.set_page_config(page_title="Analizator meczów", page_icon="⚽", layout="wide")
init_db()

MODE_LABELS = {
    "both": "Obie drużyny muszą spełnić próg",
    "any": "Wystarczy jedna drużyna",
    "mean": "Średnia obu drużyn",
    "special": "Stała formuła rynku",
}


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
        st.subheader("Progi i tryby predykcji")
        st.caption("Score 100 oznacza osiągnięcie progu; wartości powyżej 100 oznaczają zapas ponad próg.")
        for rule_index, rule in enumerate(result["recommendations"]["rules"]):
            with st.expander(rule["label"]):
                rule["enabled"] = st.checkbox(
                    "Predykcja aktywna", value=bool(rule.get("enabled", True)), key=f"enabled_{rule_index}"
                )
                current_mode = str(rule.get("mode", "both"))
                if current_mode == "special":
                    st.info("Tryb: stała, jednoznaczna formuła rynku")
                else:
                    options = ["both", "any", "mean"]
                    rule["mode"] = st.selectbox(
                        "Tryb oceny", options,
                        index=options.index(current_mode) if current_mode in options else 0,
                        format_func=lambda value: MODE_LABELS[value], key=f"mode_{rule_index}",
                    )
                for condition_index, condition in enumerate(rule.get("conditions", [])):
                    old = float(condition.get("threshold", 1))
                    current_home = float(condition.get("threshold_home", old))
                    current_away = float(condition.get("threshold_away", old))
                    step = 0.1 if max(abs(current_home), abs(current_away)) < 10 else 1.0
                    minimum = 0.1 if step == 0.1 else 1.0
                    st.caption(f"{metric_label(condition['metric'])} {condition.get('operator', '>=')}")
                    col_a, col_b = st.columns(2)
                    condition["threshold_home"] = col_a.number_input(
                        "Próg A", min_value=minimum, value=max(current_home, minimum), step=step,
                        key=f"threshold_a_{rule_index}_{condition_index}",
                    )
                    condition["threshold_away"] = col_b.number_input(
                        "Próg B", min_value=minimum, value=max(current_away, minimum), step=step,
                        key=f"threshold_b_{rule_index}_{condition_index}",
                    )
                    condition.pop("threshold", None)
                    condition.pop("side", None)
                    condition.pop("aggregation", None)
    return result


def prediction_table(item: dict) -> pd.DataFrame:
    minimum_score = float(item.get("minimum_score", 100))
    minimum_quality = float(item.get("minimum_data_quality", 100))
    require_passed = bool(item.get("require_passed", True))
    rows = []
    for rec in item.get("recommendations", []):
        qualifies = (
            float(rec.get("score", 0)) >= minimum_score
            and float(rec.get("data_quality", 0)) >= minimum_quality
            and (bool(rec.get("passed")) or not require_passed)
        )
        rows.append({
            "Predykcja": rec.get("label"), "Score": rec.get("score"),
            "Jakość danych %": rec.get("data_quality"), "Wartość": rec.get("raw_value"),
            "Próg": rec.get("threshold"), "Tryb": MODE_LABELS.get(rec.get("mode"), rec.get("mode")),
            "Warunek spełniony": "TAK" if rec.get("passed") else "NIE",
            "Spełnia filtr": "TAK" if qualifies else "NIE",
            "Uzasadnienie": " | ".join(rec.get("reasons", [])),
        })
    return pd.DataFrame(rows)


def matching_recommendations(item: dict) -> list[dict]:
    minimum_score = float(item.get("minimum_score", 100))
    minimum_quality = float(item.get("minimum_data_quality", 100))
    require_passed = bool(item.get("require_passed", True))
    return [
        rec for rec in item.get("recommendations", [])
        if float(rec.get("score", 0)) >= minimum_score
        and float(rec.get("data_quality", 0)) >= minimum_quality
        and (bool(rec.get("passed")) or not require_passed)
    ]


def ranking_values(item: dict) -> tuple[float, int, float]:
    matched = matching_recommendations(item)
    if not matched:
        return 0.0, 0, 0.0
    scores = sorted((float(rec["score"]) for rec in matched), reverse=True)
    top = scores[:3]
    return max(scores), len(scores), sum(top) / len(top)


def display_value(value: bool | None) -> str:
    if value is None:
        return "BRAK DANYCH"
    return "TAK" if value else "NIE"


base_config = load_config()
st.title("⚽ Analizator meczów")
st.caption(f"Algorytm {ALGORITHM_VERSION} — predykcje, audytowalne snapshoty, rozliczanie i kalibracja.")
analysis_tab, pending_tab, history_tab, calibration_tab = st.tabs(
    ["Analiza meczów", "Mecze do rozliczenia", "Historia", "Kalibracja progów"]
)

with analysis_tab:
    today = date.today()
    with st.sidebar:
        st.header("Zakres analizy")
        selected_range = st.date_input(
            "Zakres dat", value=(today, today), min_value=today - timedelta(days=2),
            max_value=today + timedelta(days=2), format="DD.MM.YYYY",
        )
        start_date, end_date = selected_range if isinstance(selected_range, tuple) and len(selected_range) == 2 else (selected_range, selected_range)
        display_limit = st.slider("Liczba najlepszych spotkań", 1, 100, 10)
        min_score = st.slider("Minimalny score", 50, 150, int(base_config["recommendations"].get("min_score", 100)))
        min_quality = st.slider("Minimalna jakość danych %", 0, 100, int(base_config["recommendations"].get("min_data_quality", 100)))
        require_passed = st.checkbox("Wymagaj spełnienia warunku rynku", value=True)
        current_config = runtime_config(base_config)

    try:
        listing, unsupported = load_listing_for_dates(dates_between(start_date, end_date))
    except Exception as exc:
        st.error(f"Nie udało się pobrać listy spotkań: {exc}")
        listing, unsupported = [], []
    if unsupported:
        st.warning("Źródło nie obsługuje dat: " + ", ".join(value.strftime("%d.%m.%Y") for value in unsupported))

    countries = sorted({match.country for match in listing if match.country})
    selected_countries = st.multiselect("Kraje", countries, default=[], placeholder="Brak zaznaczenia = wszystkie")
    available_leagues = sorted({match.league for match in listing if match.league and (not selected_countries or match.country in selected_countries)})
    selected_leagues = st.multiselect("Ligi", available_leagues, default=[], placeholder="Brak zaznaczenia = wszystkie")
    search = st.text_input("Wyszukaj drużynę")
    filtered = [
        match for match in listing
        if (not selected_countries or match.country in selected_countries)
        and (not selected_leagues or match.league in selected_leagues)
        and (not search or search.casefold() in f"{match.home_team} {match.away_team}".casefold())
    ]
    m1, m2, m3 = st.columns(3)
    m1.metric("Wszystkie mecze", len(listing))
    m2.metric("Po filtrach", len(filtered))
    m3.metric("Do wyświetlenia", min(display_limit, len(filtered)))

    if st.button("Przeanalizuj wszystkie spotkania", type="primary", disabled=not filtered):
        with st.spinner(f"Pobieranie i analiza {len(filtered)} spotkań w jednej sesji HTTP..."):
            details = scrape_matches(
                filtered,
                delay_seconds=float(current_config.get("source", {}).get("request_delay_seconds", 0.25)),
                session=create_session(),
            )
        all_results = []
        failed = 0
        for match in details:
            match_dict = match.to_dict()
            if match.errors or not match.stats:
                failed += 1
            recommendations = analyze_match(match_dict, current_config)
            item = {
                "match": match_dict,
                "recommendations": [rec.to_dict() for rec in recommendations],
                "thresholds": current_config["recommendations"]["rules"],
                "minimum_score": min_score, "minimum_data_quality": min_quality,
                "require_passed": require_passed, "algorithm_version": ALGORITHM_VERSION,
                "config_version": ALGORITHM_VERSION,
            }
            best, count, average = ranking_values(item)
            item["ranking"] = {"best_score": best, "matched_count": count, "top_average": average}
            all_results.append(item)
        qualifying = [item for item in all_results if matching_recommendations(item)]
        qualifying.sort(key=lambda item: (
            item["ranking"]["best_score"], item["ranking"]["matched_count"], item["ranking"]["top_average"]
        ), reverse=True)
        st.session_state["analysis_all_count"] = len(all_results)
        st.session_state["analysis_failed_count"] = failed
        st.session_state["analysis_qualifying_count"] = len(qualifying)
        st.session_state["analysis_results"] = qualifying[:display_limit]

    results = st.session_state.get("analysis_results", [])
    if "analysis_all_count" in st.session_state:
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Przeanalizowane", st.session_state["analysis_all_count"])
        r2.metric("Błędy/brak danych", st.session_state.get("analysis_failed_count", 0))
        r3.metric("Spełniające wymagania", st.session_state["analysis_qualifying_count"])
        r4.metric("Wyświetlone", len(results))

    for index, item in enumerate(results):
        match = item["match"]
        ranking = item["ranking"]
        with st.expander(
            f"{index + 1}. {match.get('match_date') or match.get('listing_date')} | "
            f"{match['home_team']} – {match['away_team']} | score {ranking['best_score']:.1f}"
        ):
            st.write(f"**Kraj:** {match.get('country') or 'brak'}  \n**Liga:** {match.get('league') or 'brak'}")
            if match.get("errors"):
                st.warning(" | ".join(match["errors"]))
            table = prediction_table(item)
            shown = table[table["Spełnia filtr"] == "TAK"].sort_values("Score", ascending=False)
            st.dataframe(shown, use_container_width=True, hide_index=True)
            with st.expander("Pokaż wszystkie predykcje"):
                st.dataframe(table, use_container_width=True, hide_index=True)
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
            home_ft = col1.number_input(f"Gole: {row['home_team']}", 0, 30, key=f"hft_{row['id']}")
            away_ft = col2.number_input(f"Gole: {row['away_team']}", 0, 30, key=f"aft_{row['id']}")
            include_ht = st.checkbox("Podaj także wynik do przerwy", key=f"iht_{row['id']}")
            home_ht = away_ht = None
            if include_ht:
                h1, h2 = st.columns(2)
                home_ht = h1.number_input(f"Do przerwy: {row['home_team']}", 0, 20, key=f"hht_{row['id']}")
                away_ht = h2.number_input(f"Do przerwy: {row['away_team']}", 0, 20, key=f"aht_{row['id']}")
            b1, b2 = st.columns(2)
            if b1.button("Rozlicz predykcje", type="primary", key=f"settle_{row['id']}"):
                valid, message = validate_scoreline(int(home_ft), int(away_ft), home_ht, away_ht)
                if not valid:
                    st.error(message)
                else:
                    settlement = settle_recommendations(snapshot.get("recommendations", []), int(home_ft), int(away_ft), home_ht, away_ht)
                    settle_match(row["id"], int(home_ft), int(away_ft), home_ht, away_ht, settlement)
                    st.success("Mecz został rozliczony.")
                    st.rerun()
            if b2.button("Usuń zapis", key=f"delete_{row['id']}"):
                delete_match(row["id"])
                st.rerun()

with history_tab:
    settled = list_matches("rozliczony")
    st.subheader("Historia rozliczonych meczów")
    st.caption("Historia jest niezmienna. Ponowne rozliczenie odbywa się wyłącznie po użyciu jawnego przycisku.")
    export_rows = []
    for row in settled:
        settlement = json.loads(row.get("settlement_json") or "[]")
        active = [item for item in settlement if item.get("result") in {"trafiona", "nietrafiona"}]
        hits = sum(item.get("result") == "trafiona" for item in active)
        with st.expander(
            f"{row['match_date']} | {row['home_team']} {row['home_ft']}:{row['away_ft']} {row['away_team']} | "
            f"{hits}/{len(active)} | alg. {row.get('algorithm_version') or 'starszy'}"
        ):
            show_no_type = st.checkbox("Pokaż brak typu", False, key=f"show_{row['id']}")
            visible = settlement if show_no_type else [item for item in settlement if item.get("result") != "brak typu"]
            display_rows = [{
                "Predykcja": item.get("label"), "Score": item.get("score"),
                "Jakość danych %": item.get("data_quality"),
                "Decyzja": "TYPUJEMY" if item.get("predicted") else "BRAK TYPU",
                "Zdarzenie wystąpiło": display_value(item.get("actual")), "Ocena": item.get("result"),
            } for item in visible]
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
            if st.button("Przelicz aktualnym algorytmem", key=f"reprocess_{row['id']}"):
                ok, message = reprocess_match(row["id"])
                (st.success if ok else st.error)(message)
                if ok:
                    st.rerun()
            for item in settlement:
                export_rows.append({"Mecz": f"{row['home_team']} – {row['away_team']}", **item})
    if export_rows:
        st.download_button("Pobierz historię CSV", pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8-sig"), "historia_predykcji.csv", "text/csv")

with calibration_tab:
    records = []
    for row in list_matches("rozliczony"):
        records.extend(item for item in json.loads(row.get("settlement_json") or "[]") if item.get("result") in {"trafiona", "nietrafiona"})
    if not records:
        st.info("Kalibracja pojawi się po rozliczeniu pierwszych aktywnych typów.")
    else:
        frame = pd.DataFrame(records)
        frame["trafiona"] = frame["result"].eq("trafiona")
        summary = frame.groupby("label").agg(
            Typy=("trafiona", "size"), Trafione=("trafiona", "sum"), Średni_score=("score", "mean")
        ).reset_index()
        summary["Nietrafione"] = summary["Typy"] - summary["Trafione"]
        summary["Skuteczność %"] = (summary["Trafione"] / summary["Typy"] * 100).round(1)
        st.dataframe(summary.sort_values(["Skuteczność %", "Typy"], ascending=[False, False]), use_container_width=True, hide_index=True)
        st.caption("Do oceny opłacalności nadal potrzebne są kursy i ROI; sama trafialność nie mierzy wartości zakładu.")

st.warning("SQLite jest odpowiedni lokalnie. Do trwałego wdrożenia wieloużytkownikowego należy ustawić PostgreSQL lub Supabase.")
