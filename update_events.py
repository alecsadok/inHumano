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

TVP_ABC_STATION = "https://www.tvpassport.com/tv-listings/stations/abc-wwsb-sarsota-fl/3192"
TVP_E_STATION = "https://www.tvpassport.com/tv-listings/stations/e-entertainment-usa-eastern-feed/617"


def http_get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def clean_text(s: str) -> str:
    s = re.sub(r"\[\d+\]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def ensure_list(x) -> list[str]:
    if not x:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    return [str(x)] if str(x).strip() else []


def merge_list_unique(a: list[str], b: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for x in a + b:
        x = str(x).strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


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


def normalize_top_nom_item(raw: str) -> str:
    s = clean_text(raw)
    s = re.sub(r"^(film|television|tv|music|cinema)\s*[-—:]\s*", "", s, flags=re.I).strip()
    s = re.sub(r"^(film|television|tv|music|cinema)\s+", "", s, flags=re.I).strip()
    m = re.search(r"\((\d{1,3})\)", s)
    if m:
        n = m.group(1)
        name = re.sub(r"\(\d{1,3}\)", "", s).strip(" -–—:")
        if name:
            return f"{name} ({n})"
        return s
    m2 = re.match(r"^(.*?)[\s\-–—:]+(\d{1,3})$", s)
    if m2:
        name = m2.group(1).strip(" -–—:")
        n = m2.group(2)
        if name:
            return f"{name} ({n})"
    return s


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
            parts = [p.strip() for p in re.split(r"\s*;\s*", v) if p.strip()] or [v]
            for p in parts:
                p2 = normalize_top_nom_item(p)
                if p2:
                    results.append(p2)
    seen = set()
    out = []
    for x in results:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


TIME_LINE_RX = re.compile(r"^\s*(\d{1,2}:\d{2}\s*[AP]M)\s*$", re.I)


def parse_tvpassport_station_day(station_base_url: str, d: date) -> list[dict]:
    url = station_base_url.rstrip("/") + f"/{d.isoformat()}"
    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    items: list[dict] = []
    i = 0
    while i < len(lines):
        m = TIME_LINE_RX.match(lines[i])
        if not m:
            i += 1
            continue
        t = m.group(1).upper().replace(" ", "")
        prog = ""
        desc = ""
        if i + 1 < len(lines):
            prog = lines[i + 1]
        if i + 2 < len(lines):
            # a veces la “sublínea” trae el episodio (ej: "Golden Globes 2026 New Live")
            # y después viene una descripción con nombres.
            maybe = lines[i + 2]
            if not TIME_LINE_RX.match(maybe):
                desc = maybe

        items.append({"time": t, "program": prog, "desc": desc, "source_url": url})
        i += 1

    def to_minutes(hhmm_ampm: str) -> int:
        m2 = re.match(r"^(\d{1,2}):(\d{2})(AM|PM)$", hhmm_ampm, re.I)
        if not m2:
            return -1
        hh = int(m2.group(1))
        mm = int(m2.group(2))
        ap = m2.group(3).upper()
        if ap == "PM" and hh != 12:
            hh += 12
        if ap == "AM" and hh == 12:
            hh = 0
        return hh * 60 + mm

    for idx in range(len(items) - 1):
        a = to_minutes(items[idx]["time"])
        b = to_minutes(items[idx + 1]["time"])
        if a >= 0 and b >= 0 and b > a:
            items[idx]["duration_minutes"] = b - a

    for it in items:
        # conv a HH:MM 24h
        m3 = re.match(r"^(\d{1,2}):(\d{2})(AM|PM)$", it["time"], re.I)
        if not m3:
            continue
        hh = int(m3.group(1))
        mm = int(m3.group(2))
        ap = m3.group(3).upper()
        if ap == "PM" and hh != 12:
            hh += 12
        if ap == "AM" and hh == 12:
            hh = 0
        it["start_local_hhmm"] = f"{hh:02d}:{mm:02d}"
    return items


def extract_names_from_desc(desc: str) -> list[str]:
    if not desc:
        return []
    # Ej típico: "Zuri Hall, Justin Sylvester, and Keltie Knight, host ..."
    head = desc.split("host")[0].strip()
    head = re.sub(r"\band\b", ",", head, flags=re.I)
    parts = [p.strip(" ,.;") for p in head.split(",") if p.strip(" ,.;")]
    out: list[str] = []
    for p in parts:
        # filtro simple de “nombres”
        if 2 <= len(p.split()) <= 4 and len(p) <= 50:
            out.append(p)
    seen = set()
    final = []
    for x in out:
        if x not in seen:
            seen.add(x)
            final.append(x)
    return final


def load_existing_events() -> tuple[dict[str, dict], dict[str, dict]]:
    if not OUT_EVENTS.exists():
        return {}, {}
    data = yaml.safe_load(OUT_EVENTS.read_text(encoding="utf-8")) or {}
    events = data.get("events", [])
    if not isinstance(events, list):
        return {}, {}
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
    return by_id, by_title


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

    # si TVPassport encontró hora, la usamos (es grilla)
    if auto.get("start_local"):
        merged["start_local"] = auto.get("start_local")
    else:
        merged["start_local"] = prefer_existing_value(merged.get("start_local"), auto.get("start_local"))

    if auto.get("duration_minutes") is not None:
        merged["duration_minutes"] = prefer_existing_value(merged.get("duration_minutes"), auto.get("duration_minutes"))

    merged["location"] = prefer_existing_value(merged.get("location"), auto.get("location"))
    merged["broadcast"] = merge_broadcast(merged.get("broadcast", {}), auto.get("broadcast", {}))

    merged["top_nominated"] = auto.get("top_nominated", [])
    merged["nomination_source_url"] = auto.get("nomination_source_url", "")
    merged["event_url"] = prefer_existing_value(merged.get("event_url"), auto.get("event_url"))

    merged["special_awards"] = merge_list_unique(
        ensure_list(merged.get("special_awards")), ensure_list(auto.get("special_awards"))
    )

    merged["guests_confirmed"] = merge_list_unique(
        ensure_list(merged.get("guests_confirmed")), ensure_list(auto.get("guests_confirmed"))
    )
    merged["guests_source_urls"] = merge_list_unique(
        ensure_list(merged.get("guests_source_urls")), ensure_list(auto.get("guests_source_urls"))
    )

    merged["confirmed_people"] = prefer_existing_value(merged.get("confirmed_people"), auto.get("confirmed_people"))
    merged["confirmed_performers"] = prefer_existing_value(merged.get("confirmed_performers"), auto.get("confirmed_performers"))
    merged["headliners"] = prefer_existing_value(merged.get("headliners"), auto.get("headliners"))
    merged["pop_artists"] = prefer_existing_value(merged.get("pop_artists"), auto.get("pop_artists"))
    merged["days"] = prefer_existing_value(merged.get("days"), auto.get("days"))

    merged["notes"] = ensure_list(merged.get("notes"))
    return merged


def main() -> None:
    if not WATCHLIST.exists():
        raise FileNotFoundError("No existe event_watchlist.yaml")

    by_id, by_title = load_existing_events()

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
            url = str(src.get("url", "")).strip()
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
        picked_source_url: str | None = None
        first_source_url: str | None = None

        for src in sources:
            u = str(src.get("url", "")).strip()
            if u:
                first_source_url = u
                break

        for src in sources:
            st = str(src.get("type", "")).strip()
            url = str(src.get("url", "")).strip()
            if not url:
                continue

            if st == "wikipedia_next_date" and "wikipedia.org/wiki/" in url:
                d, cu = next_future_from_wikipedia_list(url, today, days_ahead, preferred_terms)
                if d:
                    next_date, ceremony_url = d, cu
                    picked_source_url = url
                    break

            if st in {"official_homepage", "official_key_dates", "official_lineup_or_dates"}:
                try:
                    html = http_get(url)
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text(" ", strip=True)
                    ds = parse_any_date_candidates(text)
                    end = today + timedelta(days=days_ahead)
                    for cand in ds:
                        if today <= cand <= end:
                            next_date = cand
                            picked_source_url = url
                            break
                except Exception:
                    pass
                if next_date:
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

        event_url = ceremony_url or picked_source_url or first_source_url or ""

        start_local: str | None = None
        duration_minutes: int | None = None
        guests_auto: list[str] = []
        guests_sources: list[str] = []
        special_awards_auto: list[str] = []

        if ceremony_url:
            # dejamos special awards en manual/futuro; por ahora infobox de Wikipedia si lo trae
            # (no fuerza nada si no existe)
            special_awards_auto = []

        # TVPassport: horario + red carpet confirmado + invitados del listing
        # - Para el evento principal si el canal es ABC
        # - Para red carpet si existe en E! con el nombre del evento
        try:
            tv = ensure_list((item.get("broadcast") or {}).get("tv"))
            if isinstance(item.get("broadcast"), dict):
                tv = ensure_list(item["broadcast"].get("tv"))

            # MAIN: ABC
            if "ABC" in [t.upper() for t in tv]:
                rows = parse_tvpassport_station_day(TVP_ABC_STATION, next_date)
                # match por tokens del nombre
                tokens = [t.lower() for t in preferred_terms] or [name.lower()]
                for r in rows:
                    p = clean_text(r.get("program", "")).lower()
                    if any(tok in p for tok in tokens):
                        start_local = r.get("start_local_hhmm")
                        duration_minutes = r.get("duration_minutes")
                        if r.get("desc"):
                            guests_auto = merge_list_unique(guests_auto, extract_names_from_desc(r["desc"]))
                            guests_sources = merge_list_unique(guests_sources, [r["source_url"]])
                        break

            # RED CARPET: E!
            rows_e = parse_tvpassport_station_day(TVP_E_STATION, next_date)
            tokens = [t.lower() for t in preferred_terms] or [name.lower()]
            for r in rows_e:
                p_raw = clean_text(r.get("program", ""))
                p = p_raw.lower()
                dsc = clean_text(r.get("desc", "")).lower()
                if "red carpet" in p and any(tok in (p + " " + dsc) for tok in tokens):
                    # completar red carpet confirmado
                    bcast = item.get("broadcast", {}) or {}
                    red = (bcast.get("red_carpet", {}) or {})
                    red = dict(red)
                    red["confirmed"] = True
                    red["where"] = p_raw
                    red["start_local"] = r.get("start_local_hhmm")
                    if r.get("duration_minutes"):
                        red["duration_minutes"] = int(r["duration_minutes"])
                    bcast = dict(bcast)
                    bcast["red_carpet"] = red
                    item["broadcast"] = bcast

                    if r.get("desc"):
                        guests_auto = merge_list_unique(guests_auto, extract_names_from_desc(r["desc"]))
                        guests_sources = merge_list_unique(guests_sources, [r["source_url"]])
                    break
        except Exception:
            pass

        # fallback: defaults del watchlist
        if not start_local:
            dflt = item.get("default_start_local")
            if isinstance(dflt, str) and dflt.strip():
                start_local = dflt.strip()

        if duration_minutes is None:
            dur = item.get("duration_minutes")
            if isinstance(dur, int):
                duration_minutes = dur
            elif isinstance(dur, str) and dur.isdigit():
                duration_minutes = int(dur)
            else:
                duration_minutes = None

        auto_ev: dict = {
            "id": str(item.get("id", "")).strip(),
            "title": f"{item.get('name','')}",
            "date": next_date.isoformat(),
            "tz_local": item.get("tz_local"),
            "location": item.get("location", ""),
            "broadcast": item.get("broadcast", {"tv": [], "streaming": [], "red_carpet": {"confirmed": False}}),
            "event_url": event_url,
            "top_nominated": top_nominated,
            "nomination_source_url": nomination_source_url,
            "start_local": start_local,
            "duration_minutes": duration_minutes,
            "special_awards": special_awards_auto,
            "guests_confirmed": guests_auto,
            "guests_source_urls": guests_sources,
            "confirmed_people": {"a_list": [], "b_list": [], "argentines": []},
            "confirmed_performers": [],
            "headliners": item.get("headliners", []) if isinstance(item.get("headliners", []), list) else [],
            "pop_artists": item.get("pop_artists", []) if isinstance(item.get("pop_artists", []), list) else [],
            "days": item.get("days", []) if isinstance(item.get("days", []), list) else [],
            "notes": [],
        }

        existing_ev = by_id.get(item_id) or (by_title.get(name.lower()) if name else None)
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
