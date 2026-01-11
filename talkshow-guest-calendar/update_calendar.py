#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
import requests
from bs4 import BeautifulSoup

TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")

UA = "Mozilla/5.0 (compatible; inHumanoCalendarBot/1.0; +https://alecsadok.github.io/inHumano/)"

OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)

ICS_OUT = OUT_DIR / "talkshow-guests.ics"
JSON_OUT = OUT_DIR / "talkshow-guests.json"


def ics_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    return s


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def dtstamp_utc() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def parse_time_hhmm(s: str) -> tuple[int, int]:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", s or "")
    if not m:
        raise ValueError(f"Invalid HH:MM time: {s}")
    return int(m.group(1)), int(m.group(2))


@dataclass
class Episode:
    show_id: str
    show_name: str
    air_date: date
    guests: list[str]
    sources: list[str]


def http_get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def parse_epguides_show(url: str) -> list[tuple[date, list[str]]]:
    """
    Best-effort: EPGuides suele tener una tabla en texto/HTML con fechas + nombres.
    Vamos a extraer líneas que contengan una fecha tipo 'Jan 10 2026' o '10 Jan 26' etc.
    """
    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    # Normalizar espacios
    text = re.sub(r"[ \t]+", " ", text)

    # Detectar fechas en formato "Jan 10 2026" (inglés)
    months = "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    # Ej: "Jan 10 2026"
    rx = re.compile(rf"\b{months}\s+(\d{{1,2}})\s+(\d{{4}})\b")

    items: list[tuple[date, list[str]]] = []

    lines = text.split("\n")
    for ln in lines:
        ln = ln.strip()
        if len(ln) < 8:
            continue
        m = rx.search(ln)
        if not m:
            continue

        mon_str, day_str, year_str = m.group(1), m.group(2), m.group(3)
        month_map = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
        }
        mm = month_map.get(mon_str)
        if not mm:
            continue
        dd = int(day_str)
        yy = int(year_str)
        try:
            d = date(yy, mm, dd)
        except ValueError:
            continue

        # Guests: heurística: lo que sigue después de la fecha
        # Ej: "... Jan 10 2026  Guest: X; Musical: Y"
        tail = ln[m.end():].strip(" -–—:|")
        # Limpiar cosas tipo "Ep. #", etc
        tail = re.sub(r"\bEp\.\s*#?\S+\b", "", tail).strip()
        guests = []
        if tail:
            # Separar por ; / , / | / •
            parts = re.split(r"[;|•]+", tail)
            for p in parts:
                p = p.strip(" -–—:|")
                if p and len(p) > 1:
                    guests.append(p)
        items.append((d, guests))

    # Deduplicar por fecha (quedarse con la más completa)
    by_date: dict[date, list[str]] = {}
    for d, g in items:
        if d not in by_date or len(g) > len(by_date[d]):
            by_date[d] = g
    return [(d, by_date[d]) for d in sorted(by_date.keys())]


def parse_wikipedia_episode_table(url: str, columns: dict) -> list[tuple[date, list[str]]]:
    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")

    # tomar la primera tabla "wikitable" con un header que tenga la columna date
    date_header = columns["date"]
    guest_headers = columns["guests"]

    tables = soup.select("table.wikitable")
    for table in tables:
        headers = [th.get_text(" ", strip=True) for th in table.select("tr th")]
        if not headers:
            continue
        if date_header not in headers:
            continue

        # map header->index
        header_row = table.select_one("tr")
        ths = header_row.select("th")
        header_map = {}
        for i, th in enumerate(ths):
            header_map[th.get_text(" ", strip=True)] = i

        if date_header not in header_map:
            continue

        guest_idxs = []
        for gh in guest_headers:
            if gh in header_map:
                guest_idxs.append(header_map[gh])

        date_idx = header_map[date_header]
        rows = table.select("tr")[1:]

        out: list[tuple[date, list[str]]] = []
        for tr in rows:
            tds = tr.find_all(["td", "th"])
            if len(tds) <= date_idx:
                continue
            date_txt = tds[date_idx].get_text(" ", strip=True)
            d = parse_any_date(date_txt)
            if not d:
                continue

            guests: list[str] = []
            for gi in guest_idxs:
                if gi < len(tds):
                    val = tds[gi].get_text(" ", strip=True)
                    val = re.sub(r"\[\d+\]", "", val).strip()
                    if val and val.lower() != "tbd":
                        guests.append(val)

            # dividir invitados en lista si vienen con saltos / "and" / etc
            guests = split_guests(guests)
            out.append((d, guests))
        return out

    return []


def parse_any_date(s: str) -> date | None:
    # soporta muchas variantes via dateutil (pero sin depender de locale)
    from dateutil import parser as dtparser
    s = re.sub(r"\[\d+\]", "", s).strip()
    if not s or s.lower() in {"tba", "tbd"}:
        return None
    try:
        dt = dtparser.parse(s, fuzzy=True, dayfirst=False)
        return dt.date()
    except Exception:
        return None


def split_guests(items: list[str]) -> list[str]:
    out: list[str] = []
    for it in items:
        if not it:
            continue
        parts = re.split(r"\s*(?:,| and | & |\u2022|/)\s*", it)
        for p in parts:
            p = p.strip()
            if p and p.lower() not in {"tbd", "tba"}:
                out.append(p)
    # dedupe preserve order
    seen = set()
    final = []
    for x in out:
        if x not in seen:
            seen.add(x)
            final.append(x)
    return final


def within_window(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def build_ics(episodes: list[Episode]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//inHumano//talkshow-calendar//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Talk shows (invitados) — Argentina (GMT-3)",
        "X-WR-TIMEZONE:America/Argentina/Buenos_Aires",
        "X-PUBLISHED-TTL:PT24H",
    ]
    stamp = dtstamp_utc()

    for ep in sorted(episodes, key=lambda e: (e.air_date, e.show_name)):
        uid = f"{uuid.uuid4()}@inhumano-talkshows"
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTAMP:{stamp}")

        # DTSTART/DTEND en Argentina
        # La hora “airtime_local” se resuelve fuera y se guarda en sources? lo haremos desde JSON,
        # pero para ICS se computa en el momento de crear Episode (ver main).
        # Acá asumimos que ep.sources incluye strings con "ar_start=..."? no: mejor guardamos en JSON.
        # Solución: guardamos el start/end en el título Episode como atributos en dict: simplificamos: lo recalculamos en main y guardamos en ep.sources? no.
        # En esta implementación guardamos un "meta" en sources con "ARSTART=..."? no.
        # Mejor: en main convertimos y guardamos iso strings en Episode.guests? no.
        # Para mantener Episode simple, vamos a codificar dtstart/dtend en sources con prefijo, y lo filtramos aquí.
        # (Es estable y no se muestra al usuario.)
        arstart = None
        arend = None
        real_sources = []
        for s in ep.sources:
            if s.startswith("__ARSTART__="):
                arstart = datetime.fromisoformat(s.split("=", 1)[1])
            elif s.startswith("__AREND__="):
                arend = datetime.fromisoformat(s.split("=", 1)[1])
            else:
                real_sources.append(s)

        if not arstart or not arend:
            # all-day fallback
            d0 = ep.air_date
            lines.append(f"DTSTART;VALUE=DATE:{d0.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{(d0 + timedelta(days=1)).strftime('%Y%m%d')}")
            time_line = "Hora Argentina: por anunciar."
        else:
            lines.append(f"DTSTART;TZID=America/Argentina/Buenos_Aires:{fmt_dt(arstart)}")
            lines.append(f"DTEND;TZID=America/Argentina/Buenos_Aires:{fmt_dt(arend)}")
            time_line = f"Hora Argentina: {arstart.strftime('%d/%m %H:%M')}–{arend.strftime('%H:%M')} (GMT-3)"

        # SUMMARY
        main_guest = ep.guests[0] if ep.guests else "Invitados por anunciar"
        summary = f"{ep.show_name} — {main_guest}"
        lines.append(f"SUMMARY:{ics_escape(summary)}")

        # DESCRIPTION
        desc_lines = [time_line]
        if ep.guests:
            desc_lines.append("Invitados:")
            for g in ep.guests:
                desc_lines.append(f"- {g}")
        else:
            desc_lines.append("Invitados: (no publicados aún en las fuentes consultadas)")

        if real_sources:
            desc_lines.append("")
            desc_lines.append("Fuentes:")
            for s in real_sources:
                desc_lines.append(f"- {s}")

        lines.append("DESCRIPTION:" + ics_escape("\n".join(desc_lines)))
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    cfg_path = Path("shows.yaml")
    if not cfg_path.exists():
        raise FileNotFoundError("No existe talkshow-guest-calendar/shows.yaml")

    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    settings = cfg.get("settings", {}) or {}
    days_ahead = int(settings.get("days_ahead", 21))
    include_sources = bool(settings.get("include_sources_in_description", True))
    allow_unofficial = bool(settings.get("allow_unofficial_fallbacks", True))

    shows = cfg.get("shows", [])
    if not isinstance(shows, list):
        raise ValueError("shows.yaml: 'shows' debe ser una lista.")

    today = datetime.now(tz=TZ_AR).date()
    end = today + timedelta(days=days_ahead)

    episodes: list[Episode] = []
    json_items: list[dict] = []

    for sh in shows:
        show_id = sh.get("id")
        show_name = sh.get("name")
        tz_local = sh.get("tz_local")
        airtime_local = sh.get("airtime_local")
        duration_minutes = int(sh.get("duration_minutes", 60))

        if not (show_id and show_name and tz_local and airtime_local):
            continue

        srcs = sh.get("sources", []) or []
        parsed_rows: list[tuple[date, list[str], list[str]]] = []

        # Recolectar episodios desde fuentes (en orden)
        for src in srcs:
            stype = (src.get("type") or "").strip()
            url = (src.get("url") or "").strip()
            if not (stype and url):
                continue

            try:
                if stype == "epguides_show":
                    rows = parse_epguides_show(url)
                    for d, guests in rows:
                        parsed_rows.append((d, guests, [url] if include_sources else []))

                elif stype == "wikipedia_episode_table":
                    cols = src.get("columns") or {}
                    rows = parse_wikipedia_episode_table(url, cols)
                    for d, guests in rows:
                        parsed_rows.append((d, guests, [url] if include_sources else []))

                else:
                    # tipos no implementados en este “starter”
                    continue
            except Exception:
                continue

        # Si no hay nada y allow_unofficial es true, no hacemos más (podés sumar más handlers después)
        if not parsed_rows and not allow_unofficial:
            continue

        # Consolidar por fecha (mejor lista de guests gana)
        by_date: dict[date, tuple[list[str], list[str]]] = {}
        for d, guests, src_list in parsed_rows:
            if not within_window(d, today, end):
                continue
            prev = by_date.get(d)
            if not prev or len(guests) > len(prev[0]):
                by_date[d] = (guests, src_list)

        local_tz = ZoneInfo(str(tz_local))
        hh, mm = parse_time_hhmm(str(airtime_local))

        for d in sorted(by_date.keys()):
            guests, src_list = by_date[d]

            # datetime local (show tz)
            local_dt = datetime(d.year, d.month, d.day, hh, mm, tzinfo=local_tz)
            ar_start = local_dt.astimezone(TZ_AR)
            ar_end = (local_dt + timedelta(minutes=duration_minutes)).astimezone(TZ_AR)

            # Guardamos start/end en sources de forma interna para build_ics
            internal = [
                f"__ARSTART__={ar_start.isoformat()}",
                f"__AREND__={ar_end.isoformat()}",
            ]

            ep_sources = internal + (src_list if include_sources else [])
            ep = Episode(
                show_id=str(show_id),
                show_name=str(show_name),
                air_date=d,
                guests=guests,
                sources=ep_sources,
            )
            episodes.append(ep)

            json_items.append({
                "show_id": show_id,
                "show_name": show_name,
                "air_date_local": d.isoformat(),
                "airtime_local": airtime_local,
                "tz_local": tz_local,
                "start_argentina": ar_start.isoformat(),
                "end_argentina": ar_end.isoformat(),
                "guests": guests,
                "sources": src_list if include_sources else [],
            })

    ics_text = build_ics(episodes)
    ICS_OUT.write_text(ics_text, encoding="utf-8")
    JSON_OUT.write_text(json.dumps(json_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: escrito {ICS_OUT}")


if __name__ == "__main__":
    import uuid
    main()
