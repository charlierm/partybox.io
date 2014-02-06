## libvlc

libvlc is the library behind vlc, handles the decoding, streaming and threading.

### Streaming

Transcoding xx.mp3 to 320kbs mp3 and streaming 2 TCP hosts and one UDP multicast in RTP. This can be consumed from pretty much any device.

```bash
vlc -vvv xx.mp3 --sout '#transcode{acodec=mp3, ab=320}: duplicate{
dst=rtp{mux=ts,dst=192.168.0.20,port=1234,sdp=sap,name="PartyBox"},
dst=rtp{mux=ts,dst=192.168.0.23,port=1234,sdp=sap,name="TestStream"},
dst=rtp{access=udp,mux=ts,dst=224.0.0.1,port=1233,sdp=sap,name="PartyBox"}}'
```
