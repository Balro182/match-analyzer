from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from backtest_store import (
    DEFAULT_DB_PATH,
    aggregate_dashboard,
    export_csv,
    init_db,
    list_matches,
    recommendation_rows,
    save_analysis,
    settle_match,
)
from engine import ALGORITHM_VERSION, analyze_match
from exact_score import exact_score_diagnostics
from manual_parser import parse_pasted_stats

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / DEFAULT_DB_PATH

st.set_page_config(page_title="Backtest", page_icon="📊", layout="wide")
init_db(DB_PATH)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def metric_table(data: dict) -> pd.DataFrame:
    rows = []
    for name, values in data.items():
        rows.append({"Grupa": name, **values})
    return pd.DataFrame(rows)


st.title("📊 Backtest i rozliczanie rekomendacji")
st.caption(f"Algorytm {ALGORITHM_VERSION} · baza {DB_PATH}")
st.warning(
    "Na Streamlit Community Cloud lokalny plik SQLite może zostać usunięty przy restarcie aplikacji. "
    "Regularnie pobieraj eksport CSV albo użyj trwałego wolumenu w środowisku produkcyjnym."
)

analyze_tab, settle_tab, dashboard_tab = st.tabs(["Zapis analizy", "Rozliczenie meczu", "Dashboard"])

with analyze_tab:
    col_a, col_b = st.columns(2)
    home_team = col_a.text_input("Gospodarz", key="bt_home")
    away_team = col_b.text_input("Gość", key="bt_away")
    pasted = st.text_area("Dane statystyczne", height=360, key="bt_stats")

    if st.button("Analizuj i zapisz", type="primary", use_container_width=True):
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
                predicted_ht = diagnostics["ht"][0]["score"] if diagnostics["ht"] else None
                predicted_ft = diagnostics["ft"][0]["score"] if diagnostics["ft"] else None
                match_id = save_analysis(
                    match,
                    recommendations,
                    ALGORITHM_VERSION,
                    predicted_ht=predicted_ht,
                    predicted_ft=predicted_ft,
                    path=DB_PATH,
                )
                selected = [
                    rec.to_dict() for rec in recommendations
                    if rec.passed and any("Poziom selekcji:" in reason for reason in rec.reasons)
                ]
                st.success(f"Zapisano analizę jako mecz #{match_id}.")
                st.dataframe(pd.DataFrame(selected), use_container_width=True, hide_index=True)

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

        selected_recs = [
            row for row in recommendation_rows(DB_PATH, selected_only=True)
            if int(row["match_id"]) == int(match_id)
        ]
        odds: dict[str, float] = {}
        if selected_recs:
            st.markdown("#### Kursy opcjonalne")
            for row in selected_recs:
                value = st.number_input(
                    f"{row['label']} ({row['selected_level']})",
                    min_value=1.0,
                    value=1.0,
                    step=0.01,
                    key=f"odds_{match_id}_{row['rule_id']}",
                )
                if value > 1.0:
                    odds[str(row["rule_id"])] = float(value)

        if st.button("Rozlicz mecz", type="primary"):
            try:
                result = settle_match(match_id, actual_ht, actual_ft, odds, DB_PATH)
                st.success(f"Rozliczono {result['settled']} rynków; pominięto {result['skipped']} nierozpoznanych.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

with dashboard_tab:
    dashboard = aggregate_dashboard(DB_PATH)
    overall = dashboard["overall"]
    a, b, c, d = st.columns(4)
    a.metric("Rozliczone typy", overall["total"])
    b.metric("Trafione", overall["hits"])
    c.metric("Skuteczność", "—" if overall["hit_rate"] is None else f"{overall['hit_rate']:.1f}%")
    d.metric("ROI", "—" if overall["roi"] is None else f"{overall['roi']:.1f}%")

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

    st.download_button(
        "Pobierz wszystkie rekomendacje CSV",
        data=export_csv(DB_PATH),
        file_name="match_analyzer_backtest.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "Pobierz tylko wybrane typy CSV",
        data=export_csv(DB_PATH, selected_only=True),
        file_name="match_analyzer_selected.csv",
        mime="text/csv",
        use_container_width=True,
    )

    with st.expander("Pełny dziennik"):
        st.dataframe(pd.DataFrame(recommendation_rows(DB_PATH)), use_container_width=True, hide_index=True)
