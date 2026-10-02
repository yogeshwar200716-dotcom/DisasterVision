from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import json
import mimetypes
import socket
import subprocess
import sys
import time

from analysis_engine import BASE_DIR, DATA_DIR, discover_options, image_files

HOST = '0.0.0.0'
PORT = 8000
ANALYSIS_HOST = '127.0.0.1'
ANALYSIS_PORT = 5517


_server_process = None


def send_to_server(payload, timeout=180):
    with socket.create_connection((ANALYSIS_HOST, ANALYSIS_PORT), timeout=8) as sock:
        sock.settimeout(timeout)
        sock.sendall(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        sock.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            part = sock.recv(65536)
            if not part:
                break
            chunks.append(part)
    if not chunks:
        raise RuntimeError('Analysis server returned no response.')
    return json.loads(b''.join(chunks).decode('utf-8'))


def server_running():
    try:
        with socket.create_connection((ANALYSIS_HOST, ANALYSIS_PORT), timeout=0.5) as sock:
            sock.sendall(b'{"action":"options"}')
            sock.shutdown(socket.SHUT_WR)
            sock.recv(4096)
            return True
    except OSError:
        return False


def ensure_analysis_server():
    global _server_process
    if server_running():
        return
    if _server_process is None or _server_process.poll() is not None:
        _server_process = subprocess.Popen([sys.executable, str(BASE_DIR / 'Server.py')], cwd=str(BASE_DIR))
    for _ in range(40):
        if server_running():
            return
        time.sleep(0.15)
    raise RuntimeError('Could not start the analysis server. Please run Server.py manually.')


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        print('[WEB]', fmt % args)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, data, content_type, status=200, cache=False):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        if not cache:
            self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path == '/':
                html = (BASE_DIR / 'templates' / 'index.html').read_bytes()
                return self.send_bytes(html, 'text/html; charset=utf-8', cache=False)
            if path == '/api/options':
                return self.send_json({'options': discover_options()})
            if path == '/health':
                try:
                    ensure_analysis_server()
                    return self.send_json({'ok': True, 'server': True, 'options': discover_options()})
                except Exception as exc:
                    return self.send_json({'ok': False, 'error': str(exc)}, 503)
            if path == '/api/preview':
                disaster = (query.get('disaster', ['GLACIER'])[0] or 'GLACIER').strip()
                location = (query.get('location', [''])[0]).strip()
                options = discover_options()
                if disaster not in options or location not in options[disaster]:
                    return self.send_json({'error': 'Unknown location.'}, 404)
                files = image_files(DATA_DIR / disaster / location)
                if not files:
                    return self.send_json({'error': 'No satellite images found.'}, 404)
                year, image = files[-1]
                return self.send_json({'year': year, 'name': image.name, 'url': '/satellite/' + disaster + '/' + location + '/' + image.name})
            if path.startswith('/static/'):
                rel = path[len('/static/'):]
                target = (BASE_DIR / 'static' / rel).resolve()
                root = (BASE_DIR / 'static').resolve()
                if root not in target.parents and target != root:
                    return self.send_bytes(b'Not found', 'text/plain', 404)
                if not target.is_file():
                    return self.send_bytes(b'Not found', 'text/plain', 404)
                return self.send_bytes(target.read_bytes(), mimetypes.guess_type(str(target))[0] or 'application/octet-stream', cache=True)
            if path.startswith('/satellite/'):
                parts = path.split('/')
                if len(parts) != 5:
                    return self.send_bytes(b'Not found', 'text/plain', 404)
                _, _, disaster, location, filename = parts
                options = discover_options()
                if disaster not in options or location not in options[disaster]:
                    return self.send_bytes(b'Not found', 'text/plain', 404)
                folder = DATA_DIR / disaster / location
                valid = {p.name for _, p in image_files(folder)}
                if filename not in valid:
                    return self.send_bytes(b'Not found', 'text/plain', 404)
                target = folder / filename
                return self.send_bytes(target.read_bytes(), mimetypes.guess_type(filename)[0] or 'application/octet-stream', cache=True)
            return self.send_bytes(b'Not found', 'text/plain', 404)
        except Exception as exc:
            print('[WEB ERROR]', repr(exc))
            return self.send_json({'error': str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/analyze':
            return self.send_bytes(b'Not found', 'text/plain', 404)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length > 100_000:
                return self.send_json({'error': 'Request is too large.'}, 413)
            raw = self.rfile.read(length).decode('utf-8')
            values = parse_qs(raw)
            year_raw = values.get('future_year', [''])[0].strip()
            disaster = (values.get('disaster', ['GLACIER'])[0] or 'GLACIER').strip()
            location = values.get('location', [''])[0].strip()
            if not year_raw:
                return self.send_json({'error': 'Please enter the future year.'}, 400)
            try:
                year = int(year_raw)
            except ValueError:
                return self.send_json({'error': 'Please enter a valid numeric year.'}, 400)
            if not location:
                return self.send_json({'error': 'Please select a location.'}, 400)
            if year < 1900 or year > 2100:
                return self.send_json({'error': 'Please enter a valid year between 1900 and 2100.'}, 400)
            ensure_analysis_server()
            result = send_to_server({'action': 'analyze', 'disaster': disaster, 'location': location, 'future_year': year})
            if 'error' in result:
                return self.send_json(result, 400)
            return self.send_json(result)
        except Exception as exc:
            print('[WEB ERROR]', repr(exc))
            return self.send_json({'error': str(exc)}, 500)


if __name__ == '__main__':
    print('=' * 68)
    print('DISASTERVISION WEBSITE')
    print(f'Open: http://127.0.0.1:{PORT}')
    print('The analysis server starts automatically when needed.')
    print('=' * 68)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
