import socket
import threading
import logging
import time
import json
import select
import vlc

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
    def __init__(self, address, message, interval=1):
        """

        :param tuple address: The host or multicast address to send packets to.
        :param dict msg: Message to broadcast.
        :param int interval: The time interval in seconds between each packet.
        """
        self._timer = None
        self.is_running = False
        self.log = logging.getLogger('UDPAnnounce')
        self.start_time = None
        self._message = message
        self._address = address
        self._interval = interval
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _broadcast(self):
        """
        Sends the UDP packet to the specified port.
        """
        self.socket.sendto(json.dumps(self._message).encode('UTF-8'), self._address)
        self.log.debug('Broadcast packet sent {}'.format(self._address))

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
        :param dict message: Message to broadcast.
        """
        if not self.is_running:
            self._timer = threading.Timer(self._interval, self._run)
            self._timer.daemon = True
            self._timer.start()
            self.is_running = True
            self.start_time = time.time()

    def stop(self):
        """
        Stops the server broadcasting.1
        """
        self._timer.cancel()
        self.is_running = False
        self.start_time = None


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

    def serve_forever(self, poll_interval=0.5):
        """
        Starts announcing over UDP when the TCPServer is running.
        """
        self.announcer.start()
        socketserver.TCPServer.serve_forever(self, poll_interval)


    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        """
        :param server_address: The host address, usually '0.0.0.0'
        :param RequestHandlerClass: The handler class
        :param bind_and_activate: Whether to call bind and activate on the server.
        """
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.log = logging.getLogger('server')
        self.clients = {}

        msg = {
            'PARTYBOX': {
                'TYPE': 'BROADCAST',
                'ALIVE_SINCE': time.time(),
            }
        }
        #Setup Announcer
        self.announcer = UDPAnnounce(("224.0.0.1", self.server_address[1]), msg)

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


    def shutdown(self):
        self.announcer.stop()
        socketserver.TCPServer.shutdown()



class StreamingServer(object):
    """
    Controls starting and stopping both the TCP server and UDP broadcasting
    """

    def __init__(self, control_port, media_port, name=None):
        """

        :param control_port: The port to control clients over
        :param media_port: Port to stream on.
        :param name: The name of the server.
        """
        self.control_port = control_port
        self.media_port = media_port
        if name:
            self.name = name
        else:
            self.name = "PartyBox"
        self.server = None
        self.server_thread = None
        self.announcer = UDPAnnounce("224.0.0.1", control_port, self)


    def start(self):
        """
        Start the TCP server and UDP broadcasting
        """
        if not self.server:
            self.server = TCPServer(("0.0.0.0", self.control_port), ThreadedTCPRequestHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            logging.info('Partybox server started.')
            self.announcer.start()
            logging.info('Announcing server started.')
        else:
            logging.warning('Server is already running')


    def stop(self):
        """
        Stop the TCP server and UDP broadcasting
        """
        if not self.server:
            raise Exception('Server is already stopped')
        else:
            self.server.shutdown()
            self.server = None
            logging.info('Server stopped')
            self.announcer.stop()
            logging.info('Announcing server stopped')




if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    server = TCPServer(("0.0.0.0", 7773), ThreadedTCPRequestHandler)
    server.serve_forever()


#
# data = {
#             'PartyBox': {
#                 'type': 'broadcast',
#                 'time': time.time(),
#                 'name': self.partybox_server.name,
#                 'media_port': self.partybox_server.media_port,
#             }
#         }