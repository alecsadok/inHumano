#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")
UA = "Mozilla/5.0 (compatible; inHumanoCalendarBot/1.0; +https://alecsadok.github.io/inHumano/)"

WATCHLIST = Path("event_watchlist.yaml")
OUT_EVENTS = Path("events.yaml")
WIKI_BASE = "https://en.wikipedia.org"


def http_get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def clean_text(s: str) -> str:
    s = re.sub(r"\[\d+\]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_any_date_candidates(text: str) -> list[date]:
    candidates: list[date] = []
    rx = re.compile(
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{4}\b"
        r"|\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b"
    )
    for m in rx.finditer(text):
        s = m.group(0)
        try:
            d = dtparser.parse(s, fuzzy=True).date()
            candidates.append(d)
        except Exception:
            continue
    out: list[date] = []
    seen = set()
    for d in candidates:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def wikipedia_status_inactive(url: str) -> bool:
    try:
        html = http_get(url)
    except Exception:
        return False
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    keywords = [
        "discontinued",
        "indefinite hiatus",
        "on hiatus",
        "quietly discontinued",
        "last awarded",
        "final ceremony",
        "ended",
        "canceled",
        "cancelled",
    ]
    return any(k in text for k in keywords)


def preferred_terms_from_name(name: str) -> list[str]:
    toks = []
    for w in re.split(r"[^a-zA-Z0-9]+", (name or "").lower()):
        w = w.strip()
        if len(w) >= 4 and w not in {"awards", "award", "ceremony", "the", "with", "and"}:
            toks.append(w)
    seen = set()
    out = []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def score_ceremony_link(href: str, anchor_text: str, year: int, preferred_terms: list[str]) -> int:
    h = (href or "").lower()
    a = (anchor_text or "").lower()
    score = 0

    if re.search(r"/wiki/\d{4}_in_", h):
        score -= 250
    if "help:" in h or "wikipedia:" in h or "special:" in h:
        score -= 250
    if "list_of" in h:
        score -= 60

    if str(year) in h or str(year) in a:
        score += 60
    if re.search(r"\b\d{1,3}(st|nd|rd|th)\b", h) or re.search(r"\b\d{1,3}(st|nd|rd|th)\b", a):
        score += 45

    if "award" in h or "award" in a:
        score += 15
    if "ceremon" in h or "ceremon" in a:
        score += 15

    for t in preferred_terms:
        if t in h:
            score += 18
        if t in a:
            score += 10

    return score


def pick_best_ceremony_url(tr: BeautifulSoup, year: int, preferred_terms: list[str]) -> str | None:
    best_href = None
    best_score = -10**9

    for a in tr.select("a[href]"):
        href = a.get("href", "")
        if not href.startswith("/wiki/"):
            continue
        anchor = a.get_text(" ", strip=True)
        sc = score_ceremony_link(href, anchor, year, preferred_terms)
        if sc > best_score:
            best_score = sc
            best_href = href

    if best_href and best_score > -80:
        return WIKI_BASE + best_href
    return None


def next_future_from_wikipedia_list(
    url: str, today: date, days_ahead: int, preferred_terms: list[str]
) -> tuple[date | None, str | None]:
    try:
        html = http_get(url)
    except Exception:
        return None, None

    soup = BeautifulSoup(html, "html.parser")
    end = today + timedelta(days=days_ahead)

    tables = soup.select("table.wikitable")
    candidates: list[tuple[date, str | None]] = []

    for table in tables:
        for tr in table.select("tr"):
            row_text = clean_text(tr.get_text(" ", strip=True))
            if not row_text:
                continue
            ds = parse_any_date_candidates(row_text)
            if not ds:
                continue
            d = ds[0]
            if not (today <= d <= end):
                continue
            ceremony_url = pick_best_ceremony_url(tr, d.year, preferred_terms)
            candidates.append((d, ceremony_url))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][0], candidates[0][1]


def normalize_top_nom_item(s: str) -> str:
    s = clean_text(s)
    s = re.sub(r"^(film|television|tv|music|cinema)\s*[-—:]\s*", "", s, flags=re.I).strip()
    s = re.sub(r"^(film|television|tv|music|cinema)\s+", "", s, flags=re.I).strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_top_nominated_from_infobox(url: str) -> list[str]:
    try:
        html = http_get(url)
    except Exception:
        return []

    soup = BeautifulSo
