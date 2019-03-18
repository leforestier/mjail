from ipaddress import IPv4Network, IPv4Address
import jailconf
from mjail.cd import cd
from mjail.cmd_helpers import cmd, output, rc_conf_mod, to_tempfile
from mjail.get_jail_conf import get_jail_conf
from mjail.settings import cloned_if
from mjail.jails_network import jails_network4
from mjail.sshd_conf import SSHDConf
import os, os.path
import re
import shutil
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory

from mjail.services import PFManager, LocalUnboundManager

class CompatibilityException(Exception):
    pass

def check_compatibility():
    for service in ('local_unbound', 'pf'):
        if not output('sysrc', '-n', '%s_enable' % service).strip() == 'YES':
            raise CompatibilityException(
                "mjail requires {service}\n"
                "run:\n"
                "    sysrc {service}_enable=YES\n"
                .format(service = service)
            )

def init(ip4_network):
    check_compatibility()
    address4 = str(ip4_network.network_address + 1)
    netmask = str(ip4_network.netmask)
    rc_conf_mod('cloned_interfaces+=%s' % cloned_if())
    cmd('service', 'netif', 'cloneup')
    rc_conf_mod('ifconfig_%s=inet %s netmask %s' % (cloned_if(), address4, netmask))
    cmd('ifconfig', cloned_if(), 'inet', address4, 'netmask', netmask)
    rc_conf_mod('jail_enable=YES')
    cmd(
        'mkdir', '-p', 
        '/var/mjail/instances/',
        '/var/mjail/releases/',
        '/var/mjail/generated_confs/'
    )
    cmd('chmod', '700', '/var/mjail/instances/', '/var/mjail/releases/')
    cmd('chmod', '755', '/var/mjail/', '/var/mjail/generated_confs/')
    try:
        jail_conf = jailconf.load('/etc/jail.conf')
    except FileNotFoundError:
        jail_conf = jailconf.JailConf()
    jail_conf['exec.start'] = '"/bin/sh /etc/rc"'
    jail_conf['exec.stop'] = '"/bin/sh /etc/rc.shutdown"'
    jail_conf['exec.clean'] = True
    jail_conf['mount.devfs'] = True
    jail_conf['path'] = '"/var/mjail/instances/$name"'
    jail_conf.write('/etc/jail.conf')
    release = Release()
    if not release.built():
        release.build()
    LocalUnboundManager.enable()
    PFManager.enable()

    
class Release(object):

    @classmethod
    def current_release(cls):
        return output('uname', '-r').split('-RELEASE')[0] + '-RELEASE'
    
    def __init__(self, release = None):
        self._release = release or self.__class__.current_release()
        
    def __str__(self):
        return self._release

    def _component_url(self, component):
        return (
            'http://ftp.freebsd.org/pub/FreeBSD/releases/amd64/amd64/{release}/{component}'
            .format(
                release = self._release,
                component = component 
            )
        )
    
    @property
    def directory(self):
        return os.path.join('/var/mjail/releases/', self._release)
        
    def built(self):
        return os.path.exists(os.path.join(self.directory, 'bin/echo'))
        
    def build(self):
        components = ['base.txz', 'lib32.txz']
        if int(re.match(r'^\d+', self._release).group(0)) < 12: # There's no longer a doc.txz in FreeBSD 12
            components.append('doc.txz')
        cmd('mkdir', '-p', self.directory)
        with TemporaryDirectory() as tempdir:
            with cd(tempdir):
                for component in components:
                    cmd('fetch', self._component_url(component), '-o', component)
                    cmd('tar', 'xvf', component, '-C', self.directory)
                freebsd_update(self.directory, unattended = True)
                cmd(
                    'freebsd-update', '-b', self.directory, 'IDS',
                )
                
def freebsd_update(directory, unattended):
    if unattended:
        env = os.environ.copy()
        env['PAGER'] = 'cat'
        cmd(
            'freebsd-update', '-b', directory, 'fetch',
            env = env   
        )
        try:
            cmd(
                'freebsd-update', '-b', directory, 'install',
                env = env
            )
        except CalledProcessError as exc:
            if exc.returncode == 1: # FreeBSD offers no way to tell if that's because there was no update to install
                pass                # or if it comes from another problem
            else:
                raise
    else:
        cmd('freebsd-update', '-b', directory, 'fetch', 'install')
            
_ip_reg = r'\d+\.\d+\.\d+\.\d+'

def available_ip4():
    jails_net = jails_network4()
    taken_ip4s = set([jails_net.network_address + 1])
    jail_conf = get_jail_conf()
    for _, jail_block in jail_conf.jails():
        try:
            ip4 = IPv4Address(jail_block['ip4.addr'])
        except KeyError:
            continue
        else:
            taken_ip4s.add(ip4)
    for host in jails_net.hosts():
        if host not in taken_ip4s:
            return host
    
class JailAlreadyExists(Exception):
    pass
    
class IPAlreadyRegistered(Exception):
    pass
    
class Jail(object):

    @classmethod
    def validate_jail_name(cls, name):
        jailname_regex = re.compile('^(?=.{2})[a-z]{1,16}(\d{0,6})?$')
        # I don't remember why I was so strict about jail names
        if not jailname_regex.match(name):
            raise ValueError(
                "Not a valid jail name. "
                "It should be at least two characters, between 1 and 16 lowercase letters optionnaly followed by at most 6 digits."
            )
        
    def __init__(self, name):
        self.__class__.validate_jail_name(name)
        self.name = name
    
    @property
    def directory(self):
        return os.path.join('/var/mjail/instances/', self.name)
    
    def create(self):
        release = Release()
        if not release.built():
            release.build()
        
        if os.path.exists(self.directory):
            raise JailAlreadyExists(self.name)
            
        cmd('cp', '-R', '-v', release.directory, self.directory)
        with open(os.path.join(self.directory, 'etc', 'resolv.conf'), "w") as fp:
            fp.write("nameserver %s\n" % str(jails_network4().network_address + 1))
        
        jail_conf = get_jail_conf()
        
        if self.name in jail_conf:
            raise JailAlreadyExists(self.name)
            
        jail_conf[self.name] = jailconf.JailBlock([
            ('$mjail_managed', 'yes'),
            ('$mjail_currently_running_release', str(release)),
            ('host.hostname', self.name)
        ])
        
        jail_conf.write('/etc/jail.conf')
        
    def minor_upgrade(self, to_version, unattended = False):
        # this function would need to be tested
        freebsd_update_conf = to_tempfile(
            ''.join(
                (re.sub(r'(?<=\b)kernel(?=\b)', '', line) if re.match(r'^Components\s', line) else line)
                for line in
                open('/etc/freebsd-update.conf').readlines()
            )
        )
        try:
            jail_conf = get_jail_conf()
            currently_running = jail_conf[self.name]['$mjail_currently_running_release']
            to_version_major = to_version.split('.')[0]
            running_major = currently_running.split('.')[0]
            if to_version_major != running_major:
                raise Exception(
                    "Can't upgrade from %s to %s. Only minor version upgrade is supported at the moment." % (
                        running_major, to_version_major
                    )
                )
            env = os.environ.copy()
            if unattended:
                env['PAGER'] = 'cat'
            cmd('freebsd-update',
                '-b', self.directory,
                '-f', freebsd_update_conf,
                '-r', to_version, 'upgrade', 'install', '--currently-running', currently_running,
                env = env
            )
            for _ in range(2):
                cmd('freebsd-update',
                    '-b', self.directory,
                    '-f', freebsd_update_conf,
                    'install',
                    env = env
                )
            jail_conf[self.name]['$mjail_currently_running_release'] = to_version
            jail_conf.write('/etc/jail.conf')
        finally:
            os.remove(freebsd_update_conf)
        
    def start(self):
        cmd('service', 'jail', 'start', self.name)
        
    def stop(self):
        cmd('service', 'jail', 'stop', self.name)
        
    def set_ip4(self, ip4):
        assert isinstance(ip4, IPv4Address)
        jail_conf = get_jail_conf()
        
        for jail_name, jail_block in jail_conf.jails():
            try:
                ip4_addr = jail_block['ip4.addr']
            except KeyError:
                continue
            if ip4_addr == str(ip4):
                raise IPAlreadyRegistered
            elif isinstance(ip4_addr, (list, tuple)):
                if str(ip4) in ip4_addr:
                    raise IPAlreadyRegistered
                        
        jail_conf[self.name]['interface'] = cloned_if()
        jail_conf[self.name]['ip4.addr'] = str(ip4)
        
        jail_conf.write('/etc/jail.conf')
        
        PFManager.refresh_anchor()
        
        line = '%s %s\n' % (str(ip4), self.name)
        lines = open('/etc/hosts').readlines()
        if line not in lines:
            lines.append(line)
        temp_etc_hosts = to_tempfile(''.join(lines))
        shutil.move(temp_etc_hosts, '/etc/hosts')
        
    def assign_ip4(self):
        self.set_ip4(available_ip4())
        
    def delete(self):
        cmd('service', 'jail', 'stop', self.name)
        jail_conf = get_jail_conf()
        try:
            jail_block = jail_conf[self.name]
        except KeyError:
            pass
        else:
            try:
                ip4 = jail_block['ip4.addr']
            except KeyError:
                pass
            else:
                assert isinstance(ip4, str) # list of ips not yet supported by mjail
                line = '%s %s\n' % (ip4, self.name)
                lines = [l for l in open('/etc/hosts').readlines() if l != line]
                temp_etc_hosts = to_tempfile(''.join(lines))
                shutil.move(temp_etc_hosts, '/etc/hosts')    
            del jail_conf[self.name]
            jail_conf.write('/etc/jail.conf')
            
        if os.path.exists(self.directory):
            cmd('chflags', '-R', 'noschg', self.directory)
            cmd('rm', '-rf', self.directory)
        PFManager.refresh_anchor()
        
        
        
    def available_shells(self):
        return list(
            filter(
                os.path.exists,
                (
                    line.strip()
                    for line in (
                        open(os.path.join(self.directory, 'etc/shells'))
                        .readlines()
                    )
                    if line.startswith('/')
                )
            )
        )
        
    def execute(self, command, *args):
        cmd('jexec', self.name, command, *args)
        
    def shell(self, shell_path = None):
        shell_path = shell_path or '/bin/csh'
        if shell_path in self.available_shells():
            self.execute(shell_path)
        else:
            raise Exception("No such shell: '%s'." % shell_path)
            
    def freebsd_update(self, unattended):
        freebsd_update(self.directory, unattended)
        
    def rdr(self, proto, internet_facing_host_port, jail_port):
        assert proto in ('tcp', 'udp')
        jail_conf = get_jail_conf()
        jail_conf[self.name][
            '$mjail_rdr_%s_%s' % (proto, int(internet_facing_host_port))
        ] = str(int(jail_port))
        jail_conf.write('/etc/jail.conf')
        PFManager.refresh_anchor()
        
    @classmethod
    def cancel_rdr(self, proto, internet_facing_host_port):
        assert proto in ('tcp', 'udp')
        jail_conf = get_jail_conf()
        for _, jail_block in jail_conf.jails():
            try:
                del jail_block['$mjail_rdr_%s_%s' % (proto, int(internet_facing_host_port))]
            except KeyError:
                pass
        jail_conf.write('/etc/jail.conf')
        PFManager.refresh_anchor()
        
    def ssh_box(self, public_key, internet_facing_port, jail_port = 22):
        internet_facing_port = int(internet_facing_port)
        host_sshd_conf = SSHDConf('/etc/ssh/sshd_config')
        if internet_facing_port == int(host_sshd_conf.get('Port', '22')):
            raise ValueError("This port is the ssh port used by the host.")
        root_ssh_dir = os.path.join(self.directory, 'root', '.ssh')
        authorized_keys_file = os.path.join(root_ssh_dir, 'authorized_keys')
        os.makedirs(root_ssh_dir, exist_ok = True)
        cmd('chmod', '700', root_ssh_dir) 
        with open(authorized_keys_file, "w") as fp:
            fp.write(public_key)
        cmd('chmod', '600', authorized_keys_file)
        s_conf = SSHDConf(os.path.join(self.directory, 'etc/ssh/sshd_config'))
        for option, value in (
            ('PermitRootLogin', 'prohibit-password'),  
            ('RSAAuthentication', 'yes'),
            ('PubkeyAuthentication', 'yes'),
            ('PasswordAuthentication', 'no'),
            ('Port', str(jail_port))
        ):
            s_conf.set_option(option, value)
        s_conf.overwrite()
        rc_conf_mod('sshd_enable=YES', f = os.path.join(self.directory, 'etc/rc.conf'))
        self.rdr('tcp', internet_facing_port, jail_port)

