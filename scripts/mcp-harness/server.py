"""Local MCP Apps test host: serves index.html and proxies POST /mcp to the dev API.

Run: python3 -I server.py [port]   (default 8765, upstream http://localhost:8000/mcp)
"""
import http.server
import pathlib
import sys
import urllib.request

UPSTREAM = "http://localhost:8000/mcp"
HERE = pathlib.Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def do_POST(self):
        if self.path != "/mcp":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        for h in ("MCP-Session-Id", "MCP-Protocol-Version"):
            if self.headers.get(h):
                headers[h] = self.headers[h]
        req = urllib.request.Request(UPSTREAM, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data, status, rh = r.read(), r.status, r.headers
        except urllib.error.HTTPError as e:
            data, status, rh = e.read(), e.code, e.headers
        self.send_response(status)
        self.send_header("Content-Type", rh.get("Content-Type", "application/json"))
        if rh.get("MCP-Session-Id"):
            self.send_header("MCP-Session-Id", rh["MCP-Session-Id"])
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
