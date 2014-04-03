##Communication

Communication between clients and server will use both TCP and UDP. UDP drops too many packets over WiFi for it to be used for critical messages and media transmission. TCP will be used to push control messages to clients, such as 'stop'. UDP will be used to broadcast the server availability and media information. 

Provisionally the following ports will be used:

* 7775 (UDP) - This will be used by the server, broadcasting its location, uptime and current media information.
* 7775 (TCP) - After the client receives the UDP packet it will attempt to connect to the server by UDP. This socket will be used to push commands to the client, volume, play, pause etc.
* 7776 (TCP) - RTP will be streamed to clients on this port.
* 7776 (UDP) - Streaming of RTP over UDP for ethernet connected clients.


### Broadcasting
A server will broadcast its location and availability over UDP, the most effective time interval will have to be established (Provisionally 1 second). UDP packets will be pure JSON less than 1024 bytes, so only one packet will need to be send per message.

#### Initial Broadcast Packet Design
The following information will need to be included in the broadcast packet:

* Time - Timestamp of when the packet was sent.
* Uptime - Uptime of the server.
* Name - The human name of the server.  
* TCP Port - The port being used for TCP RTP.
* UDP Port - The port being used for multicast UDP RTP.
* TCP communication PORT - The port being used to control clients.
* Type - The type of message, in this case 'broadcast'

An example packet will look like this:

```json
{
  "partbox": {
      "type": "broadcast",
    "uptime": 3423,
    "name": "Charlie's Party",
    "tcp_port": 7775,
    "udp_port": 7775,
    "comms_port": 7776
  }
}
```

### Media Broadcasting
It is important clients are aware of what they're playing, this allows mobile devices acting as clients to visually display information. This will be broadcast over UDP on. The following information will be useful for clients:

* Time - Timestamp of when the packet was sent 
* Type - The type of message, in this case 'playing'
* Backend - The name of the backend.
* Title - Title of the track/stream.
* Artist - Artist of track.
* Album - Album name if relevant.
* Album art - Image relating to the track.

Somehow the album art needs to either be transmitted with the packet, alternatively images could be pulled from the internet, however this would require external network access.



