# Ręczny analizator statystyk

Drugi interfejs aplikacji pozwala wkleić cały blok statystyk gospodarza i gościa, a następnie uruchomić ten sam silnik i progi z `engine.py` oraz `config.yaml`.

## Uruchomienie

```bash
pip install -r requirements.txt
streamlit run manual_app.py
```

## Użycie

1. Wpisz opcjonalnie nazwy drużyn.
2. Wklej dane w układzie `wartość gospodarza — nazwa metryki — wartość gościa`.
3. Kliknij **Analizuj**.
4. Sprawdź końcowe TOP 5, wszystkie rynki spełniające progi przed selekcją oraz pełne wyliczenia każdej reguły.

Program zgłasza brakujące metryki i duplikaty. Nagłówki, sekcje oraz nazwy drużyn są pomijane automatycznie.

## Streamlit Community Cloud

Aby opublikować ten interfejs jako osobną aplikację, wybierz repozytorium `Balro182/match-analyzer`, branch `main` i ustaw main file path:

```text
manual_app.py
```

Ręczny analizator nie korzysta ze scrapera. Analizuje wyłącznie dane wklejone przez użytkownika.
