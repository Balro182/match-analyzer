from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from engine import ALGORITHM_VERSION, analyze_match
from exact_score import exact_score_diagnostics
from manual_parser import parse_pasted_stats
from validation_store import (
    DEFAULT_DB_PATH,
    DuplicateAnalysisError,
    aggregate_dashboard,
    backend_name,
    export_csv,
    import_history_csv,
    init_db,
    list_matches,
    recommendation_rows,
    save_analysis,
    settle_match,
)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / DEFAULT_DB_PATH

st.set_page_config(page_title="Backtest", page_icon="📊", layout="wide")


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def metric_table(data: dict) -> pd.DataFrame:
    return pd.DataFrame([{"Grupa": name, **values} for name, values in data.items()])


def selected_recommendations(recommendations):
    return [
        rec for rec in recommendations
        if rec.passed and any("Poziom selekcji:" in reason for reason in rec.reasons)
    ]


try:
    init_db(DB_PATH)
except Exception as exc:
    st.error(f"Nie można połączyć się z magazynem backtestu: {exc}")
    st.stop()

st.title("📊 Backtest i walidacja modelu")
st.caption(f"Algorytm {ALGORITHM_VERSION} · backend: {backend_name()}")
if backend_name().startswith("SQLite"):
    st.warning(
        "Działa fallback SQLite. Na Streamlit Cloud dane mogą zniknąć po restarcie. "
        "Dodaj SUPABASE_URL i SUPABASE_SERVICE_ROLE_KEY w Secrets, aby włączyć trwały PostgreSQL."
    )
else:
    st.success("Trwały magazyn Supabase PostgreSQL jest aktywny.")

analyze_tab, settle_tab, dashboard_tab, import_tab = st.tabs([
    "Zapis prognozy", "Rozliczenie", "Dashboard", "Import historyczny"
])

with analyze_tab:
    st.caption("Prognoza i kursy są zapisywane w chwili analizy, przed poznaniem wyniku.")
    meta_a, meta_b, meta_c = st.columns(3)
    match_date = meta_a.date_input("Data meczu", value=date.today())
    series_name = meta_b.text_input("Seria walidacyjna", value="validation-2.11")
    bookmaker = meta_c.text_input("Bukmacher", placeholder="opcjonalnie")

    col_a, col_b = st.columns(2)
    home_team = col_a.text_input("Gospodarz", key="bt_home")
    away_team = col_b.text_input("Gość", key="bt_away")
    pasted = st.text_area("Dane statystyczne", height=360, key="bt_stats")

    if st.button("Analizuj", type="primary", use_container_width=True):
        if not pasted.strip():
            st.error("Wklej dane statystyczne.")
        else:
            parsed = parse_pasted_stats(pasted)
            if not parsed.stats:
                st.error("Nie rozpoznano danych.")
            else:
                match = {
                    "home_team": home_team.strip() or "Gospodarz",
                    "away_team": away_team.strip() or "Gość",
                    "stats": parsed.stats,
                    "errors": [],
                }
                config = load_config()
                recommendations = analyze_match(match, config)
                diagnostics = exact_score_diagnostics(parsed.stats)
                st.session_state["pending_backtest"] = {
                    "match": match,
                    "recommendations": recommendations,
                    "config": config,
                    "predicted_ht": diagnostics["ht"][0]["score"] if diagnostics["ht"] else None,
                    "predicted_ft": diagnostics["ft"][0]["score"] if diagnostics["ft"] else None,
                    "match_date": match_date.isoformat(),
                    "series_name": series_name.strip() or "validation-2.11",
                    "bookmaker": bookmaker.strip() or None,
                }

    pending = st.session_state.get("pending_backtest")
    if pending:
        selected = selected_recommendations(pending["recommendations"])
        st.markdown(f"### {pending['match']['home_team']} – {pending['match']['away_team']}")
        st.info(f"Scenariusz diagnostyczny: HT {pending['predicted_ht']} → FT {pending['predicted_ft']}")
        if selected:
            st.dataframe(pd.DataFrame([rec.to_dict() for rec in selected]), use_container_width=True, hide_index=True)
            st.markdown("#### Kursy w chwili prognozy")
            odds_by_rule: dict[str, float] = {}
            for rec in selected:
                value = st.number_input(
                    f"{rec.label}", min_value=1.0, value=1.0, step=0.01,
                    key=f"prediction_odds_{pending['match_date']}_{rec.rule_id}",
                )
                if value > 1.0:
                    odds_by_rule[rec.rule_id] = float(value)
            policy = st.radio(
                "Gdy analiza już istnieje",
                ["Anuluj zapis", "Zwróć istniejący rekord"], horizontal=True,
            )
            if st.button("💾 Zapisz dokładnie tę prognozę", type="primary", use_container_width=True):
                try:
                    match_id = save_analysis(
                        pending["match"], pending["recommendations"], ALGORITHM_VERSION,
                        predicted_ht=pending["predicted_ht"], predicted_ft=pending["predicted_ft"],
                        path=DB_PATH, match_date=pending["match_date"], source="live_analysis",
                        series_name=pending["series_name"], config_snapshot=pending["config"],
                        odds_by_rule=odds_by_rule, bookmaker=pending["bookmaker"],
                        duplicate_policy="return_existing" if policy.startswith("Zwróć") else "error",
                    )
                    st.success(f"Zapisano prognozę jako mecz #{match_id}.")
                    del st.session_state["pending_backtest"]
                except DuplicateAnalysisError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Błąd zapisu: {exc}")
        else:
            st.warning("Brak oficjalnie wybranych typów; analizy nie zapisano.")

with settle_tab:
    open_matches = list_matches(DB_PATH, unsettled_only=True)
    if not open_matches:
        st.info("Brak nierozliczonych meczów.")
    else:
        labels = {
            f"#{row['id']} · {row['home_team']} – {row['away_team']} · {row['algorithm_version']}": row["id"]
            for row in open_matches
        }
        selected_label = st.selectbox("Mecz", list(labels))
        match_id = labels[selected_label]
        ht_col, ft_col = st.columns(2)
        actual_ht = ht_col.text_input("Wynik HT", placeholder="0:0")
        actual_ft = ft_col.text_input("Wynik FT", placeholder="1:0")

        selected_rows = [r for r in recommendation_rows(DB_PATH, selected_only=True) if int(r["match_id"]) == int(match_id)]
        closing_odds: dict[str, float] = {}
        if selected_rows:
            st.dataframe(pd.DataFrame(selected_rows), use_container_width=True, hide_index=True)
            st.markdown("#### Kursy zamknięcia — opcjonalnie")
            for row in selected_rows:
                value = st.number_input(
                    f"Closing: {row['label']}", min_value=1.0, value=1.0, step=0.01,
                    key=f"closing_{match_id}_{row['rule_id']}",
                )
                if value > 1.0:
                    closing_odds[str(row["rule_id"])] = float(value)

        if st.button("Rozlicz mecz", type="primary"):
            try:
                result = settle_match(
                    match_id, actual_ht, actual_ft, path=DB_PATH,
                    closing_odds_by_rule=closing_odds,
                )
                st.success(f"Rozliczono {result['settled']} rynków; pominięto {result['skipped']}.")
                st.rerun()
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))

with dashboard_tab:
    all_matches = list_matches(DB_PATH)
    versions = sorted({str(row["algorithm_version"]) for row in all_matches})
    sources = sorted({str(row.get("source")) for row in all_matches if row.get("source")})
    series = sorted({str(row.get("series_name")) for row in all_matches if row.get("series_name")})

    f1, f2, f3 = st.columns(3)
    version_filter = f1.selectbox("Wersja", ["Wszystkie", *versions])
    source_filter = f2.selectbox("Źródło", ["Wszystkie", *sources])
    series_filter = f3.selectbox("Seria", ["Wszystkie", *series])
    filters = {
        "algorithm_version": None if version_filter == "Wszystkie" else version_filter,
        "source": None if source_filter == "Wszystkie" else source_filter,
        "series_name": None if series_filter == "Wszystkie" else series_filter,
    }
    dashboard = aggregate_dashboard(DB_PATH, **filters)
    overall = dashboard["overall"]
    a, b, c, d = st.columns(4)
    a.metric("Rozliczone typy", overall["total"])
    b.metric("Trafione", overall["hits"])
    c.metric("Skuteczność", "—" if overall["hit_rate"] is None else f"{overall['hit_rate']:.1f}%")
    d.metric("ROI", "—" if overall["roi"] is None else f"{overall['roi']:.1f}%")

    if overall["total"] < 20:
        st.warning("Próbka poniżej 20 rekomendacji — wynik jest wyłącznie informacyjny.")
    elif overall["total"] < 50:
        st.info("Niska wiarygodność próby. Nie zmieniaj jeszcze parametrów modelu.")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Według poziomu")
        st.dataframe(metric_table(dashboard["by_level"]), use_container_width=True, hide_index=True)
        st.markdown("#### Według score")
        st.dataframe(metric_table(dashboard["by_score"]), use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### Według rynku")
        st.dataframe(metric_table(dashboard["by_market"]), use_container_width=True, hide_index=True)
        st.markdown("#### Według zapasu nad progiem")
        st.dataframe(metric_table(dashboard["by_margin"]), use_container_width=True, hide_index=True)

    st.download_button("Pobierz wszystkie rekomendacje CSV", data=export_csv(DB_PATH, **filters),
                       file_name="match_analyzer_backtest.csv", mime="text/csv", use_container_width=True)
    st.download_button("Pobierz tylko wybrane typy CSV", data=export_csv(DB_PATH, selected_only=True, **filters),
                       file_name="match_analyzer_selected.csv", mime="text/csv", use_container_width=True)

    with st.expander("Pełny dziennik"):
        st.dataframe(pd.DataFrame(recommendation_rows(DB_PATH, **filters)), use_container_width=True, hide_index=True)

with import_tab:
    st.write(
        "Importuj wyłącznie rzeczywiste rekordy historyczne. Brakujące dane nie są odtwarzane ani zgadywane. "
        "Rekordy historyczne są oznaczane jako osobne źródło i nie powinny być mieszane z czystą serią walidacyjną."
    )
    uploaded = st.file_uploader("CSV historyczny", type=["csv"])
    if uploaded and st.button("Importuj historię"):
        try:
            result = import_history_csv(uploaded.getvalue(), DB_PATH)
            st.success(f"Zaimportowano: {result['imported']}; pominięto: {result['skipped']}.")
        except Exception as exc:
            st.error(f"Import nie powiódł się: {exc}")
