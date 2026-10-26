import os
from pathlib import Path
import socket
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest

RELAY=Path(__file__).with_name('relay.py')
class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        data=self.request.recv(65536)
        self.request.sendall(b'fixed-target:'+data)
class Server(socketserver.ThreadingTCPServer):
    daemon_threads=True

class RelayTests(unittest.TestCase):
    def test_unix_relay_forwards_only_to_fixed_target_and_uses_private_socket(self):
        with tempfile.TemporaryDirectory() as directory,Server(('127.0.0.1',0),Echo) as target:
            thread=threading.Thread(target=target.serve_forever,daemon=True);thread.start()
            path=Path(directory)/'relay.sock'
            child=subprocess.Popen([sys.executable,str(RELAY),'--listen','unix','--unix',str(path),
                                    '--tcp-port',str(target.server_address[1])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if path.exists():break
                    if child.poll() is not None:self.fail('Relay stopped before becoming ready')
                    time.sleep(.01)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(2);client.connect(str(path))
                    payload=b'CONNECT unrelated.example:443 HTTP/1.1\r\nHost: unrelated.example\r\n\r\n'
                    client.sendall(payload)
                    self.assertEqual(client.recv(65536),b'fixed-target:'+payload)
            finally:
                child.terminate();child.wait(timeout=3);target.shutdown()
    def test_existing_path_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'existing';path.write_text('preserve')
            result=subprocess.run([sys.executable,str(RELAY),'--listen','unix','--unix',str(path),
                                   '--tcp-port','1'],capture_output=True,timeout=3)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(path.read_text(),'preserve')

if __name__=='__main__':unittest.main()
