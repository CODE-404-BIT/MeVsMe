"""Loopback-only dashboard HTTP server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import argparse
import json
import secrets

from .dashboard import Dashboard
from .api_routes import dispatch_api, ASSETS


def make_server(root: Path, port=8765):
    app = Dashboard(root)
    token = secrets.token_urlsafe(32)
    static = Path(__file__).parent / "static"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log credentials, request bodies or provider tracebacks.

        def send(self, status, body, mime="application/json"):
            data = json.dumps(body, allow_nan=False).encode() if mime == "application/json" else body
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {"error": "Local access only"})
            url = urlsplit(self.path)
            args = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path.startswith('/api/'):
                    status, body = dispatch_api(app, 'GET', url.path, args)
                    if url.path == '/api/status' and status == 200:
                        body = {**body, 'token': token}
                    return self.send(status, body)
                assets = ASSETS
                if url.path in assets:
                    filename, mime = assets[url.path]
                    return self.send(200, (static / filename).read_bytes(), mime)
                return self.send(404, {"error": "Not found"})
            except (ValueError, KeyError):
                return self.send(400, {"error": "Invalid date, timezone or page"})
            except Exception:
                return self.send(500, {"error": "Could not load saved data"})

        def do_POST(self):
            origin = self.headers.get("Origin")
            if (not self.valid_host() or self.headers.get("X-Dashboard-Token") != token
                    or origin not in {None, f"http://{self.headers.get('Host')}"}):
                return self.send(403, {"error": "Refresh the dashboard before trying again"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Invalid request")
                status, body = dispatch_api(app, 'POST', self.path, {}, data)
                return self.send(status, body)
            except (ValueError, KeyError, TypeError) as exc:
                message = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else "Invalid request"
                return self.send(400, {"error": message})
            except Exception:
                return self.send(500, {"error": "Could not start the operation"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.dashboard = app
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.root, args.port)
    print(f"Daily Model dashboard: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
