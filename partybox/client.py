import vlc
import socket
import time
import json
import logging
import select

class PartyBoxClient(object):

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._player = vlc.MediaPlayer('rtp://@:{}'.format(port))


    def play(self):
        self._player.play()


    def stop(self):
        self._player.stop()


    def pause(self):
        self._player.pause()


    @property
    def volume(self):
        return self._player.audio_get_volume()

    @volume.setter
    def volume(self, value):
        if not 100 > value > 0:
            raise ValueError('Volume must be between 0 and 100.')
        self._player.audio_set_volume(value)


    def connect(self):
        """
        Open up a socket connection to the host
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port,))
        while True:
            msg = s.recv(1024)
            print msg


class NetworkListener(object):
    """
    Listens on the local network for any PartyBox servers.
    """

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



#Port to listen on
PORT = 8234

#Create VLC stuff
instance = vlc.Instance()
player = vlc.MediaPlayer(instance)

#UDP listen
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('224.0.0.1', PORT))

server_ip = None

while True:
    data, addr = s.recvfrom(1024)

    try:
        data = json.loads(data)
        if 'PARTYBOX' in data:
            print("Found server - {}".format(addr[0]))
            server_ip = addr[0]
            s.close()
            break

    except ValueError:
        continue

#Now try and connect to the server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((server_ip, PORT))

#Set the media for vlc
media = vlc.Media("rtp://{0}:{1}".format(server_ip, PORT))
player.set_media(media)

while True:
    data = s.recv(1024)
    print(data)
    if 'SOUT UPDATED' in data:
        print("Starting stream")
        print player.play()
    elif 'RESTART' in data:
        print("Restarting stream")
        player.stop()
        player.play()
    elif 'VOLUME' in data:
        print("Setting volume")
        volume = data.split(" ")[1]
        player.audio_set_volume(int(volume))
    # import pdb; pdb.set_trace()
        print player.get_state()


