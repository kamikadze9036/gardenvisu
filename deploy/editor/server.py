# Editor container: serves tools/editor/ and keeps the shared layout on a volume.
#
#   GET  /                 editor.html
#   GET  /api/layout       the saved layout (404 until the first save); header X-Rev = revision
#   GET  /api/layout?v=ID  an older version from the history (ID from /api/versions)
#   GET  /api/versions     current + history, newest first: [{id, saved, label, items, rev}]
#   PUT  /api/layout       save; send X-Base-Rev with the revision you loaded, 409 if someone saved in between
#                          (X-Force: 1 overwrites). The previous version goes to /data/history (last 50 kept).
#   GET  /healthz          ok
import hashlib, json, os, re, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

STATIC = os.environ.get('STATIC', '/app/static')
DATA = os.environ.get('DATA', '/data')
LAYOUT = os.path.join(DATA, 'layout.json')
HISTORY = os.path.join(DATA, 'history')
MAX_BODY = 40 * 1024 * 1024
KEEP = 50

def rev_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]

def versions():
    """The saved layout and its history with the time, label and size from each file's meta."""
    files = [('current', LAYOUT)] if os.path.exists(LAYOUT) else []
    if os.path.isdir(HISTORY):
        files += [(n, os.path.join(HISTORY, n)) for n in sorted(os.listdir(HISTORY), reverse=True)]
    out = []
    for vid, path in files:
        try:
            raw = open(path, 'rb').read(); data = json.loads(raw); meta = data.get('meta') or {}
            out.append({'id': vid, 'saved': meta.get('saved') or time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(os.path.getmtime(path))),
                        'label': meta.get('label') or '', 'items': len(data.get('items', [])), 'rev': rev_of(raw)})
        except Exception:
            continue
    return out

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC, **kw)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def reply(self, code, body=b'', ctype='application/json', headers=()):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        for k, v in headers: self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/healthz': return self.reply(200, b'ok', 'text/plain')
        if path == '/api/versions': return self.reply(200, json.dumps(versions(), ensure_ascii=False).encode())
        if path == '/api/layout':
            v = (self.path.split('v=', 1)[1].split('&')[0] if 'v=' in self.path else 'current')
            file = LAYOUT if v == 'current' else os.path.join(HISTORY, v) if re.fullmatch(r'layout-[\d-]+\.json', v) else None
            if not file or not os.path.exists(file): return self.reply(404, b'{"error":"no such layout"}')
            raw = open(file, 'rb').read()
            return self.reply(200, raw, headers=[('X-Rev', rev_of(raw))])
        if path == '/': self.path = '/editor.html'
        return super().do_GET()

    def do_PUT(self):
        if self.path.split('?')[0] != '/api/layout': return self.reply(404, b'{}')
        n = int(self.headers.get('Content-Length') or 0)
        if not 0 < n <= MAX_BODY: return self.reply(413, b'{"error":"too large"}')
        raw = self.rfile.read(n)
        try:
            data = json.loads(raw)
            assert isinstance(data.get('items'), list) and isinstance(data.get('layers'), list)
        except Exception:
            return self.reply(400, b'{"error":"not a layout"}')
        current = open(LAYOUT, 'rb').read() if os.path.exists(LAYOUT) else None
        base = self.headers.get('X-Base-Rev', '')
        if current is not None and base != rev_of(current) and self.headers.get('X-Force') != '1':
            return self.reply(409, json.dumps({'error': 'changed on the server', 'rev': rev_of(current)}).encode())
        os.makedirs(HISTORY, exist_ok=True)
        if current is not None:
            with open(os.path.join(HISTORY, time.strftime('layout-%Y%m%d-%H%M%S.json')), 'wb') as f: f.write(current)
            for old in sorted(os.listdir(HISTORY))[:-KEEP]: os.remove(os.path.join(HISTORY, old))
        tmp = LAYOUT + '.tmp'
        with open(tmp, 'wb') as f: f.write(raw)
        os.replace(tmp, LAYOUT)
        return self.reply(200, json.dumps({'rev': rev_of(raw)}).encode(), headers=[('X-Rev', rev_of(raw))])

    def log_message(self, fmt, *args):
        if not args or 'healthz' not in str(args[0]): super().log_message(fmt, *args)

if __name__ == '__main__':
    os.makedirs(DATA, exist_ok=True)
    print('editor on :8080', flush=True)
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
