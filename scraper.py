from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.mutating.com"
DEFAULT_LISTING_URL = f"{BASE_URL}/football-stats/"
DATE_URLS = {
    -2: f"{BASE_URL}/football-stats/before-yesterday/",
    -1: f"{BASE_URL}/football-stats/yesterday/",
    0: f"{BASE_URL}/football-stats/",
    1: f"{BASE_URL}/football-stats/tomorrow/",
    2: f"{BASE_URL}/football-stats/future-days/",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AnalizatorMeczow/2.0; +browser-app)",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}
COUNTRY_NAMES_PL = {
    "WORLD": "Świat", "AUSTRALIA": "Australia", "BELARUS": "Białoruś", "BHUTAN": "Bhutan",
    "BOLIVIA": "Boliwia", "BRAZIL": "Brazylia", "BULGARIA": "Bułgaria", "CHILE": "Chile",
    "CHINA": "Chiny", "ECUADOR": "Ekwador", "ENGLAND": "Anglia", "ESTONIA": "Estonia",
    "FINLAND": "Finlandia", "FRANCE": "Francja", "GERMANY": "Niemcy", "ICELAND": "Islandia",
    "IRELAND": "Irlandia", "ITALY": "Włochy", "KAZAKHSTAN": "Kazachstan", "LATVIA": "Łotwa",
    "LITHUANIA": "Litwa", "MACAO": "Makau", "MALAWI": "Malawi", "MEXICO": "Meksyk",
    "MOLDOVA": "Mołdawia", "NETHERLANDS": "Holandia", "NICARAGUA": "Nikaragua",
    "PARAGUAY": "Paragwaj", "PERU": "Peru", "POLAND": "Polska", "PORTUGAL": "Portugalia",
    "ROMANIA": "Rumunia", "RUSSIA": "Rosja", "SERBIA": "Serbia", "SLOVENIA": "Słowenia",
    "SOUTH-KOREA": "Korea Południowa", "SOUTH KOREA": "Korea Południowa", "SPAIN": "Hiszpania",
    "SWEDEN": "Szwecja", "SWITZERLAND": "Szwajcaria", "TURKEY": "Turcja", "UKRAINE": "Ukraina",
    "URUGUAY": "Urugwaj", "USA": "Stany Zjednoczone",
}


@dataclass
class MatchSummary:
    home_team: str
    away_team: str
    kickoff: str | None
    country: str | None
    league: str | None
    url: str
    listing_date: str | None = None


@dataclass
class MatchDetails(MatchSummary):
    match_date: str | None = None
    stats: dict[str, dict[str, float]] = field(default_factory=dict)
    home_trends: list[str] = field(default_factory=list)
    away_trends: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def polish_country_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = clean_text(value)
    return COUNTRY_NAMES_PL.get(cleaned.upper(), cleaned.title())


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def listing_url_for_date(selected_date: date, today: date | None = None) -> str | None:
    today = today or date.today()
    return DATE_URLS.get((selected_date - today).days)


def _parse_match_label(anchor: Tag) -> tuple[str, str] | None:
    candidates = [anchor.get("title", ""), anchor.get("aria-label", ""), anchor.get_text(" ", strip=True)]
    for candidate in candidates:
        text = clean_text(candidate)
        match = re.search(r"(.+?)\s+vs\.?\s+(.+?)(?:\s+stats|\s+h2h|$)", text, re.I)
        if match:
            home = re.sub(r"^(?:[01]?\d|2[0-3]):[0-5]\d\s+", "", clean_text(match.group(1)))
            return home, clean_text(match.group(2))
    return None


def _classify_context_link(node: Tag) -> tuple[str | None, str | None]:
    href = str(node.get("href", ""))
    text = clean_text(node.get_text(" ", strip=True))
    if not text:
        return None, None
    slug = urlparse(urljoin(BASE_URL, href)).path.rstrip("/").split("/")[-1].lower()
    if slug.startswith("country-"):
        return polish_country_name(text), None
    if slug.startswith("league-"):
        return None, text
    return None, None


def _nearest_heading(anchor: Tag) -> tuple[str | None, str | None]:
    country = league = None
    node: Tag | None = anchor
    for _ in range(80):
        node = node.find_previous("a") if node is not None else None
        if node is None:
            break
        found_country, found_league = _classify_context_link(node)
        if league is None and found_league:
            league = found_league
        if country is None and found_country:
            country = found_country
        if country and league:
            break
    return country, league


def list_matches(session: requests.Session, listing_url: str = DEFAULT_LISTING_URL, listing_date: str | None = None) -> list[MatchSummary]:
    response = session.get(listing_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    items: list[MatchSummary] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="match-preview-"]'):
        href = anchor.get("href")
        if not href:
            continue
        url = urljoin(BASE_URL, href)
        if url in seen:
            continue
        parsed = _parse_match_label(anchor)
        if not parsed:
            continue
        seen.add(url)
        home, away = parsed
        context = clean_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else ""
        kickoff_match = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", context)
        country, league = _nearest_heading(anchor)
        items.append(MatchSummary(home, away, kickoff_match.group(0) if kickoff_match else None, country, league, url, listing_date))
    return items


def list_matches_for_dates(session: requests.Session, selected_dates: Iterable[date]) -> tuple[list[MatchSummary], list[date]]:
    matches: list[MatchSummary] = []
    unsupported: list[date] = []
    seen: set[str] = set()
    for selected_date in selected_dates:
        url = listing_url_for_date(selected_date)
        if not url:
            unsupported.append(selected_date)
            continue
        for match in list_matches(session, url, selected_date.isoformat()):
            key = f"{match.url}|{match.listing_date}"
            if key not in seen:
                seen.add(key)
                matches.append(match)
    return matches, unsupported


def _extract_teams(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    h1 = soup.find("h1")
    if not h1:
        return None, None
    match = re.match(r"(.+?)\s*-\s*(.+?)\s+Stats\b", clean_text(h1.get_text(" ", strip=True)), re.I)
    return (clean_text(match.group(1)), clean_text(match.group(2))) if match else (None, None)


KNOWN_METRICS = [
    "Goals scored per game", "Goals conceded per game", "Clean sheets", "Team scored",
    "Team scored twice", "Scored in both halves", "Goal in both halves", "Win", "Draw", "Lose",
    "Win and Over 1.5 goals", "Lose and Over 1.5 goals", "Team win first half",
    "Team draw at half time", "Team lost first half", "Both Teams to Score",
    "BTTS in first-half", "BBTS in second-half", "BBTS and Over 1.5", "BBTS and Over 2.5",
    "Win and BTTS", "Draw and BTTS", "Lose and BTTS",
    "Match total goals 0 or 1", "Match total goals 2 or 3", "Match total goals 4+",
    "Match total goals 0", "Match total goals 1", "Match total goals 2", "Match total goals 3", "Match total goals 4",
    "Over 1.5 goals", "Over 2.5 goals", "Over 3.5 goals", "Under 1.5 goals", "Under 2.5 goals", "Under 3.5 goals",
    "Over 0.5 goals at half-time", "Over 1.5 goals at half-time", "Over 2.5 goals at half-time",
    "Win HT - Win FT", "Win HT - Draw FT", "Win HT - Lose FT", "Draw HT - Win FT",
    "Draw HT - Draw FT", "Draw HT - Lose FT", "Lose HT - Win FT", "Lose HT - Draw FT", "Lose HT - Lose FT",
]


def _extract_stat_pairs(text: str) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    number = r"(\d+(?:[.,]\d+)?%?)"
    for label in sorted(KNOWN_METRICS, key=len, reverse=True):
        match = re.compile(rf"{number}\s+{re.escape(label)}\s+{number}", re.I).search(text)
        if match:
            stats[label] = {
                "home": float(match.group(1).replace("%", "").replace(",", ".")),
                "away": float(match.group(2).replace("%", "").replace(",", ".")),
            }
    return stats


def _section_paragraphs(soup: BeautifulSoup, title: str) -> list[str]:
    heading = soup.find(lambda tag: tag.name in {"h2", "h3"} and clean_text(tag.get_text(" ", strip=True)).lower() == title.lower())
    if not heading:
        return []
    result: list[str] = []
    for elem in heading.find_all_next():
        if elem is not heading and elem.name in {"h1", "h2", "h3"}:
            break
        if elem.name in {"p", "li"}:
            value = clean_text(elem.get_text(" ", strip=True))
            if value and value not in result:
                result.append(value)
    return result


def parse_match(session: requests.Session, summary: MatchSummary) -> MatchDetails:
    response = session.get(summary.url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    text = clean_text(soup.get_text(" ", strip=True))
    page_home, page_away = _extract_teams(soup)
    date_match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
    time_match = re.search(r"\b([01]\d|2[0-3]):[0-5]\d\b", text)
    home = page_home or summary.home_team
    away = page_away or summary.away_team
    return MatchDetails(
        home_team=home, away_team=away, kickoff=time_match.group(0) if time_match else summary.kickoff,
        country=summary.country, league=summary.league, url=summary.url, listing_date=summary.listing_date,
        match_date=date_match.group(1) if date_match else summary.listing_date, stats=_extract_stat_pairs(text),
        home_trends=_section_paragraphs(soup, f"{home} Trends"), away_trends=_section_paragraphs(soup, f"{away} Trends"),
    )


def scrape_matches(
    summaries: Iterable[MatchSummary],
    delay_seconds: float = 0.25,
    session: requests.Session | None = None,
) -> list[MatchDetails]:
    active_session = session or create_session()
    results: list[MatchDetails] = []
    for index, summary in enumerate(summaries):
        try:
            details = parse_match(active_session, summary)
            if not details.stats:
                details.errors.append("Nie znaleziono żadnych obsługiwanych statystyk na stronie meczu.")
            results.append(details)
        except Exception as exc:
            results.append(MatchDetails(**asdict(summary), errors=[str(exc)]))
        if index < len(results) and delay_seconds:
            time.sleep(max(0.0, delay_seconds))
    return results
