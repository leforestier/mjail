from mjail.cmd_helpers import cmd, output, to_tempfile, rc_conf_mod
from mjail.get_jail_conf import get_jail_conf
from mjail.settings import cloned_if
from mjail.pf_conf_split import pf_conf_split
from mjail.jails_network import jails_network4
import os
import os.path
import re
from subprocess import CalledProcessError
    
def pf_is_running():
    return output('service', 'pf', 'status').startswith(
        'Status: Enabled'
    )

_ip_reg = r'\d+\.\d+\.\d+\.\d+'
  
def interface_ip4():
    strg = output('sysrc', '-n', 'ifconfig_%s' % cloned_if()).strip() 
    return re.match(
        '^inet\s(?P<ip4>{ip_reg})\s*(netmask {ip_reg})?$'.format(ip_reg = _ip_reg),
        strg
    ).groupdict()['ip4']
    
class NoDefaultGatewayError(Exception):
    pass   
    
def get_ext_if():
    route_table = output('netstat', '-rn')
    try:
        return next(
            line[3]
            for line in (
                l.split() for l in route_table.split('\n')
            )
            if (
                len(line) >= 4
                and
                line[0] == 'default'
                and
                re.match(r'^%s$' % _ip_reg, line[1])
            )
        )
    except StopIteration:
        raise NoDefaultGatewayError
        
class LocalUnboundManager(object):
    _conf_dir = '/var/mjail/generated_confs/local-unbound/'
    _conf_file = os.path.join(_conf_dir, 'unbound.conf')
    
    @classmethod
    def enable(cls):
        cmd('mkdir', '-p', cls._conf_dir)
        temp_path = to_tempfile(
            cls._conf(),
            prefix = cls._conf_file
        )
        os.rename(temp_path, cls._conf_file)
        cmd('local-unbound-setup', '-C', cls._conf_dir)
        
    @classmethod
    def _conf(cls):
        jails_net = jails_network4()
        return (
            'server:\n'
            '   access-control: {net4} allow\n'
            '   access-control: 127.0.0.0/8 allow\n'
            '   interface: {ip4}\n'
            '   interface: 127.0.0.1\n'
        ).format(
            net4 = jails_net,
            ip4 = jails_net.network_address + 1
        )
    

    
class PFManager(object):

    _anchor_conf_file = '/var/mjail/generated_confs/mjail-pf.conf'
    _comment = "# added by mjail, don't modify this line by hand"
    _load_anchor = 'load anchor mjail from "%s" %s' % (_anchor_conf_file, _comment)
    _insert_anchor_filter = "anchor mjail %s" % _comment
    _insert_anchor_nat = "nat-anchor mjail %s" % _comment
    _insert_anchor_rdr = "rdr-anchor mjail %s" % _comment
    
    @classmethod
    def pf_conf_path(cls):
        try:
            return output('sysrc', '-n', 'pf_rules').strip()
        except CalledProcessError as exc:
            if exc.returncode == 1:
                return '/etc/pf.conf'
            else:
                raise
                       
    @classmethod
    def enable(cls):
        #rc_conf_mod('gateway_enable=YES')
        #rc_conf_mod('net.inet.ip.forwarding=1')
        pf_conf_path = cls.pf_conf_path()
        try:
            pf_conf = [
                line.rstrip()
                for line in open(pf_conf_path).readlines()
                if not line.endswith(cls._comment + "\n")
            ]
        except FileNotFoundError:
            pf_conf = []
        start, translation_rules, filter_rules = pf_conf_split(pf_conf)
        new_conf = (
            start
            +
            [cls._load_anchor, cls._insert_anchor_nat, cls._insert_anchor_rdr]
            +
            translation_rules
            +
            filter_rules
            +
            [cls._insert_anchor_filter]
        )
        new_conf = '\n'.join(new_conf)
        if not new_conf.endswith('\n'): # required by the pf configuration parser
            new_conf += '\n'
        cmd('mkdir', '-p', os.path.dirname(cls._anchor_conf_file))
        if not os.path.exists(cls._anchor_conf_file):
            cls.overwrite_anchor_conf()
        temp_path = to_tempfile(new_conf, prefix = pf_conf_path)
        cmd('pfctl', '-vnf', temp_path) # checking the new conf before replacing the old conf with it
        os.rename(temp_path, pf_conf_path)
        
        if pf_is_running():
            cmd('pfctl', '-f', pf_conf_path)
        else:
            rc_conf_mod('pf_enable=YES')
            rc_conf_mod('pf_rules=%s' % pf_conf_path)
            cmd('service', 'pf', 'start')

    
            
    @classmethod
    def disable(cls):
        pf_conf_path = cls.pf_conf_path()
        try:
            pf_conf = [
                line
                for line in open(pf_conf_path).readlines()
                if not line.endswith(cls._comment + "\n")
            ]
        except FileNotFoundError:
            pass
        else:
            new_conf = ''.join(pf_conf)
            if not new_conf.endswith('\n'):
                new_conf += '\n'
            temp_path = to_tempfile(new_conf, prefix = pf_conf_path)
            cmd('pfctl', '-vnf', temp_path)
            os.rename(temp_path, pf_conf_path)
            if pf_is_running():
                 cmd('pfctl' '-f', pf_conf_path)
                 
    @classmethod
    def _anchor_conf(cls):
        ext_if = get_ext_if()
        filter_rules = []
        translation_rules = []
        jail_conf = get_jail_conf()
        jails = [
            jail_block
            for name, jail_block in jail_conf.jails()
            if (
                jail_block.get('$mjail_managed') == 'yes'
                and
                jail_block.get('ip4.addr')
            )
        ]
        cif = cloned_if()
        def append_jail_line(rules, jail, *strgs, **formats):
            for strg in strgs:
                rules.append(
                    strg.format(
                        ext_if = ext_if,
                        cif = cif,
                        ip4 = jail['ip4.addr'],
                        **formats
                    )
                )
        for jail in jails:
            append_jail_line(
                translation_rules,
                jail,
                'nat on {ext_if} inet from {ip4} to any -> ({ext_if})'
            )
            append_jail_line(
                filter_rules,
                jail,
                'pass quick on {cif} inet proto udp from {ip4} to ({cif}) port 53',
                'pass quick on {cif} inet proto tcp from {ip4} to ({cif}) port 53'
            )
            for key in jail:
                if key.startswith('$mjail_rdr_'):
                    proto, host_port = key[len('$mjail_rdr_'):].split('_')
                    assert proto in ('udp', 'tcp')
                    host_port = int(host_port)
                    jail_port = int(jail[key])
                    append_jail_line(
                        translation_rules,
                        jail,
                        'rdr pass on {ext_if} inet proto {proto} from any to ({ext_if}) port {host_port} -> {ip4} port {jail_port}',
                        proto = proto,
                        host_port = host_port,
                        jail_port = jail_port,
                    )
        filter_rules.append(
            'pass quick on {cif} from ({cif}) to ({cif}:network)'.format(cif = cif),
            # TODO: allow only the host to access the jails but not the jails between them?
            # (could be an option in `mjail init`)
        )
        ruleset = translation_rules + filter_rules + ['']
        return '\n'.join(ruleset)
        
    @classmethod
    def overwrite_anchor_conf(cls):
        temp_path = to_tempfile(cls._anchor_conf(), prefix = cls._anchor_conf_file)
        cmd('pfctl', '-vnf', temp_path)
        os.rename(temp_path, cls._anchor_conf_file)
        
    @classmethod
    def refresh_anchor(cls):
        cls.overwrite_anchor_conf()
        cmd('pfctl', '-a', 'mjail', '-F', 'all', '-f',  cls._anchor_conf_file)

        
