import socket
import threading
import logging
import time
import json
import select

try:
    import SocketServer as socketserver
    import Queue as queue
except ImportError:
    import socketserver
    import queue


class UDPAnnounce(object):
    """
    Periodically sends UDP packets to and address with a defined interval time. Broadcasting can
    be stopped and started by calling stop() and start() respectively. The address and port can be changed
    whilst the Announcer is running.

    """
    def __init__(self, address, port, interval=1):
        """

        :param str address: The host or multicast address to send packets to.
        :param int port: The port to use.
        :param int interval: The time interval in seconds between each packet.
        """
        self._timer = None
        self.interval = interval
        self.is_running = False
        self.socket = None
        self.port = port
        self.address = address
        self.setup()
        self.log = logging.getLogger('Broadcaster')

    def setup(self):
        """
        Sets up the UDP socket, this can be overridden.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


    def _broadcast(self):
        """
        Sends the UDP packet to the specified port.
        """
        payload = {'type': 'PartyBoxAnnounce',
                   'id': '12345'}
        self.socket.sendto(json.dumps(payload).encode('UTF-8'), (self.address, self.port))
        self.log.debug('Broadcast packet sent on port {}'.format(self.port))

    def _run(self):
        """
        Called periodically by the timer.
        """
        self.is_running = False
        self.start()
        self._broadcast()

    def start(self):
        """
        Starts broadcasting on UDP.
        """
        if not self.is_running:
            self._timer = threading.Timer(self.interval, self._run)
            self._timer.daemon = True
            self._timer.start()
            self.is_running = True

    def stop(self):
        """
        Stops the server broadcasting.
        """
        self._timer.cancel()
        self.is_running = False


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def setup(self):
        """
        Sets up the handlers outbox queue and log, because the handler blocks finish_request until it closes we have
        to add the handler to the clients list in this method. Its a bit backwards but it works!
        """
        self.server.clients[self.client_address] = self
        self.outbox = queue.Queue()
        self.log = logging.getLogger('Request')

    def handle(self):
        """
        Handles the request, continuously checks the outbox queue pushing any messages to the client. Blocks until
        the connection is explicitly closed or an exception is raised.
        """
        while True:
            msg = self.outbox.get(block=True)
            self.request.sendall(msg)

    def finish(self):
        """
        Called when the client closes the connection like a good boy.
        """
        self.log.debug('Request finished or closed by client')
        self.server.remove_client()


class TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    A publish/subscribe server using SocketServer. Allows the server to push messages out to clients.
    Clients are pinged every second to ensure they're still connected. Each connection is handled in a seperate
    thread. Messages are pushed onto a queue.
    """

    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        """
        :param server_address: The host address, usually '0.0.0.0'
        :param RequestHandlerClass: The handler class
        :param bind_and_activate: Whether to call bind and activate on the server.
        """
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.log = logging.getLogger('server')
        self.clients = {}

    def finish_request(self, request, client_address):
        """
        Called to initialise the handler for a request.
        """
        self.log.info('Connection from {0}:{1}'.format(client_address[0], client_address[1]))
        self.RequestHandlerClass(request, client_address, self)

    def send(self, message):
        """
        Sends a message to all connected clients.
        :param str message: The message to send.
        """
        self.log.debug('Sending message to {} clients'.format(len(self.clients)))
        for address, handler in self.clients.items():
            handler.outbox.put(message)

    def remove_client(self, client_address):
        """
        Removes the client from the client list, closing the connection if required. The client may have already been
        removed if the client closes properly.
        :param tuple client_address: The host,port tuple
        """
        try:
            self.clients[client_address].request.close()
            del self.clients[client_address]
            self.log.info('Client removed {}'.format(client_address))
        except KeyError as e:
            self.log.info('Could not remove client from list')

    def handle_error(self, request, client_address):
        """
        Handles an exception raised from the handler. Used to remove the client from the client list if the connection
        is no longer open.
        """
        self.log.warning('Lost connection to client {0}:{1}'.format(client_address[0], client_address[1]))
        self.remove_client(client_address)

class PartyBoxHost(object):

    def __init__(self, address, port, id):
        self.address = address
        self.port = port
        self.id = id

    def __eq__(self, other):
        if self.id == other.id:
            return True
        else:
            return False


class PartyBoxListener(object):

    def __init__(self, port, callback=None):
        """
        Sets up the socket for listening
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', port))
        self.socket.setblocking(0)
        self.log = logging.getLogger('PartyBox')
        self.callback = callback



    def _listen(self, timeout=10):
        """
        Starts listening for partybox hosts
        """
        self.log.info('Listening for party hosts for {} seconds'.format(timeout))

        start = time.time()
        #TODO: This is poorly implemented, might be better to constantly listen for any hosts.
        while time.time() - start < timeout:
            ready = select.select([self.socket], [], [], 1)

            if ready[0]:
                data, addr = self.socket.recvfrom(1024)

                try:
                    data = json.loads(data)
                    return addr[0]

                except ValueError as e:
                    self.log.debug('Could not decode broadcast data from {}'.format(addr))
                    return None


class PartyBoxServer():

    def __init__(self, control_port, media_port, name=None):
        self.control_port = control_port
        self.media_port = media_port
        if name:
            self.name = name
        else:
            self.name = "PartyBox"
        self.server = None
        self.server_thread = None



    def start(self):
        if not self.server:
            self.server = TCPServer(("0.0.0.0", self.control_port), ThreadedTCPRequestHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            logging.info('Partybox server started.')
        else:
            logging.warning('Server is already running')


    def stop(self):
        if not self.server:
            raise Exception('Server is already stopped')
        else:
            self.server.shutdown()
            self.server = None

    @property
    def clients(self):
        clients = []
        for client in self.server.clients:
            clients.append(client[0])
        return set(clients)




if __name__ == "__main__":
    #Server is started so begin listening for any party box clients, 30 seconds should do it.

    #Start the server
    server = PartyBoxServer()
    server.start()
    serv
