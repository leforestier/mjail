from mjail.cmd_helpers import output

def local_unbound_enabled():
    return output('sysrc', '-n', 'local_unbound_enable').strip() == 'YES'
