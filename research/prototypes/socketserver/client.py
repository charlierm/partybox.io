import socket
import threading
import logging
import time
import json

try:
    import SocketServer as socketserver
    import Queue as queue
except ImportError:
    import socketserver
    import queue

class NodeAnnouncer(object):

    def __init__(self, port):
        self.port = port
        self.thread = None
        self._running = False
        self.log = logging.getLogger('Announcer')

    def start(self):
        self._running = True
        if not self.thread:
            self.thread = threading.Thread(target=self._start)
            self.thread.daemon = True
        self.thread.start()

    def _start(self):
        multicast = '224.0.0.1'
        self.log.info('Starting broadcasting location on {0}:{1}'.format(multicast, self.port))
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        host = socket.gethostbyname(socket.gethostname())

        while self._running:
            #TODO: Need to set headers so clients know its a PartyBox host.
            payload = {'type': 'PartyBoxAnnounce',
                       'id': '12345',
                       'host': host,
                       'port': port}
            s.sendto(json.dumps(payload).encode('UTF-8'), (multicast, self.port))
            self.log.debug('Broadcast packet sent on port {}'.format(self.port))
            time.sleep(5)

    def stop(self):
        self._running = False
        self.thread = None

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def setup(self):
        self.server.clients[self.client_address] = self
        setattr(self, 'outbox', queue.Queue())
        setattr(self, 'log', logging.getLogger(__name__))

    def handle(self):
        while True:
            msg = self.outbox.get(block=True)
            self.request.sendall(msg)

    def finish(self):
        self.log.debug('Request finished or closed by client')



class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.log = logging.getLogger('server')
        self.clients = {}

    def finish_request(self, request, client_address):
        self.log.debug('Received request from {0}:{1}'.format(client_address[0], client_address[1]))
        self.RequestHandlerClass(request, client_address, self)

    def broadcast(self, message):
        self.log.debug('Sending message to {} clients'.format(len(self.clients)))
        for address, handler in self.clients.items():
            handler.outbox.put(message)

    def handle_error(self, request, client_address):
        self.log.warning('Lost connection to client {0}:{1}'.format(client_address[0], client_address[1]))
        try:
            del self.clients[client_address]
        except KeyError:
            self.log.warning('Could not remove handler from client list {}'.format(client_address))
        self.log.debug('Removed client from client list')

if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    # Port 0 means to select an arbitrary unused port
    HOST, PORT = "0.0.0.0", 0



    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    ip, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    logging.debug('Server started {0}:{1}'.format(ip, port))

    announcer = NodeAnnouncer(port=port)
    announcer.start()

    while True:
        server.broadcast("This is a test {}\n".format(time.time()))
        time.sleep(5)