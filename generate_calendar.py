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


def join_channel_streaming(tv: list[str], streaming: list[str]) -> str | None:
    parts = []
    if tv:
        parts.append(" / ".join(tv))
    if streaming:
        parts.append(" / ".join(streaming))
    if not parts:
        return None
    return " / ".join(parts)


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
    out.append("DESCRIPTION:" + ics_escape("\n".join(description_lines)))

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
        nomination_source_url = str(ev.get("nomination_source_url", "") or "").strip()
        guests_source_urls = ensure_list(ev.get("guests_source_urls"))

        broadcast = ev.get("broadcast", {}) or {}
        tv = ensure_list(broadcast.get("tv"))
        streaming = ensure_list(broadcast.get("streaming"))

        red = broadcast.get("red_carpet", {}) or {}
        red_confirmed = bool(red.get("confirmed", False))
        red_where = str(red.get("where", "")).strip()
        red_start_local = red.get("start_local")
        red_duration_minutes = red.get("duration_minutes")

        top_nominated = ensure_list(ev.get("top_nominated"))
        special_awards = ensure_list(ev.get("special_awards"))
        guests_confirmed = ensure_list(ev.get("guests_confirmed"))

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

            # 1) Red carpet como evento separado (solo confirmado + horario)
            if red_confirmed and tz_local and red_start_local and red_duration_minutes:
                rc_local_dt = parse_local_dt(day_date, str(red_start_local), str(tz_local))
                rc_start = rc_local_dt.astimezone(TZ_AR)
                rc_end = (rc_local_dt + timedelta(minutes=int(red_duration_minutes))).astimezone(TZ_AR)

                desc_rc: list[str] = []
                desc_rc.append("Hora Argentina: " + ar_time_window_style(rc_start, rc_end))

                ch = join_channel_streaming(tv, streaming)
                if ch:
                    desc_rc.append("Canal/Streaming: " + ch)

                if top_nominated:
                    desc_rc.append("Más nominaciones: " + "; ".join(top_nominated))

                if special_awards:
                    desc_rc.append("Premios especiales: " + "; ".join(special_awards))

                if guests_confirmed:
                    desc_rc.append("Famosos invitados: " + "; ".join(guests_confirmed))

                if event_url:
                    desc_rc.append("Fuente (evento): " + event_url)
                if nomination_source_url and top_nominated:
                    desc_rc.append("Fuente (nominaciones): " + nomination_source_url)
                if guests_source_urls and guests_confirmed:
                    desc_rc.append("Fuente (invitados): " + "; ".join(guests_source_urls))

                rc_summary = f"{title} — Red Carpet"
                if red_where:
                    rc_summary = f"{title} — Red Carpet ({red_where})"

                lines.extend(
                    build_event_lines(
                        stamp=stamp,
                        summary=rc_summary,
                        location=location,
                        description_lines=desc_rc,
                        dtstart_ba=rc_start,
                        dtend_ba=rc_end,
                        allday_date=None,
                    )
                )

            # 2) Evento principal
            desc_main: list[str] = []

            has_time = bool(start_local and tz_local and duration_minutes)
            if has_time:
                local_dt = parse_local_dt(day_date, str(start_local), str(tz_local))
                ar_start = local_dt.astimezone(TZ_AR)
                ar_end = (local_dt + timedelta(minutes=int(duration_minutes))).astimezone(TZ_AR)
                desc_main.append("Hora Argentina: " + ar_time_window_style(ar_start, ar_end))
            else:
                ar_start = None
                ar_end = None
                desc_main.append("Hora Argentina: por anunciar (sin horario oficial publicado).")

            ch = join_channel_streaming(tv, streaming)
            if ch:
                desc_main.append("Canal/Streaming: " + ch)

            if top_nominated:
                desc_main.append("Más nominaciones: " + "; ".join(top_nominated))

            if special_awards:
                desc_main.append("Premios especiales: " + "; ".join(special_awards))

            if guests_confirmed:
                desc_main.append("Famosos invitados: " + "; ".join(guests_confirmed))

            if event_url:
                desc_main.append("Fuente (evento): " + event_url)
            if nomination_source_url and top_nominated:
                desc_main.append("Fuente (nominaciones): " + nomination_source_url)
            if guests_source_urls and guests_confirmed:
                desc_main.append("Fuente (invitados): " + "; ".join(guests_source_urls))

            if has_time:
                lines.extend(
                    build_event_lines(
                        stamp=stamp,
                        summary=title,
                        location=location,
                        description_lines=desc_main,
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
                        description_lines=desc_main,
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
