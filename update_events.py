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
    for w in re.split(r"[^a-zA-Z0-9]+", name.lower()):
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
    if re.search(
