import asyncore
import socket
import logging
import config
import json

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('client')

#First listen for any partybox hosts
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('0.0.0.0', config.BROADCAST_PORT))

host = None

log.debug('Starting listening for hosts on port {}'.format(config.BROADCAST_PORT))

while True:
    data, addr = s.recvfrom(1024)
    log.debug('Received data from {}'.format(addr))
    try:
        data = json.loads(data)
    except ValueError as e:
        log.warning('Could not decode broadcast data from {}'.format(addr))

    if data['type'] == 'PartyBoxAnnounce':
        host = data
        log.info('Found host {0} at {1}:{2}'.format(host['id'], host['host'], host['port']))
        break


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((host['host'], host['port']))

log.info('Connected to host at {0}:{1}'.format(host['host'], host['port']))

while True:
    data = s.recv(1024)
    log.debug('Received TCP packet')