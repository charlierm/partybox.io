import vlc
import socket
import time
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


if __name__ == '__main__':
    client = PartyBoxClient('localhost', 7775)
    client.play()
    while True:
        time.sleep(1)


