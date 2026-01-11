#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import uuid
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


def clean_guest_label(s: str) -> str:
    s = re.sub(
        r"^(Guests?|Musical|Musical guest|Musical/entertainment guest|Host)\s*:\s*",
        "",
        s,
        flags=re.I,
    ).strip()
    return s


def parse_epguides_show(url: str) -> list[tuple[date, list[str]]]:
    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)

    months = "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    rx = re.compile(rf"\b{months}\s+(\d{{1,2}})\s+(\d{{2,4}})\b")

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
            "Jan": 1,
            "Feb": 2,
            "Mar": 3,
            "Apr": 4,
            "May": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12,
        }
        mm = month_map.get(mon_str)
        if not mm:
            continue
        dd = int(day_str)
        yy = int(year_str)
        if yy < 100:
            yy += 2000
        try:
            d = date(yy, mm, dd)
        except ValueError:
            continue

        tail = ln[m.end() :].strip(" -–—:|")
        tail = re.sub(r"\bEp\.\s*#?\S+\b", "", tail).strip()
        guests: list[str] = []
        if tail:
            parts = re.split(r"[;|•]+", tail)
            for p in parts:
                p = p.strip(" -–—:|")
                p = clean_guest_label(p)
                if p and len(p) > 1:
                    guests.append(p)
        items.append((d, guests))

    by_date: dict[date, list[str]] = {}
    for d, g in items:
        if d not in by_date or len(g) > len(by_date[d]):
            by_date[d] = g
    return [(d, by_date[d]) for d in sorted(by_date.keys())]


def parse_wikipedia_episode_table(url: str, columns: dict) -> list[tuple[date, list[str]]]:
    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")

    date_header = columns["date"]
    guest_headers = columns["guests"]

    tables = soup.select("table.wikitable")
    for table in tables:
        headers = [th.get_text(" ", strip=True) for th in table.select("tr th")]
        if not headers:
            continue
        if date_header not in headers:
            continue

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

            guests = split_guests(guests)
            out.append((d, guests))
        return out

    return []


def parse_any_date(s: str) -> date | None:
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
            p = clean_guest_label(p)
            if p and p.lower() not in {"tbd", "tba"}:
                out.append(p)
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
            d0 = ep.air_date
            lines.append(f"DTSTART;VALUE=DATE:{d0.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{(d0 + timedelta(days=1)).strftime('%Y%m%d')}")
            time_line = "Hora Argentina: por anunciar."
        else:
            lines.append(f"DTSTART;TZID=America/Argentina/Buenos_Aires:{fmt_dt(arstart)}")
            lines.append(f"DTEND;TZID=America/Argentina/Buenos_Aires:{fmt_dt(arend)}")
            time_line = f"Hora Argentina: {arstart.strftime('%d/%m %H:%M')}–{arend.strftime('%H:%M')} (GMT-3)"

        main_guest = ep.guests[0] if ep.guests else "Invitados por anunciar"
        summary = f"{ep.show_name} — {main_guest}"
        lines.append(f"SUMMARY:{ics_escape(summary)}")

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
                    continue
            except Exception:
                continue

        if not parsed_rows and not allow_unofficial:
            continue

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

            local_dt = datetime(d.year, d.month, d.day, hh, mm, tzinfo=local_tz)
            ar_start = local_dt.astimezone(TZ_AR)
            ar_end = (local_dt + timedelta(minutes=duration_minutes)).astimezone(TZ_AR)

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

            json_items.append(
                {
                    "show_id": show_id,
                    "show_name": show_name,
                    "air_date_local": d.isoformat(),
                    "airtime_local": airtime_local,
                    "tz_local": tz_local,
                    "start_argentina": ar_start.isoformat(),
                    "end_argentina": ar_end.isoformat(),
                    "guests": guests,
                    "sources": src_list if include_sources else [],
                }
            )

    ics_text = build_ics(episodes)
    ICS_OUT.write_text(ics_text, encoding="utf-8")
    JSON_OUT.write_text(json.dumps(json_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: escrito {ICS_OUT}")


if __name__ == "__main__":
    main()
