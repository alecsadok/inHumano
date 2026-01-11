#!/usr/bin/env python3
"""
Genera docs/calendar.ics a partir de events.yaml

Reglas:
- En la DESCRIPCIÓN: SOLO hora Argentina (GMT-3). No mostrar horarios locales.
- Convertir desde tz_local usando zoneinfo (respeta DST automáticamente).
- Solo listar celebridades/performers/asistentes si están confirmados (lo controlás en events.yaml).
- Para festivales: si hay set_times oficiales, listar "Horarios de shows (hora Argentina)".
- Mantener actualizado docs/last_updated.txt para evitar que GitHub desactive el cron por inactividad.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import uuid

import yaml


TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")


def ics_escape(s: str) -> str:
    """
    Escapado mínimo para ICS:
    - backslash, coma y punto y coma
    - newlines como \n
    """
    return (
        s.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
    )


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def fmt_date(d: datetime.date) -> str:
    return d.strftime("%Y%m%d")


def dtstamp_utc() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def parse_local_dt(date_str: str, time_str: str, tz_name: str) -> datetime:
    """
    date_str: 'YYYY-MM-DD'
    time_str: 'HH:MM'
    tz_name:  IANA tz, ej 'America/New_York'
    """
    tz = ZoneInfo(tz_name)
    # fromisoformat no pone tz, se la seteamos
    local_naive = datetime.fromisoformat(f"{date_str}T{time_str}:00")
    return local_naive.replace(tzinfo=tz)


def ar_time_window(ar_start: datetime, ar_end: datetime) -> str:
    """
    Devuelve SOLO horario Argentina (GMT-3).
    Si cruza medianoche, lo aclara.
    """
    same_day = ar_start.date() == ar_end.date()
    if same_day:
        return f"{ar_start.strftime('%d/%m %H:%M')}–{ar_end.strftime('%H:%M')} (Argentina, GMT-3)"
    return (
        f"{ar_start.strftime('%d/%m %H:%M')}–{ar_end.strftime('%d/%m %H:%M')} "
        f"(Argentina, GMT-3)"
    )


def ensure_list(x) -> list[str]:
    if not x:
        return []
    if isinstance(x, list):
        return [str(i) for i in x]
    return [str(x)]


def add_people_block(desc_lines: list[str], label: str, arr: list[str]) -> None:
    if arr:
        desc_lines.append(f"{label}: " + ", ".join(arr))
    else:
        desc_lines.append(f"{label}: (sin confirmaciones oficiales publicadas)")


def main() -> None:
    root = Path(".")
    yaml_path = root / "events.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError("No existe events.yaml en la raíz del repo.")

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    events = data.get("events", [])
    if not isinstance(events, list):
        raise ValueError("events.yaml: 'events' debe ser una lista.")

    docs = root / "docs"
    docs.mkdir(exist_ok=True)

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//alist-calendar//weekly//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Eventos (confirmados) — Argentina (GMT-3)",
        "X-WR-TIMEZONE:America/Argentina/Buenos_Aires",
        # TTL sugerido: no garantiza nada en Google, pero es estándar
        "X-PUBLISHED-TTL:PT24H",
    ]

    stamp = dtstamp_utc()

    for ev in events:
        title = str(ev.get("title", "")).strip()
        if not title:
            continue

        location = str(ev.get("location", "")).strip()

        # date puede ser 'YYYY-MM-DD' o puede omitirse si usás days[]
        date_str = ev.get("date")
        days = ev.get("days")  # opcional para festivales por día

        # Distinguir: evento con horario (start_local/duration) vs all-day
        start_local = ev.get("start_local")  # 'HH:MM'
        tz_local = ev.get("tz_local")  # 'America/New_York'
        duration_minutes = ev.get("duration_minutes")

        broadcast = ev.get("broadcast", {}) or {}
        tv = ensure_list(broadcast.get("tv"))
        streaming = ensure_list(broadcast.get("streaming"))
        red = broadcast.get("red_carpet", {}) or {}
        red_confirmed = bool(red.get("confirmed", False))
        red_where = str(red.get("where", "")).strip()
        red_time_local = red.get("start_local")  # opcional HH:MM
        red_duration = red.get("duration_minutes")  # opcional

        # Confirmed people
        confirmed_people = ev.get("confirmed_people", {}) or {}
        a_list = ensure_list(confirmed_people.get("a_list"))
        b_list = ensure_list(confirmed_people.get("b_list"))
        argentines = ensure_list(confirmed_people.get("argentines"))

        # Para premiaciones: más nominadas, performers confirmados, premios especiales
        top_nominated = ensure_list(ev.get("top_nominated"))
        confirmed_performers = ensure_list(ev.get("confirmed_performers"))
        special_awards = ensure_list(ev.get("special_awards"))

        # Para festivales: headliners, pop_artists
        headliners = ensure_list(ev.get("headliners"))
        pop_artists = ensure_list(ev.get("pop_artists"))

        notes = ensure_list(ev.get("notes"))

        # Soportar eventos "por día" (p.ej. Lolla día 1, 2, 3)
        # Si viene 'days', generamos un VEVENT por día
        day_entries = []
        if isinstance(days, list) and days:
            for d in days:
                if not isinstance(d, dict):
                    continue
                d_date = str(d.get("date", "")).strip()
                if not d_date:
                    continue
                day_entries.append(d)
        else:
            # un único evento
            day_entries.append({"date": str(date_str).strip() if date_str else ""})

        for day_ev in day_entries:
            day_date = str(day_ev.get("date", "")).strip()
            if not day_date:
                # si no hay fecha, no se puede publicar
                continue

            # Permitir override por día
            day_set_times = day_ev.get("set_times") or ev.get("set_times") or []
            day_headliners = ensure_list(day_ev.get("headliners")) or headliners
            day_pop = ensure_list(day_ev.get("pop_artists")) or pop_artists
            day_notes = ensure_list(day_ev.get("notes")) + notes

            uid = f"{uuid.uuid4()}@alist-calendar"
            lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}"]
            lines.append(f"SUMMARY:{ics_escape(title)}")
            if location:
                lines.append(f"LOCATION:{ics_escape(location)}")

            desc_lines: list[str] = []

            # HORARIO PRINCIPAL del evento (si existe)
            if start_local and tz_local and duration_minutes:
                local_dt = parse_local_dt(day_date, str(start_local), str(tz_local))
                ar_start = local_dt.astimezone(TZ_AR)
                ar_end = (local_dt + timedelta(minutes=int(duration_minutes))).astimezone(TZ_AR)

                # En el VEVENT guardamos horario Argentina
                lines.append(f"DTSTART;TZID=America/Argentina/Buenos_Aires:{fmt_dt(ar_start)}")
                lines.append(f"DTEND;TZID=America/Argentina/Buenos_Aires:{fmt_dt(ar_end)}")

                desc_lines.append("Hora Argentina: " + ar_time_window(ar_start, ar_end))
            else:
                # All-day
                d0 = datetime.fromisoformat(day_date).date()
                lines.append(f"DTSTART;VALUE=DATE:{fmt_date(d0)}")
                lines.append(f"DTEND;VALUE=DATE:{fmt_date(d0 + timedelta(days=1))}")
                desc_lines.append("Hora Argentina: por anunciar (sin horario oficial publicado).")

            # TV / streaming
            if tv:
                desc_lines.append("TV: " + ", ".join(tv))
            if streaming:
                desc_lines.append("Streaming: " + ", ".join(streaming))

            # Red carpet: si está confirmado y hay hora local, convertir y mostrar SOLO Argentina
            if red_confirmed:
                if red_time_local and tz_local and red_duration:
                    red_local_dt = parse_local_dt(day_date, str(red_time_local), str(tz_local))
                    red_ar_start = red_local_dt.astimezone(TZ_AR)
                    red_ar_end = (red_local_dt + timedelta(minutes=int(red_duration))).astimezone(TZ_AR)
                    desc_lines.append(
                        "Red carpet confirmado: "
                        + (red_where + " — " if red_where else "")
                        + "Hora Argentina: "
                        + ar_time_window(red_ar_start, red_ar_end)
                    )
                else:
                    desc_lines.append(
                        "Red carpet confirmado: " + (red_where if red_where else "Sí (detalle por anunciar)")
                    )
            else:
                desc_lines.append("Red carpet: no confirmado oficialmente.")

            # Premios / nominaciones / performers (solo si vos cargás confirmaciones)
            if top_nominated:
                desc_lines.append("Más nominadas/os: " + ", ".join(top_nominated))
            if confirmed_performers:
                desc_lines.append("Performances confirmadas: " + ", ".join(confirmed_performers))
            if special_awards:
                desc_lines.append("Premios especiales confirmados: " + ", ".join(special_awards))

            # Festivales: headliners + pop
            if day_headliners:
                desc_lines.append("Headliners: " + ", ".join(day_headliners))
            if day_pop:
                desc_lines.append("Artistas pop destacados: " + ", ".join(day_pop))

            # Set times (solo si están publicados oficialmente y los cargás en YAML)
            if isinstance(day_set_times, list) and day_set_times:
                if tz_local:
                    desc_lines.append("Horarios de shows (hora Argentina, GMT-3):")
                    for st in day_set_times:
                        if not isinstance(st, dict):
                            continue
                        artist = str(st.get("artist", "")).strip()
                        st_start = str(st.get("start_local", "")).strip()
                        st_end = str(st.get("end_local", "")).strip()
                        stage = str(st.get("stage", "")).strip()
                        if not (artist and st_start and st_end):
                            continue

                        local_tz = ZoneInfo(str(tz_local))
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

            # Celebs confirmadas
            add_people_block(desc_lines, "Celebrities A-list confirmadas", a_list)
            add_people_block(desc_lines, "Celebrities B-list confirmadas", b_list)
            add_people_block(desc_lines, "Argentinos confirmados", argentines)

            # Notas finales
            for n in day_notes:
                if n:
                    desc_lines.append(str(n))

            desc = "\n".join(desc_lines)
            lines.append("DESCRIPTION:" + ics_escape(desc))

            lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    (docs / "calendar.ics").write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")

    # keep-alive para que el cron no se desactive por falta de actividad
    (docs / "last_updated.txt").write_text(datetime.utcnow().isoformat() + "Z\n", encoding="utf-8")

    print("OK: docs/calendar.ics actualizado")


if __name__ == "__main__":
    main()
