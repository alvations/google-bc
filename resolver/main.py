"""Google B.C. lucky resolver.

GET /lucky?q=<query>             -> 302 to the Wayback Machine capture (last one on or
                                    before 2022-12-31) of the first search result
GET /lucky?q=<query>&format=json -> the same decision as JSON, no redirect
GET /status                      -> "ok"

Stdlib only. A browser cannot read where Google's "I'm Feeling Lucky" redirect lands
(cross-origin), so this service resolves it. Result sources, in order:

  1. Google Custom Search JSON API, if CSE_KEY and CSE_CX are set (official API,
     supports a real date filter; 100 free queries/day)
  2. Google's own lucky redirect (works from residential IPs; cloud IPs get a captcha)
  3. Bing web results via its RSS feed

Candidates from these sources are pooled (Google's first) and the first one with a
Wayback capture on or before the cutoff wins. If nothing can be resolved, the user is sent to Google's own
lucky URL so they always land somewhere.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CUTOFF_DATE = "2022-12-31"
CUTOFF_TS = "20221231235959"
OPERATOR = "before:" + CUTOFF_DATE
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TIMEOUT = 7
MAX_CANDIDATES = 5
CACHE = {}
CACHE_TTL = 6 * 3600
CSE_KEY = os.environ.get("CSE_KEY", "")
CSE_CX = os.environ.get("CSE_CX", "")
SKIP_GOOGLE = os.environ.get("SKIP_GOOGLE") == "1"  # for testing the fallbacks
SKIP_HOSTS = ("google.", "googleusercontent.", "bing.com", "duckduckgo.com",
              "youtube.com/redirect", "microsoft.com/en-us/bing")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER_NOFOLLOW = urllib.request.build_opener(NoRedirect)
OPENER_FOLLOW = urllib.request.build_opener()


def fetch(url, follow=False, timeout=TIMEOUT):
    """Return (status, location_header, body_text)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    opener = OPENER_FOLLOW if follow else OPENER_NOFOLLOW
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.headers.get("Location"), r.read(500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read(500_000).decode("utf-8", "replace") if e.fp else ""
        return e.code, e.headers.get("Location"), body
    except Exception as e:  # noqa: BLE001
        log("fetch failed", url[:120], repr(e))
        return 0, None, ""


def with_cutoff(q):
    q = " ".join((q or "").split())
    if re.search(r"(^|\s)before:\s*\d{4}(-\d{1,2}){0,2}(\s|$)", q, re.I):
        return q
    return (q + " " + OPERATOR).strip()


def strip_operators(q):
    return " ".join(w for w in q.split() if not re.match(r"^(before|after):", w, re.I))


def google_lucky_url(q):
    return "https://www.google.com/search?" + urllib.parse.urlencode(
        {"q": with_cutoff(q), "btnI": "1", "hl": "en"})


def unwrap_google(url):
    """google.com/url?q=TARGET -> TARGET"""
    p = urllib.parse.urlsplit(url)
    if p.netloc.endswith("google.com") and p.path == "/url":
        qs = urllib.parse.parse_qs(p.query)
        target = qs.get("q") or qs.get("url")
        if target:
            return target[0]
    return url


def usable(url):
    if not url or not url.startswith("http"):
        return False
    low = url.lower()
    host = urllib.parse.urlsplit(low).netloc
    return bool(host) and not any(s in host or s in low for s in SKIP_HOSTS)


def dedupe(urls):
    seen, out = set(), []
    for u in urls:
        u = html.unescape(u).strip()
        if usable(u) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


# ---- result sources -------------------------------------------------------

def candidates_cse(q):
    if not (CSE_KEY and CSE_CX):
        return []
    url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode({
        "key": CSE_KEY, "cx": CSE_CX, "q": strip_operators(q), "num": 10,
        "sort": "date:r:19900101:20221231"})
    status, _, body = fetch(url, follow=True)
    log("cse", status)
    if status != 200:
        return []
    try:
        return dedupe(item.get("link", "") for item in json.loads(body).get("items", []))
    except ValueError:
        return []


def candidates_google(q):
    if SKIP_GOOGLE:
        return []
    url = google_lucky_url(q)
    status, loc, body = fetch(url)
    log("google", status, (loc or "")[:100])
    if status in (301, 302, 303, 307) and loc:
        loc = urllib.parse.urljoin(url, loc)
        if "/sorry/" in loc or "consent.google" in loc:
            return []
        target = unwrap_google(loc)
        if usable(target):
            return [target]
        status2, loc2, _ = fetch(target)
        if loc2:
            target2 = unwrap_google(urllib.parse.urljoin(target, loc2))
            if usable(target2):
                return [target2]
        return []
    if status == 200 and body:
        found = []
        for m in re.finditer(r'href="(/url\?q=([^"&]+)[^"]*|https?://[^"]+)"', body):
            cand = urllib.parse.unquote(m.group(2)) if m.group(2) else m.group(1)
            if "webcache" not in cand and "gstatic" not in cand:
                found.append(cand)
        return dedupe(found)[:MAX_CANDIDATES]
    return []


def candidates_bing(q):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"format": "rss", "q": strip_operators(q), "setlang": "en"})
    status, _, body = fetch(url, follow=True)
    log("bing", status)
    if status != 200:
        return []
    links = re.findall(r"<item>.*?<link>(.*?)</link>", body, re.S)
    return dedupe(links)[:MAX_CANDIDATES]


# ---- wayback --------------------------------------------------------------

def wayback_before(target):
    """Timestamp of the last capture on or before the cutoff: a string,
    "" when archive.org says there is none, None when archive.org is unreachable."""
    cdx = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode({
        "url": target, "to": CUTOFF_TS, "limit": "-1", "fl": "timestamp",
        "filter": "statuscode:200", "output": "json"})
    status, _, body = fetch(cdx, follow=True, timeout=6)
    log("cdx", status, body[:60].replace("\n", " "))
    if status == 200:
        try:
            rows = json.loads(body)
            return rows[-1][0] if len(rows) >= 2 else ""
        except ValueError:
            pass
    # The availability API only knows "closest", which may be after the cutoff,
    # so step back through a few earlier dates.
    answered = False
    for probe in (CUTOFF_TS, "20220701", "20210101"):
        avail = "https://archive.org/wayback/available?" + urllib.parse.urlencode(
            {"url": target, "timestamp": probe})
        status, _, body = fetch(avail, follow=True, timeout=6)
        log("avail", probe, status, body[:60])
        if status != 200:
            break
        try:
            snap = json.loads(body).get("archived_snapshots", {}).get("closest") or {}
        except ValueError:
            break
        answered = True
        ts = snap.get("timestamp", "")
        if not ts:
            return ""
        if ts <= CUTOFF_TS:
            return ts
    return "" if answered else None


# ---- decision -------------------------------------------------------------

def decide(q):
    key = with_cutoff(q).lower()
    hit = CACHE.get(key)
    if hit and hit["t"] > time.time() - CACHE_TTL:
        return hit["v"]
    out = {"query": with_cutoff(q), "source": None, "target": None,
           "wayback_timestamp": None, "candidates": [],
           "redirect": google_lucky_url(q), "note": "nothing resolved; Google's own lucky redirect"}
    cands, sources = [], []
    for name, fn in (("google-cse", candidates_cse), ("google", candidates_google), ("bing", candidates_bing)):
        if len(cands) >= MAX_CANDIDATES:
            break
        more = [c for c in fn(q) if c not in cands]
        if more:
            sources.append(name)
            cands.extend(more)
    source = "+".join(sources) or None
    if cands:
        out["source"] = source
        out["candidates"] = cands[:MAX_CANDIDATES]
        chosen, chosen_ts, unreachable = None, None, False
        for cand in cands[:MAX_CANDIDATES]:
            ts = wayback_before(cand)
            if ts:
                chosen, chosen_ts = cand, ts
                break
            if ts is None:
                unreachable = True
                break
        if chosen:
            out["target"], out["wayback_timestamp"] = chosen, chosen_ts
            out["redirect"] = "https://web.archive.org/web/%s/%s" % (chosen_ts, chosen)
            out["note"] = "last capture on or before %s" % CUTOFF_DATE
        else:
            out["target"] = cands[0]
            out["redirect"] = "https://web.archive.org/web/%s/%s" % (CUTOFF_TS, cands[0])
            out["note"] = ("archive.org unreachable; Wayback will pick the nearest capture" if unreachable
                           else "no capture before the cutoff for any candidate; Wayback will pick the nearest one")
    CACHE[key] = {"t": time.time(), "v": out}
    if len(CACHE) > 5000:
        CACHE.clear()
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "google-bc-lucky/2.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urllib.parse.urlsplit(self.path)
        params = urllib.parse.parse_qs(p.query)
        if p.path == "/status":
            return self._send(200, "ok", "text/plain")
        if p.path not in ("/", "/lucky"):
            return self._send(404, '{"error":"not found"}')
        q = (params.get("q") or [""])[0].strip()
        if not q:
            return self._send(400, '{"error":"missing q"}')
        if len(q) > 500:
            return self._send(400, '{"error":"query too long"}')
        out = decide(q)
        if (params.get("format") or [""])[0] == "json":
            return self._send(200, json.dumps(out, indent=1))
        return self._send(302, "", "text/plain", {"Location": out["redirect"]})

    def log_message(self, fmt, *args):
        log(self.address_string(), fmt % args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    log("listening on", port, "cse" if CSE_KEY and CSE_CX else "no-cse")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
