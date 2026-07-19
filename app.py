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
                rule["enabled"] = st.checkbox(
                    "Predykcja aktywna",
                    bool(rule.get("enabled", True)),
                    key=f"en_{r_i}",
                )
                for c_i, condition in enumerate(rule.get("conditions", [])):
                    side = condition.get("side")
                    method = (
                        "gospodarze (A)"
                        if side == "home"
                        else "goście (B)"
                        if side == "away"
                        else {
                            "min": "niższa wartość obu drużyn",
                            "max": "wyższa wartość obu drużyn",
                            "sum": "suma obu drużyn",
                            "mean": "średnia obu drużyn",
                        }.get(condition.get("aggregation"), "średnia obu drużyn")
                    )
                    current = float(condition["threshold"])
                    condition["threshold"] = st.number_input(
                        f"{metric_label(condition['metric'])} — {method} {condition.get('operator', '>=')}",
                        value=current,
                        step=0.05 if current < 10 else 1.0,
                        key=f"th_{r_i}_{c_i}",
                    )
    return result


def prediction_table(item: dict) -> pd.DataFrame:
    minimum_score = float(item.get("minimum_score", 0))
    require_passed = bool(item.get("require_passed", False))
    return pd.DataFrame(
        [
            {
                "Predykcja": recommendation["label"],
                "Wynik zgodności": recommendation["score"],
                "Wszystkie warunki spełnione": "TAK" if recommendation["passed"] else "NIE",
                "Spełnia filtr": "TAK"
                if recommendation["score"] >= minimum_score
                and (recommendation["passed"] or not require_passed)
                else "NIE",
                "Uzasadnienie": " | ".join(recommendation.get("reasons", [])),
            }
            for recommendation in item["recommendations"]
        ]
    )


def matching_recommendations(item: dict) -> list[dict]:
    minimum_score = float(item.get("minimum_score", 0))
    require_passed = bool(item.get("require_passed", False))
    return [
        recommendation
        for recommendation in item["recommendations"]
        if recommendation["score"] >= minimum_score
        and (recommendation["passed"] or not require_passed)
    ]


def ranking_values(item: dict) -> tuple[float, int, float]:
    matched = matching_recommendations(item)
    if not matched:
        return 0.0, 0, 0.0
    scores = sorted((float(rec["score"]) for rec in matched), reverse=True)
    top_scores = scores[:3]
    return max(scores), len(matched), sum(top_scores) / len(top_scores)


base_config = load_config()
st.title("⚽ Analizator meczów")
st.caption("Predykcje przedmeczowe, zapis do weryfikacji, rozliczanie wyników i kalibracja progów.")

analysis_tab, pending_tab, history_tab, calibration_tab = st.tabs(
    ["Analiza meczów", "Mecze do rozliczenia", "Historia", "Kalibracja progów"]
)

with analysis_tab:
    today = date.today()
    with st.sidebar:
        st.header("Zakres analizy")
        selected_range = st.date_input(
            "Zakres dat",
            value=(today, today),
            min_value=today - timedelta(days=2),
            max_value=today + timedelta(days=2),
            format="DD.MM.YYYY",
        )
        start_date, end_date = (
            selected_range
            if isinstance(selected_range, tuple) and len(selected_range) == 2
            else (selected_range, selected_range)
        )
        display_limit = st.slider(
            "Liczba najlepszych spotkań do wyświetlenia",
            1,
            100,
            10,
            help="Aplikacja najpierw analizuje całą pulę, a następnie pokazuje wskazaną liczbę najwyżej ocenionych spotkań.",
        )
        min_score = st.slider(
            "Minimalny wynik predykcji",
            0,
            100,
            int(base_config["recommendations"].get("min_score", 60)),
        )
        require_passed = st.checkbox(
            "Wymagaj spełnienia wszystkich warunków predykcji",
            value=True,
            help="Po wyłączeniu wystarczy osiągnięcie minimalnego wyniku zgodności.",
        )
        current_config = runtime_config(base_config)

    try:
        listing, unsupported = load_listing_for_dates(dates_between(start_date, end_date))
    except Exception as exc:
        st.error(f"Nie udało się pobrać listy spotkań: {exc}")
        listing, unsupported = [], []

    if unsupported:
        unsupported_text = ", ".join(value.strftime("%d.%m.%Y") for value in unsupported)
        st.warning(f"Źródło nie udostępnia stron dla dat: {unsupported_text}.")

    countries = sorted({match.country for match in listing if match.country})
    c1, c2, c3 = st.columns(3)
    country = c1.selectbox("Kraj", ["Wszystkie"] + countries)
    leagues = sorted(
        {
            match.league
            for match in listing
            if match.league and (country == "Wszystkie" or match.country == country)
        }
    )
    league = c2.selectbox("Liga", ["Wszystkie"] + leagues)
    search = c3.text_input("Wyszukaj drużynę")
    filtered = [
        match
        for match in listing
        if (country == "Wszystkie" or match.country == country)
        and (league == "Wszystkie" or match.league == league)
        and (not search or search.casefold() in f"{match.home_team} {match.away_team}".casefold())
    ]

    m1, m2, m3 = st.columns(3)
    m1.metric("Wszystkie spotkania w terminie", len(listing))
    m2.metric("Spotkania po filtrach wstępnych", len(filtered))
    m3.metric("Maksymalnie wyświetlanych", min(display_limit, len(filtered)))

    st.info(
        "Po kliknięciu aplikacja pobierze statystyki dla wszystkich spotkań pozostałych po filtrach kraju, ligi i drużyny. "
        "Dopiero po pełnej analizie odrzuci mecze niespełniające progów i utworzy ranking najlepszych wyników."
    )

    if st.button(
        "Przeanalizuj wszystkie spotkania z wybranego zakresu",
        type="primary",
        disabled=not filtered,
    ):
        progress = st.progress(0, text="Rozpoczynanie pełnej analizy...")
        details = []
        for idx, summary in enumerate(filtered, 1):
            progress.progress(
                idx / len(filtered),
                text=f"Pobieranie i analiza {idx}/{len(filtered)}: {summary.home_team} – {summary.away_team}",
            )
            details.extend(scrape_matches([summary], delay_seconds=0))
        progress.empty()

        all_results = []
        for match in details:
            recommendations = analyze_match(match.to_dict(), current_config)
            item = {
                "match": match.to_dict(),
                "recommendations": [recommendation.to_dict() for recommendation in recommendations],
                "thresholds": current_config["recommendations"]["rules"],
                "minimum_score": min_score,
                "require_passed": require_passed,
            }
            best_score, matched_count, top_average = ranking_values(item)
            item["ranking"] = {
                "best_score": best_score,
                "matched_count": matched_count,
                "top_average": top_average,
            }
            all_results.append(item)

        qualifying = [item for item in all_results if matching_recommendations(item)]
        qualifying.sort(
            key=lambda item: (
                item["ranking"]["best_score"],
                item["ranking"]["matched_count"],
                item["ranking"]["top_average"],
            ),
            reverse=True,
        )
        st.session_state["analysis_all_count"] = len(all_results)
        st.session_state["analysis_qualifying_count"] = len(qualifying)
        st.session_state["analysis_results"] = qualifying[:display_limit]

    results = st.session_state.get("analysis_results", [])
    if "analysis_all_count" in st.session_state:
        r1, r2, r3 = st.columns(3)
        r1.metric("Przeanalizowane spotkania", st.session_state["analysis_all_count"])
        r2.metric("Spełniające wymagania", st.session_state["analysis_qualifying_count"])
        r3.metric("Wyświetlone najlepsze", len(results))

    if "analysis_all_count" in st.session_state and not results:
        st.warning("Żadne spotkanie nie spełniło ustawionych progów i wymagań.")

    for index, item in enumerate(results):
        match = item["match"]
        ranking = item.get("ranking", {})
        with st.expander(
            f"{index + 1}. {match.get('match_date') or match.get('listing_date')} | "
            f"{match['home_team']} – {match['away_team']} | "
            f"najlepszy wynik {ranking.get('best_score', 0):.0f}"
        ):
            st.write(
                f"**Kraj:** {match.get('country') or 'brak danych'}  \n"
                f"**Liga:** {match.get('league') or 'brak danych'}  \n"
                f"**Liczba predykcji spełniających filtr:** {ranking.get('matched_count', 0)}"
            )
            table = prediction_table(item)
            shown = table[table["Spełnia filtr"] == "TAK"].sort_values(
                "Wynik zgodności", ascending=False
            )
            st.dataframe(shown, use_container_width=True, hide_index=True)
            with st.expander("Pokaż wszystkie predykcje dla tego meczu"):
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
            home_ft = col1.number_input(
                f"Gole: {row['home_team']}", min_value=0, max_value=30, step=1, key=f"hft_{row['id']}"
            )
            away_ft = col2.number_input(
                f"Gole: {row['away_team']}", min_value=0, max_value=30, step=1, key=f"aft_{row['id']}"
            )
            include_ht = st.checkbox("Podaj także wynik do przerwy", key=f"iht_{row['id']}")
            home_ht = away_ht = None
            if include_ht:
                h1, h2 = st.columns(2)
                home_ht = h1.number_input(
                    f"Do przerwy: {row['home_team']}", min_value=0, max_value=20, step=1, key=f"hht_{row['id']}"
                )
                away_ht = h2.number_input(
                    f"Do przerwy: {row['away_team']}", min_value=0, max_value=20, step=1, key=f"aht_{row['id']}"
                )
            b1, b2 = st.columns(2)
            if b1.button("Rozlicz predykcje", type="primary", key=f"settle_{row['id']}"):
                settlement = settle_recommendations(
                    snapshot["recommendations"],
                    int(home_ft),
                    int(away_ft),
                    None if home_ht is None else int(home_ht),
                    None if away_ht is None else int(away_ht),
                )
                settle_match(
                    row["id"],
                    int(home_ft),
                    int(away_ft),
                    None if home_ht is None else int(home_ht),
                    None if away_ht is None else int(away_ht),
                    settlement,
                )
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
        with st.expander(
            f"{row['match_date']} | {row['home_team']} {row['home_ft']}:{row['away_ft']} {row['away_team']}"
        ):
            frame = pd.DataFrame(settlement)
            if not frame.empty:
                frame = frame.rename(
                    columns={
                        "label": "Predykcja",
                        "score": "Wynik zgodności",
                        "predicted": "Przewidywana",
                        "actual": "Rzeczywista",
                        "result": "Ocena",
                    }
                )
                st.dataframe(
                    frame[["Predykcja", "Wynik zgodności", "Przewidywana", "Rzeczywista", "Ocena"]],
                    use_container_width=True,
                    hide_index=True,
                )
            for item in settlement:
                all_rows.append(
                    {
                        "Mecz": f"{row['home_team']} – {row['away_team']}",
                        "Predykcja": item["label"],
                        "Wynik zgodności": item["score"],
                        "Ocena": item["result"],
                    }
                )
    if all_rows:
        st.download_button(
            "Pobierz historię CSV",
            pd.DataFrame(all_rows).to_csv(index=False).encode("utf-8-sig"),
            "historia_predykcji.csv",
            "text/csv",
        )

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
        summary = (
            frame.groupby("label")
            .agg(
                Typy=("trafiona", "size"),
                Trafione=("trafiona", "sum"),
                Średni_wynik=("score", "mean"),
            )
            .reset_index()
        )
        summary["Skuteczność %"] = (summary["Trafione"] / summary["Typy"] * 100).round(1)
        summary = summary.rename(
            columns={"label": "Predykcja", "Średni_wynik": "Średni wynik zgodności"}
        )
        st.dataframe(
            summary.sort_values(["Skuteczność %", "Typy"], ascending=[False, False]),
            use_container_width=True,
            hide_index=True,
        )
        chosen = st.selectbox("Predykcja do analizy progów", sorted(frame["label"].unique()))
        subset = frame[frame["label"] == chosen]
        threshold_rows = []
        for threshold in range(0, 101, 5):
            sample = subset[subset["score"] >= threshold]
            if len(sample):
                threshold_rows.append(
                    {
                        "Minimalny wynik": threshold,
                        "Liczba typów": len(sample),
                        "Trafione": int(sample["trafiona"].sum()),
                        "Skuteczność %": round(sample["trafiona"].mean() * 100, 1),
                    }
                )
        st.dataframe(pd.DataFrame(threshold_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Wnioski są wiarygodniejsze przy większej liczbie rozliczonych typów. "
            "Nie należy optymalizować progu na kilku spotkaniach."
        )

st.warning(
    "Dane są przechowywane w lokalnej bazie SQLite aplikacji. Na Streamlit Community Cloud mogą zostać utracone "
    "podczas przebudowy lub przeniesienia aplikacji. Do pełnej trwałości potrzebna będzie zewnętrzna baza, "
    "np. Supabase lub PostgreSQL."
)
