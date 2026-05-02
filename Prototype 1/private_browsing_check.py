"""
Private browsing detection via artefact-pattern analysis.

Private mode cannot be confirmed directly — there is no explicit "private_mode"
flag written to disk.  This module infers it probabilistically by combining
three classes of indicators:

  1. Schema-level absence
        e.g. downloads exist but the URL/history table is empty
  2. Cross-table inconsistency
        e.g. URL rows present but no visit timestamps
  3. Temporal gap correlation  ← the strongest single signal
        bookmarks or downloads with timestamps that fall inside quiet windows
        in the visit timeline.  Bookmarks and downloaded files survive private
        mode while history does not, so an artefact landing in a multi-hour
        gap of zero browsing activity is a strong indicator of a private
        session having occurred during that window.

Returned indicators are evidence of *likely* private usage, not proof.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone


# ── Tunables ─────────────────────────────────────────────────────────────────

# Minimum gap between consecutive visits to consider it a "quiet window".
# 30 min is short enough to catch typical private sessions but long enough that
# a corroborating bookmark/download in the gap is forensically meaningful.
GAP_THRESHOLD_MINUTES = 30
GAP_THRESHOLD_SECONDS = GAP_THRESHOLD_MINUTES * 60

CHROMIUM_BROWSERS = ("Chrome", "Edge", "Brave", "Opera", "Vivaldi", "Chromium")


# ── Public API ───────────────────────────────────────────────────────────────

def check_private_browsing_indicators(db_path, browser):
    """
    Analyse a browser SQLite database for artefact patterns consistent with
    private/incognito browsing.

    Returns:
        (flagged: bool, indicators: list[str])
    """
    indicators = []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception:
        return False, []

    try:
        cur = conn.cursor()
        if browser in CHROMIUM_BROWSERS:
            _check_chromium(cur, indicators)
            _check_chromium_temporal_gaps(db_path, cur, indicators)
        elif browser == "Firefox":
            _check_firefox(cur, indicators)
            _check_firefox_temporal_gaps(cur, indicators)
    except Exception:
        pass
    finally:
        conn.close()

    return len(indicators) > 0, indicators


# ── Helpers ──────────────────────────────────────────────────────────────────

def _count(cur, query):
    """Run a COUNT query and return the integer, or None on error."""
    try:
        cur.execute(query)
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception:
        return None


def _chromium_to_dt(microseconds):
    """Chromium timestamps are microseconds since 1601-01-01 UTC."""
    if not microseconds:
        return None
    try:
        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        return epoch + timedelta(microseconds=int(microseconds))
    except Exception:
        return None


def _firefox_to_dt(microseconds):
    """Firefox timestamps are microseconds since the UNIX epoch."""
    if not microseconds:
        return None
    try:
        return datetime.fromtimestamp(int(microseconds) / 1_000_000, tz=timezone.utc)
    except Exception:
        return None


def _fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "?"


def format_duration(td):
    """Format a timedelta as 'Xh Ym' (or just 'Ym' under an hour)."""
    total_minutes = max(0, int(td.total_seconds() / 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _find_gaps(sorted_timestamps, threshold_seconds=GAP_THRESHOLD_SECONDS):
    """
    Given a chronologically sorted list of datetime objects, return all
    (gap_start, gap_end) pairs where consecutive timestamps differ by more
    than threshold_seconds.
    """
    gaps = []
    for i in range(len(sorted_timestamps) - 1):
        delta = (sorted_timestamps[i + 1] - sorted_timestamps[i]).total_seconds()
        if delta > threshold_seconds:
            gaps.append((sorted_timestamps[i], sorted_timestamps[i + 1]))
    return gaps


# ── Schema-level checks (pre-existing) ───────────────────────────────────────

def _check_chromium(cur, indicators):
    """
    Chromium-based browsers (Chrome, Edge, Brave, Opera, Vivaldi) all use the
    same History DB schema.  Key tables:
      urls      — every page visited (suppressed in private mode)
      visits    — per-visit timestamps        (suppressed in private mode)
      downloads — downloaded files            (persists through private mode)
      keyword_search_terms — omnibar searches (suppressed in private mode)
    """
    url_count      = _count(cur, "SELECT COUNT(*) FROM urls")
    visit_count    = _count(cur, "SELECT COUNT(*) FROM visits")
    download_count = _count(cur, "SELECT COUNT(*) FROM downloads")
    search_count   = _count(cur, "SELECT COUNT(*) FROM keyword_search_terms")

    if download_count is not None and url_count is not None:
        if download_count > 0 and url_count == 0:
            indicators.append(
                f"Downloads recorded ({download_count}) but browsing history is completely "
                f"empty — downloaded files persist through private mode while history does not"
            )
        elif download_count > 0 and url_count < download_count:
            indicators.append(
                f"Download records ({download_count}) outnumber history entries ({url_count}) "
                f"— an unusual ratio for a normal browsing session"
            )

    if url_count and visit_count == 0:
        indicators.append(
            f"URL records found ({url_count}) but no visit timestamps exist — "
            f"timestamps are suppressed in private mode"
        )

    if search_count == 0 and download_count:
        indicators.append(
            "No keyword search terms recorded alongside download activity — "
            "search history is suppressed in private mode"
        )


def _check_firefox(cur, indicators):
    """
    Firefox uses places.sqlite.  Key tables:
      moz_places        — URL records + visit counts
      moz_historyvisits — individual visit timestamps (suppressed in private mode)
      moz_bookmarks     — bookmarks                  (persists through private mode)
    """
    visited_count = _count(cur, "SELECT COUNT(*) FROM moz_places WHERE visit_count > 0")
    total_places  = _count(cur, "SELECT COUNT(*) FROM moz_places")
    hist_visits   = _count(cur, "SELECT COUNT(*) FROM moz_historyvisits")
    bookmarks     = _count(
        cur,
        "SELECT COUNT(*) FROM moz_bookmarks WHERE type=1 AND fk IS NOT NULL"
    )

    if bookmarks is not None and visited_count is not None:
        if bookmarks > 0 and visited_count == 0:
            indicators.append(
                f"Bookmarks found ({bookmarks}) but no visited pages recorded — "
                f"bookmarks persist through private mode while visit history does not"
            )

    if hist_visits == 0 and total_places:
        indicators.append(
            f"Place entries recorded ({total_places}) but visit history table is empty — "
            f"consistent with private browsing suppressing moz_historyvisits"
        )

    if visited_count == 0 and hist_visits == 0 and total_places == 0:
        indicators.append(
            "No browsing history, visit timestamps, or place entries found in this profile"
        )


# ── Temporal gap analysis ────────────────────────────────────────────────────

def _check_chromium_temporal_gaps(db_path, cur, indicators):
    """
    Pull every visit timestamp from the History DB, find quiet windows between
    consecutive visits, then check whether any download or bookmark timestamp
    falls inside those windows.  An artefact appearing in a quiet window is a
    strong indicator that private browsing happened during that window.
    """
    visit_times = _collect_chromium_visits(cur)
    if len(visit_times) < 2:
        return  # not enough timeline data to find gaps

    gaps = _find_gaps(visit_times)
    if not gaps:
        return

    download_times = _collect_chromium_downloads(cur)
    bookmark_times = _read_chromium_bookmark_times(db_path)
    if not download_times and not bookmark_times:
        return  # no corroborating artefacts to fall in the gaps

    flagged = []
    for gap_start, gap_end in gaps:
        bms_in = [t for t in bookmark_times if gap_start < t < gap_end]
        dls_in = [t for t in download_times if gap_start < t < gap_end]
        if bms_in or dls_in:
            all_times = bms_in + dls_in
            flagged.append((gap_start, gap_end,
                            min(all_times), max(all_times),
                            len(bms_in), len(dls_in)))

    # Surface the gaps with the most artefacts first
    flagged.sort(key=lambda g: g[4] + g[5], reverse=True)
    for gap_start, gap_end, active_start, active_end, n_bms, n_dls in flagged:
        gap_dur = format_duration(gap_end - gap_start)
        parts = []
        if n_dls:
            parts.append(f"{n_dls} download(s)")
        if n_bms:
            parts.append(f"{n_bms} bookmark(s)")
        what = " and ".join(parts)

        if active_start == active_end:
            active_info = f"single artefact at {_fmt_dt(active_start)}"
        else:
            active_dur = format_duration(active_end - active_start)
            active_info = (f"{active_dur} of confirmed private activity "
                           f"({_fmt_dt(active_start)} → {_fmt_dt(active_end)})")

        indicators.append(
            f"Quiet window {_fmt_dt(gap_start)} → {_fmt_dt(gap_end)} "
            f"(gap {gap_dur}; {active_info}) contains {what} — "
            f"likely private browsing session"
        )


def _check_firefox_temporal_gaps(cur, indicators):
    """
    Same approach for Firefox: gaps in moz_historyvisits cross-checked against
    moz_bookmarks dateAdded.  (Firefox download metadata lives in a separate
    DB so we only correlate bookmarks here.)
    """
    visit_times = []
    try:
        cur.execute(
            "SELECT visit_date FROM moz_historyvisits "
            "WHERE visit_date > 0 ORDER BY visit_date"
        )
        for (vt,) in cur.fetchall():
            dt = _firefox_to_dt(vt)
            if dt:
                visit_times.append(dt)
    except Exception:
        return

    if len(visit_times) < 2:
        return

    gaps = _find_gaps(visit_times)
    if not gaps:
        return

    bookmark_times = []
    try:
        cur.execute("""
            SELECT dateAdded FROM moz_bookmarks
             WHERE type = 1 AND fk IS NOT NULL AND dateAdded > 0
             ORDER BY dateAdded
        """)
        for (dt_us,) in cur.fetchall():
            dt = _firefox_to_dt(dt_us)
            if dt:
                bookmark_times.append(dt)
    except Exception:
        pass

    if not bookmark_times:
        return

    flagged = []
    for gap_start, gap_end in gaps:
        bms_in = [t for t in bookmark_times if gap_start < t < gap_end]
        if bms_in:
            flagged.append((gap_start, gap_end,
                            min(bms_in), max(bms_in), len(bms_in)))

    flagged.sort(key=lambda g: g[4], reverse=True)
    for gap_start, gap_end, active_start, active_end, n_bms in flagged:
        gap_dur = format_duration(gap_end - gap_start)
        if active_start == active_end:
            active_info = f"single bookmark at {_fmt_dt(active_start)}"
        else:
            active_dur = format_duration(active_end - active_start)
            active_info = (f"{active_dur} of confirmed private activity "
                           f"({_fmt_dt(active_start)} → {_fmt_dt(active_end)})")
        indicators.append(
            f"Quiet window {_fmt_dt(gap_start)} → {_fmt_dt(gap_end)} "
            f"(gap {gap_dur}; {active_info}) contains {n_bms} bookmark(s) — "
            f"likely private browsing session"
        )


# ── Timestamp collectors ─────────────────────────────────────────────────────

def _collect_chromium_visits(cur):
    """Return a chronologically sorted list of visit datetimes."""
    times = []
    try:
        cur.execute("SELECT visit_time FROM visits ORDER BY visit_time")
        for (vt,) in cur.fetchall():
            dt = _chromium_to_dt(vt)
            if dt:
                times.append(dt)
    except Exception:
        # If the visits table is missing, fall back to urls.last_visit_time
        try:
            cur.execute(
                "SELECT last_visit_time FROM urls "
                "WHERE last_visit_time > 0 ORDER BY last_visit_time"
            )
            for (vt,) in cur.fetchall():
                dt = _chromium_to_dt(vt)
                if dt:
                    times.append(dt)
        except Exception:
            return []
    return times


def _collect_chromium_downloads(cur):
    """Return a chronologically sorted list of download start datetimes."""
    times = []
    try:
        cur.execute(
            "SELECT start_time FROM downloads "
            "WHERE start_time > 0 ORDER BY start_time"
        )
        for (st,) in cur.fetchall():
            dt = _chromium_to_dt(st)
            if dt:
                times.append(dt)
    except Exception:
        pass
    return times


def _read_chromium_bookmark_times(history_db_path):
    """
    Walk the Chromium Bookmarks JSON file (sibling to History) and return
    a list of bookmark date_added datetimes.
    """
    times = []
    bookmarks_dir = os.path.dirname(history_db_path)
    for name in ("Bookmarks", "bookmarks"):
        path = os.path.join(bookmarks_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return times

        def walk(node):
            if not isinstance(node, dict):
                return
            if node.get("type") == "url":
                dt = _chromium_to_dt(node.get("date_added"))
                if dt:
                    times.append(dt)
            for child in node.get("children") or []:
                walk(child)

        for root_node in (data.get("roots") or {}).values():
            walk(root_node)
        break

    return times


# ── Structured artefact data (for the Flagged Artefacts viewer) ──────────────

def get_flagged_artefacts(db_path, browser):
    """
    Return structured details of every artefact (download / bookmark) that
    falls inside a quiet window in the visit timeline.

    Returns a list of gap dicts:
      [
          {
              'start':     datetime,
              'end':       datetime,
              'downloads': [{'url', 'file', 'size', 'time'}, ...],
              'bookmarks': [{'title', 'url', 'time'}, ...],
          },
          ...
      ]
    Returns [] if nothing is flagged or the database can't be read.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception:
        return []

    try:
        cur = conn.cursor()
        if browser in CHROMIUM_BROWSERS:
            return _flagged_chromium(db_path, cur)
        elif browser == "Firefox":
            return _flagged_firefox(cur)
    except Exception:
        return []
    finally:
        conn.close()
    return []


def _flagged_chromium(db_path, cur):
    visit_times = _collect_chromium_visits(cur)
    if len(visit_times) < 2:
        return []
    gaps = _find_gaps(visit_times)
    if not gaps:
        return []

    downloads = _collect_chromium_downloads_full(cur)
    bookmarks = _read_chromium_bookmarks_full(db_path)
    if not downloads and not bookmarks:
        return []

    out = []
    for gap_start, gap_end in gaps:
        dls_in = [d for d in downloads if gap_start < d['time'] < gap_end]
        bms_in = [b for b in bookmarks if gap_start < b['time'] < gap_end]
        if dls_in or bms_in:
            out.append({
                'start': gap_start,
                'end': gap_end,
                'downloads': dls_in,
                'bookmarks': bms_in,
            })
    return out


def _flagged_firefox(cur):
    visit_times = []
    try:
        cur.execute(
            "SELECT visit_date FROM moz_historyvisits "
            "WHERE visit_date > 0 ORDER BY visit_date"
        )
        for (vt,) in cur.fetchall():
            dt = _firefox_to_dt(vt)
            if dt:
                visit_times.append(dt)
    except Exception:
        return []
    if len(visit_times) < 2:
        return []
    gaps = _find_gaps(visit_times)
    if not gaps:
        return []

    bookmarks = []
    try:
        cur.execute("""
            SELECT b.title, p.url, b.dateAdded
              FROM moz_bookmarks b
         LEFT JOIN moz_places p ON b.fk = p.id
             WHERE b.type = 1 AND p.url IS NOT NULL AND b.dateAdded > 0
             ORDER BY b.dateAdded
        """)
        for title, url, date_added in cur.fetchall():
            dt = _firefox_to_dt(date_added)
            if dt:
                bookmarks.append({
                    'title': title or "",
                    'url':   url,
                    'time':  dt,
                })
    except Exception:
        pass

    if not bookmarks:
        return []

    out = []
    for gap_start, gap_end in gaps:
        bms_in = [b for b in bookmarks if gap_start < b['time'] < gap_end]
        if bms_in:
            out.append({
                'start':     gap_start,
                'end':       gap_end,
                'downloads': [],   # Firefox download metadata lives elsewhere
                'bookmarks': bms_in,
            })
    return out


def _collect_chromium_downloads_full(cur):
    """Return a list of {url, file, size, time} dicts for every download."""
    out = []
    try:
        cur.execute("""
            SELECT d.target_path, c.url, d.received_bytes, d.start_time
              FROM downloads d
         LEFT JOIN downloads_url_chains c
                ON d.id = c.id AND c.chain_index = 0
             WHERE d.start_time > 0
             ORDER BY d.start_time
        """)
        for target, url, size, start in cur.fetchall():
            dt = _chromium_to_dt(start)
            if not dt:
                continue
            target = target or ""
            filename = os.path.basename(target) or target
            out.append({
                'url':  url or "",
                'file': filename,
                'size': size or 0,
                'time': dt,
            })
    except Exception:
        pass
    return out


def _read_chromium_bookmarks_full(history_db_path):
    """Return a list of {title, url, time} dicts for every bookmark."""
    out = []
    bookmarks_dir = os.path.dirname(history_db_path)
    for name in ("Bookmarks", "bookmarks"):
        path = os.path.join(bookmarks_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return out

        def walk(node):
            if not isinstance(node, dict):
                return
            if node.get("type") == "url":
                dt = _chromium_to_dt(node.get("date_added"))
                if dt:
                    out.append({
                        'title': node.get("name", ""),
                        'url':   node.get("url", ""),
                        'time':  dt,
                    })
            for child in node.get("children") or []:
                walk(child)

        for root_node in (data.get("roots") or {}).values():
            walk(root_node)
        break

    return out
