# -*- coding: utf-8 -*-
"""Google Calendar (iCal) parsing for the Usagi widget. Standard library only."""
import re
from datetime import datetime, timedelta, timezone

DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]  # index == datetime.weekday()

# Fixed offsets for common zones (Windows Python has no tz database by default)
FIXED = {
    "Asia/Seoul": 9, "Asia/Tokyo": 9, "Asia/Shanghai": 8, "Asia/Hong_Kong": 8,
    "Asia/Taipei": 8, "Asia/Singapore": 8, "UTC": 0, "Etc/UTC": 0, "GMT": 0, "Etc/GMT": 0,
}


def local_tz():
    return datetime.now().astimezone().tzinfo


def _tz(name):
    if name in FIXED:
        return timezone(timedelta(hours=FIXED[name]))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return None


def _to_local(aware):
    return aware.astimezone(local_tz()).replace(tzinfo=None)


def parse_date(params, val):
    """-> (local naive datetime, all_day, original naive datetime in its own zone)"""
    val = val.strip()
    if re.fullmatch(r"\d{8}", val):
        d = datetime.strptime(val, "%Y%m%d")
        return d, True, d
    utc = val[-1:] in ("Z", "z")
    d = datetime.strptime(val.rstrip("Zz")[:15], "%Y%m%dT%H%M%S")
    if utc:
        return _to_local(d.replace(tzinfo=timezone.utc)), False, d
    m = re.search(r'TZID="?([^;:"]+)', params or "", re.I)
    if m:
        tz = _tz(m.group(1).strip())
        if tz is not None:
            try:
                return _to_local(d.replace(tzinfo=tz)), False, d
            except Exception:
                pass
    return d, False, d


def _key(d):
    return d.strftime("%Y%m%d")


def _colon(line):
    q = False
    for i, ch in enumerate(line):
        if ch == '"':
            q = not q
        elif ch == ":" and not q:
            return i
    return -1


def _unescape(s):
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            i += 1
            out.append(" " if s[i] in "nN" else s[i])
        else:
            out.append(ch)
        i += 1
    return "".join(out).strip()


def parse_ics(text):
    events = []
    if not text:
        return events
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]", "", text)
    cur = None
    for line in text.split("\n"):
        if line == "BEGIN:VEVENT":
            cur = dict(uid=None, summary="", status="", start=None, end=None, allday=False,
                       rrule=None, exdates=set(), recid=None, rulestart=None, shift=0)
            continue
        if line == "END:VEVENT":
            if cur and cur["start"] is not None:
                events.append(cur)
            cur = None
            continue
        if cur is None:
            continue
        c = _colon(line)
        if c < 0:
            continue
        left, val = line[:c], line[c + 1:]
        name, _, params = left.partition(";")
        name = name.upper()
        try:
            if name == "UID":
                cur["uid"] = val.strip()
            elif name == "SUMMARY":
                cur["summary"] = _unescape(val)
            elif name == "STATUS":
                cur["status"] = val.strip().upper()
            elif name == "DTSTART":
                cur["start"], cur["allday"], orig = parse_date(params, val)
                cur["rulestart"] = orig
                cur["shift"] = (cur["start"].date() - orig.date()).days
            elif name == "DTEND":
                cur["end"] = parse_date(params, val)[0]
            elif name == "RRULE":
                rule = {}
                for part in val.split(";"):
                    k, eq, v = part.partition("=")
                    if eq:
                        rule[k.strip().upper()] = v.strip().upper()
                cur["rrule"] = rule
            elif name == "EXDATE":
                for p in val.split(","):
                    if p.strip():
                        cur["exdates"].add(_key(parse_date(params, p)[0]))
            elif name == "RECURRENCE-ID":
                cur["recid"] = _key(parse_date(params, val)[0])
        except Exception:
            pass
    return events


# ---------------------------------------------------------------- recurrence
def _day_code(tok):
    tok = tok.strip()
    return DAYS.index(tok[-2:]) if len(tok) >= 2 and tok[-2:] in DAYS else -1


def _day_in(byday, d):
    return any(_day_code(t) == d.weekday() for t in byday.split(","))


def _days_in_month(d):
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (nxt - timedelta(days=1)).day


def _nth_day_in(byday, d):
    dim = _days_in_month(d)
    for t in byday.split(","):
        t = t.strip()
        if _day_code(t) != d.weekday():
            continue
        num = t[:-2].replace("+", "")
        if not num:
            return True
        try:
            n = int(num)
        except ValueError:
            continue
        if n > 0 and (d.day - 1) // 7 + 1 == n:
            return True
        if n < 0 and (dim - d.day) // 7 + 1 == -n:
            return True
    return False


def _month_day_in(bymd, d):
    dim = _days_in_month(d)
    for t in bymd.split(","):
        try:
            n = int(t.strip())
        except ValueError:
            continue
        if (n > 0 and d.day == n) or (n < 0 and d.day == dim + n + 1):
            return True
    return False


def _list_has(lst, v):
    for t in lst.split(","):
        try:
            if int(t.strip()) == v:
                return True
        except ValueError:
            pass
    return False


def _matches(ev, day):
    """Does the RRULE pattern (ignoring COUNT/UNTIL/EXDATE) hit this local date?"""
    d = day - timedelta(days=ev["shift"])
    s = ev["rulestart"].date()
    if d < s:
        return False
    r = ev["rrule"]
    freq = r.get("FREQ", "")
    try:
        interval = max(1, int(r.get("INTERVAL", "1")))
    except ValueError:
        interval = 1
    byday, bymd, bymonth = r.get("BYDAY"), r.get("BYMONTHDAY"), r.get("BYMONTH")
    if bymonth and not _list_has(bymonth, d.month):
        return False
    if freq == "DAILY":
        return ((d - s).days % interval == 0
                and (not byday or _day_in(byday, d))
                and (not bymd or _month_day_in(bymd, d)))
    if freq == "WEEKLY":
        wk = _day_code(r.get("WKST", "MO"))
        wk = 0 if wk < 0 else wk
        ws = s - timedelta(days=(s.weekday() - wk) % 7)
        wd = d - timedelta(days=(d.weekday() - wk) % 7)
        if ((wd - ws).days // 7) % interval:
            return False
        return _day_in(byday, d) if byday else d.weekday() == s.weekday()
    if freq == "MONTHLY":
        if ((d.year - s.year) * 12 + d.month - s.month) % interval:
            return False
        if bymd:
            return _month_day_in(bymd, d)
        if byday:
            return _nth_day_in(byday, d)
        return d.day == s.day
    if freq == "YEARLY":
        if (d.year - s.year) % interval:
            return False
        if not bymonth and d.month != s.month:
            return False
        if bymd:
            return _month_day_in(bymd, d)
        if byday:
            return _nth_day_in(byday, d)
        return d.day == s.day
    return False


def diagnose(text, now_local):
    """Summary of a raw feed for troubleshooting. Never includes event titles."""
    out = []
    text = (text or "").replace("\r\n", "\n")
    text = re.sub(r"\n[ \t]", "", text)
    out.append("  bytes=%d  VCALENDAR=%s  events=%d  X-WR-TIMEZONE=%s" % (
        len(text), "BEGIN:VCALENDAR" in text, text.count("BEGIN:VEVENT"),
        (re.search(r"^X-WR-TIMEZONE:(.*)$", text, re.M) or [None, "-"])[1].strip()))
    recent = []
    for block in re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, re.S):
        def field(name):
            m = re.search(r"^%s[;:](.*)$" % name, block, re.M)
            return m.group(1).strip() if m else ""
        stamps = [re.sub(r"[^0-9T]", "", field(n))[:15] for n in ("CREATED", "LAST-MODIFIED")]
        stamps = [s for s in stamps if len(s) == 15]
        if not stamps:
            continue
        newest = max(stamps)
        try:
            when = datetime.strptime(newest, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).astimezone(local_tz()).replace(tzinfo=None)
        except ValueError:
            continue
        if (now_local - when).days <= 3:
            def raw(name):
                m = re.search(r"^%s([;:].*)$" % name, block, re.M)
                return m.group(1).strip() if m else ":-"
            recent.append((when, "DTSTART%s | DTEND%s | RRULE=%s | STATUS=%s | RECURRENCE-ID=%s" % (
                raw("DTSTART"), raw("DTEND"), "yes" if field("RRULE") else "no",
                field("STATUS") or "-", "yes" if field("RECURRENCE-ID") else "no")))
    recent.sort(reverse=True)
    out.append("  최근 3일 안에 만들거나 고친 일정: %d개" % len(recent))
    for when, desc in recent[:15]:
        out.append("    [%s 수정] %s" % (when.strftime("%m-%d %H:%M"), desc))
    return out


def on_day(events, day):
    """Events occurring on `day` (a date). -> list of dict(summary, start, allday), sorted."""
    key = _key(day)
    overrides = {(e["uid"], e["recid"]) for e in events if e["recid"] and e["uid"]}
    day_start = datetime(day.year, day.month, day.day)
    day_end = day_start + timedelta(days=1)
    res = []
    for e in events:
        if e["status"] == "CANCELLED":
            continue
        if not e["rrule"] or e["recid"]:
            st = e["start"]
            end = e["end"] or (st + timedelta(days=1) if e["allday"] else st)
            hit = (st.date() == day) if end <= st else (st < day_end and end > day_start)
            if hit:
                res.append(dict(summary=e["summary"], start=st, allday=e["allday"] or st < day_start))
            continue
        if key in e["exdates"] or (e["uid"], key) in overrides:
            continue
        until = e["rrule"].get("UNTIL")
        if until:
            try:
                if day > parse_date("", until)[0].date():
                    continue
            except Exception:
                pass
        if not _matches(e, day):
            continue
        count = e["rrule"].get("COUNT")
        if count and count.isdigit():
            n, d, over = 0, e["start"].date(), False
            while d < day:
                if _matches(e, d):
                    n += 1
                    if n >= int(count):
                        over = True
                        break
                d += timedelta(days=1)
            if over:
                continue
        start = datetime.combine(day, e["start"].time())
        res.append(dict(summary=e["summary"], start=start, allday=e["allday"]))
    res.sort(key=lambda o: (not o["allday"], o["start"]))
    return res
