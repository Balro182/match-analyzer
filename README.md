# Match Analyzer

Aplikacja webowa Streamlit pobierająca listę spotkań i statystyki z `mutating.com/football-stats/`, a następnie oceniająca spotkania według konfigurowalnych reguł.

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publikacja w Streamlit Community Cloud

1. Zaloguj się na `share.streamlit.io` kontem GitHub.
2. Kliknij **Create app**.
3. Wybierz repozytorium `Balro182/match-analyzer`.
4. Ustaw branch `main`.
5. Ustaw main file path `app.py`.
6. Kliknij **Deploy**.

## Własne rekomendacje

Reguły znajdują się w `config.yaml`. Dostępne są m.in. rynki Over 1.5, Over 2.5, BTTS oraz wygrana gospodarzy lub gości.

Scraping zależy od struktury zewnętrznej strony i może wymagać aktualizacji parsera po zmianach serwisu.
