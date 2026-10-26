"""Fixed-target staging transport. A worker cannot choose a relay destination."""
import argparse
import os
import selectors
import socket
import socketserver
import threading

parser = argparse.ArgumentParser()
parser.add_argument('--unix', required=True)
parser.add_argument('--tcp-port', type=int, required=True)
parser.add_argument('--tcp-host', default='127.0.0.1')
parser.add_argument('--listen', choices=['unix', 'tcp'], required=True)
args = parser.parse_args()

class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        if args.listen == 'unix':
            upstream = socket.create_connection((args.tcp_host, args.tcp_port), timeout=10)
        else:
            upstream = socket.socket(socket.AF_UNIX)
            upstream.settimeout(10)
            upstream.connect(args.unix)
        with upstream, selectors.DefaultSelector() as selector:
            upstream.settimeout(10)
            self.request.settimeout(10)
            selector.register(self.request, selectors.EVENT_READ, upstream)
            selector.register(upstream, selectors.EVENT_READ, self.request)
            while True:
                events = selector.select(timeout=60)
                if not events:
                    return
                for key, _ in events:
                    chunk = key.fileobj.recv(65536)
                    if not chunk:
                        return
                    key.data.sendall(chunk)

class BoundedThreads:
    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)
    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

class UnixServer(BoundedThreads, socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
class TcpServer(BoundedThreads, socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

if args.listen == 'unix':
    if os.path.exists(args.unix):
        raise SystemExit('Refusing to replace an existing relay socket')
    server = UnixServer(args.unix, Forward)
    os.chmod(args.unix, 0o600)
else:
    server = TcpServer((args.tcp_host, args.tcp_port), Forward)
with server:
    server.serve_forever()
