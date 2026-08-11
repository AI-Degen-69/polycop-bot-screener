#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import urllib.parse
import sys
import os
import json
import math

PORT = 8050
# Canonical header: make app/src importable so `paths` and the sibling
# packages are reachable whether the server runs as a script or via -m.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import WEB_DIR, DATA_DIR, PHASE3_FILE  # noqa: E402

from server.feed_projection import project_feed  # noqa: E402


# The compact feed projection is cached until the source file changes, keyed
# on the file's (mtime, size) — the same signal the browser uses to know a
# scan is fresh. Projecting ~6 MB on every request would make the page slower
# than fetching the raw file was; one re-projection per written scan is cheap.
_feed_cache = {"key": None, "body": None}


def _feed_projection_body():
    """The projected v1 feed as JSON bytes, or None when no scan has run."""
    feed_path = os.path.join(DATA_DIR, PHASE3_FILE)
    try:
        st = os.stat(feed_path)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    if _feed_cache["key"] != key:
        with open(feed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Body first, key second: a concurrent reader that lands between the
        # two writes sees a new body with the old key and recomputes (duplicate
        # work, correct result) instead of serving a stale scan under a fresh
        # key.
        _feed_cache["body"] = json.dumps(project_feed(data)).encode("utf-8")
        _feed_cache["key"] = key
    return _feed_cache["body"]


class PolyCopScreenerWebHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path):
        clean_path = path.split('?')[0]
        
        # Route /data requests to app/data/ directory
        if clean_path.startswith('/data/'):
            rel = clean_path[len('/data/'):]
            return os.path.join(DATA_DIR, rel)
            
        # Default route to app/web/ directory
        return os.path.join(WEB_DIR, clean_path.lstrip('/'))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        response = _dispatch(parsed.path, parsed.query)
        if response is not None:
            status, payload = response
            _send_json(self, status, payload)
            return

        # Default root handler
        if parsed.path == '/' or parsed.path == '':
            self.path = '/index.html'

        return super().do_GET()

# ---------------------------------------------------------------------------
# JSON API: one endpoint function per route, a routing table, and one writer.
# The router is a pure function (status, payload) so the mapping of exceptions
# to status codes and the framing live behind a seam tests can call directly.
# ---------------------------------------------------------------------------

# Ordered prefix table: first match wins. The prefixes are distinct first path
# segments today, but keep the ordering explicit so a future overlapping
# prefix is handled deliberately rather than by accident. Handlers are stored
# by name and resolved at call time so a test (or a future caller) can patch
# any endpoint behind the router.
_API_ROUTES = [
    ("/api/leaderboard", "endpoint_leaderboard"),
    ("/api/clear_data", "endpoint_clear_data"),
    # The compact feed projection must be matched before any generic fallback;
    # today no prefix overlaps, but the table is ordered deliberately.
    ("/api/feed/v1", "endpoint_feed"),
    ("/api/rescan", "endpoint_rescan"),
    ("/api/cap_backtest", "endpoint_cap_backtest"),
    ("/api/measure_latency", "endpoint_measure_latency"),
]


def endpoint_leaderboard(path, query):
    """Proxy the PolyCop Leaderboard API: forward path and query verbatim and
    return the upstream bytes unchanged. A raw-bytes payload is the one
    exception to the dict contract, so the upstream body is never re-serialized.
    """
    target_url = f"https://polycop.fun{path}"
    if query:
        target_url += "?" + query
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(target_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return (200, resp.read())


def endpoint_clear_data(path, query):
    """Delete the cached dataset files so the next scan starts from scratch."""
    from pipeline.reset_data_cache import reset_data_cache
    reset_data_cache()
    return (200, {"status": "cleared", "message": "Scan data cache deleted."})


def endpoint_feed(path, query):
    """The compact, versioned feed the page fetches instead of the raw scan
    file (~6 MB, of which ~92% is a skip log the page shows 12 rows of). The
    projection is computed server-side from the same file screen.py and the
    audit record read, and cached on the file's mtime — so the page gets a
    small payload without a second file to drift from the scan.
    """
    body = _feed_projection_body()
    if body is None:
        return (404, {"error": "No cached scan data — run a scan first"})
    return (200, body)


def endpoint_rescan(path, query):
    """Run the full scan pipeline and return the freshly produced feed.

    One call site for the phase1→2→3 sequence, shared with screen.py, so
    adding a phase cannot desync the two runners. The response is the same
    compact projection the page reads from /api/feed/v1, never the raw file:
    a finished scan fills the grid through the one path that knows how to
    normalise it.
    """
    from pipeline.orchestrator import run_pipeline

    verified_file = run_pipeline()
    if not os.path.exists(verified_file):
        raise FileNotFoundError("Verified dataset file was not created.")
    with open(verified_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # The scan just rewrote the file, so the mtime-keyed cache is stale by
    # definition: serve the projection of the data just read, and let the next
    # /api/feed/v1 hit re-project on its new mtime.
    _feed_cache["key"] = None
    return (200, project_feed(data))


def endpoint_cap_backtest(path, query):
    """Backtest one wallet at caller-chosen per-position caps — the custom-caps
    control in the wallet modal. Each cap is derived via with_position_cap, so
    the profile defaults and every already-computed result's cache key are left
    untouched.
    """
    params = urllib.parse.parse_qs(query)
    wallet = (params.get("wallet") or [""])[0].strip()
    caps_raw = (params.get("caps") or [""])[0]
    if not wallet:
        raise ValueError("wallet is required")
    # A wallet that cannot be an address is a typo, not a target: fail fast
    # instead of burning live simulation calls on it.
    if not wallet.lower().startswith("0x") or len(wallet) < 8:
        raise ValueError("wallet must be a 0x… address")
    cap_levels = _parse_cap_levels(caps_raw)
    from screener.simulated_verdict import backtest_wallet_at_caps
    try:
        levels = backtest_wallet_at_caps(wallet=wallet, cap_levels=cap_levels)
    except Exception as e:
        # Any sweep failure is a server-side problem (the client's caps were
        # already validated), so it is 500, never 400 — even a ValueError
        # raised inside the sweep.
        raise RuntimeError(f"Backtest failed: {e}") from e
    return (200, {"wallet": wallet, "levels": levels})


def endpoint_measure_latency(path, query):
    """Run the budgeted live latency and slippage benchmark."""
    return (200, _measure_latency_payload())


def _dispatch(path, query=""):
    """Route an API request to its endpoint function, mapping errors to
    statuses. Returns (status, payload); returns None for non-API paths so the
    caller falls through to static file serving.
    """
    for prefix, handler_name in _API_ROUTES:
        if path.startswith(prefix):
            try:
                # Resolved inside the try: a missing route name is a server
                # error, not a crash in the request thread.
                endpoint = globals()[handler_name]
                return endpoint(path, query)
            except json.JSONDecodeError as e:
                # A corrupt or truncated scan file on disk is a server fault,
                # not a bad request. JSONDecodeError subclasses ValueError, so
                # it has to be caught before the client-error branch or the
                # page shows "bad request" for a request that was fine.
                return (500, {"error": f"Scan data could not be read: {e}"})
            except ValueError as e:
                # A client error: the request itself is wrong.
                return (400, {"error": str(e)})
            except Exception as e:
                # A server error: the request was fine but the work failed.
                # The message is kept for the UI — this is a local tool and the
                # modal displays it for debugging.
                return (500, {"error": str(e)})
    if path.startswith("/api/"):
        return (404, {"error": "unknown endpoint: " + path})
    return None


def _send_json(handler, status, payload):
    """The one place a JSON API response is framed: content type, CORS, and an
    exact Content-Length on every response, with the body serialized once via
    json.dumps so no error message can ever corrupt the payload. Raw bytes pass
    through untouched for the leaderboard proxy.
    """
    if isinstance(payload, bytes):
        body = payload
    else:
        body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except Exception:
        # The client went away mid-write; the response is already framed and
        # there is nothing left to do for this request.
        pass


# The custom-caps control can ask for any positive per-position caps; each is
# a live backtest (two simulation runs, uncached, against the CLOB endpoint),
# so the count is bounded to keep a typo from launching a long job.
MAX_CUSTOM_CAP_LEVELS = 6


def _parse_cap_levels(raw: str):
    """Parse the comma-separated cap list from the custom-caps control.

    Accepts positive finite dollar amounts, dedupes, and sorts ascending.
    Raises ValueError with a message safe to show in the UI on bad input.
    """
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    if not parts:
        raise ValueError("caps is required (comma-separated dollar amounts, e.g. 8,20,30)")
    if len(parts) > MAX_CUSTOM_CAP_LEVELS:
        raise ValueError(f"at most {MAX_CUSTOM_CAP_LEVELS} caps per run")
    caps = []
    for part in parts:
        try:
            cap = float(part)
        except ValueError:
            raise ValueError(f'"{part}" is not a number') from None
        if cap <= 0 or not math.isfinite(cap):
            raise ValueError(f'caps must be positive and finite, got "{part}"')
        caps.append(cap)
    return sorted(set(caps))


def _measure_latency_payload():
    """Run the budgeted live latency and slippage benchmark.

    A live probe with a hard time budget: each measurement is attempted only
    while budget remains, and the payload states which stages were skipped so
    a partial run is visible rather than looking complete.
    """
    from tools.measure_latency_slippage import (
        discover_markets, measure_http_rtt, measure_ws_rtt, profile_timeframe
    )
    import datetime
    import time

    start_time = time.monotonic()
    TOTAL_BUDGET = 14.0
    is_partial = False

    def remaining_budget():
        return max(0.0, TOTAL_BUDGET - (time.monotonic() - start_time))

    markets = discover_markets()
    probe_token = ""
    if markets.get("5m"):
        probe_token = markets["5m"][0]["token_id"]
    elif markets.get("15m"):
        probe_token = markets["15m"][0]["token_id"]

    latency_stats = {"avg": 0.0, "min": 0.0, "max": 0.0, "ok": False, "error": "Skipped due to deadline budget", "samples_completed": 0, "samples_attempted": 0, "url": ""}
    ws_stats = {"avg": 0.0, "min": 0.0, "max": 0.0, "ok": False, "error": "Skipped due to deadline budget", "samples_completed": 0, "samples_attempted": 0, "url": ""}
    profile_5m = {}
    profile_15m = {}

    if remaining_budget() > 0.5:
        latency_stats = measure_http_rtt(probe_token, samples=3)
    else:
        is_partial = True

    if remaining_budget() > 0.5:
        ws_stats = measure_ws_rtt(samples=3)
    else:
        is_partial = True

    if remaining_budget() > 0.5:
        profile_5m = profile_timeframe(markets.get("5m", []), "5m")
    else:
        is_partial = True

    if remaining_budget() > 0.5:
        profile_15m = profile_timeframe(markets.get("15m", []), "15m")
    else:
        is_partial = True

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "partial": is_partial or (time.monotonic() - start_time) >= TOTAL_BUDGET,
        "latency": {
            "http_rtt_ms": latency_stats,
            "ws_rtt_ms": {
                "avg": ws_stats.get("avg", 0.0),
                "min": ws_stats.get("min", 0.0),
                "max": ws_stats.get("max", 0.0),
                "ok": ws_stats.get("ok", False),
                "error": ws_stats.get("error", ""),
                "samples_completed": ws_stats.get("samples_completed", 0),
                "samples_attempted": ws_stats.get("samples_attempted", 0),
                "url": ws_stats.get("url", "")
            }
        },
        "markets": {
            "5m_markets": profile_5m,
            "15m_markets": profile_15m
        }
    }


def start_server(port=PORT):
    os.chdir(WEB_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    server_address = ("", port)
    httpd = http.server.ThreadingHTTPServer(server_address, PolyCopScreenerWebHandler)
    print(f"=== PolyCop Bot Screener Running on http://localhost:{port} ===")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    start_server(PORT)
