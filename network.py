import subprocess
import re

class ARPException(Exception):
    pass

class HostResolutionException(Exception):
    pass

class NetworkUtilsException(Exception):
    pass

class NetworkUtils():
    """
    A collection of utility methods for general network tasks.
    """

    @classmethod
    def _get_mac_address(cls, host):
        """
        Searches the arp table for a hostname, returns the mac address.
        :param str host: Host to search for.
        :return: MAC address for host.
        :rtype: str
        """
        cls.send_ping(host)
        cmds = ['arp', '-n', host]
        p = subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = p.communicate()
        if result[1]:
            raise HostResolutionException(result[1])
        if 'no entry' in result[0]:
            raise ARPException('{} not in ARP table'.format(host))

        mac = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})", result[0]).groups()[0]
        return mac

    @classmethod
    def get_mac_address(cls, host):
        """
        Returns the mac address for a host on the same subnet.
        :param str host: Host to retrieve mac address.
        """
        #Ping the host so it appears in arp table.
        cls.send_ping(host)
        #Get mac from arp table.
        return cls._get_mac_address(host)

    @classmethod
    def active_device(cls):
        """
        Returns the name of the current active network interface.
        :returns: The network interface name
        :rtype: str
        """
        cmd = ['route', 'get', '224.0.0.1']
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        result = p.communicate()
        if result[1]:
            raise NetworkUtilsException(result[1])
        else:
            for line in result[0].splitlines():
                if 'interface:' in line:
                    return line.split(':')[1].strip()


    @classmethod
    def send_ping(cls, host):
        """
        Sends a single ping to a host. Raises a HostResolutionException if the host cannot be
        reached.
        :param str host: Hostname or IP to ping
        """
        cmd = ['ping', '-c', '1', host]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = p.communicate()
        if result[1]:
            raise HostResolutionException(result[1])



print NetworkUtils.active_device()