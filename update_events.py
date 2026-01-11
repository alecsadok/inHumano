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


def extract_top_nominated_from_infobox(url: str) -> list[str]:
    try:
        html = http_get(url)
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    infobox = soup.select_one("table.infobox")
    if not infobox:
        return []

    results: list[str] = []
    for tr in infobox.select("tr"):
        th = tr.select_one("th")
        td = tr.select_one("td")
        if not th or not td:
            continue

        k = clean_text(th.get_text(" ", strip=True)).lower()
        v = clean_text(td.get_text(" ", strip=True))
        if not v:
            continue

        if ("most nomination" in k) or ("most nominated" in k):
            parts = [p.strip() for p in re.split(r"\s*;\s*", v) if p.strip()]
            if parts:
                results.extend(parts)
            else:
                results.append(v)

    seen = set()
    out = []
    for x in results:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def infer_nomination_source_for_announcements(item_id: str) -> str | None:
    mapping = {
        "oscars_noms": "https://en.wikipedia.org/wiki/List_of_Academy_Awards_ceremonies",
    }
    return mapping.get(item_id)


def load_existing_events() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    if not OUT_EVENTS.exists():
        return [], {}, {}
    data = yaml.safe_load(OUT_EVENTS.read_text(encoding="utf-8")) or {}
    events = data.get("events", [])
    if not isinstance(events, list):
        return [], {}, {}

    by_id: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        eid = str(ev.get("id", "")).strip()
        title = str(ev.get("title", "")).strip()
        if eid:
            by_id[eid] = ev
        if title:
            by_title[title.lower()] = ev
    return events, by_id, by_title


def prefer_existing_value(existing, fallback):
    if existing is None:
        return fallback
    if isinstance(existing, str) and not existing.strip():
        return fallback
    if isinstance(existing, list) and len(existing) == 0:
        return fallback
    if isinstance(existing, dict) and len(existing) == 0:
        return fallback
    return existing


def merge_broadcast(existing_b: dict | None, watch_b: dict | None) -> dict:
    existing_b = existing_b or {}
    watch_b = watch_b or {}

    merged = dict(existing_b)

    if "tv" not in merged or not merged.get("tv"):
        merged["tv"] = watch_b.get("tv", []) or []
    if "streaming" not in merged or not merged.get("streaming"):
        merged["streaming"] = watch_b.get("streaming", []) or []

    existing_red = merged.get("red_carpet", {}) or {}
    watch_red = watch_b.get("red_carpet", {}) or {}
    red = dict(existing_red)

    for k in ["confirmed", "where", "start_local", "duration_minutes"]:
        red[k] = prefer_existing_value(existing_red.get(k), watch_red.get(k))

    merged["red_carpet"] = red
    return merged


def merge_event(existing: dict | None, auto: dict) -> dict:
    if not existing:
        return auto

    merged = dict(existing)

    merged["id"] = auto.get("id", merged.get("id", ""))
    merged["title"] = prefer_existing_value(merged.get("title"), auto.get("title"))
    merged["date"] = auto.get("date")
    merged["tz_local"] = auto.get("tz_local")

    merged["start_local"] = prefer_existing_value(merged.get("start_local"), auto.get("start_local"))
    merged["duration_minutes"] = prefer_existing_value(merged.get("duration_minutes"), auto.get("duration_minutes"))
    merged["location"] = prefer_existing_value(merged.get("location"), auto.get("location"))

    merged["broadcast"] = merge_broadcast(merged.get("broadcast", {}), auto.get("broadcast", {}))

    merged["top_nominated"] = auto.get("top_nominated", [])
    merged["nomination_source_url"] = auto.get("nomination_source_url", "")

    merged["confirmed_people"] = prefer_existing_value(merged.get("confirmed_people"), auto.get("confirmed_people"))
    merged["confirmed_performers"] = prefer_existing_value(merged.get("confirmed_performers"), auto.get("confirmed_performers"))
    merged["special_awards"] = prefer_existing_value(merged.get("special_awards"), auto.get("special_awards"))

    merged["headliners"] = prefer_existing_value(merged.get("headliners"), auto.get("headliners"))
    merged["pop_artists"] = prefer_existing_value(merged.get("pop_artists"), auto.get("pop_artists"))
    merged["days"] = prefer_existing_value(merged.get("days"), auto.get("days"))

    existing_notes = merged.get("notes", [])
    auto_notes = auto.get("notes", [])
    if not isinstance(existing_notes, list):
        existing_notes = []
    if not isinstance(auto_notes, list):
        auto_notes = []

    combined = []
    seen = set()
    for n in existing_notes + auto_notes:
        n = str(n).strip()
        if n and n not in seen:
            seen.add(n)
            combined.append(n)
    merged["notes"] = combined

    return merged


def build_auto_event_entry(item: dict, d: date, top_nominated: list[str], nomination_source_url: str) -> dict:
    entry: dict = {
        "id": str(item.get("id", "")).strip(),
        "title": f"{item.get('name','')}",
        "date": d.isoformat(),
        "tz_local": item.get("tz_local"),
        "location": item.get("location", ""),
        "broadcast": item.get("broadcast", {"tv": [], "streaming": [], "red_carpet": {"confirmed": False}}),
        "confirmed_people": {"a_list": [], "b_list": [], "argentines": []},
        "top_nominated": top_nominated,
        "nomination_source_url": nomination_source_url or "",
        "confirmed_performers": [],
        "special_awards": [],
        "headliners": item.get("headliners", []) if isinstance(item.get("headliners", []), list) else [],
        "pop_artists": item.get("pop_artists", []) if isinstance(item.get("pop_artists", []), list) else [],
        "days": item.get("days", []) if isinstance(item.get("days", []), list) else [],
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

    _, existing_by_id, existing_by_title = load_existing_events()

    cfg = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    settings = cfg.get("settings", {}) or {}
    days_ahead = int(settings.get("days_ahead", 400))
    include_inactive = bool(settings.get("include_inactive", False))

    watchlist = cfg.get("watchlist", [])
    if not isinstance(watchlist, list):
        raise ValueError("event_watchlist.yaml: 'watchlist' debe ser una lista")

    today = datetime.now(tz=TZ_AR).date()
    merged_out: list[dict] = []

    for item in watchlist:
        if not isinstance(item, dict):
            continue

        item_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        status = item.get("status", "active")
        kind = str(item.get("kind", "")).strip()
        sources = item.get("sources", []) or []
        preferred_terms = preferred_terms_from_name(name)

        for src in sources:
            st = src.get("type")
            url = src.get("url")
            if not url:
                continue
            if st in {"wikipedia_status", "news_status"} and wikipedia_status_inactive(url):
                status = "inactive"
                break

        if status != "active" and not include_inactive:
            continue

        next_date: date | None = None
        ceremony_url: str | None = None
        picked_source_url: str | None = None

        for src in sources:
            st = src.get("type")
            url = src.get("url")
            if not url:
                continue

            if st == "wikipedia_next_date" and "wikipedia.org/wiki/" in url:
                d, cu = next_future_from_wikipedia_list(url, today, days_ahead, preferred_terms)
                if d:
                    next_date, ceremony_url = d, cu
                    picked_source_url = url
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
                    picked_source_url = url
                    break

        if not next_date:
            continue

        top_nominated: list[str] = []
        nomination_source_url = ""

        if kind in {"awards", "announcement"}:
            if ceremony_url:
                top_nominated = extract_top_nominated_from_infobox(ceremony_url)
                nomination_source_url = ceremony_url
            if not top_nominated and picked_source_url and "wikipedia.org/wiki/" in picked_source_url:
                top_nominated = extract_top_nominated_from_infobox(picked_source_url)
                if top_nominated and not nomination_source_url:
                    nomination_source_url = picked_source_url

            if not top_nominated and kind == "announcement":
                inferred = infer_nomination_source_for_announcements(item_id)
                if inferred:
                    d2, cu2 = next_future_from_wikipedia_list(inferred, today, days_ahead, preferred_terms)
                    if cu2:
                        top_nominated = extract_top_nominated_from_infobox(cu2)
                        nomination_source_url = cu2 or nomination_source_url

        auto_ev = build_auto_event_entry(item, next_date, top_nominated, nomination_source_url)

        existing_ev = existing_by_id.get(item_id)
        if not existing_ev and name:
            existing_ev = existing_by_title.get(name.lower())

        merged = merge_event(existing_ev, auto_ev)
        merged_out.append(merged)

    merged_out.sort(key=lambda ev: (str(ev.get("date", "")), str(ev.get("title", ""))))

    OUT_EVENTS.write_text(
        yaml.safe_dump({"events": merged_out}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"OK: escrito {OUT_EVENTS} con {len(merged_out)} eventos")


if __name__ == "__main__":
    main()
