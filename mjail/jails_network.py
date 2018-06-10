from ipaddress import IPv4Network
from mjail.cmd_helpers import output
from mjail.settings import cloned_if
import re

_ip_reg = r'\d+\.\d+\.\d+\.\d+'

def jails_network4():
    cloned_if_params = output('sysrc', '-n', 'ifconfig_%s' % cloned_if())
    gd = (
        re.match(
            r'^inet\s+(?P<inet>{ip_reg})\s+netmask\s+(?P<netmask>{ip_reg})'.format(ip_reg = _ip_reg),
            cloned_if_params
         )
        .groupdict()
    )
    return IPv4Network((gd['inet'], gd['netmask']), strict = False)
