"""Local server for the dashboard — serves the static files and exposes
/api/refresh-prices for the manual Refresh button.

Run with: venv\\Scripts\\python.exe dashboard_server.py
Then open: http://localhost:8765

Opening dashboard/index.html directly (double-click) still works for
viewing, but the Refresh button only works when the page is loaded through
this server, since a plain file:// page has nothing to call.
"""
import json
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from src.report.dashboard import DASHBOARD_DIR, refresh_prices_only

PORT = 8765


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/refresh-prices":
            self._handle_refresh()
        else:
            super().do_GET()

    def _handle_refresh(self):
        try:
            portfolio = refresh_prices_only()
            body = json.dumps(portfolio).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:  # noqa: BLE001 - surface any failure to the button
            print(f"[refresh] ERROR: {e!r}")
            error = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(error)

    def log_message(self, format, *args):
        # Base class calls this with non-string args (e.g. an HTTPStatus enum)
        # on error responses -- stringify everything so logging itself never
        # crashes the request it's trying to log.
        print(f"[{self.address_string()}] {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("localhost", PORT), DashboardHandler)
    url = f"http://localhost:{PORT}"
    print(f"Dashboard server running at {url}  (Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
