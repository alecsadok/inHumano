#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
import requests
from dateutil import parser as dtparser
from bs4 import BeautifulSoup

TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")
UA = "Mozilla/5.0 (compatible; inHumanoCalendarBot/1.0; +https://alecsadok.github.io/inHumano/)"

WATCHLIST = Path("event_watchlist.yaml")
OUT_EVENTS = Path("events.yaml")


def http_get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def parse_any_date_candidates(text: str) -> list[date]:
    """
    Extrae muchas fechas del texto (best-effort) y devuelve lista de date().
    Esto funciona bien para Wikipedia / páginas con fechas explícitas.
    """
    # Para mejorar precisión, buscamos segmentos que parezcan fechas en inglés/es
    # y dejamos a dateutil parsear.
    # Limitamos matches para no parsear toda la web.
    candidates: list[date] = []

    # Patrones básicos tipo "January 11, 2026" / "11 January 2026" / "Jan 11 2026"
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

    # dedupe preserve order
    out = []
    seen = set()
    for d in candidates:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def next_future_date_from_url(url: str, today: date, days_ahead: int) -> date | None:
    try:
        html = http_get(url)
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    dates = parse_any_date_candidates(text)
    end = today + timedelta(days=days_ahead)
    for d in dates:
        if today <= d <= end:
            return d
    return None


def wikipedia_status_inactive(url: str) -> bool:
    """
    Marca como inactivo si en el resumen/texto aparece "discontinued", "hiatus",
    o si el infobox indica años cerrados. Best-effort.
    """
    try:
        html = http_get(url)
    except Exception:
        return False
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    keywords = [
        "discontinued", "indefinite hiatus", "on hiatus", "quietly discontinued",
        "last awarded", "final ceremony", "ended"
    ]
    return any(k in text for k in keywords)


def build_event_entry(item: dict, d: date) -> dict:
    """
    Convierte un item del watchlist + fecha a entrada events.yaml
    """
    entry = {
        "title": f"{item['name']}",
        "date": d.isoformat(),
        "tz_local": item.get("tz_local"),
        "location": item.get("location", ""),
        "broadcast": item.get("broadcast", {"tv": [], "streaming": [], "red_carpet": {"confirmed": False}}),
        "confirmed_people": {"a_list": [], "b_list": [], "argentines": []},
        "top_nominated": [],
        "confirmed_performers": [],
        "special_awards": [],
        "notes": [
            "Auto-updated: fecha tomada de fuentes en watchlist (Wikipedia/oficial).",
            "Regla: si no hay hora oficial publicada, queda all-day."
        ]
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
        raise ValueError("watchlist debe ser lista")

    today = datetime.now(tz=TZ_AR).date()
    events_out: list[dict] = []

    for item in watchlist:
        if not isinstance(item, dict):
            continue

        status = item.get("status", "active")
        if status != "active" and not include_inactive:
            # igual chequeamos si Wikipedia dice que revivió? (no, por seguridad)
            continue

        sources = item.get("sources", []) or []
        next_date: date | None = None

        # Si el tipo es wikipedia_status, marcamos inactivo automáticamente
        for src in sources:
            st = src.get("type")
            url = src.get("url")
            if not url:
                continue

            if st in {"wikipedia_status", "news_status"}:
                if wikipedia_status_inactive(url):
                    # Skip (inactivo)
                    next_date = None
                    status = "inactive"
                    break

        if status != "active" and not include_inactive:
            continue

        # Buscar próxima fecha
        for src in sources:
            st = src.get("type")
            url = src.get("url")
            if not url:
                continue

            if st in {"wikipedia_next_date", "official_homepage", "official_key_dates", "official_lineup_or_dates", "instagram_profile"}:
                d = next_future_date_from_url(url, today, days_ahead)
                if d:
                    next_date = d
                    break

        if not next_date:
            continue

        events_out.append(build_event_entry(item, next_date))

    OUT_EVENTS.write_text(yaml.safe_dump({"events": events_out}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"OK: escrito {OUT_EVENTS} con {len(events_out)} eventos")


if __name__ == "__main__":
    main()
