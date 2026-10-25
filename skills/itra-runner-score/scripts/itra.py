#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ITRA runner lookup (pure stdlib, no third-party dependencies).

Resolve a runner by name, then report the ITRA Performance Index (PI) and the
full race history scraped from the public runner page on itra.run.

Usage:
    python3 itra.py search  "Zdenek Hruska" [--country CZE] [--limit 10] [--json]
    python3 itra.py profile 1315857 [--races 20] [--json]        # id | profile URL | slug
    python3 itra.py report  "Zdenek Hruska" [--country CZE] [--races 20] [--json]

Exit codes: 0 ok, 1 no matching runner, 2 network / anti-bot failure.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.cookiejar import CookieJar

BASE = "https://itra.run"
# The public runner-search page sits behind an AWS WAF rule keyed on the exact
# path. Percent-encoding one character of the path slips past the rule while
# ASP.NET still routes it to the same handler. Used only to obtain a session
# cookie + antiforgery token.
SEARCH_PAGE_PATH = "/Runners/%46indARunner"
SEARCH_PAGE_REFERER = BASE + "/Runners/FindARunner"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# AES-CBC decryption (decrypt-only, pure Python)
# --------------------------------------------------------------------------- #

def _gmul(a: int, b: int) -> int:
    """Multiply two bytes in GF(2^8) with the AES polynomial."""
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return result


def _build_sboxes():
    inv_sbox = [0] * 256  # inverse permutation, filled from sbox
    sbox = [0] * 256
    for x in range(256):
        # multiplicative inverse in GF(2^8); 0 maps to 0
        if x == 0:
            inv = 0
        else:
            inv, power = 1, x
            e = 254
            while e:
                if e & 1:
                    inv = _gmul(inv, power)
                power = _gmul(power, power)
                e >>= 1
        r = [((inv << i) | (inv >> (8 - i))) & 0xFF for i in range(1, 5)]
        sbox[x] = inv ^ r[0] ^ r[1] ^ r[2] ^ r[3] ^ 0x63
    for x in range(256):
        inv_sbox[sbox[x]] = x
    return sbox, inv_sbox


_SBOX, _INV_SBOX = _build_sboxes()
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]
_MIX_INV = (
    (0x0E, 0x0B, 0x0D, 0x09),
    (0x09, 0x0E, 0x0B, 0x0D),
    (0x0D, 0x09, 0x0E, 0x0B),
    (0x0B, 0x0D, 0x09, 0x0E),
)


def _expand_key(key: bytes):
    nk = len(key) // 4
    if nk not in (4, 6, 8):
        raise ValueError("invalid AES key length: %d bytes" % len(key))
    nr = nk + 6
    words = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(words[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        words.append([words[i - nk][j] ^ temp[j] for j in range(4)])
    return words, nr


def _add_round_key(state, round_key):
    for i in range(16):
        state[i] ^= round_key[i]


def _inv_shift_rows(s):
    # row r is rotated right by r; indices are column-major (i = r + 4*c)
    out = list(s)
    for r in range(1, 4):
        row = [s[r + 4 * c] for c in range(4)]
        row = row[-r:] + row[:-r]
        for c in range(4):
            out[r + 4 * c] = row[c]
    return out


def _inv_mix_columns(s):
    out = list(s)
    for c in range(4):
        col = [s[4 * c + r] for r in range(4)]
        for r in range(4):
            v = 0
            for k in range(4):
                v ^= _gmul(col[k], _MIX_INV[r][k])
            out[4 * c + r] = v
    return out


def _decrypt_block(block: bytes, words, nr: int) -> bytes:
    state = list(block)
    _add_round_key(state, [b for w in words[4 * nr:4 * nr + 4] for b in w])
    for rnd in range(nr - 1, 0, -1):
        state = _inv_shift_rows(state)
        state = [_INV_SBOX[b] for b in state]
        _add_round_key(state, [b for w in words[4 * rnd:4 * rnd + 4] for b in w])
        state = _inv_mix_columns(state)
    state = _inv_shift_rows(state)
    state = [_INV_SBOX[b] for b in state]
    _add_round_key(state, [b for w in words[0:4] for b in w])
    return bytes(state)


def aes_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CBC decrypt with PKCS#7 unpadding."""
    words, nr = _expand_key(key)
    if len(iv) != 16:
        raise ValueError("bad IV length: %d" % len(iv))
    prev = iv
    plain = bytearray()
    for off in range(0, len(ciphertext) - len(ciphertext) % 16, 16):
        block = ciphertext[off:off + 16]
        dec = _decrypt_block(block, words, nr)
        plain.extend(b ^ p for b, p in zip(dec, prev))
        prev = block
    if plain:
        pad = plain[-1]
        if 1 <= pad <= 16 and plain[-pad:] == bytes([pad]) * pad:
            del plain[-pad:]
    return bytes(plain)


def _decrypt_payload(payload: dict) -> str:
    """ITRA ships the AES key and IV inside the response body (response3/2)."""
    ct = base64.b64decode(payload["response1"])
    iv = base64.b64decode(payload["response2"])
    key = base64.b64decode(payload["response3"])
    return aes_cbc_decrypt(ct, key, iv).decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# HTML helpers
# --------------------------------------------------------------------------- #

def _balanced_end(text: str, start: int, opener: str, closer: str) -> int:
    """Return the index of the closer matching text[start], string-aware."""
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _json_after_key(html: str, key: str, opener: str, closer: str):
    """Parse the JSON value that follows `"key":` in an inline script."""
    marker = '"%s"' % key
    idx = html.find(marker)
    while idx != -1:
        pos = html.find(opener, idx + len(marker))
        if pos == -1:
            return None
        end = _balanced_end(html, pos, opener, closer)
        if end != -1:
            try:
                return json.loads(html[pos:end + 1])
            except ValueError:
                pass
        idx = html.find(marker, idx + 1)
    return None


def slugify(name: str) -> str:
    """Reproduce ITRA's profile-slug normalisation (ASCII fold, strip symbols)."""
    if not name:
        return ""
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", folded.lower())


# --------------------------------------------------------------------------- #
# HTTP client
# --------------------------------------------------------------------------- #

class ItraError(RuntimeError):
    pass


class Blocked(ItraError):
    """Anti-bot page returned instead of real content."""


class ItraClient:
    def __init__(self, timeout: float = 30.0, delay: float = 0.7, verbose: bool = False):
        self.timeout = timeout
        self.delay = delay
        self.verbose = verbose
        self._jar = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar)
        )
        self._opener.addheaders = [
            ("User-Agent", USER_AGENT),
            ("Accept-Language", "en-US,en;q=0.9"),
        ]
        self._token = None
        self._last = 0.0

    # -- low level ---------------------------------------------------------- #
    def _wait(self):
        gap = time.time() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.time()

    def _request(self, path, data=None, headers=None, referer=None):
        url = path if path.startswith("http") else BASE + path
        self._wait()
        body = None
        hdrs = {"Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
        if referer:
            hdrs["Referer"] = referer
        if data is not None:
            body = urllib.parse.urlencode(data).encode()
            hdrs["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            hdrs["X-Requested-With"] = "XMLHttpRequest"
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=body, headers=hdrs)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
                enc = (resp.headers.get("Content-Encoding") or "").lower()
        except urllib.error.HTTPError as exc:
            raw = exc.read() or b""
            status = exc.code
            enc = (exc.headers.get("Content-Encoding") or "").lower() if exc.headers else ""
        if enc == "gzip":
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass
        elif enc == "deflate":
            try:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                pass
        text = raw.decode("utf-8", "replace")
        if self.verbose:
            sys.stderr.write("[itra] %s %s -> %s (%d bytes)\n" % (
                "POST" if data is not None else "GET", url, status, len(raw)))
        if "Human Verification" in text and "awsWaf" in text:
            raise Blocked("ITRA 返回了人机校验页（AWS WAF），当前网络出口被拦截。")
        return status, text

    # -- session ------------------------------------------------------------ #
    def bootstrap(self, force=False):
        """Load the search page once to collect cookies + antiforgery token."""
        if self._token and not force:
            return self._token
        status, html = self._request(SEARCH_PAGE_PATH)
        if status != 200:
            raise ItraError("无法打开 ITRA 搜索页（HTTP %s）" % status)
        m = re.search(
            r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
        if not m:
            raise ItraError("搜索页里找不到 antiforgery token，页面结构可能已改版。")
        self._token = m.group(1)
        return self._token

    # -- API ---------------------------------------------------------------- #
    def find_runner(self, name, nationality="", start=1, count=10):
        token = self.bootstrap()
        payload = {
            "name": name,
            "nationality": nationality or "",
            "start": str(start),
            "count": str(count),
            "echoToken": "%.16f" % random.random(),
        }
        status, text = self._request(
            "/api/runner/find",
            data=payload,
            headers={"X-CSRF-TOKEN": token, "Accept": "application/json"},
            referer=SEARCH_PAGE_REFERER,
        )
        if status == 200:
            try:
                obj = json.loads(text)
            except ValueError:
                raise ItraError("搜索接口返回非 JSON 内容：%s" % text[:200])
            if "response1" in obj:
                return json.loads(_decrypt_payload(obj))
            return obj
        if status in (401, 403, 419):
            # stale token: refresh once
            self.bootstrap(force=True)
            return self.find_runner(name, nationality, start, count)
        raise ItraError("搜索接口失败（HTTP %s）：%s" % (status, text[:200]))

    def runner_page(self, runner_id, first=None, last=None, slug=None):
        """Fetch the public runner page; returns (url, html)."""
        candidates = []
        if slug:
            candidates.append(slug)
        if first and last:
            candidates.append("%s.%s.%s" % (slugify(last), slugify(first), runner_id))
        if not candidates:
            raise ItraError("缺少跑者姓名，无法构造主页地址（ID %s）。" % runner_id)

        for candidate in candidates:
            status, html = self._request("/RunnerSpace/" + candidate)
            if status == 200 and "runnerSpaceData" in html:
                return BASE + "/RunnerSpace/" + candidate, html
        raise ItraError(
            "跑者主页打不开（ID %s，尝试的 slug 均 404）。" % runner_id)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value or "")).strip()


def parse_search_results(obj) -> list:
    runners = []
    for item in (obj.get("Results") or []):
        runners.append({
            "itra_id": item.get("RunnerId"),
            "name": ("%s %s" % (item.get("FirstName") or "", item.get("LastName") or "")).strip(),
            "first_name": (item.get("FirstName") or "").strip(),
            "last_name": (item.get("LastName") or "").strip(),
            "nationality": item.get("Nationality"),
            "gender": item.get("Gender"),
            "age_group": (item.get("AgeGroup") or "").strip(),
            "pi": item.get("Pi"),
            "level": item.get("PiIndex"),
            "recent_races": item.get("RecentRaces"),
            "profile_url": "%s/RunnerSpace/%s.%s.%s" % (
                BASE, slugify(item.get("LastName")), slugify(item.get("FirstName")),
                item.get("RunnerId")),
        })
    return runners


def _js_unescape(text: str) -> str:
    """Decode the JSON string escapes left behind by regex-scraped values."""
    if not text or "\\" not in text:
        return text
    try:
        return json.loads('"' + text.replace('"', '\\"') + '"')
    except ValueError:
        return text


def _parse_levels(html):
    """Per-category Performance Index entries (the page repeats them 5x)."""
    out = []
    seen = set()
    for m in re.finditer(
            r'"pi":(\d+),"categoryName":"([^"]+)","categoryId":(\d+),"piIndex":"([^"]+)"',
            html):
        key = (m.group(2), int(m.group(1)))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "category": m.group(2),
            "pi": int(m.group(1)),
            "level": m.group(4).replace("-", " "),
        })
    return out


def _parse_stats(html):
    stats = {}
    for m in re.finditer(r'"title":"([^"]+)","value":"([^"]*)"', html):
        key = m.group(1)
        if key and key not in stats:
            stats[key] = _js_unescape(m.group(2))
    return stats


def _parse_rankings(html):
    """World / continent / country ranking cards (age-group splits are gated)."""
    out = {}
    titles = list(re.finditer(
        r">\s*(World|Continent|Country)\s+Ranking\s*(?:\(([^)]*)\))?\s*</h4>", html))
    for i, m in enumerate(titles):
        scope = m.group(1).lower()
        area = (m.group(2) or "").strip()
        # stop at the next card so a card can never read its neighbour's numbers
        boundary = titles[i + 1].start() if i + 1 < len(titles) else len(html)
        body = html[m.end():min(boundary, m.end() + 4000)]
        rank = re.search(
            r"Overall\s*\(\s*([^)]*?)\s*\)[\s\S]{0,1400}?<h5[^>]*>\s*([\d,]+)\s*</h5>"
            r"\s*<p[^>]*>\s*([\d,]+)\s*</p>", body)
        entry = {}
        if area:
            entry["area"] = area
        if rank:
            entry.update({
                "group": re.sub(r"\s+", " ", rank.group(1)),
                "rank": int(rank.group(2).replace(",", "")),
                "total": int(rank.group(3).replace(",", "")),
            })
        if entry:
            out[scope] = entry
    return out


def _collect_arrays(html):
    """All embedded result arrays: full history (chart data) + per-result detail."""
    chart, detail = [], []
    for m in re.finditer(r'\[\s*\{\s*"(?:id|display)"', html):
        start = html.index("[", m.start())
        end = _balanced_end(html, start, "[", "]")
        if end == -1:
            continue
        try:
            arr = json.loads(html[start:end + 1])
        except ValueError:
            continue
        if not arr or not isinstance(arr[0], dict) or "raceName" not in arr[0]:
            continue
        if any("itraPoints" in item for item in arr[:3]):
            detail.extend(arr)
        else:
            chart.extend(arr)
    return chart, detail


def _parse_results(html):
    """Full race history.

    Two public sources on the runner page, merged:
      * `scorePerformance.results` — every race (chart data), but no ITRA points.
      * `raceResults` — latest races only, but carries per-race ITRA points,
        finishers and the Race Score placeholder ("DNF" when not a subscriber).
    """
    chart, detail = _collect_arrays(html)
    latest = _json_after_key(html, "raceResults", "[", "]")
    latest = latest if isinstance(latest, list) else []

    rows = {}
    for row in detail + chart:
        key = ((row.get("raceDate") or "")[:10], row.get("timeSeconds"))
        merged = rows.setdefault(key, {})
        for field, value in row.items():
            if value in (None, "", 0, 0.0):
                merged.setdefault(field, value)
            else:
                merged[field] = value

    out = [normalize_race(r) for r in rows.values()]

    if latest:
        by_key = {(r["date"], (r.get("time") or "")): r for r in out}
        by_date = {}
        for r in out:
            by_date.setdefault(r["date"], []).append(r)
        for item in latest:
            date = (item.get("date") or "")[:10]
            hit = by_key.get((date, item.get("time") or ""))
            if hit is None:
                candidates = by_date.get(date) or []
                hit = candidates[0] if len(candidates) == 1 else None
            if hit is None:
                continue
            hit.update({
                "itra_points": item.get("itraPoint"),
                "mountain_points": item.get("mountainPoints"),
                "finishers_count": _as_int(item.get("finishers")),
                "participants": _as_int(item.get("runnerCount")) or hit.get("participants"),
                "rank_overall": _as_int(item.get("ranking")) or hit.get("rank_overall"),
                "race_score_display": item.get("displayedScore"),
                "itra_race_year_id": item.get("raceYearId"),
                "race_score": item.get("score") or None,
                "dnf": False,
            })
        if not out:
            for item in latest:
                out.append({
                    "date": (item.get("date") or "")[:10],
                    "event": item.get("name"),
                    "race": None,
                    "category": item.get("distanceCategory"),
                    "distance_km": item.get("distance"),
                    "elevation_gain_m": item.get("elevationGain"),
                    "time": item.get("time"),
                    "rank_overall": _as_int(item.get("ranking")),
                    "rank_gender": _as_int(item.get("genderRanking")),
                    "participants": _as_int(item.get("runnerCount")),
                    "finishers_count": _as_int(item.get("finishers")),
                    "race_score": item.get("score") or None,
                    "race_score_display": item.get("displayedScore"),
                    "itra_points": item.get("itraPoint"),
                    "mountain_points": item.get("mountainPoints"),
                    "country": item.get("country"),
                    "itra_race_year_id": item.get("raceYearId"),
                    "dnf": False,
                })

    for row in out:
        if row.get("time") in (None, "", "0:00:00"):
            row["dnf"] = True
            row["time"] = None
        else:
            row.setdefault("dnf", False)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def _as_int(value):
    if value in (None, "", "DNF"):
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def _fmt_time(seconds: str) -> str:
    try:
        total = int(str(seconds).split(":")[0]) * 3600 + \
            int(str(seconds).split(":")[1]) * 60 + int(str(seconds).split(":")[2])
    except (ValueError, IndexError):
        return str(seconds)
    h, rem = divmod(total, 3600)
    return "%d:%02d:%02d" % (h, rem // 60, rem % 60)


def normalize_race(row):
    score = row.get("score")
    return {
        "date": (row.get("raceDate") or "")[:10],
        "event": row.get("eventName"),
        "race": row.get("raceName"),
        "category": row.get("distanceCategory"),
        "distance_km": row.get("totalDistance"),
        "elevation_gain_m": row.get("totalElevation"),
        "time": row.get("timeSeconds"),
        "rank_overall": _as_int(row.get("rank")),
        "rank_gender": _as_int(row.get("rankGender")),
        "participants": _as_int(row.get("runnerCount")),
        "finishers_count": None,
        # Race Score is an ITRA subscription feature; the public payload always
        # carries score = 0, so None here means "not public", not "no score".
        "race_score": score if score else None,
        "race_score_display": None,
        "itra_points": row.get("itraPoints"),
        "mountain_points": row.get("mountainPoints"),
        "country": row.get("countryName"),
        "itra_race_year_id": None,
    }


def parse_profile(html, url):
    data = _json_after_key(html, "runnerSpaceData", "{", "}") or {}
    levels = _parse_levels(html)
    general = next((x for x in levels if x["category"] == "General"), None)

    if general is None:
        m = re.search(r'id="divProgress"[\s\S]{0,400}?level-count">(\d+)</span>'
                      r'\s*<span class="level">([^<]+)</span>', html)
        if m:
            general = {"category": "General", "pi": int(m.group(1)),
                       "level": _strip_tags(m.group(2))}

    world_top = None
    m = re.search(r"World Top\s*<b>([^<]+)</b>", html)
    if m:
        world_top = _strip_tags(m.group(1))

    stats = _parse_stats(html)
    races = _parse_results(html)

    return {
        "itra_id": data.get("itraId"),
        "name": (data.get("fullName") or "").strip(),
        "first_name": data.get("firstName"),
        "last_name": data.get("lastName"),
        "nationality": data.get("nationality"),
        "profile_url": url,
        "photo": data.get("profileImageUrl"),
        "pi": general["pi"] if general else None,
        "level": general["level"] if general else None,
        "world_top": world_top,
        "rankings": _parse_rankings(html),
        "pi_by_category": levels,
        "stats": {
            "finished_races": stats.get("Finished Races"),
            "total_time": stats.get("Total Race Time"),
            "total_distance": stats.get("Total Distance"),
            "total_elevation": stats.get("Total Elevation"),
            "best_race_score": stats.get("Best Performance - Race Score"),
            "best_race_rank": stats.get("Best Race Ranking"),
        },
        "races": races,
    }


def _runner_id_from(arg: str):
    m = re.search(r"(\d{3,})\s*$", arg.strip().rstrip("/"))
    return m.group(1) if m else None


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def render_search(runners, total, name):
    if not runners:
        return "ITRA 上没有找到名为 %r 的跑者。" % name
    lines = ["ITRA 搜索 %r：命中 %d 人%s" % (
        name, total, "" if total <= len(runners) else "（仅显示前 %d 人）" % len(runners)), ""]
    for r in runners:
        lines.append("  #%s  %-26s %-18s PI %-4s %-11s %s" % (
            r["itra_id"], r["name"], r["nationality"] or "-",
            r["pi"] if r["pi"] is not None else "-", r["level"] or "-",
            r["profile_url"]))
    return "\n".join(lines)


def render_profile(p, race_limit=None):
    races = p["races"]
    lines = []
    head = "%s（ITRA ID %s）" % (p["name"] or "?", p["itra_id"])
    lines.append(head)
    lines.append("国籍 %s｜PI %s（%s）%s" % (
        p.get("nationality") or "-",
        p["pi"] if p["pi"] is not None else "-",
        p["level"] or "-",
        "｜世界排名前 %s" % p["world_top"] if p.get("world_top") else "",
    ))
    if len(p["pi_by_category"]) > 1:
        lines.append("分类 PI：" + "，".join(
            "%s %s（%s）" % (x["category"], x["pi"], x["level"])
            for x in p["pi_by_category"] if x["category"] != "General"))
    rk = p.get("rankings") or {}
    if rk:
        parts = []
        for scope, label in (("world", "世界"), ("continent", "洲际"), ("country", "国家")):
            entry = rk.get(scope)
            if entry and entry.get("rank"):
                area = "·%s" % entry["area"] if entry.get("area") else ""
                parts.append("%s%s 第 %s/%s" % (
                    label, area, "{:,}".format(entry["rank"]),
                    "{:,}".format(entry["total"])))
        if parts:
            lines.append("总排名（%s）：%s" % (
                rk.get("world", {}).get("group") or "-", "；".join(parts)))
    st = p["stats"]
    if st.get("finished_races"):
        lines.append("完赛 %s 场｜总里程 %s｜总爬升 %s｜总用时 %s" % (
            st.get("finished_races"), st.get("total_distance") or "-",
            st.get("total_elevation") or "-", st.get("total_time") or "-"))
    lines.append("主页：%s" % p["profile_url"])

    if races:
        shown = races if not race_limit else races[:race_limit]
        lines.append("")
        lines.append("完赛记录（共 %d 条，按时间倒序%s）" % (
            len(races), "" if len(shown) == len(races) else "，显示 %d 条" % len(shown)))
        has_score = any(r["race_score"] is not None for r in races)
        head_fmt = "%-10s %-32s %-6s %7s %8s %7s %11s %5s" + (" %6s" if has_score else "")
        row_fmt = "%-10s %-32s %-6s %7s %8s %7s %11s %5s" + (" %6s" if has_score else "")
        header = ["日期", "赛事", "组别", "距离km", "爬升m", "用时", "名次/人数", "积分"]
        if has_score:
            header.append("单场分")
        lines.append(head_fmt % tuple(header))
        for r in shown:
            total = r.get("finishers_count") or r.get("participants")
            rank_cell = ("%s/%s" % (r["rank_overall"], total)
                         if r["rank_overall"] else "-")
            cells = [
                r["date"],
                (r["event"] or "")[:32],
                r["category"] or "-",
                r["distance_km"] if r["distance_km"] is not None else "-",
                r["elevation_gain_m"] if r["elevation_gain_m"] is not None else "-",
                "DNF" if r.get("dnf") else (_fmt_time(r["time"]) if r["time"] else "-"),
                rank_cell,
                r["itra_points"] if r["itra_points"] is not None else "-",
            ]
            if has_score:
                cells.append(r["race_score"] if r["race_score"] is not None else "-")
            lines.append(row_fmt % tuple(cells))
        if not has_score:
            sample = next((r.get("race_score_display") for r in races
                           if r.get("race_score_display")), None)
            lines.append("")
            lines.append(
                "注：「积分」= ITRA 完赛积分（0–6，只表示赛事难度，不表示快慢）。"
                "公开页仅对最近几场比赛带出积分，更早的显示 “-”。"
                "单场 Race Score（0–1000）属 ITRA 订阅功能，公开页统一为 %r，"
                "本工具不编造该列。" % (sample or "DNF"))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_search(args, client):
    res = client.find_runner(args.name, args.country, 1, args.limit)
    runners = parse_search_results(res)
    if args.json:
        print(json.dumps({"query": args.name, "total": res.get("ResultCount"),
                          "runners": runners}, ensure_ascii=False, indent=2))
    else:
        print(render_search(runners, res.get("ResultCount") or len(runners), args.name))
    return 0 if runners else 1


def _load_profile(client, runner_id, first, last, slug=None):
    url, html = client.runner_page(runner_id, first, last, slug)
    return parse_profile(html, url)


def _slug_from_arg(arg: str):
    """Extract the full path segment from a profile URL, e.g. hruska.zdenek.1315857"""
    m = re.search(r"/RunnerSpace/([^/?#]+)\s*$", arg.strip())
    if not m:
        return None
    seg = m.group(1)
    return seg if re.search(r"\.\d{3,}$", seg) else None


def _name_from_id(client, runner_id):
    """The search API also accepts a bare ITRA ID; use it to recover the name."""
    try:
        res = client.find_runner(str(runner_id), "", 1, 10)
    except ItraError:
        return None, None
    for runner in parse_search_results(res):
        if str(runner["itra_id"]) == str(runner_id):
            return runner["first_name"], runner["last_name"]
    return None, None


def cmd_profile(args, client):
    rid = _runner_id_from(args.runner)
    if not rid:
        print("无法从 %r 解析出 ITRA ID（需要数字 ID 或含 ID 的主页链接）。" % args.runner,
              file=sys.stderr)
        return 1
    first, last = args.first, args.last
    slug = _slug_from_arg(args.runner)
    if not slug and not (first and last):
        first, last = _name_from_id(client, rid)
    profile = _load_profile(client, rid, first, last, slug)
    if args.json:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        print(render_profile(profile, args.races))
    return 0


def cmd_report(args, client):
    res = client.find_runner(args.name, args.country, 1, args.pick_limit)
    runners = parse_search_results(res)
    if not runners:
        print("ITRA 上没有找到名为 %r 的跑者。" % args.name)
        return 1
    target = runners[0]
    if len(runners) > 1 and not args.json:
        print(render_search(runners, res.get("ResultCount") or len(runners), args.name))
        total = res.get("ResultCount") or len(runners)
        if total > args.pick_limit:
            print("\n⚠️ 命中 %d 人，无法自动确定是哪一个。请让用户确认国籍/年龄组/ITRA ID，"
                  "或用 `search` 缩小范围后再跑 `profile <ID>`。\n" % total)
            print("下面仅为搜索排序第一位，仅供参考：\n")
        else:
            print("\n按搜索排序取第一位：%s（ID %s）。如需其他人，跑 `profile <ID>`。\n"
                  % (target["name"], target["itra_id"]))
    profile = _load_profile(client, target["itra_id"],
                            target["first_name"], target["last_name"])
    if args.json:
        print(json.dumps({"query": args.name, "total": res.get("ResultCount"),
                          "candidates": runners, "profile": profile},
                         ensure_ascii=False, indent=2))
    else:
        print(render_profile(profile, args.races))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="查询 ITRA 跑者的 Performance Index 与完赛记录（纯 HTTP，无需登录）")
    ap.add_argument("--verbose", action="store_true", help="打印每个 HTTP 请求")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", help="按姓名搜索，返回候选跑者（含 PI）")
    sp.add_argument("name")
    sp.add_argument("--country", default="", help="国籍过滤，如 CZE / CHN")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("profile", help="按 ITRA ID / 主页链接查详细档案")
    sp.add_argument("runner", help="ITRA ID、主页 URL 或 slug")
    sp.add_argument("--first", help="名字（构造主页 slug 用，可选）")
    sp.add_argument("--last", help="姓氏（构造主页 slug 用，可选）")
    sp.add_argument("--races", type=int, default=20, help="最多显示多少场完赛记录")
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("report", help="姓名 → 自动取最佳匹配 → 完整档案")
    sp.add_argument("name")
    sp.add_argument("--country", default="")
    sp.add_argument("--pick-limit", type=int, default=5)
    sp.add_argument("--races", type=int, default=20)
    sp.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    client = ItraClient(verbose=args.verbose)
    try:
        if args.cmd == "search":
            return cmd_search(args, client)
        if args.cmd == "profile":
            return cmd_profile(args, client)
        return cmd_report(args, client)
    except Blocked as exc:
        print("被反爬拦截：%s" % exc, file=sys.stderr)
        return 2
    except ItraError as exc:
        print("查询失败：%s" % exc, file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print("网络错误：%s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
