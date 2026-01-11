from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


OUTPUT_DIR = Path("output")
OUTPUT_ICS = OUTPUT_DIR / "talkshow-guests.ics"
OUTPUT_JSON = OUTPUT_DIR / "talkshow-guests.json"

USER_AGENT = "talkshow-guest-calendar/1.0 (+https://github.com/yourname/yourrepo)"


@dataclass(frozen=True)
class Appearance:
    show_id: str
    show_name: str
    date: dt.date
    guests: tuple[str, ...]
    sources: tuple[str, ...]


def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def http_get(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def clean_text(s: str) -> str:
    s = re.sub(r"\[\d+\]", "", s)  # [1]
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_guests(raw: str) -> list[str]:
    raw = clean_text(raw)
    raw = raw.replace(";", ",")
    raw = raw.replace(" & ", ", ")
    # “X performs” / “with a performance by …” → mantenemos el nombre, quitamos verbo
    raw = re.sub(r"\b(performs|performing)\b.*$", "", raw, flags=re.IGNORECASE).strip()
    parts = [p.strip(" ,") for p in raw.split(",")]
    parts = [p for p in parts if p and p.lower() not in {"n/a", "none"}]
    # dedupe conservando orden
    seen = set()
    out: list[str] = []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def parse_date_from_text(text: str, today: dt.date) -> dt.date | None:
    """
    Intenta sacar una fecha.
    Prioridad:
      - ISO dentro de paréntesis: (2026-01-05)
      - parseo libre con dateutil (en inglés)
    """
    m = re.search(r"\((\d{4}-\d{2}-\d{2})\)", text)
    if m:
        return dt.date.fromisoformat(m.group(1))

    try:
        d = dateparser.parse(text, fuzzy=True, default=dt.datetime(today.year, 1, 1))
        if not d:
            return None
        # si no venía año y quedamos muy en el pasado, empujamos al año siguiente
        candidate = d.date()
        if candidate < today - dt.timedelta(days=180):
            candidate = dt.date(today.year + 1, candidate.month, candidate.day)
        return candidate
    except Exception:
        return None


# ---------- Scrapers ----------

def scrape_abc_guest_schedule(session: requests.Session, url: str, show_id: str, show_name: str, today: dt.date) -> list[Appearance]:
    html = http_get(session, url)
    soup = BeautifulSoup(html, "html.parser")

    # En la página de ABC suelen aparecer items tipo:
    # "Friday, Jan 09, 2026 Denis Leary; Rachel Maddow; HUNTR/X performs."
    items = [clean_text(li.get_text(" ", strip=True)) for li in soup.select("li")]

    out: list[Appearance] = []
    for t in items:
        if not re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", t):
            continue
        d = parse_date_from_text(t, today)
        if not d:
            continue
        # guests: todo lo que viene después de la fecha
        # Intento “cortar” a partir del año
        m = re.search(r"\b\d{4}\b", t)
        if not m:
            continue
        after = t[m.end():].strip(" -–: ")
        guests = split_guests(after)
        if guests:
            out.append(Appearance(show_id, show_name, d, tuple(guests), (url,)))
    return out


def scrape_cbs_episode_guide(session: requests.Session, url: str, show_id: str, show_name: str, today: dt.date) -> list[Appearance]:
    html = http_get(session, url)
    soup = BeautifulSoup(html, "html.parser")

    # En CBS suele haber H2 del estilo:
    # "1/8/26 (Tom Hiddleston, Terry Gross)"
    out: list[Appearance] = []
    for h2 in soup.find_all(["h2", "h3"]):
        t = clean_text(h2.get_text(" ", strip=True))
        m = re.match(r"^(\d{1,2}/\d{1,2}/\d{2})\s*\((.+)\)$", t)
        if not m:
            continue
        d = parse_date_from_text(m.group(1), today)
        if not d:
            continue
        guests = split_guests(m.group(2))
        if guests:
            out.append(Appearance(show_id, show_name, d, tuple(guests), (url,)))
    return out


def scrape_wikipedia_episode_table(
    session: requests.Session,
    url: str,
    show_id: str,
    show_name: str,
    today: dt.date,
    date_header: str,
    guest_headers: list[str],
) -> list[Appearance]:
    html = http_get(session, url)
    soup = BeautifulSoup(html, "html.parser")

    def norm(x: str) -> str:
        return re.sub(r"\s+", " ", x.strip()).lower()

    date_h = norm(date_header)
    guest_hs = {norm(h) for h in guest_headers}

    # buscamos una tabla que contenga el header de fecha + alguno de invitados
    for table in soup.select("table.wikitable"):
        headers = [norm(th.get_text(" ", strip=True)) for th in table.select("tr th")]
        if date_h not in headers:
            continue
        if not any(h in headers for h in guest_hs):
            continue

        # map header->index (primer row de headers real)
        header_row = table.select_one("tr")
        if not header_row:
            continue
        header_cells = header_row.find_all(["th", "td"])
        header_map: dict[str, int] = {}
        for i, cell in enumerate(header_cells):
            header_map[norm(cell.get_text(" ", strip=True))] = i

        if date_h not in header_map:
            continue
        guest_idxs = [header_map[h] for h in header_map.keys() if h in guest_hs]
        date_idx = header_map[date_h]

        out: list[Appearance] = []
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all(["th", "td"])
            if len(tds) <= max([date_idx, *guest_idxs], default=date_idx):
                continue

            date_text = clean_text(tds[date_idx].get_text(" ", strip=True))
            d = parse_date_from_text(date_text, today)
            if not d:
                continue

            guests_all: list[str] = []
            for gi in guest_idxs:
                guests_all.extend(split_guests(tds[gi].get_text(" ", strip=True)))

            if guests_all:
                out.append(Appearance(show_id, show_name, d, tuple(guests_all), (url,)))
        return out

    return []


def scrape_interbridge_lineups_by_date(session: requests.Session, url: str, today: dt.date) -> list[Appearance]:
    html = http_get(session, url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    # Bloques tipo:
    # "Monday, January 12" luego líneas "Jimmy Fallon: X, Y"
    lines = [clean_text(l) for l in text.split("\n") if l.strip()]
    out: list[Appearance] = []

    current_date: dt.date | None = None
    for line in lines:
        # encabezado de día
        if re.match(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\w+\s+\d{1,2}$", line):
            d = parse_date_from_text(line, today)
            current_date = d
            continue

        if not current_date:
            continue

        m = re.match(r"^(.+?):\s+(.+)$", line)
        if not m:
            continue

        show_name = m.group(1).strip()
        guests = split_guests(m.group(2))
        if not guests:
            continue

        show_id = "interbridge_" + re.sub(r"[^a-z0-9]+", "_", show_name.lower()).strip("_")
        out.append(Appearance(show_id, show_name, current_date, tuple(guests), (url,)))

    return out


def scrape_tvguide_listing(session: requests.Session, url: str, show_id: str, show_name: str, today: dt.date) -> list[Appearance]:
    html = http_get(session, url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [clean_text(l) for l in text.split("\n") if l.strip()]

    # Buscamos “Friday 9 January” + en la parte de “Guest”
    date_line = next((l for l in lines if re.match(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}\s+\w+$", l)), None)
    if not date_line:
        return []
    d = parse_date_from_text(date_line, today)
    if not d:
        return []

    # Extraemos invitados desde el bloque donde aparecen pares “Nombre” + “Guest”
    guests: list[str] = []
    for i, l in enumerate(lines):
        if l.lower() == "guest" and i > 0:
            candidate = lines[i - 1]
            # Evitar labels genéricos
            if candidate.lower() not in {"host", "guest"}:
                guests.append(candidate)

    # De-dupe
    guests = split_guests(", ".join(guests))
    if not guests:
        # fallback: a veces están en la descripción
        # (esto es muy heurístico, lo dejamos vacío si no aparece)
        pass

    if guests:
        return [Appearance(show_id, show_name, d, tuple(guests), (url,))]
    return []


# ---------- Output ----------

def fold_ics_line(line: str) -> str:
    # RFC 5545: 75 octets aprox; simplificamos por caracteres
    if len(line) <= 75:
        return line
    out = []
    while len(line) > 75:
        out.append(line[:75])
        line = " " + line[75:]
    out.append(line)
    return "\r\n".join(out)


def to_ics(appearances: list[Appearance], generated_at_utc: dt.datetime) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "PRODID:-//talkshow-guest-calendar//EN",
    ]
    stamp = generated_at_utc.strftime("%Y%m%dT%H%M%SZ")

    for a in sorted(appearances, key=lambda x: (x.date, x.show_name)):
        uid_raw = f"{a.show_id}-{a.date.isoformat()}-{','.join(a.guests)}"
        uid = hashlib.sha256(uid_raw.encode("utf-8")).hexdigest()[:24] + "@talkshow"
        dtstart = a.date.strftime("%Y%m%d")

        summary = f"{a.show_name} — " + "; ".join(a.guests)
        desc_parts = [
            f"Show: {a.show_name}",
            f"Date: {a.date.isoformat()}",
            f"Guests: {', '.join(a.guests)}",
        ]
        if a.sources:
            desc_parts.append("Sources:")
            desc_parts.extend([f"- {u}" for u in a.sources])

        description = "\\n".join(desc_parts)

        lines.extend([
            "BEGIN:VEVENT",
            fold_ics_line(f"UID:{uid}"),
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{dtstart}",
            fold_ics_line(f"SUMMARY:{summary}"),
            fold_ics_line(f"DESCRIPTION:{description}"),
        ])
        if a.sources:
            lines.append(fold_ics_line(f"URL:{a.sources[0]}"))
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="shows.yaml")
    ap.add_argument("--days-ahead", type=int, default=None)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    settings = cfg.get("settings", {})
    days_ahead = args.days_ahead or int(settings.get("days_ahead", 21))
    allow_unofficial = bool(settings.get("allow_unofficial_fallbacks", True))

    today = dt.datetime.utcnow().date()
    until = today + dt.timedelta(days=days_ahead)

    session = build_session()

    all_apps: list[Appearance] = []

    for show in cfg.get("shows", []):
        sid = show["id"]
        sname = show["name"]
        for src in show.get("sources", []):
            stype = src["type"]
            url = src["url"]

            try:
                if stype == "abc_guest_schedule":
                    all_apps.extend(scrape_abc_guest_schedule(session, url, sid, sname, today))

                elif stype == "cbs_episode_guide":
                    all_apps.extend(scrape_cbs_episode_guide(session, url, sid, sname, today))

                elif stype == "wikipedia_episode_table":
                    cols = src["columns"]
                    all_apps.extend(
                        scrape_wikipedia_episode_table(
                            session=session,
                            url=url,
                            show_id=sid,
                            show_name=sname,
                            today=today,
                            date_header=cols["date"],
                            guest_headers=cols["guests"],
                        )
                    )

                elif stype == "interbridge_lineups_by_date":
                    if allow_unofficial:
                        all_apps.extend(scrape_interbridge_lineups_by_date(session, url, today))

                elif stype == "tvguide_listing":
                    if allow_unofficial:
                        all_apps.extend(scrape_tvguide_listing(session, url, sid, sname, today))

                else:
                    # Placeholder: instagram_graph_api, bbc_programmes_api, etc.
                    continue

            except Exception as e:
                print(f"[WARN] {sname} ({stype}) falló: {e}")

    # filtro rango
    all_apps = [a for a in all_apps if today <= a.date <= until]

    # de-dup por (show_name, date) uniendo invitados + fuentes
    merged: dict[tuple[str, dt.date], tuple[set[str], set[str], str]] = {}
    for a in all_apps:
        k = (a.show_name, a.date)
        if k not in merged:
            merged[k] = (set(a.guests), set(a.sources), a.show_id)
        else:
            merged[k][0].update(a.guests)
            merged[k][1].update(a.sources)

    final: list[Appearance] = []
    for (show_name, d), (guests_set, sources_set, show_id) in merged.items():
        guests_sorted = tuple(sorted(guests_set, key=lambda x: x.lower()))
        sources_sorted = tuple(sorted(sources_set))
        final.append(Appearance(show_id, show_name, d, guests_sorted, sources_sorted))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated_at = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    ics = to_ics(final, generated_at)

    OUTPUT_ICS.write_text(ics, encoding="utf-8")

    # JSON simple para debug/uso en web
    import json
    payload = {
        "generated_at_utc": generated_at.isoformat(),
        "days_ahead": days_ahead,
        "count": len(final),
        "items": [
            {
                "show_id": a.show_id,
                "show_name": a.show_name,
                "date": a.date.isoformat(),
                "guests": list(a.guests),
                "sources": list(a.sources),
            }
            for a in sorted(final, key=lambda x: (x.date, x.show_name))
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {len(final)} eventos → {OUTPUT_ICS} / {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
