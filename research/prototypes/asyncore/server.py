import asyncore
import logging
import socket
import collections
import threading
import config
import json
import time

class NodeAnnouncer(object):

    def __init__(self, interval=1):
        self.interval = interval
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
        self.log.info('Starting broadcasting location on {0}:{1}'.format(multicast, config.BROADCAST_PORT))
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        host = socket.gethostbyname(socket.gethostname())

        while self._running:
            #TODO: Need to set headers so clients know its a PartyBox host.
            payload = {'type': 'PartyBoxAnnounce',
                       'id': config.HOST_ID,
                       'host': host,
                       'port': config.MESSAGING_PORT}
            s.sendto(json.dumps(payload).encode('UTF-8'), (multicast, config.BROADCAST_PORT))
            self.log.debug('Broadcast packet sent on port {}'.format(config.BROADCAST_PORT))
            time.sleep(5)

    def stop(self):
        self._running = False
        self.thread = None


class RemoteClient(asyncore.dispatcher):

    MAX_MESSAGE_LENGTH = 1024
    log = logging.getLogger('Host')

    def __init__(self, host, socket, address):
        asyncore.dispatcher.__init__(self, socket)
        self.host = host
        self.outbox = collections.deque()

    def message(self, message):
        self.outbox.append(message)

    def handle_write(self):
        if not self.outbox:
            return
        message = self.outbox.popleft()
        if len(message) > self.MAX_MESSAGE_LENGTH:
            raise ValueError('Message too long')
        self.send(message)

    def handle_close(self):
        self.host.clients.remove(self)
        self.log.info("Client removed from list")
        self.close()

    def handle_error(self):
        self.log.error("Socket error")


class Host(asyncore.dispatcher):

    log = logging.getLogger('Host')

    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('0.0.0.0', config.MESSAGING_PORT,))
        self.listen(1)
        self.clients = []

    def handle_accepted(self, sock, addr):
        self.log.info("Accepted client at {0}:{1}".format(addr[0], addr[1]))
        self.clients.append(RemoteClient(self, sock, addr))

    def handle_accept(self):
        socket, addr = self.accept()
        self.log.info("Accepted client at {0}:{1}".format(addr[0], addr[1]))
        self.clients.append(RemoteClient(self, socket, addr))

    def broadcast(self, message):
        self.log.info("Broadcasting message: {0}".format(message))
        for client in self.clients:
            client.message(message)



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    host = Host()

    #Start loop in thread
    thread = threading.Thread(target=asyncore.loop)
    thread.daemon = True
    thread.start()

    #Start broadcasting
    announcer = NodeAnnouncer()
    announcer.start()

    thread.join()
