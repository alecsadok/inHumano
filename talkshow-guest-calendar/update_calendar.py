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

TIME_LINE_RX = re.compile(r"^\s*(\d{1,2}:\d{2}\s*[AP]M)\s*$", re.I)


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


def split_guests(items: list[str]) -> list[str]:
    out: list[str] = []
    for it in items:
        if not it:
            continue
        parts = re.split(r"\s*(?:,| and | & |\u2022|/)\s*", it)
        for p in parts:
            p = clean_guest_label(p.strip())
            if p and p.lower() not in {"tbd", "tba"}:
                out.append(p)
    seen = set()
    final = []
    for x in out:
        if x not in seen:
            seen.add(x)
            final.append(x)
    return final


def parse_any_date(s: str) -> date | None:
    from dateutil import parser as dtparser

    s = re.sub(r"\[\d+\]", "", (s or "")).strip()
    if not s or s.lower() in {"tba", "tbd"}:
        return None
    try:
        dt = dtparser.parse(s, fuzzy=True, dayfirst=False)
        return dt.date()
    except Exception:
        return None


def within_window(d: date, start: date, end: date) -> bool:
    return start <= d <= end


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
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
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

        tail = ln[m.end():].strip(" -–—:|")
        tail = re.sub(r"\bEp\.\s*#?\S+\b", "", tail).strip()
        guests: list[str] = []
        if tail:
            parts = re.split(r"[;|•]+", tail)
            for p in parts:
                p = clean_guest_label(p.strip(" -–—:|"))
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
        if not headers or date_header not in headers:
            continue

        header_row = table.select_one("tr")
        ths = header_row.select("th")
        header_map = {th.get_text(" ", strip=True): i for i, th in enumerate(ths)}
        if date_header not in header_map:
            continue

        guest_idxs = [header_map[gh] for gh in guest_headers if gh in header_map]
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
                    val = re.sub(r"\[\d+\]", "", tds[gi].get_text(" ", strip=True)).strip()
                    if val and val.lower() != "tbd":
                        guests.append(val)

            guests = split_guests(guests)
            out.append((d, guests))
        return out

    return []


def to_minutes_ampm(t: str) -> int:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*$", t, re.I)
    if not m:
        return -1
    hh = int(m.group(1))
    mm = int(m.group(2))
    ap = m.group(3).upper()
    if ap == "PM" and hh != 12:
        hh += 12
    if ap == "AM" and hh == 12:
        hh = 0
    return hh * 60 + mm


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
        t = m.group(1).upper().strip()
        prog = lines[i + 1] if i + 1 < len(lines) else ""
        desc = lines[i + 2] if i + 2 < len(lines) else ""
        items.append({"time": t, "program": prog, "desc": desc, "source_url": url})
        i += 1

    for idx in range(len(items) - 1):
        a = to_minutes_ampm(items[idx]["time"])
        b = to_minutes_ampm(items[idx + 1]["time"])
        if a >= 0 and b >= 0 and b > a:
            items[idx]["duration_minutes"] = b - a

    for it in items:
        m2 = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*$", it["time"], re.I)
        if not m2:
            continue
        hh = int(m2.group(1))
        mm = int(m2.group(2))
        ap = m2.group(3).upper()
        if ap == "PM" and hh != 12:
            hh += 12
        if ap == "AM" and hh == 12:
            hh = 0
        it["start_local_hhmm"] = f"{hh:02d}:{mm:02d}"
    return items


def match_program(program: str, contains_any: list[str]) -> bool:
    p = (program or "").lower()
    for t in contains_any:
        if str(t).strip().lower() in p:
            return True
    return False


def extract_guests_from_tvpassport_desc(desc: str) -> list[str]:
    d = (desc or "").strip()
    if not d:
        return []
    d = re.sub(r"^\s*New\s+Live\s*", "", d, flags=re.I).strip()
    d = re.sub(r"^[Ee]pisode\s*\d+\s*[-–—]\s*", "", d).strip()
    if ":" in d and any(k in d.lower() for k in ["guest", "guests", "with", "starring"]):
        tail = d.split(":", 1)[1]
    else:
        tail = d
    tail = re.sub(r"\band\b", ",", tail, flags=re.I)
    parts = [p.strip(" ,.;") for p in tail.split(",") if p.strip(" ,.;")]
    out: list[str] = []
    for p in parts:
        if 2 <= len(p.split()) <= 5 and len(p) <= 80:
            out.append(p)
    seen = set()
    final = []
    for x in out:
        if x not in seen:
            seen.add(x)
            final.append(x)
    return final


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
            desc_lines.append("Invitados: " + "; ".join(ep.guests))
        else:
            desc_lines.append("Invitados: (no publicados aún en las fuentes consultadas)")

        if real_sources:
            desc_lines.append("Fuentes: " + "; ".join(real_sources))

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

        by_date: dict[date, dict] = {}

        for src in srcs:
            stype = (src.get("type") or "").strip()
            url = (src.get("url") or "").strip()
            if not (stype and url):
                continue

            try:
                if stype == "tvpassport_station":
                    match_cfg = src.get("match") or {}
                    contains_any = ensure_list(match_cfg.get("contains_any"))
                    for off in range(days_ahead + 1):
                        d = today + timedelta(days=off)
                        items = parse_tvpassport_station_day(url, d)
                        for it in items:
                            if not match_program(it.get("program", ""), contains_any):
                                continue
                            hhmm = it.get("start_local_hhmm")
                            if not hhmm:
                                continue
                            guests = extract_guests_from_tvpassport_desc(it.get("desc", ""))
                            src_list = [it.get("source_url", url)] if include_sources else []
                            cur = by_date.get(d, {})
                            prev_guests = cur.get("guests", [])
                            if len(guests) >= len(prev_guests):
                                by_date[d] = {"guests": guests, "sources": src_list, "hhmm": hhmm}
                            break

                elif stype == "epguides_show":
                    rows = parse_epguides_show(url)
                    for d, guests in rows:
                        if not within_window(d, today, end):
                            continue
                        src_list = [url] if include_sources else []
                        cur = by_date.get(d, {})
                        prev_guests = cur.get("guests", [])
                        if len(guests) > len(prev_guests):
                            by_date[d] = {"guests": guests, "sources": src_list, "hhmm": cur.get("hhmm")}

                elif stype == "wikipedia_episode_table":
                    cols = src.get("columns") or {}
                    rows = parse_wikipedia_episode_table(url, cols)
                    for d, guests in rows:
                        if not within_window(d, today, end):
                            continue
                        src_list = [url] if include_sources else []
                        cur = by_date.get(d, {})
                        prev_guests = cur.get("guests", [])
                        if len(guests) > len(prev_guests):
                            by_date[d] = {"guests": guests, "sources": src_list, "hhmm": cur.get("hhmm")}

                else:
                    continue
            except Exception:
                continue

        local_tz = ZoneInfo(str(tz_local))
        default_hh, default_mm = parse_time_hhmm(str(airtime_local))

        for d in sorted(by_date.keys()):
            info = by_date[d]
            guests = info.get("guests", []) or []
            src_list = info.get("sources", []) or []
            hhmm_override = info.get("hhmm")

            if isinstance(hhmm_override, str) and re.match(r"^\d{2}:\d{2}$", hhmm_override):
                hh, mm = parse_time_hhmm(hhmm_override)
            else:
                hh, mm = default_hh, default_mm

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
                guests=split_guests([", ".join(guests)]) if guests and len(guests) == 1 else guests,
                sources=ep_sources,
            )
            episodes.append(ep)

            json_items.append(
                {
                    "show_id": show_id,
                    "show_name": show_name,
                    "air_date_local": d.isoformat(),
                    "tz_local": tz_local,
                    "start_argentina": ar_start.isoformat(),
                    "end_argentina": ar_end.isoformat(),
                    "guests": ep.guests,
                    "sources": src_list if include_sources else [],
                }
            )

    ics_text = build_ics(episodes)
    ICS_OUT.write_text(ics_text, encoding="utf-8")
    JSON_OUT.write_text(json.dumps(json_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: escrito {ICS_OUT}")


if __name__ == "__main__":
    main()
