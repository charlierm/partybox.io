import socket
import threading
import logging
import time
import json

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
        self.server._clients[self.client_address] = self
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


    def serve_forever(self, poll_interval=0.5):
        """
        Starts announcing over UDP when the TCPServer is running.
        """
        self.announcer.start()
        socketserver.TCPServer.serve_forever(self, poll_interval)

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
        List of unique clients
        """
        clients = []
        for client in self._clients.keys():
            clients.append(client[0])
        return list(set(clients))


    def shutdown(self):
        self.announcer.stop()
        socketserver.TCPServer.shutdown()



class RDPConsumer(object):
    """
    A simple RDP player.
    """
    pass


class VLCTools(object):

    @staticmethod
    def generate_sout(clients, port):
        """
        Generates a VLC sout string for a Media object.
        :param list clients: Addresses to push stream to.
        :param int port: Port to stream on.
        """
        sout = []
        for client in clients:
            protocol = 'udp'
            cmd = "dst=rtp{{access={0},mux=ts,dst={1},port={2}}}".format(
                protocol, client, port)
            sout.append(cmd)
        sout.append("dst=rtp{{access=udp,mux=ts,dst=224.0.0.1,port={0}}}".format(port+1))
        return ":sout=#transcode{{acodec=mp3,ab=320}}: duplicate{{{0}}}".format(",".join(sout))



class MediaServer(object):
    """
    Plays music and streams it to clients.
    """

    def __init__(self, port=8234):
        #Start the TCP server
        self._server = TCPServer(("0.0.0.0", port), ThreadedTCPRequestHandler)
        t = threading.Thread(target=self._server.serve_forever)
        t.daemon = True
        t.start()
        #Setup vlc
        self.instance = vlc.Instance()
        self._player = vlc.MediaPlayer(self.instance)
        self._port = port
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

        playing = self._player.get_state() == vlc.State.Playing

        #Load the media
        m = self._get_vlc_media(media.get_uri())
        self._player.set_media(m)
        self._now_playing = media

        if playing:
            self.play()

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
            #No tracks left in the queue so return
            return None

        playing = self._player.get_state() == vlc.State.Playing

        #Stop and clear previous player
        if playing:
            self._player.stop()

        print(self._player.get_state())

        #Create new player and attach events
        self._player = vlc.MediaPlayer(self.instance)
        self._setup_events()

        #Load media
        m = self._get_vlc_media(media.get_uri())
        self._player.set_media(m)
        self._now_playing = media
        if playing:
            self.play()

    def _encountered_error(self, event):
        """
        Called when the player encounters an error, used to recover from it.
        """
        self._log.error(vlc.libvlc_errmsg())
        self.next()

    def _end_reached(self, event):
        """
        VLC callback - Track finished playing
        """
        self._log.info('Track ended')
        self.next()
        self._player.play()

    def _media_changed(self, event):
        """
        VLC callback - Media changed.
        Called when self._player has a new media set, does not always mean self.now_playing has changed.
        """
        self._log.info("Track changed: {}".format(self._player.get_media().get_mrl()))
        self._server.message_all(self._player.get_media().get_mrl() + "\n")
        self._sout_updated()

    def _sout_updated(self):
        """
        Callback - Called when the server SOUT is updated to connected clients.
        """
        self._server.message_all("SOUT UPDATED\n")

    def _setup_events(self):
        """
        Attaches events to the MediaPlayer object, called when self._player is replaced.
        """
        self.events = self._player.event_manager()
        self.events.event_attach(vlc.EventType.MediaPlayerEndReached, self._end_reached)
        self.events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._encountered_error)
        self.events.event_attach(vlc.EventType.MediaPlayerMediaChanged, self._media_changed)


    def _get_vlc_media(self, uri):
        """
        Creates a vlc_media object with the correct sout.

        :param str uri: URI to create media object with.
        :return: vlc.Media
        """
        cmd = VLCTools.generate_sout(self._server.clients, self._port)
        print cmd
        return vlc.Media(uri, cmd)


    def stop(self):
        """
        Stops current playback.
        """
        if 0 <= self._player.stop():
            self._now_playing = None
            #TODO: Now playing will be out of sync here.


    def play(self):
        """
        Plays or resumes the current loaded media.
        """
        #Check for loaded media
        if not self._player.get_media():
            self.next()
            self._player.play()
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
        """
        Current position of the player as a percentage.
        None if not playing or idle.
        """
        pos = self._player.get_position()
        if pos < 0:
            print(vlc.libvlc_errmsg())
            return None
        else:
            return pos*100

    @position.setter
    def position(self, value):
        self._player.set_position(float(value)/100)

    def pause(self):
        """
        Toggle pause for the player. If media is stopped or not loaded then
        it will have no effect.
        """
        self._player.set_pause(True)

    @property
    def paused(self):
        """
        Whether or not playback is paused. If playback is stopped
        or idle then this will not evaluate to True.
        :rtype : bool
        """
        if self._player.get_state() == vlc.State.Paused:
            return True
        else:
            return False

    @paused.setter
    def paused(self, value):
        self._player.set_pause(value)

    @property
    def volume(self):
        """
        Volume of media player as percentage.
        0 <> 100
        """
        return self._player.audio_get_volume()

    @volume.setter
    def volume(self, value):
        self._server.message_all("VOLUME {}".format(value))
        #TODO: Need to be able to control volume on each client
        self._player.audio_set_volume(value)


    @property
    def time(self):
        """
        Current positon of playback in seconds
        """
        return self._player.get_time()/1000.0

    @time.setter
    def time(self, value):
        self._player.set_time(value*1000)

    def fade_out(self):
        """
        Fades out volume and pauses media.
        """
        if self._player.get_state() == vlc.State.Playing:
            v = self.volume
            while self.volume > 0:
                self.volume -= 1
                time.sleep(0.05)
            self.pause()
            self.volume = v


    def update_stream_output(self):
        """
        Updates the list of clients the server is streaming to.
        Media will pause briefly while the media with updated output
        is loaded.
        """
        if not self._player.get_media():
            return
        playing = self._player.get_state() == vlc.State.Playing
        if playing:
            self.pause()

        pos = self.position
        uri = self.now_playing.get_uri()
        m = self._get_vlc_media(uri)
        self._player.set_media(m)

        if playing:
            self._player.play()
            self.position = pos



    def restart_clients(self):
        """
        Causes all clients to restart, usually sorts any synchronisation issues.
        """
        self._server.message_all("RESTART")







logging.basicConfig(level=logging.INFO)
server = MediaServer()
#Load some fucking tracks
playlist = (
            "http://bbcmedia.ic.llnwd.net/stream/bbcmedia_lc1_radio1_p?s=1398175066&e=1398189466&h=6f82ebdc4806c8c259ff90e63f7f482d",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/Snow Patrol/Fallen Empires/02 Called Out In The Dark.mp3",
            "http://icy-e-01.sharp-stream.com:80/tcnation.mp3",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/Arctic Monkeys/AM (Deluxe LP Edition)/11 Knee Socks.mp3",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/Athlete/Vehicles & Animals/01 El Salvador.mp3",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/Bon Iver/For Emma, Forever Ago/09 Re_ Stacks.mp3",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/The Killers/Sam's Town/03 When You Were Young.mp3",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/Of Monsters and Men/My Head Is an Animal/13 Numb Bears.mp3",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/Rhye/Woman/02 The Fall.mp3",
            "/Users/charlie/Music/iTunes/iTunes Media/Music/Tycho/Dive/01 A Walk.mp3",
)
for t in playlist:
    server.queue.append(media.TestMedia(t))


server.play()





#
# data = {
#             'PartyBox': {
#                 'type': 'broadcast',
#                 'time': time.time(),
#                 'name': self.partybox_server.name,
#                 'media_port': self.partybox_server.media_port,
#             }
#         }