import socket
import threading
import logging
import time
import json
import select

import vlc
import media
import decorators

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
        self.queue = queue.Queue()
        self.log = logging.getLogger('Request')

    def handle(self):
        """
        Handles the request, continuously checks the outbox queue pushing any messages to the client. Blocks until
        the connection is explicitly closed or an exception is raised.
        """
        while True:
            msg = self.queue.get(block=True)
            self.request.sendall(msg)

    def finish(self):
        """
        Called when the client closes the connection like a good boy.
        """
        self.log.debug('Request finished or closed by client')
        self.server.remove_client()


    def message(self, msg):
        """
        Sends a message to the client
        """
        self.queue.put(msg)


class TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    A publish/subscribe server using SocketServer. Allows the server to push messages out to clients.
    Clients are pinged every second to ensure they're still connected. Each connection is handled in a seperate
    thread. Messages are pushed onto a queue.
    """

    #TODO: Should periodically ping to ensure all clients are alive.

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
        self._clients = {}

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
        socketserver.TCPServer.finish_request(self, request, client_address)

    def message_all(self, message):
        """
        Sends a message to all connected clients.
        :param str message: The message to send.
        """
        self.log.debug('Sending message to {} clients'.format(len(self._clients)))
        for address, handler in self._clients.items():
            handler.message(message)

    def remove_client(self, client_address):
        """
        Removes the client from the client list, closing the connection if required. The client may have already been
        removed if the client closes properly.
        :param tuple client_address: The host,port tuple
        """
        try:
            self._clients[client_address].request.close()
            del self._clients[client_address]
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


    @property
    def clients(self):
        """
        List of connected clients
        """
        return self._clients


    def shutdown(self):
        self.announcer.stop()
        socketserver.TCPServer.shutdown()



class RDPConsumer(object):
    """
    A simple RDP player.
    """
    pass


class MediaServer(object):
    """
    Plays music and streams it to clients.
    """

    def __init__(self, media_port=7775, comm_port=7776):
        #Start the TCP server
        self.server = TCPServer(("0.0.0.0", comm_port), ThreadedTCPRequestHandler)
        t = threading.Thread(target=self.server.serve_forever)
        t.daemon = True
        t.start()
        #Setup vlc
        self.instance = vlc.Instance()
        self._player = vlc.MediaPlayer(self.instance)
        self._port = media_port
        self._queue = media.Queue()
        self._log = logging.getLogger('MediaServer')
        self._setup_events()
        self._now_playing = None
        self.history = []


    @property
    def now_playing(self):
        """
        The media item currently playing
        """
        return self._now_playing

    @property
    def queue(self):
        """
        :rtype : media.Queue
        """
        return self._queue

    @decorators.synchronized
    def previous(self):
        """
        Plays the most recent track in history
        """
        #Get last track and move now playing back into queue
        try:
            media = self.history.pop()
            if self.now_playing:
                self.queue.insert(0, self.now_playing)
        except IndexError:
            self._log.warning("No tracks in history to load")
            return

        #Load the media
        m = vlc.Media(media.get_uri())
        self._player.set_media(m)
        self._now_playing = media

    @decorators.synchronized
    def next(self):
        """
        Skips to the next track in the Queue
        """
        #Move now playing to history
        if self.now_playing:
            self.history.append(self.now_playing)

        try:
            media = self._queue.pop(0)
        except IndexError:
            #No tracks left in the queue so stop
            self.stop()
            return

        #Create new player and attach events
        paused = self.paused
        self._player = vlc.MediaPlayer(self.instance)
        self._setup_events()

        #Load media
        m = vlc.Media(media.get_uri())
        self._player.set_media(m)
        self._now_playing = media
        if not paused:
            self.play()

    def _encountered_error(self, event):
        """
        Called when the player encounters an error, used to recover from it.
        """
        self._log.error(vlc.libvlc_errmsg())
        self.next()

    def _stopped(self, event):
        """
        Libvlc event, called when stopped. Empties queue and removes now playing.
        """
        self.queue.clear()
        self._now_playing = None
        self._player.set_media(None)

    def _end_reached(self, event):
        print("Track finished")
        print(event)
        self._log.info('Track ended')
        self.next()

    def _media_changed(self, event):
        self._log.info("Track changed: {}".format(self._player.get_media().get_mrl()))

    def _setup_events(self):
        self.events = self._player.event_manager()
        self.events.event_attach(vlc.EventType.MediaPlayerEndReached, self._end_reached)
        self.events.event_attach(vlc.EventType.MediaPlayerStopped, self._stopped)
        self.events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._encountered_error)
        self.events.event_attach(vlc.EventType.MediaPlayerMediaChanged, self._media_changed)


    def stop(self):
        if self._player.get_media():
            self.stop()

    def play(self):
        """
        Plays or resumes the current loaded media.
        """
        #Check for loaded media
        if not self._player.get_media():
            self.next()
            return

        state = self._player.get_state()
        if state == vlc.State.Ended:
            #Start next track
            self.next()

        elif state == vlc.State.Stopped:
            #Repeat the current loaded track?
            self._player.stop()
            self._player.play()

        elif state == vlc.State.Paused or state == vlc.State.NothingSpecial:
            self._player.play()

    @property
    def position(self):
        pos = self._player.get_position()
        if pos < 0:
            return None
        else:
            return pos*100

    @position.setter
    def position(self, value):
        self._player.set_position(float(value)/100)


    def pause(self):
        self._player.set_pause(True)

    @property
    def paused(self):
        if self._player.get_state() == vlc.State.Paused:
            return True
        else:
            return False

    @paused.setter
    def paused(self, value):
        self.pause()





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
    logging.basicConfig(level=logging.INFO)
    server = MediaServer()
    #Load some fucking tracks
    playlist = (
        "/Users/charlie/Music/iTunes/iTunes Media/Music/Arctic Monkeys/AM (Deluxe LP Edition)/11 Knee Socks.mp3",
        "/Users/charlie/Music/iTunes/iTunes Media/Music/Athlete/Vehicles & Animals/01 El Salvador.mp3",
        "/Users/charlie/Music/iTunes/iTunes Media/Music/Bon Iver/For Emma, Forever Ago/09 Re_ Stacks.mp3",
        "/Users/charlie/Music/iTunes/iTunes Media/Music/The Killers/Sam's Town/03 When You Were Young.mp3",
        "/Users/charlie/Music/iTunes/iTunes Media/Music/Of Monsters and Men/My Head Is an Animal/13 Numb Bears.mp3",
        "/Users/charlie/Music/iTunes/iTunes Media/Music/Rhye/Woman/02 The Fall.mp3",
        "/Users/charlie/Music/iTunes/iTunes Media/Music/Tycho/Dive/01 A Walk.mp3",
        "/Users/charlie/Music/iTunes/iTunes Media/Music/Snow Patrol/Fallen Empires/02 Called Out In The Dark.mp3"
    )
    for t in playlist:
        server.queue.append(media.TestMedia(t))

    server.queue.shuffle()
    print("loaded {} tracks".format(len(server.queue)))

    print("Play queue length: {}".format(len(server.queue)))
    print("Player state: {}".format(server._player.get_state()))
    print("Currently playing: {}".format(server.now_playing))


    server.play()
    server.position = 95
    counter = 0
    while True:
        counter +=1
        time.sleep(1)
        print("Play queue length: {}".format(len(server.queue)))
        print("History stack length: {}".format(len(server.history)))
        print("Player state: {}".format(server._player.get_state()))
        print("Currently playing: {}".format(server.now_playing))
        if counter == 20:
            server.previous()







#
# data = {
#             'PartyBox': {
#                 'type': 'broadcast',
#                 'time': time.time(),
#                 'name': self.partybox_server.name,
#                 'media_port': self.partybox_server.media_port,
#             }
#         }