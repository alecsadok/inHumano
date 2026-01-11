#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import uuid
import yaml

TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")

OUTPUT_DIR = Path(".")
OUTPUT_ICS_NAME = "premios.ics"
OUTPUT_LAST_UPDATED = "last_updated.txt"


def ics_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    return s


def dtstamp_utc() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def fmt_date(d) -> str:
    return d.strftime("%Y%m%d")


def ensure_list(x) -> list[str]:
    if not x:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    return [str(x)] if str(x).strip() else []


def parse_local_dt(date_str: str, time_str: str, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    naive = datetime.fromisoformat(f"{date_str}T{time_str}:00")
    return naive.replace(tzinfo=tz)


def ar_time_window(ar_start: datetime, ar_end: datetime) -> str:
    if ar_start.date() == ar_end.date():
        return f"{ar_start.strftime('%d/%m %H:%M')}–{ar_end.strftime('%H:%M')} (Argentina, GMT-3)"
    return f"{ar_start.strftime('%d/%m %H:%M')}–{ar_end.strftime('%d/%m %H:%M')} (Argentina, GMT-3)"


def add_people_block(desc_lines: list[str], label: str, arr: list[str]) -> None:
    if arr:
        desc_lines.append(f"{label}: " + ", ".join(arr))
    else:
        desc_lines.append(f"{label}: (sin confirmaciones oficiales publicadas)")


def main() -> None:
    yaml_path = Path("events.yaml")
    if not yaml_path.exists():
        raise FileNotFoundError("No existe events.yaml en la raíz del repo.")

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    events = data.get("events", [])
    if not isinstance(events, list):
        raise ValueError("events.yaml: la clave 'events' debe ser una lista.")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//inHumano//premios-calendar//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Premios/Eventos (confirmados) — Argentina (GMT-3)",
        "X-WR-TIMEZONE:America/Argentina/Buenos_Aires",
        "X-PUBLISHED-TTL:PT24H",
    ]

    stamp = dtstamp_utc()

    for ev in events:
        if not isinstance(ev, dict):
            continue

        title = str(ev.get("title", "")).strip()
        if not title:
            continue

        location = str(ev.get("location", "")).strip()
        base_date = str(ev.get("date", "")).strip()

        start_local = ev.get("start_local")
        tz_local = ev.get("tz_local")
        duration_minutes = ev.get("duration_minutes")

        broadcast = ev.get("broadcast", {}) or {}
        tv = ensure_list(broadcast.get("tv"))
        streaming = ensure_list(broadcast.get("streaming"))

        red = broadcast.get("red_carpet", {}) or {}
        red_confirmed = bool(red.get("confirmed", False))
        red_where = str(red.get("where", "")).strip()
        red_start_local = red.get("start_local")
        red_duration_minutes = red.get("duration_minutes")

        confirmed_people = ev.get("confirmed_people", {}) or {}
        a_list = ensure_list(confirmed_people.get("a_list"))
        b_list = ensure_list(confirmed_people.get("b_list"))
        argentines = ensure_list(confirmed_people.get("argentines"))

        top_nominated = ensure_list(ev.get("top_nominated"))
        confirmed_performers = ensure_list(ev.get("confirmed_performers"))
        special_awards = ensure_list(ev.get("special_awards"))

        headliners = ensure_list(ev.get("headliners"))
        pop_artists = ensure_list(ev.get("pop_artists"))

        notes = ensure_list(ev.get("notes"))

        days = ev.get("days")
        day_entries: list[dict] = []
        if isinstance(days, list) and days:
            for d in days:
                if isinstance(d, dict) and str(d.get("date", "")).strip():
                    day_entries.append(d)
        else:
            if base_date:
                day_entries.append({"date": base_date})
            else:
                continue

        for day_ev in day_entries:
            day_date = str(day_ev.get("date", "")).strip()
            if not day_date:
                continue

            day_set_times = day_ev.get("set_times", ev.get("set_times", [])) or []
            day_headliners = ensure_list(day_ev.get("headliners")) or headliners
            day_pop = ensure_list(day_ev.get("pop_artists")) or pop_artists
            day_notes = ensure_list(day_ev.get("notes")) + notes

            uid = f"{uuid.uuid4()}@inhumano"
            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:{uid}")
            lines.append(f"DTSTAMP:{stamp}")
            lines.append(f"SUMMARY:{ics_escape(title)}")
            if location:
                lines.append(f"LOCATION:{ics_escape(location)}")

            desc_lines: list[str] = []

            has_time = bool(start_local and tz_local and duration_minutes)
            if has_time:
                local_dt = parse_local_dt(day_date, str(start_local), str(tz_local))
                ar_start = local_dt.astimezone(TZ_AR)
                ar_end = (local_dt + timedelta(minutes=int(duration_minutes))).astimezone(TZ_AR)

                lines.append(f"DTSTART;TZID=America/Argentina/Buenos_Aires:{fmt_dt(ar_start)}")
                lines.append(f"DTEND;TZID=America/Argentina/Buenos_Aires:{fmt_dt(ar_end)}")
                desc_lines.append("Hora Argentina: " + ar_time_window(ar_start, ar_end))
            else:
                d0 = datetime.fromisoformat(day_date).date()
                lines.append(f"DTSTART;VALUE=DATE:{fmt_date(d0)}")
                lines.append(f"DTEND;VALUE=DATE:{fmt_date(d0 + timedelta(days=1))}")
                desc_lines.append("Hora Argentina: por anunciar (sin horario oficial publicado).")

            if tv:
                desc_lines.append("TV: " + ", ".join(tv))
            if streaming:
                desc_lines.append("Streaming: " + ", ".join(streaming))

            if red_confirmed:
                if red_start_local and tz_local and red_duration_minutes:
                    red_local = parse_local_dt(day_date, str(red_start_local), str(tz_local))
                    red_ar_start = red_local.astimezone(TZ_AR)
                    red_ar_end = (red_local + timedelta(minutes=int(red_duration_minutes))).astimezone(TZ_AR)
                    line = "Red carpet confirmado: "
                    if red_where:
                        line += red_where + " — "
                    line += "Hora Argentina: " + ar_time_window(red_ar_start, red_ar_end)
                    desc_lines.append(line)
                else:
                    desc_lines.append("Red carpet confirmado: " + (red_where if red_where else "Sí (detalle por anunciar)"))
            else:
                desc_lines.append("Red carpet: no confirmado oficialmente.")

            if top_nominated:
                desc_lines.append("Más nominadas/os: " + ", ".join(top_nominated))
            if confirmed_performers:
                desc_lines.append("Performances confirmadas: " + ", ".join(confirmed_performers))
            if special_awards:
                desc_lines.append("Premios especiales confirmados: " + ", ".join(special_awards))

            if day_headliners:
                desc_lines.append("Headliners: " + ", ".join(day_headliners))
            if day_pop:
                desc_lines.append("Artistas pop destacados: " + ", ".join(day_pop))

            if isinstance(day_set_times, list) and day_set_times:
                if tz_local:
                    desc_lines.append("Horarios de shows (hora Argentina, GMT-3):")
                    local_tz = ZoneInfo(str(tz_local))
                    for st in day_set_times:
                        if not isinstance(st, dict):
                            continue
                        artist = str(st.get("artist", "")).strip()
                        st_start = str(st.get("start_local", "")).strip()
                        st_end = str(st.get("end_local", "")).strip()
                        stage = str(st.get("stage", "")).strip()
                        if not (artist and st_start and st_end):
                            continue

                        dt_s_local = datetime.fromisoformat(f"{day_date}T{st_start}:00").replace(tzinfo=local_tz)
                        dt_e_local = datetime.fromisoformat(f"{day_date}T{st_end}:00").replace(tzinfo=local_tz)
                        dt_s_ar = dt_s_local.astimezone(TZ_AR)
                        dt_e_ar = dt_e_local.astimezone(TZ_AR)

                        line = f"- {dt_s_ar.strftime('%H:%M')}–{dt_e_ar.strftime('%H:%M')} {artist}"
                        if stage:
                            line += f" ({stage})"
                        desc_lines.append(line)
                else:
                    desc_lines.append("Horarios de shows: no se pueden convertir (falta tz_local).")

            add_people_block(desc_lines, "Celebrities A-list confirmadas", a_list)
            add_people_block(desc_lines, "Celebrities B-list confirmadas", b_list)
            add_people_block(desc_lines, "Argentinos confirmados", argentines)

            for n in day_notes:
                if str(n).strip():
                    desc_lines.append(str(n).strip())

            desc = "\n".join(desc_lines)
            lines.append("DESCRIPTION:" + ics_escape(desc))
            lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    ics_text = "\r\n".join(lines) + "\r\n"
    (OUTPUT_DIR / OUTPUT_ICS_NAME).write_text(ics_text, encoding="utf-8")
    (OUTPUT_DIR / OUTPUT_LAST_UPDATED).write_text(datetime.utcnow().isoformat() + "Z\n", encoding="utf-8")
    print(f"OK: generado {OUTPUT_ICS_NAME}")


if __name__ == "__main__":
    main()
