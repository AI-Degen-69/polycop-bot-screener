import os
import sys

print("LAUNCHER cwd:", os.getcwd(), flush=True)
sys.path.insert(0, os.path.join(os.getcwd(), "app", "src"))
from server.serve_web_app import start_server  # noqa: E402

print("SERVER sys.path:", flush=True)
for i, p in enumerate(sys.path):
    print(f"  {i}: {p}", flush=True)
try:
    import tools.measure_latency_slippage  # noqa: F401
    print("tools import OK", flush=True)
except Exception as e:
    print("tools import FAIL:", type(e).__name__, e, flush=True)

start_server(8051)
