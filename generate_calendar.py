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


def ar_time_window_style(ar_start: datetime, ar_end: datetime) -> str:
    return f"{ar_start.strftime('%d/%m %H:%M')}–{ar_end.strftime('%H:%M')} (Argentina, GMT-3)"


def combine_celebs(confirmed_people: dict | None) -> list[str]:
    confirmed_people = confirmed_people or {}
    a = ensure_list(confirmed_people.get("a_list"))
    b = ensure_list(confirmed_people.get("b_list"))
    ar = ensure_list(confirmed_people.get("argentines"))
    out = []
    seen = set()
    for x in a + b + ar:
        x = str(x).strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def build_event_lines(
    stamp: str,
    summary: str,
    location: str,
    description_lines: list[str],
    dtstart_ba: datetime | None,
    dtend_ba: datetime | None,
    allday_date: datetime.date | None,
) -> list[str]:
    out: list[str] = []
    out.append("BEGIN:VEVENT")
    out.append(f"UID:{uuid.uuid4()}@inhumano")
    out.append(f"DTSTAMP:{stamp}")
    out.append(f"SUMMARY:{ics_escape(summary)}")
    if location:
        out.append(f"LOCATION:{ics_escape(location)}")
    desc = "\n".join(description_lines)
    out.append("DESCRIPTION:" + ics_escape(desc))

    if dtstart_ba and dtend_ba:
        out.append(f"DTSTART;TZID=America/Argentina/Buenos_Aires:{fmt_dt(dtstart_ba)}")
        out.append(f"DTEND;TZID=America/Argentina/Buenos_Aires:{fmt_dt(dtend_ba)}")
    else:
        if allday_date is None:
            raise ValueError("All-day event requires allday_date")
        out.append(f"DTSTART;VALUE=DATE:{fmt_date(allday_date)}")
        out.append(f"DTEND;VALUE=DATE:{fmt_date(allday_date + timedelta(days=1))}")

    out.append("END:VEVENT")
    return out


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
        "PRODID:-//inHumano//Calendario A-List AR//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Eventos A-List (confirmados) — Argentina (GMT-3)",
        "X-WR-TIMEZONE:America/Argentina/Buenos_Aires",
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

        tz_local = ev.get("tz_local")
        start_local = ev.get("start_local")
        duration_minutes = ev.get("duration_minutes")

        event_url = str(ev.get("event_url", "") or "").strip()

        broadcast = ev.get("broadcast", {}) or {}
        tv = ensure_list(broadcast.get("tv"))
        streaming = ensure_list(broadcast.get("streaming"))

        red = broadcast.get("red_carpet", {}) or {}
        red_confirmed = bool(red.get("confirmed", False))
        red_where = str(red.get("where", "")).strip()
        red_start_local = red.get("start_local")
        red_duration_minutes = red.get("duration_minutes")

        top_nominated = ensure_list(ev.get("top_nominated"))
        nomination_source_url = str(ev.get("nomination_source_url", "") or "").strip()

        confirmed_people = ev.get("confirmed_people", {}) or {}
        celebs = combine_celebs(confirmed_people)

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

            # 1) Red carpet como evento separado (solo si confirmado + horario completo)
            if red_confirmed and tz_local and red_start_local and red_duration_minutes:
                rc_local_dt = parse_local_dt(day_date, str(red_start_local), str(tz_local))
                rc_start = rc_local_dt.astimezone(TZ_AR)
                rc_end = (rc_local_dt + timedelta(minutes=int(red_duration_minutes))).astimezone(TZ_AR)

                desc_lines_rc: list[str] = []
                desc_lines_rc.append("Hora Argentina: " + ar_time_window_style(rc_start, rc_end))
                if tv:
                    desc_lines_rc.append("TV (origen): " + "; ".join(tv) + ".")
                if streaming:
                    desc_lines_rc.append("Streaming (origen): " + "; ".join(streaming) + ".")

                if event_url:
                    desc_lines_rc.append("Fuente (evento): " + event_url)

                if top_nominated:
                    desc_lines_rc.append("Más nominadas/os: " + "; ".join(top_nominated) + ".")
                    if nomination_source_url:
                        desc_lines_rc.append("Fuente (nominados): " + nomination_source_url)

                if special_awards:
                    desc_lines_rc.append("Premios especiales confirmados: " + "; ".join(special_awards) + ".")

                if celebs:
                    desc_lines_rc.append("Celebridades que van: " + "; ".join(celebs) + ".")

                for n in day_notes:
                    if str(n).strip():
                        desc_lines_rc.append(str(n).strip())

                rc_summary = f"{title} — Red Carpet"
                if red_where:
                    rc_summary = f"{title} — Red Carpet ({red_where})"

                lines.extend(
                    build_event_lines(
                        stamp=stamp,
                        summary=rc_summary,
                        location=location,
                        description_lines=desc_lines_rc,
                        dtstart_ba=rc_start,
                        dtend_ba=rc_end,
                        allday_date=None,
                    )
                )

            # 2) Evento principal (NO mencionar red carpet)
            desc_lines_main: list[str] = []
            has_time = bool(start_local and tz_local and duration_minutes)
            if has_time:
                local_dt = parse_local_dt(day_date, str(start_local), str(tz_local))
                ar_start = local_dt.astimezone(TZ_AR)
                ar_end = (local_dt + timedelta(minutes=int(duration_minutes))).astimezone(TZ_AR)
                desc_lines_main.append("Hora Argentina: " + ar_time_window_style(ar_start, ar_end))
            else:
                ar_start = None
                ar_end = None
                desc_lines_main.append("Hora Argentina: por anunciar (sin horario oficial publicado).")

            if tv:
                desc_lines_main.append("TV (origen): " + "; ".join(tv) + ".")
            if streaming:
                desc_lines_main.append("Streaming (origen): " + "; ".join(streaming) + ".")

            if event_url:
                desc_lines_main.append("Fuente (evento): " + event_url)

            if top_nominated:
                desc_lines_main.append("Más nominadas/os: " + "; ".join(top_nominated) + ".")
                if nomination_source_url:
                    desc_lines_main.append("Fuente (nominados): " + nomination_source_url)

            if confirmed_performers:
                desc_lines_main.append("Performances confirmadas: " + "; ".join(confirmed_performers) + ".")
            if special_awards:
                desc_lines_main.append("Premios especiales confirmados: " + "; ".join(special_awards) + ".")

            if day_headliners:
                desc_lines_main.append("Headliners: " + "; ".join(day_headliners) + ".")
            if day_pop:
                desc_lines_main.append("Pop destacado: " + "; ".join(day_pop) + ".")

            if isinstance(day_set_times, list) and day_set_times and tz_local:
                desc_lines_main.append("Horarios de shows (hora Argentina, GMT-3):")
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
                    desc_lines_main.append(line)

            if celebs:
                desc_lines_main.append("Celebridades que van: " + "; ".join(celebs) + ".")

            for n in day_notes:
                if str(n).strip():
                    desc_lines_main.append(str(n).strip())

            if has_time:
                lines.extend(
                    build_event_lines(
                        stamp=stamp,
                        summary=title,
                        location=location,
                        description_lines=desc_lines_main,
                        dtstart_ba=ar_start,
                        dtend_ba=ar_end,
                        allday_date=None,
                    )
                )
            else:
                d0 = datetime.fromisoformat(day_date).date()
                lines.extend(
                    build_event_lines(
                        stamp=stamp,
                        summary=title,
                        location=location,
                        description_lines=desc_lines_main,
                        dtstart_ba=None,
                        dtend_ba=None,
                        allday_date=d0,
                    )
                )

    lines.append("END:VCALENDAR")

    ics_text = "\r\n".join(lines) + "\r\n"
    (OUTPUT_DIR / OUTPUT_ICS_NAME).write_text(ics_text, encoding="utf-8")
    (OUTPUT_DIR / OUTPUT_LAST_UPDATED).write_text(datetime.utcnow().isoformat() + "Z\n", encoding="utf-8")
    print(f"OK: generado {OUTPUT_ICS_NAME}")


if __name__ == "__main__":
    main()
