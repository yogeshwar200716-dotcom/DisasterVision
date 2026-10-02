import json
import socket
import sys
from analysis_engine import DATA_DIR, discover_options, analyze

HOST = '127.0.0.1'
PORT = 5517
BUFFER = 64 * 1024


def send(conn, payload):
    data = (json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8')
    conn.sendall(data)


def handle(conn, addr):
    try:
        chunks = []
        while True:
            part = conn.recv(BUFFER)
            if not part:
                break
            chunks.append(part)
        if not chunks:
            return
        req = json.loads(b''.join(chunks).decode('utf-8'))
        action = req.get('action', 'analyze')
        if action == 'options':
            send(conn, {'options': discover_options()})
            return
        if action != 'analyze':
            send(conn, {'error': 'Unknown server action.'})
            return
        try:
            year = int(req.get('future_year'))
        except (TypeError, ValueError):
            send(conn, {'error': 'Enter a valid future year.'})
            return
        disaster = str(req.get('disaster', 'GLACIER')).strip() or 'GLACIER'
        location = str(req.get('location', '')).strip()
        if not location:
            send(conn, {'error': 'Please select a location.'})
            return
        if year < 1900 or year > 2100:
            send(conn, {'error': 'Enter a valid year between 1900 and 2100.'})
            return
        print(f'[SERVER] {disaster} | {location} | future {year}')
        try:
            result = analyze(disaster, location, year)
        except ValueError as exc:
            send(conn, {'error': str(exc)})
            return
        except Exception as exc:
            print('[SERVER ERROR]', repr(exc))
            send(conn, {'error': f'Analysis failed: {exc}'})
            return
        send(conn, result)
    except Exception as exc:
        print('[SERVER ERROR]', repr(exc))
        try:
            send(conn, {'error': str(exc)})
        except Exception:
            pass
    finally:
        conn.close()


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(10)
        print('=' * 68)
        print('DISASTERVISION ANALYSIS SERVER')
        print(f'Listening : {HOST}:{PORT}')
        print(f'Data      : {DATA_DIR}')
        print('Photos are stored on the server. Client sends location + year only.')
        print('=' * 68)
        while True:
            conn, addr = server.accept()
            handle(conn, addr)


if __name__ == '__main__':
    main()
