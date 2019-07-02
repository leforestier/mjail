from ipaddress import IPv4Network, IPv6Network
from mjail.cmd_helpers import output
from mjail.settings import cloned_if
import re
from subprocess import CalledProcessError

_ip_reg = r'\d+\.\d+\.\d+\.\d+'
_ip6_reg = r'[0123456789abcdefABCDEF:]+'

class NoJailNetwork(Exception):
    pass

class NoIPv4JailNetwork(NoJailNetwork):
    pass

class NoIPv6JailNetwork(NoJailNetwork):
    pass

def jails_network4():
    try:
        cloned_if_params = output('sysrc', '-n', 'ifconfig_%s' % cloned_if())
    except CalledProcessError:
        raise NoIPv4JailNetwork
    else:
        gd = (
            re.match(
                r'^inet\s+(?P<inet>{ip_reg})\s+netmask\s+(?P<netmask>{ip_reg})'.format(ip_reg = _ip_reg),
                cloned_if_params
             )
            .groupdict()
        )
        return IPv4Network((gd['inet'], gd['netmask']), strict = False)

def jails_network6():
    try:
        cloned_if_params = output('sysrc', '-n', 'ifconfig_%s_ipv6' % cloned_if())
    except CalledProcessError:
        raise NoIPv6JailNetwork
    else:
        gd = (
            re.match(
                r'^inet6\s+(?P<inet6>{ip6_reg})\s+prefixlen\s+(?P<prefixlen>\d+)'.format(ip6_reg = _ip6_reg),
                cloned_if_params
             )
            .groupdict()
        )
        return IPv6Network(gd['inet6'] + '/' + gd['prefixlen'], strict = False)
