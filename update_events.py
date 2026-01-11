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


def clean_wiki_text(s: str) -> str:
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

    out = []
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


def next_future_from_wikipedia_list(url: str, today: date, days_ahead: int) -> tuple[date | None, str | None]:
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
            row_text = clean_wiki_text(tr.get_text(" ", strip=True))
            if not row_text:
                continue

            ds = parse_any_date_candidates(row_text)
            if not ds:
                continue

            d = ds[0]
            if not (today <= d <= end):
                continue

            ceremony_url = None
            for a in tr.select("a[href]"):
                href = a.get("href", "")
                if href.startswith("/wiki/") and not href.startswith("/wiki/Help:"):
                    ceremony_url = WIKI_BASE + href
                    break

            candidates.append((d, ceremony_url))

    if not candidates:
        # fallback: solo fecha sin link
        try:
            html2 = http_get(url)
            soup2 = BeautifulSoup(html2, "html.parser")
            text = soup2.get_text(" ", strip=True)
            ds2 = parse_any_date_candidates(text)
            for d in ds2:
                if today <= d <= end:
                    return d, None
        except Exception:
            pass
        return None, None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][0], candidates[0][1]


def extract_most_nominations_from_ceremony_page(url: str) -> list[str]:
    try:
        html = http_get(url)
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    infobox = soup.select_one("table.infobox")
    if not infobox:
        return []

    keys = {
        "most nominations",
        "most nominated",
        "most nominations (film)",
        "most nominations (television)",
        "most nominations (tv)",
        "most nominations (music)",
    }

    results: list[str] = []
    for tr in infobox.select("tr"):
        th = tr.select_one("th")
        td = tr.select_one("td")
        if not th or not td:
            continue
        k = clean_wiki_text(th.get_text(" ", strip=True)).lower()
        v = clean_wiki_text(td.get_text(" ", strip=True))
        if k in keys and v:
            # si hay varios ítems separados por ";", los separamos en lista
            parts = [p.strip() for p in re.split(r"\s*;\s*", v) if p.strip()]
            if parts:
                results.extend(parts)
            else:
                results.append(v)

    # dedupe preserve order
    seen = set()
    out = []
    for x in results:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def build_event_entry(item: dict, d: date, top_nominated: list[str]) -> dict:
    entry = {
        "title": f"{item['name']}",
        "date": d.isoformat(),
        "tz_local": item.get("tz_local"),
        "location": item.get("location", ""),
        "broadcast": item.get("broadcast", {"tv": [], "streaming": [], "red_carpet": {"confirmed": False}}),
        "confirmed_people": {"a_list": [], "b_list": [], "argentines": []},
        "top_nominated": top_nominated,
        "confirmed_performers": [],
        "special_awards": [],
        "notes": [
            "Auto-updated: fecha tomada de fuentes en event_watchlist.yaml (Wikipedia/oficial).",
            "Regla: si no hay hora oficial publicada, queda all-day.",
        ],
    }

    start = item.get("default_start_local")
    dur = item.get("duration_minutes")
    if start and dur and item.get("tz_local"):
        entry["start_local"] = start
        entry["duration_minutes"] = int(dur)

    return entry


def main() -> None:
    if not WATCHLIST.exists():
        raise FileNotFoundError("No existe event_watchlist.yaml")

    cfg = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    settings = cfg.get("settings", {}) or {}
    days_ahead = int(settings.get("days_ahead", 400))
    include_inactive = bool(settings.get("include_inactive", False))

    watchlist = cfg.get("watchlist", [])
    if not isinstance(watchlist, list):
        raise ValueError("event_watchlist.yaml: 'watchlist' debe ser una lista")

    today = datetime.now(tz=TZ_AR).date()
    events_out: list[dict] = []

    for item in watchlist:
        if not isinstance(item, dict):
            continue

        status = item.get("status", "active")
        kind = item.get("kind", "")
        sources = item.get("sources", []) or []

        # chequear inactivo por wiki/news si aplica
        for src in sources:
            st = src.get("type")
            url = src.get("url")
            if not url:
                continue
            if st in {"wikipedia_status", "news_status"}:
                if wikipedia_status_inactive(url):
                    status = "inactive"
                    break

        if status != "active" and not include_inactive:
            continue

        next_date: date | None = None
        ceremony_url: str | None = None

        for src in sources:
            st = src.get("type")
            url = src.get("url")
            if not url:
                continue

            if st == "wikipedia_next_date" and "wikipedia.org/wiki/" in url:
                d, cu = next_future_from_wikipedia_list(url, today, days_ahead)
                if d:
                    next_date, ceremony_url = d, cu
                    break

            if st in {"official_homepage", "official_key_dates", "official_lineup_or_dates", "instagram_profile"}:
                d = None
                try:
                    html = http_get(url)
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text(" ", strip=True)
                    ds = parse_any_date_candidates(text)
                    end = today + timedelta(days=days_ahead)
                    for cand in ds:
                        if today <= cand <= end:
                            d = cand
                            break
                except Exception:
                    d = None
                if d:
                    next_date = d
                    ceremony_url = None
                    break

        if not next_date:
            continue

        top_nominated: list[str] = []
        if kind == "awards" and ceremony_url:
            top_nominated = extract_most_nominations_from_ceremony_page(ceremony_url)

        events_out.append(build_event_entry(item, next_date, top_nominated))

    OUT_EVENTS.write_text(
        yaml.safe_dump({"events": events_out}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"OK: escrito {OUT_EVENTS} con {len(events_out)} eventos")


if __name__ == "__main__":
    main()
