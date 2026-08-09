#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import urllib.parse
import sys
import os
import json

PORT = 8050
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# SCRIPT_DIR is app/src/server -> APP_DIR is app/
APP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
WEB_DIR = os.path.join(APP_DIR, "web")
DATA_DIR = os.path.join(APP_DIR, "data")
SRC_DIR = os.path.join(APP_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

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
        
        # Proxy endpoint for PolyCop Leaderboard API
        if parsed.path.startswith('/api/leaderboard'):
            target_url = f"https://polycop.fun{self.path}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(content)
                    return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f'{{"error": "{str(e)}"}}'.encode('utf-8'))
                return

        # API endpoint to clear cached dataset files
        if parsed.path.startswith('/api/clear_data'):
            from pipeline.reset_data_cache import reset_data_cache
            reset_data_cache()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status": "cleared", "message": "Scan data cache deleted."}')
            return

        # API endpoint to trigger full rescan pipeline (Phase 1 & Phase 2)
        if parsed.path.startswith('/api/rescan'):
            try:
                from pipeline.phase1_scrape_leaderboard import fetch_and_scrape_leaderboard
                from pipeline.phase2_filter_targets import run_phase2_filter
                
                fetch_and_scrape_leaderboard(min_score=60.0)
                run_phase2_filter()

                verified_file = os.path.join(DATA_DIR, "phase2_verified_targets.json")
                if os.path.exists(verified_file):
                    with open(verified_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps(data).encode('utf-8'))
                else:
                    raise FileNotFoundError("Verified dataset file was not created.")
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f'{{"error": "{str(e)}"}}'.encode('utf-8'))
            return

        # API endpoint to run live latency and slippage benchmark
        if parsed.path.startswith('/api/measure_latency'):
            try:
                from tools.measure_latency_slippage import (
                    discover_markets, measure_http_rtt, measure_ws_rtt, profile_timeframe
                )
                import datetime

                markets = discover_markets()
                probe_token = ""
                if markets.get("5m"):
                    probe_token = markets["5m"][0]["token_id"]
                elif markets.get("15m"):
                    probe_token = markets["15m"][0]["token_id"]

                latency_stats = measure_http_rtt(probe_token, samples=3)
                ws_stats = measure_ws_rtt(samples=3)
                profile_5m = profile_timeframe(markets.get("5m", []), "5m")
                profile_15m = profile_timeframe(markets.get("15m", []), "15m")

                payload = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "latency": {
                        "http_rtt_ms": latency_stats,
                        "ws_rtt_ms": {
                            "avg": ws_stats["avg"],
                            "min": ws_stats["min"],
                            "max": ws_stats["max"],
                            "ok": ws_stats["ok"],
                            "error": ws_stats["error"],
                            "samples_completed": ws_stats["samples_completed"],
                            "samples_attempted": ws_stats["samples_attempted"],
                            "url": ws_stats["url"]
                        }
                    },
                    "markets": {
                        "5m_markets": profile_5m,
                        "15m_markets": profile_15m
                    }
                }
                payload_bytes = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(payload_bytes)))
                self.end_headers()
                self.wfile.write(payload_bytes)
            except Exception as e:
                err_bytes = json.dumps({"error": str(e)}).encode("utf-8")
                try:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(err_bytes)))
                    self.end_headers()
                    self.wfile.write(err_bytes)
                except Exception:
                    pass
            return

        # Default root handler
        if parsed.path == '/' or parsed.path == '':
            self.path = '/index.html'

        return super().do_GET()

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
