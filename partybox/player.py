class ClientManager(object):

    def __init__(self, control_port, media_port, bitrate=320, ):
        self.control_port = control_port
        self.media_port = media_port
        self.bitrate = bitrate


    def _sout_command(self):
        clients = self._server_manager.clients
        for client in clients:
            cmd = "dst=rtp{{access={0},mux=ts,dst={1},port={2}}}".format(
                'tcp', client.host, client.port)
            clients.append(cmd)
        cmd = "dst=rtp{{access={0},mux=ts,dst={1},port={2}}}".format(
                'udp', '224.0.0.1', self.media_port)
        return ":sout=#transcode{{acodec=mp3,ab=320}}: duplicate{{{0}}}".format(",".join(clients))




class StreamServer(object):
    """
    This needs to somehow implement some transparent API to add/remove clients.
    1. If a track is playing then pause the stream
    2. store the current position.
    3. dispose of the media object
    4. create a new media object with the updated clients
    5. change position
    6. continue playback
    """

    def __init__(self):
        self.clients = []