from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml
from dateutil import parser as dateparser
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
INPUT_YAML = ROOT / "events.yml"
OUTPUT_DIR = ROOT / "output"
OUTPUT_ICS = OUTPUT_DIR / "events.ics"


def fold_ics_line(line: str) -> str:
    # RFC 5545 folding (simplificado por caracteres)
    if len(line) <= 75:
        return line
    out = []
    while len(line) > 75:
        out.append(line[:75])
        line = " " + line[75:]
    out.append(line)
    return "\r\n".join(out)


def ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s.strip())


def parse_time_hhmm(s: str) -> tuple[int, int]:
    m = re.match(r"^(\d{1,2}):(\d{2})$", s.strip())
    if not m:
        raise ValueError(f"Hora inválida (esperaba HH:MM): {s}")
    return int(m.group(1)), int(m.group(2))


def is_placeholder(event: dict[str, Any]) -> bool:
    title = str(event.get("title", "")).lower()
    if "placeholder" in title:
        return True
    notes = event.get("notes", [])
    if isinstance(notes, list):
        joined = " ".join(str(x) for x in notes).lower()
        if "no usar" in joined:
            return True
    return False


def build_description(e: dict[str, Any]) -> str:
    lines: list[str] = []

    loc = e.get("location")
    if loc:
        lines.append(f"Location: {loc}")

    tz = e.get("tz_local")
    if tz:
        lines.append(f"Timezone: {tz}")

    # Broadcast
    b = e.get("broadcast") or {}
    if isinstance(b, dict):
        tv = b.get("tv") or []
        streaming = b.get("streaming") or []
        if tv:
            lines.append("TV: " + ", ".join(map(str, tv)))
        if streaming:
            lines.append("Streaming: " + ", ".join(map(str, streaming)))

        rc = b.get("red_carpet") or {}
        if isinstance(rc, dict):
            if rc.get("confirmed") is True:
                where = rc.get("where")
                start_local = rc.get("start_local")
                duration = rc.get("duration_minutes")
                extra = []
                if where:
                    extra.append(f"where={where}")
                if start_local:
                    extra.append(f"start={start_local}")
                if duration:
                    extra.append(f"dur={duration}m")
                if extra:
                    lines.append("Red carpet: confirmed (" + ", ".join(extra) + ")")
                else:
                    lines.append("Red carpet: confirmed")
            elif rc.get("confirmed") is False:
                lines.append("Red carpet: not confirmed")

    # People buckets
    cp = e.get("confirmed_people") or {}
    if isinstance(cp, dict):
        a_list = cp.get("a_list") or []
        b_list = cp.get("b_list") or []
        argentines = cp.get("argentines") or []
        if a_list:
            lines.append("A-list: " + ", ".join(map(str, a_list)))
        if b_list:
            lines.append("B-list: " + ", ".join(map(str, b_list)))
        if argentines:
            lines.append("Argentines: " + ", ".join(map(str, argentines)))

    # Headliners / performers
    headliners = e.get("headliners") or []
    if headliners:
        lines.append("Headliners: " + ", ".join(map(str, headliners)))

    performers = e.get("confirmed_performers") or []
    if performers:
        lines.append("Performers: " + ", ".join(map(str, performers)))

    # Notes
    notes = e.get("notes") or []
    if isinstance(notes, list) and notes:
        lines.append("Notes:")
        for n in notes:
            lines.append(f"- {n}")

    return "\n".join(lines).strip()


def vevent_all_day(summary: str, date_: dt.date, uid_seed: str, location: str | None, description: str | None) -> list[str]:
    # All-day event uses DTSTART;VALUE=DATE and DTEND;VALUE=DATE (exclusive)
    dtstart = date_.strftime("%Y%m%d")
    dtend = (date_ + dt.timedelta(days=1)).strftime("%Y%m%d")

    uid = hashlib.sha256(uid_seed.encode("utf-8")).hexdigest()[:24] + "@inhumano"
    lines = [
        "BEGIN:VEVENT",
        fold_ics_line(f"UID:{uid}"),
        fold_ics_line(f"SUMMARY:{ics_escape(summary)}"),
        f"DTSTART;VALUE=DATE:{dtstart}",
        f"DTEND;VALUE=DATE:{dtend}",
    ]
    if location:
        lines.append(fold_ics_line(f"LOCATION:{ics_escape(location)}"))
    if description:
        lines.append(fold_ics_line(f"DESCRIPTION:{ics_escape(description)}"))
    lines.append("END:VEVENT")
    return lines


def vevent_timed(summary: str, start: dt.datetime, end: dt.datetime, tzid: str, uid_seed: str, location: str | None, description: str | None) -> list[str]:
    uid = hashlib.sha256(uid_seed.encode("utf-8")).hexdigest()[:24] + "@inhumano"

    # Formato local con TZID (sin convertir a UTC)
    fmt = "%Y%m%dT%H%M%S"
    dtstart = start.strftime(fmt)
    dtend = end.strftime(fmt)

    lines = [
        "BEGIN:VEVENT",
        fold_ics_line(f"UID:{uid}"),
        fold_ics_line(f"SUMMARY:{ics_escape(summary)}"),
        f"DTSTART;TZID={tzid}:{dtstart}",
        f"DTEND;TZID={tzid}:{dtend}",
    ]
    if location:
        lines.append(fold_ics_line(f"LOCATION:{ics_escape(location)}"))
    if description:
        lines.append(fold_ics_line(f"DESCRIPTION:{ics_escape(description)}"))
    lines.append("END:VEVENT")
    return lines


def main() -> None:
    data = yaml.safe_load(INPUT_YAML.read_text(encoding="utf-8"))
    events = data.get("events", [])

    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    cal_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "PRODID:-//inHumano eventos//EN",
        f"DTSTAMP:{now_utc}",
    ]

    for e in events:
        if not isinstance(e, dict):
            continue
        if is_placeholder(e):
            continue

        title = str(e.get("title", "Evento")).strip()
        location = e.get("location")
        description = build_description(e) or None

        # Si trae days:, creamos eventos por día (all-day)
        days = e.get("days")
        if isinstance(days, list) and days:
            # All-day por cada día
            for idx, d in enumerate(days, start=1):
                if not isinstance(d, dict) or "date" not in d:
                    continue
                day_date = parse_date(str(d["date"]))
                day_notes = d.get("notes") or []
                day_desc = description
                if isinstance(day_notes, list) and day_notes:
                    extra = "\n".join(f"- {n}" for n in day_notes)
                    day_desc = (description + "\n\nDay notes:\n" + extra) if description else ("Day notes:\n" + extra)

                summary = f"{title} — Día {idx}"
                uid_seed = f"{title}|day|{day_date.isoformat()}|{location or ''}"
                cal_lines.extend(vevent_all_day(summary, day_date, uid_seed, location, day_desc))
            continue

        # Si NO trae days:
        date_str = e.get("date")
        if not date_str:
            continue
        date_ = parse_date(str(date_str))

        tzid = str(e.get("tz_local") or "UTC")
        start_local = e.get("start_local")
        duration = e.get("duration_minutes")

        if start_local:
            hh, mm = parse_time_hhmm(str(start_local))
            tz = ZoneInfo(tzid)
            start_dt = dt.datetime(date_.year, date_.month, date_.day, hh, mm, 0, tzinfo=tz)

            dur_min = int(duration) if duration is not None else 180
            end_dt = start_dt + dt.timedelta(minutes=dur_min)

            uid_seed = f"{title}|timed|{start_dt.isoformat()}|{location or ''}"
            cal_lines.extend(vevent_timed(title, start_dt, end_dt, tzid, uid_seed, location, description))
        else:
            # All-day si no hay hora
            uid_seed = f"{title}|allday|{date_.isoformat()}|{location or ''}"
            cal_lines.extend(vevent_all_day(title, date_, uid_seed, location, description))

    cal_lines.append("END:VCALENDAR")
    ics = "\r\n".join(cal_lines) + "\r\n"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_ICS.write_text(ics, encoding="utf-8")

    print(f"[OK] wrote {OUTPUT_ICS}")


if __name__ == "__main__":
    main()
