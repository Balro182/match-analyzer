from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.mutating.com"
DEFAULT_LISTING_URL = f"{BASE_URL}/football-stats/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MatchAnalyzer/1.0; +local-analysis)",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}


@dataclass
class MatchSummary:
    home_team: str
    away_team: str
    kickoff: str | None
    country: str | None
    league: str | None
    url: str


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


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _parse_match_label(text: str) -> tuple[str, str] | None:
    text = clean_text(text)
    match = re.search(r"(.+?)\s+vs\.?\s+(.+?)(?:\s+stats|\s+h2h|$)", text, re.I)
    if not match:
        return None
    return clean_text(match.group(1)), clean_text(match.group(2))


def _nearest_heading(anchor: Tag) -> tuple[str | None, str | None]:
    country = league = None
    node = anchor
    for _ in range(12):
        node = node.find_previous()
        if node is None:
            break
        text = clean_text(node.get_text(" ", strip=True)) if isinstance(node, Tag) else ""
        href = node.get("href", "") if isinstance(node, Tag) else ""
        if not league and "/football-league/" in href:
            league = text
        elif not country and "/football-country/" in href:
            country = text
        if country and league:
            break
    return country, league


def list_matches(session: requests.Session, listing_url: str = DEFAULT_LISTING_URL) -> list[MatchSummary]:
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
        parsed = _parse_match_label(anchor.get_text(" ", strip=True) or anchor.get("title", ""))
        if not parsed:
            continue
        seen.add(url)
        home, away = parsed
        context = clean_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else ""
        kickoff_match = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", context)
        country, league = _nearest_heading(anchor)
        items.append(MatchSummary(home, away, kickoff_match.group(0) if kickoff_match else None, country, league, url))
    return items


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
    "Win and BTTS", "Draw and BTTS", "Lose and BTTS", "Over 1.5 goals", "Over 2.5 goals",
    "Over 3.5 goals", "Under 1.5 goals", "Under 2.5 goals", "Under 3.5 goals",
    "Over 0.5 goals at half-time", "Over 1.5 goals at half-time", "Over 2.5 goals at half-time",
    "Win HT - Win FT", "Win HT - Draw FT", "Win HT - Lose FT", "Draw HT - Win FT",
    "Draw HT - Draw FT", "Draw HT - Lose FT", "Lose HT - Win FT", "Lose HT - Draw FT",
    "Lose HT - Lose FT",
]


def _extract_stat_pairs(text: str) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    number = r"(\d+(?:[.,]\d+)?%?)"
    for label in sorted(KNOWN_METRICS, key=len, reverse=True):
        pattern = re.compile(rf"{number}\s+{re.escape(label)}\s+{number}", re.I)
        match = pattern.search(text)
        if not match:
            continue
        home = float(match.group(1).replace("%", "").replace(",", "."))
        away = float(match.group(2).replace("%", "").replace(",", "."))
        stats[label] = {"home": home, "away": away}
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
        home_team=home,
        away_team=away,
        kickoff=time_match.group(0) if time_match else summary.kickoff,
        country=summary.country,
        league=summary.league,
        url=summary.url,
        match_date=date_match.group(1) if date_match else None,
        stats=_extract_stat_pairs(text),
        home_trends=_section_paragraphs(soup, f"{home} Trends"),
        away_trends=_section_paragraphs(soup, f"{away} Trends"),
    )


def scrape_matches(summaries: Iterable[MatchSummary], delay_seconds: float = 1.0) -> list[MatchDetails]:
    session = create_session()
    results: list[MatchDetails] = []
    for index, summary in enumerate(summaries):
        try:
            results.append(parse_match(session, summary))
        except Exception as exc:
            results.append(MatchDetails(**asdict(summary), errors=[str(exc)]))
        if index:
            time.sleep(max(0.0, delay_seconds))
    return results
